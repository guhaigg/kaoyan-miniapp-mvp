import time
import uuid
from collections import defaultdict

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .models import PortalUser, PortalUserSubscription, User, UserEvent, utcnow
from .security import parse_visitor_token
from .services.account_access import (
    get_active_admin_user_ids,
    resolve_portal_access,
)
from .services.search_cache import search_response_cache

_in_memory_rate_limit: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))


def get_request_id() -> str:
    return str(uuid.uuid4())


def get_visitor_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()
    header_token = request.headers.get("X-Visitor-Token", "")
    return header_token.strip() or None


def get_current_user_optional(request: Request, db: Session) -> User | None:
    settings = get_settings()
    token = get_visitor_token(request)
    if not token:
        return None
    payload = parse_visitor_token(token, settings.secret_key, settings.visitor_token_ttl_seconds)
    if not payload:
        return None
    user_id = str(payload.get("uid", "")).strip()
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).one_or_none()


def get_portal_access_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip() or None
    header_token = request.headers.get("X-User-Token", "").strip()
    return header_token or None


def get_portal_user_optional(request: Request, db: Session) -> PortalUser | None:
    settings = get_settings()
    token = get_portal_access_token(request)
    if not token:
        return None
    payload = parse_visitor_token(token, settings.secret_key, settings.user_session_ttl_seconds)
    if not payload or payload.get("typ") != "user":
        return None
    user_id = str(payload.get("uid", "")).strip()
    if not user_id:
        return None
    user = db.query(PortalUser).filter(PortalUser.id == user_id).one_or_none()
    if user is None or user.status != "active":
        return None
    return user


def require_portal_user(request: Request, db: Session) -> PortalUser:
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    return user


def is_portal_admin(db: Session, portal_user_id: str) -> bool:
    return portal_user_id in get_active_admin_user_ids(db)


def recycle_expired_premium_access_for_user(db: Session, user: PortalUser) -> bool:
    state = resolve_portal_access(db, user)
    if state.is_admin or state.is_premium or not state.expired_premium:
        return False

    rows = (
        db.query(PortalUserSubscription)
        .filter(
            PortalUserSubscription.user_id == user.id,
            PortalUserSubscription.subscription_type == "school",
            PortalUserSubscription.status == "active",
        )
        .all()
    )
    for row in rows:
        row.status = "deleted"
    db.commit()
    db.refresh(user)
    return True


def has_premium_monitoring_access(db: Session, user: PortalUser) -> bool:
    state = resolve_portal_access(db, user)
    if state.is_admin or state.is_premium:
        return True
    if state.expired_premium:
        rows = (
            db.query(PortalUserSubscription)
            .filter(
                PortalUserSubscription.user_id == user.id,
                PortalUserSubscription.subscription_type == "school",
                PortalUserSubscription.status == "active",
            )
            .all()
        )
        for row in rows:
            row.status = "deleted"
        db.commit()
        db.refresh(user)
    return False


def require_premium_or_admin(request: Request, db: Session) -> PortalUser:
    user = require_portal_user(request, db)
    if has_premium_monitoring_access(db, user):
        return user
    # Backward-compatible path: allow access when request carries valid admin auth.
    if is_admin_request(request):
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="premium monitoring required")


def enforce_rate_limit(request: Request, identity: str) -> None:
    settings = get_settings()
    window = int(time.time() // 60)
    key = f"rl:{identity}:{request.url.path}:{window}"
    redis_client = getattr(request.app.state, "redis", None)

    if redis_client is not None:
        try:
            value = redis_client.incr(key)
            if value == 1:
                redis_client.expire(key, 120)
            if value > settings.rate_limit_per_minute:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
            return
        except Exception:
            # Redis 运行中断时降级到进程内限流，避免业务接口 500。
            request.app.state.redis = None

    current, current_window = _in_memory_rate_limit.get(key, (0, window))
    if current_window != window:
        current = 0
    current += 1
    _in_memory_rate_limit[key] = (current, window)
    if current > settings.rate_limit_per_minute:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")


def audit_event(
    db: Session,
    request: Request,
    event_type: str,
    user_id: str | None,
    event_data: dict | None = None,
) -> None:
    event = UserEvent(
        user_id=user_id,
        event_type=event_type,
        endpoint=request.url.path,
        event_data=event_data or {},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    db.add(event)
    db.commit()


def _get_portal_admin_identity(request: Request) -> str | None:
    settings = get_settings()
    token = get_portal_access_token(request)
    if not token:
        return None
    payload = parse_visitor_token(token, settings.secret_key, settings.user_session_ttl_seconds)
    if not payload or payload.get("typ") != "user":
        return None
    user_id = str(payload.get("uid", "")).strip()
    if not user_id:
        return None
    with SessionLocal() as db:
        user = db.query(PortalUser).filter(PortalUser.id == user_id, PortalUser.status == "active").one_or_none()
        if user is None:
            return None
        if not is_portal_admin(db, user.id):
            return None
        return user.username


def get_admin_identity(request: Request) -> str | None:
    settings = get_settings()
    legacy_token = request.headers.get("X-Admin-Token", "").strip()
    if legacy_token and legacy_token == settings.admin_token:
        return settings.admin_username

    portal_admin_username = _get_portal_admin_identity(request)
    if portal_admin_username:
        return portal_admin_username
    return None


def is_admin_request(request: Request) -> bool:
    return get_admin_identity(request) is not None


def require_admin_request(request: Request) -> None:
    if not is_admin_request(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin login required")


def reset_runtime_state_for_tests() -> None:
    _in_memory_rate_limit.clear()
    search_response_cache.clear()
