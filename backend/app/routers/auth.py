import time
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import (
    audit_event,
    enforce_rate_limit,
    get_portal_user_optional,
)
from ..models import AccountPaymentOrder, NotificationDelivery, PortalUser, PortalUserSession, User, utcnow
from ..schemas import (
    BarkNotificationSettingsRequest,
    BarkNotificationSettingsResponse,
    SilentLoginRequest,
    SilentLoginResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserIdentityItem,
    UserIdentityListResponse,
    UserRoleItem,
    UserEntitlementItem,
    UserAccountOverviewResponse,
    UserChangePasswordRequest,
    UserChangePasswordResponse,
    UserLogoutResponse,
    UserMeResponse,
    UserNotificationHistoryItem,
    UserNotificationHistoryResponse,
    UserPaymentOrderCreateRequest,
    UserPaymentOrderItem,
    UserPaymentOrderListResponse,
    UserRefreshRequest,
    UserRefreshResponse,
    UserRegisterRequest,
    UserRegisterResponse,
    WechatBindCodeClaimRequest,
    WechatBindCodeResponse,
    WechatBindResponse,
)
from ..security import (
    create_session_token,
    create_visitor_token,
    hash_password,
    hash_session_token,
    parse_visitor_token,
    verify_password,
)
from ..services.account_access import (
    ENTITLEMENT_PREMIUM_MONITORING,
    ENTITLEMENT_SOURCE_WECHAT_PAY,
    ENTITLEMENT_SOURCE_WEB_PAY,
    claim_wechat_bind_code,
    create_payment_order,
    ensure_password_identity,
    ensure_wechat_identity,
    find_active_wechat_bind_code,
    find_password_login_account,
    find_wechat_identity_account,
    issue_wechat_bind_code,
    resolve_portal_access,
    set_password_hash,
)
from ..services.wechat import WechatService

router = APIRouter(prefix="/auth", tags=["auth"])
USER_REFRESH_COOKIE = "gw_user_refresh"
PREMIUM_PRICE_CENTS_BY_DURATION = {30: 2900, 90: 7900, 365: 19900}


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


def _build_portal_profile_payload(db: Session, user: PortalUser) -> dict:
    access_state = resolve_portal_access(db, user)
    is_admin = access_state.is_admin
    is_premium = access_state.is_premium
    role = "admin" if is_admin else ("premium" if is_premium else "user")
    return {
        "user_id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "status": user.status,
        "is_admin": is_admin,
        "is_premium": is_premium,
        "role": role,
        "premium_expires_at": access_state.premium_expires_at,
    }


def _build_user_identity_item(identity) -> UserIdentityItem:
    return UserIdentityItem(
        id=identity.id,
        identity_type=identity.identity_type,
        status=identity.status,
        login_name=identity.login_name,
        provider_app_id=identity.provider_app_id,
        verified_at=identity.verified_at,
        last_login_at=identity.last_login_at,
    )


def _build_user_role_item(role) -> UserRoleItem:
    return UserRoleItem(
        role_code=role.role_code,
        status=role.status,
        source=role.source,
        created_at=role.created_at,
    )


def _build_user_entitlement_item(entitlement) -> UserEntitlementItem:
    return UserEntitlementItem(
        entitlement_code=entitlement.entitlement_code,
        status=entitlement.status,
        source=entitlement.source,
        starts_at=entitlement.starts_at,
        expires_at=entitlement.expires_at,
        revoked_at=entitlement.revoked_at,
        order_ref=entitlement.order_ref,
    )


def _build_user_payment_order_item(order: AccountPaymentOrder) -> UserPaymentOrderItem:
    return UserPaymentOrderItem(
        id=order.id,
        entitlement_code=order.entitlement_code,
        source=order.source,
        status=order.status,
        duration_days=order.duration_days,
        amount_cents=order.amount_cents,
        currency=order.currency,
        order_ref=order.order_ref,
        provider_name=order.provider_name,
        provider_order_ref=order.provider_order_ref,
        provider_payment_ref=order.provider_payment_ref,
        paid_at=order.paid_at,
        canceled_at=order.canceled_at,
        created_at=order.created_at,
        meta_json=dict(order.meta_json or {}),
    )


