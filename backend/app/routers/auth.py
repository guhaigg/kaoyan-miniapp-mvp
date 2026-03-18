import time
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit, get_portal_user_optional
from ..models import PortalUser, PortalUserSession, User, utcnow
from ..schemas import (
    BarkNotificationSettingsRequest,
    BarkNotificationSettingsResponse,
    SilentLoginRequest,
    SilentLoginResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserLogoutResponse,
    UserMeResponse,
    UserRefreshRequest,
    UserRefreshResponse,
    UserRegisterRequest,
    UserRegisterResponse,
)
from ..security import (
    create_session_token,
    create_visitor_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from ..services.wechat import WechatService

router = APIRouter(prefix="/auth", tags=["auth"])
USER_REFRESH_COOKIE = "gw_user_refresh"


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def _issue_user_access_token(user: PortalUser) -> str:
    settings = get_settings()
    return create_visitor_token(
        {"typ": "user", "uid": user.id, "usr": user.username, "iat": int(time.time()), "jti": create_session_token()},
        settings.secret_key,
    )


def _set_user_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=USER_REFRESH_COOKIE,
        value=refresh_token,
        max_age=settings.user_refresh_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=False,
    )


def _extract_refresh_token(request: Request, payload: UserRefreshRequest | None) -> str | None:
    if payload is not None and payload.refresh_token:
        value = payload.refresh_token.strip()
        if value:
            return value
    cookie_token = (request.cookies.get(USER_REFRESH_COOKIE) or "").strip()
    return cookie_token or None


