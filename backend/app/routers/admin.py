import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import (
    audit_event,
    clear_admin_login_failures,
    enforce_rate_limit,
    ensure_admin_not_locked,
    get_admin_identity,
    record_admin_login_failure,
    require_admin_request,
)
from ..models import AdminAccount, Content, PortalUser, UserEvent, utcnow
from ..schemas import (
    AdminAuditItem,
    AdminAuditListResponse,
    AdminChangePasswordRequest,
    AdminChangePasswordResponse,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminMeResponse,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserUpdateRequest,
    ContentOut,
    ManualEntryRequest,
)
from ..security import create_visitor_token, hash_password, verify_password
from ..services.content import upsert_content

router = APIRouter(prefix="/admin", tags=["admin"])


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _issue_admin_session_token(username: str) -> str:
    settings = get_settings()
    return create_visitor_token(
        {"typ": "admin", "usr": username, "iat": int(time.time())},
        settings.secret_key,
    )


def _admin_expected_password() -> str:
    settings = get_settings()
    password = settings.admin_password.strip()
    if password:
        return password
    return settings.admin_token.strip()


def _to_admin_user_item(user: PortalUser, is_admin: bool) -> AdminUserItem:
    return AdminUserItem(
        id=user.id,
        username=user.username,
        status=user.status,
        is_admin=is_admin,
        nickname=user.nickname,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _get_portal_admin_account(db: Session, username: str) -> AdminAccount | None:
    return (
        db.query(AdminAccount)
        .join(PortalUser, PortalUser.id == AdminAccount.user_id)
        .filter(PortalUser.username == username, AdminAccount.status == "active", PortalUser.status == "active")
        .one_or_none()
    )


def _login_with_portal_admin(payload: AdminLoginRequest, db: Session) -> str | None:
    username = _normalize_username(payload.username)
    account = _get_portal_admin_account(db, username)
    if account is None:
        return None
    if not verify_password(payload.password, account.user.password_hash):
        return None
    account.last_login_at = utcnow()
    account.user.last_login_at = utcnow()
    db.commit()
    return account.user.username


@router.post("/auth/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest, response: Response, request: Request, db: Session = Depends(get_db)) -> AdminLoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(request, f"admin_login:{client_ip}")
    username = _normalize_username(payload.username)
    ensure_admin_not_locked(username)

    login_username = _login_with_portal_admin(payload, db)
    if login_username is None:
        settings = get_settings()
        expected_password = _admin_expected_password()
        if not expected_password:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="admin password not configured")

        username_ok = hmac.compare_digest(username, settings.admin_username)
        password_ok = hmac.compare_digest(payload.password, expected_password)
        if not (username_ok and password_ok):
            record_admin_login_failure(username)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin credentials")
        login_username = settings.admin_username

    settings = get_settings()
    clear_admin_login_failures(username)
    session_token = _issue_admin_session_token(login_username)
    response.set_cookie(
        key="gw_admin_session",
        value=session_token,
        max_age=settings.admin_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return AdminLoginResponse(username=login_username, expires_in=settings.admin_session_ttl_seconds)


@router.post("/auth/logout")
def admin_logout(response: Response, request: Request) -> dict[str, str]:
    require_admin_request(request)
    response.delete_cookie("gw_admin_session")
    return {"status": "ok"}


@router.get("/auth/me", response_model=AdminMeResponse)
def admin_me(request: Request) -> AdminMeResponse:
    require_admin_request(request)
    return AdminMeResponse(username=get_admin_identity(request) or get_settings().admin_username, authenticated=True)


@router.post("/auth/change-password", response_model=AdminChangePasswordResponse)
def admin_change_password(
    payload: AdminChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminChangePasswordResponse:
    require_admin_request(request)
    username = get_admin_identity(request) or get_settings().admin_username
    account = _get_portal_admin_account(db, username)
    if account is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="current admin account is env-based and cannot be changed here")

    if not verify_password(payload.old_password, account.user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="old password incorrect")

    account.user.password_hash = hash_password(payload.new_password)
    db.commit()
    audit_event(db, request, "admin.password_change", None, {"operator": username})
    return AdminChangePasswordResponse(status="ok")


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    state: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=120),
) -> AdminUserListResponse:
    require_admin_request(request)

    query = db.query(PortalUser)
    if state:
        query = query.filter(PortalUser.status == state.strip())
    if keyword:
        kw = f"%{keyword.strip()}%"
        query = query.filter(or_(PortalUser.username.ilike(kw), PortalUser.nickname.ilike(kw)))

    total = query.count()
    rows = query.order_by(PortalUser.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    admin_ids = {x[0] for x in db.query(AdminAccount.user_id).filter(AdminAccount.status == "active").all()}
    return AdminUserListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_admin_user_item(x, x.id in admin_ids) for x in rows],
    )