def _build_user_account_overview(db: Session, user: PortalUser) -> UserAccountOverviewResponse:
    profile = _build_portal_profile_payload(db, user)
    identities = [
        _build_user_identity_item(identity)
        for identity in sorted(user.identities, key=lambda item: (item.identity_type, item.created_at))
    ]
    roles = [
        _build_user_role_item(role)
        for role in sorted(user.roles, key=lambda item: (item.role_code, item.created_at))
    ]
    entitlements = [
        _build_user_entitlement_item(entitlement)
        for entitlement in sorted(user.entitlements, key=lambda item: (item.entitlement_code, item.created_at))
    ]
    return UserAccountOverviewResponse(
        identities=identities,
        roles=roles,
        entitlements=entitlements,
        **profile,
    )


def _build_wechat_bind_response(
    *,
    db: Session,
    request: Request,
    response: Response,
    shadow_user: User,
    user: PortalUser,
) -> WechatBindResponse:
    provider_app_id = WechatService().provider_app_id()
    try:
        identity = ensure_wechat_identity(
            db,
            user=user,
            provider_subject=shadow_user.openid,
            provider_app_id=provider_app_id,
            provider_unionid=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    user.last_login_at = utcnow()
    identity.last_login_at = user.last_login_at
    refresh_token = _create_user_refresh_session(db, request, user)
    db.commit()
    _set_user_refresh_cookie(response, refresh_token)
    settings = get_settings()
    profile = _build_portal_profile_payload(db, user)
    audit_event(
        db,
        request,
        "auth.wechat_bind",
        shadow_user.id,
        {"portal_user_id": user.id, "identity_id": identity.id},
    )
    return WechatBindResponse(
        status="ok",
        linked=True,
        user_id=profile["user_id"],
        username=profile["username"],
        nickname=profile["nickname"],
        user_status=user.status,
        identity_id=identity.id,
        provider_subject=identity.provider_subject or shadow_user.openid,
        provider_unionid=identity.provider_unionid,
        access_token=_issue_user_access_token(user),
        access_expires_in=settings.user_session_ttl_seconds,
        refresh_token=refresh_token,
        refresh_expires_in=settings.user_refresh_ttl_seconds,
        is_admin=profile["is_admin"],
        is_premium=profile["is_premium"],
        role=profile["role"],
        premium_expires_at=profile["premium_expires_at"],
    )


def _require_shadow_user_for_wechat_bind(request: Request, db: Session) -> User:
    settings = get_settings()
    visitor_token = request.headers.get("X-Visitor-Token", "").strip()
    if not visitor_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wechat visitor login required")
    payload = parse_visitor_token(visitor_token, settings.secret_key, settings.visitor_token_ttl_seconds)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wechat visitor login required")
    user_id = str(payload.get("uid", "")).strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wechat visitor login required")
    user = db.query(User).filter(User.id == user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wechat visitor login required")
    return user


@router.post("/silent-login", response_model=SilentLoginResponse)
def silent_login(
    payload: SilentLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> SilentLoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(request, f"silent:{client_ip}")

    try:
        wechat_identity = WechatService().exchange_code(payload.code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - network dependent
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="silent login failed") from exc

    shadow_user = db.query(User).filter(User.openid == wechat_identity.openid).one_or_none()
    if shadow_user is None:
        shadow_user = User(openid=wechat_identity.openid, state="shadow")
        db.add(shadow_user)
        db.flush()
    shadow_user.last_seen_at = utcnow()

    settings = get_settings()
    token = create_visitor_token(
        {"uid": shadow_user.id, "openid": shadow_user.openid, "iat": int(time.time())},
        settings.secret_key,
    )
    account, identity = find_wechat_identity_account(
        db,
        provider_subject=wechat_identity.openid,
        provider_app_id=wechat_identity.provider_app_id,
        provider_unionid=wechat_identity.unionid,
    )
    if account is not None and identity is not None and account.status == "active":
        account.last_login_at = utcnow()
        identity.status = "active"
        if wechat_identity.unionid and identity.provider_unionid != wechat_identity.unionid:
            identity.provider_unionid = wechat_identity.unionid
        if identity.verified_at is None:
            identity.verified_at = utcnow()
        identity.last_login_at = account.last_login_at
        refresh_token = _create_user_refresh_session(db, request, account)
        db.commit()
        _set_user_refresh_cookie(response, refresh_token)
        profile = _build_portal_profile_payload(db, account)
        audit_event(
            db,
            request,
            "auth.silent_login",
            shadow_user.id,
            {"state": "bound", "portal_user_id": account.id},
        )
        return SilentLoginResponse(
            visitor_token=token,
            user_state="bound",
            expires_in=settings.visitor_token_ttl_seconds,
            bind_required=False,
            shadow_user_id=shadow_user.id,
            linked_portal_user_id=account.id,
            token_type="bearer",
            access_token=_issue_user_access_token(account),
            access_expires_in=settings.user_session_ttl_seconds,
            refresh_token=refresh_token,
            refresh_expires_in=settings.user_refresh_ttl_seconds,
            **profile,
        )

    db.commit()
    db.refresh(shadow_user)
    audit_event(db, request, "auth.silent_login", shadow_user.id, {"state": "shadow"})
    return SilentLoginResponse(
        visitor_token=token,
        user_id=shadow_user.id,
        user_state="shadow",
        expires_in=settings.visitor_token_ttl_seconds,
        bind_required=True,
        shadow_user_id=shadow_user.id,
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
    db.flush()
    ensure_password_identity(db, user)
    db.commit()
    db.refresh(user)
    audit_event(db, request, "auth.register", None, {"portal_user_id": user.id})
    return UserRegisterResponse(user_id=user.id, username=user.username, status=user.status)


@router.post("/login", response_model=UserLoginResponse)
def login_user(payload: UserLoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> UserLoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(request, f"login:{client_ip}")

    username = _normalize_username(payload.username)
    user, identity = find_password_login_account(db, username)
    if user is None or identity is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")
    if not verify_password(payload.password, identity.password_hash or user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")

    user.last_login_at = utcnow()
    identity.last_login_at = user.last_login_at
    refresh_token = _create_user_refresh_session(db, request, user)
    db.commit()
    _set_user_refresh_cookie(response, refresh_token)
    access_token = _issue_user_access_token(user)
    settings = get_settings()
    audit_event(db, request, "auth.login", None, {"portal_user_id": user.id})
    return UserLoginResponse(
        access_token=access_token,
        expires_in=settings.user_session_ttl_seconds,
        refresh_token=refresh_token,
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
        refresh_token=new_refresh_token,
        refresh_expires_in=settings.user_refresh_ttl_seconds,
        user_id=session.user.id,
        username=session.user.username,
    )


@router.post("/wechat/bind", response_model=WechatBindResponse)
def bind_wechat_identity(request: Request, response: Response, db: Session = Depends(get_db)) -> WechatBindResponse:
    shadow_user = _require_shadow_user_for_wechat_bind(request, db)
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    return _build_wechat_bind_response(db=db, request=request, response=response, shadow_user=shadow_user, user=user)


@router.post("/wechat/bind-code", response_model=WechatBindCodeResponse)
def create_wechat_bind_code(request: Request, db: Session = Depends(get_db)) -> WechatBindCodeResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    try:
        row = issue_wechat_bind_code(
            db,
            user=user,
            ttl_seconds=get_settings().wechat_bind_code_ttl_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    db.commit()
    audit_event(
        db,
        request,
        "auth.wechat_bind_code.create",
        None,
        {"portal_user_id": user.id, "bind_code_id": row.id},
    )
    now = utcnow()
    expires_in = max(int((_as_utc(row.expires_at) - now).total_seconds()), 0)
    return WechatBindCodeResponse(
        status="ok",
        code=row.code,
        expires_at=row.expires_at,
        expires_in=expires_in,
    )


@router.post("/wechat/bind-code/claim", response_model=WechatBindResponse)
def claim_wechat_bind_code_endpoint(
    payload: WechatBindCodeClaimRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> WechatBindResponse:
    shadow_user = _require_shadow_user_for_wechat_bind(request, db)
    bind_code = find_active_wechat_bind_code(db, payload.code)
    if bind_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="bind code not found or expired")
    user = db.query(PortalUser).filter(PortalUser.id == bind_code.account_id).one_or_none()
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="target account unavailable")
    claim_wechat_bind_code(db, bind_code=bind_code, shadow_user_id=shadow_user.id)
    return _build_wechat_bind_response(db=db, request=request, response=response, shadow_user=shadow_user, user=user)


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
    return UserMeResponse(**_build_portal_profile_payload(db, user))


@router.get("/me/identities", response_model=UserIdentityListResponse)
def current_user_identities(request: Request, db: Session = Depends(get_db)) -> UserIdentityListResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    items = [
        _build_user_identity_item(identity)
        for identity in sorted(user.identities, key=lambda item: (item.identity_type, item.created_at))
    ]
    return UserIdentityListResponse(total=len(items), items=items)


@router.get("/me/account", response_model=UserAccountOverviewResponse)
def current_user_account_overview(request: Request, db: Session = Depends(get_db)) -> UserAccountOverviewResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    return _build_user_account_overview(db, user)


@router.get("/me/premium-orders", response_model=UserPaymentOrderListResponse)
def current_user_payment_orders(request: Request, db: Session = Depends(get_db)) -> UserPaymentOrderListResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    rows = (
        db.query(AccountPaymentOrder)
        .filter(AccountPaymentOrder.account_id == user.id)
        .order_by(AccountPaymentOrder.created_at.desc())
        .all()
    )
    return UserPaymentOrderListResponse(total=len(rows), items=[_build_user_payment_order_item(row) for row in rows])


@router.post("/me/premium-orders", response_model=UserPaymentOrderItem)
def create_current_user_payment_order(
    payload: UserPaymentOrderCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> UserPaymentOrderItem:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    source = payload.source
    if source not in {ENTITLEMENT_SOURCE_WEB_PAY, ENTITLEMENT_SOURCE_WECHAT_PAY}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported payment source")
    order = create_payment_order(
        db,
        user_id=user.id,
        entitlement_code=ENTITLEMENT_PREMIUM_MONITORING,
        source=source,
        duration_days=payload.duration_days,
        amount_cents=PREMIUM_PRICE_CENTS_BY_DURATION[payload.duration_days],
        currency="CNY",
        meta_json={"channel": "web" if source == ENTITLEMENT_SOURCE_WEB_PAY else "miniapp_reserved"},
    )
    db.commit()
    audit_event(
        db,
        request,
        "auth.premium_order_create",
        None,
        {"portal_user_id": user.id, "order_id": order.id, "source": source, "duration_days": payload.duration_days},
    )
    return _build_user_payment_order_item(order)


@router.post("/me/change-password", response_model=UserChangePasswordResponse)
def change_user_password(
    payload: UserChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> UserChangePasswordResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    identity = ensure_password_identity(db, user)
    current_hash = identity.password_hash or user.password_hash
    if not verify_password(payload.old_password, current_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid current password")
    if verify_password(payload.new_password, current_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new password must differ from current password")
    set_password_hash(db, user, hash_password(payload.new_password))
    db.commit()
    audit_event(db, request, "auth.change_password", None, {"portal_user_id": user.id})
    return UserChangePasswordResponse(status="ok")


@router.get("/me/notifications/history", response_model=UserNotificationHistoryResponse)
def list_user_notification_history(
    request: Request,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> UserNotificationHistoryResponse:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    rows = (
        db.query(NotificationDelivery)
        .filter(NotificationDelivery.user_id == user.id)
        .order_by(NotificationDelivery.created_at.desc())
        .limit(max(1, min(int(limit), 100)))
        .all()
    )
    items = [
        UserNotificationHistoryItem(
            id=row.id,
            outbox_id=row.outbox_id,
            channel=row.channel,
            status=row.status,
            created_at=row.created_at,
            sent_at=row.sent_at,
            last_error=row.last_error,
            payload=dict(row.payload or {}),
        )
        for row in rows
    ]
    return UserNotificationHistoryResponse(total=len(items), items=items)


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