def _create_user_refresh_session(db: Session, request: Request, user: PortalUser) -> str:
    settings = get_settings()
    refresh_token = create_session_token()
    session = PortalUserSession(
        user_id=user.id,
        token_hash=hash_session_token(refresh_token),
        status="active",
        expires_at=utcnow() + timedelta(seconds=settings.user_refresh_ttl_seconds),
        last_seen_at=utcnow(),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(session)
    return refresh_token


def _as_utc(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_bark_settings_response(user: PortalUser) -> BarkNotificationSettingsResponse:
    settings = get_settings()
    bark_key = (user.notify_bark_key or "").strip()
    bark_endpoint = f"{settings.bark_server_url.rstrip('/')}/{bark_key}" if bark_key else None
    return BarkNotificationSettingsResponse(
        enabled=bool(user.notify_bark_enabled) and bool(bark_key),
        bark_key_configured=bool(bark_key),
        bark_endpoint=bark_endpoint,
    )


@router.post("/silent-login", response_model=SilentLoginResponse)
def silent_login(payload: SilentLoginRequest, request: Request, db: Session = Depends(get_db)) -> SilentLoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(request, f"silent:{client_ip}")

    try:
        openid = WechatService().exchange_code_for_openid(payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - network dependent
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="silent login failed") from exc

    user = db.query(User).filter(User.openid == openid).one_or_none()
    if user is None:
        user = User(openid=openid, state="shadow")
        db.add(user)
        db.flush()
    user.last_seen_at = utcnow()
    db.commit()
    db.refresh(user)

    settings = get_settings()
    token = create_visitor_token({"uid": user.id, "openid": user.openid, "iat": int(time.time())}, settings.secret_key)
    audit_event(db, request, "auth.silent_login", user.id, {"state": "shadow"})

    return SilentLoginResponse(
        visitor_token=token,
        user_id=user.id,
        user_state="shadow",
        expires_in=settings.visitor_token_ttl_seconds,
    )


@router.post("/register", response_model=UserRegisterResponse)
def register_user(payload: UserRegisterRequest, request: Request, db: Session = Depends(get_db)) -> UserRegisterResponse:
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(request, f"register:{client_ip}")

    username = _normalize_username(payload.username)
    existing = db.query(PortalUser).filter(PortalUser.username == username).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")

    user = PortalUser(
        username=username,
        password_hash=hash_password(payload.password),
        nickname=(payload.nickname or "").strip() or None,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_event(db, request, "auth.register", None, {"portal_user_id": user.id})
    return UserRegisterResponse(user_id=user.id, username=user.username, status=user.status)


@router.post("/login", response_model=UserLoginResponse)
def login_user(payload: UserLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> UserLoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(request, f"login:{client_ip}")

    username = _normalize_username(payload.username)
    user = db.query(PortalUser).filter(PortalUser.username == username).one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")

    user.last_login_at = utcnow()
    refresh_token = _create_user_refresh_session(db, request, user)
    db.commit()
    _set_user_refresh_cookie(response, refresh_token)
    access_token = _issue_user_access_token(user)
    settings = get_settings()
    audit_event(db, request, "auth.login", None, {"portal_user_id": user.id})
    return UserLoginResponse(
        access_token=access_token,
        expires_in=settings.user_session_ttl_seconds,
        refresh_expires_in=settings.user_refresh_ttl_seconds,
        user_id=user.id,
        username=user.username,
    )


@router.post("/refresh", response_model=UserRefreshResponse)
def refresh_user_session(
    request: Request,
    response: Response,
    payload: UserRefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> UserRefreshResponse:
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(request, f"refresh:{client_ip}")

    refresh_token = _extract_refresh_token(request, payload)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token required")

    token_hash = hash_session_token(refresh_token)
    session = (
        db.query(PortalUserSession)
        .join(PortalUser, PortalUser.id == PortalUserSession.user_id)
        .filter(PortalUserSession.token_hash == token_hash)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid refresh token")

    now = utcnow()
    if session.status != "active" or session.revoked_at is not None or _as_utc(session.expires_at) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh token expired or revoked")
    if session.user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="account unavailable")

    session.status = "revoked"
    session.revoked_at = now
    session.last_seen_at = now
    session.user.last_login_at = now

    new_refresh_token = _create_user_refresh_session(db, request, session.user)
    db.commit()

    _set_user_refresh_cookie(response, new_refresh_token)
    access_token = _issue_user_access_token(session.user)
    settings = get_settings()
    audit_event(db, request, "auth.refresh", None, {"portal_user_id": session.user.id})
    return UserRefreshResponse(
        access_token=access_token,
        expires_in=settings.user_session_ttl_seconds,
        refresh_expires_in=settings.user_refresh_ttl_seconds,
        user_id=session.user.id,
        username=session.user.username,
    )


@router.post("/logout", response_model=UserLogoutResponse)
def logout_user(
    request: Request,
    response: Response,
    payload: UserRefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> UserLogoutResponse:
    refresh_token = _extract_refresh_token(request, payload)
    if refresh_token:
        token_hash = hash_session_token(refresh_token)
        session = db.query(PortalUserSession).filter(PortalUserSession.token_hash == token_hash).one_or_none()
        if session is not None and session.revoked_at is None:
            session.status = "revoked"
            session.revoked_at = utcnow()
            session.last_seen_at = utcnow()
            db.commit()
            audit_event(db, request, "auth.logout", None, {"portal_user_id": session.user_id})

    response.delete_cookie(USER_REFRESH_COOKIE)
    return UserLogoutResponse(status="ok")


@router.get("/me", response_model=UserMeResponse)
def current_user_profile(request: Request, db: Session = Depends(get_db)) -> UserMeResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    return UserMeResponse(user_id=user.id, username=user.username, nickname=user.nickname, status=user.status)


@router.get("/me/notifications/bark", response_model=BarkNotificationSettingsResponse)
def get_bark_notification_settings(request: Request, db: Session = Depends(get_db)) -> BarkNotificationSettingsResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    return _build_bark_settings_response(user)


@router.put("/me/notifications/bark", response_model=BarkNotificationSettingsResponse)
def update_bark_notification_settings(
    payload: BarkNotificationSettingsRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> BarkNotificationSettingsResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")

    next_key = user.notify_bark_key
    if payload.bark_key is not None:
        candidate = payload.bark_key.strip()
        next_key = candidate or None

    if payload.enabled and not next_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bark key required when enabling Bark")

    user.notify_bark_key = next_key
    user.notify_bark_enabled = 1 if (payload.enabled and next_key) else 0
    db.commit()
    db.refresh(user)
    audit_event(
        db,
        request,
        "auth.bark_notification_settings.update",
        None,
        {"portal_user_id": user.id, "enabled": bool(user.notify_bark_enabled)},
    )
    return _build_bark_settings_response(user)