@router.patch("/users/{user_id}", response_model=AdminUserItem)
def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AdminUserItem:
    require_admin_request(request)
    user = db.query(PortalUser).filter(PortalUser.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

    if payload.status is not None:
        user.status = payload.status
    if payload.nickname is not None:
        nickname = payload.nickname.strip()
        user.nickname = nickname or None

    db.commit()
    db.refresh(user)
    audit_event(db, request, "admin.user_update", None, {"user_id": user.id})
    is_admin = db.query(AdminAccount).filter(AdminAccount.user_id == user.id, AdminAccount.status == "active").count() > 0
    return _to_admin_user_item(user, is_admin)


@router.post("/users/{user_id}/promote", response_model=AdminUserItem)
def promote_user(user_id: str, request: Request, db: Session = Depends(get_db)) -> AdminUserItem:
    require_admin_request(request)
    user = db.query(PortalUser).filter(PortalUser.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot promote blocked user")

    account = db.query(AdminAccount).filter(AdminAccount.user_id == user.id).one_or_none()
    operator = get_admin_identity(request) or get_settings().admin_username
    if account is None:
        account = AdminAccount(user_id=user.id, status="active", promoted_by=operator, last_login_at=None)
        db.add(account)
    else:
        account.status = "active"
        if not account.promoted_by:
            account.promoted_by = operator

    db.commit()
    db.refresh(user)
    audit_event(db, request, "admin.user_promote", None, {"user_id": user.id, "operator": operator})
    return _to_admin_user_item(user, True)


@router.get("/audits", response_model=AdminAuditListResponse)
def list_admin_audits(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    prefix: str = Query(default="admin.", max_length=64),
) -> AdminAuditListResponse:
    require_admin_request(request)
    query = db.query(UserEvent).filter(UserEvent.event_type.ilike(f"{prefix}%"))
    total = query.count()
    rows = query.order_by(UserEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return AdminAuditListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[
            AdminAuditItem(
                id=x.id,
                event_type=x.event_type,
                endpoint=x.endpoint,
                event_data=x.event_data,
                ip=x.ip,
                created_at=x.created_at,
            )
            for x in rows
        ],
    )


@router.post("/manual-entry", response_model=ContentOut)
def manual_entry(payload: ManualEntryRequest, request: Request, db: Session = Depends(get_db)) -> ContentOut:
    require_admin_request(request)

    if payload.action == "offline":
        if not payload.content_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content_id is required when action=offline")
        content = db.query(Content).filter(Content.id == payload.content_id).one_or_none()
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")
        next_extra = dict(content.extra or {})
        next_extra["offline"] = True
        next_extra["offline_reason"] = payload.reason or "manual offline"
        content.extra = next_extra
        db.commit()
        audit_event(db, request, "admin.offline", None, {"content_id": content.id})
        return ContentOut(id=content.id, status="updated")

    if payload.content is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is required when action=upsert")
    content_data = payload.content.model_copy(update={"source_type": "manual"})
    content, result = upsert_content(db, content_data)
    audit_event(db, request, "admin.manual_upsert", None, {"content_id": content.id, "status": result})
    return ContentOut(id=content.id, status=result)
