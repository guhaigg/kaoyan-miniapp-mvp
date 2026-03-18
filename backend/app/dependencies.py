import time
import uuid
from collections import defaultdict

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AdminAccount, PortalUser, User, UserEvent
from .security import parse_visitor_token

_in_memory_rate_limit: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
_in_memory_admin_login_failures: dict[str, tuple[int, int, int]] = {}


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
    count = (
        db.query(AdminAccount.id)
        .filter(
            AdminAccount.user_id == portal_user_id,
            AdminAccount.status == "active",
        )
        .count()
    )
    return count > 0


def has_premium_monitoring_access(db: Session, user: PortalUser) -> bool:
    if is_portal_admin(db, user.id):
        return True
    return bool(user.premium_monitoring_enabled)


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


def get_admin_session_token(request: Request) -> str | None:
    cookie_token = (request.cookies.get("gw_admin_session") or "").strip()
    if cookie_token:
        return cookie_token

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "", 1).strip()
        if token:
            return token

    header_token = request.headers.get("X-Admin-Session", "").strip()
    return header_token or None


def _parse_admin_session_payload(request: Request) -> dict | None:
    settings = get_settings()
    session_token = get_admin_session_token(request)
    if not session_token:
        return None
    payload = parse_visitor_token(session_token, settings.secret_key, settings.admin_session_ttl_seconds)
    if not payload:
        return None
    if payload.get("typ") != "admin":
        return None
    return payload


def get_admin_identity(request: Request) -> str | None:
    settings = get_settings()
    legacy_token = request.headers.get("X-Admin-Token", "").strip()
    if legacy_token and legacy_token == settings.admin_token:
        return settings.admin_username

    payload = _parse_admin_session_payload(request)
    if not payload:
        return None
    username = str(payload.get("usr", "")).strip()
    return username or None


def is_admin_request(request: Request) -> bool:
    return get_admin_identity(request) is not None


def require_admin_request(request: Request) -> None:
    if not is_admin_request(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="admin login required")


def _admin_failure_state(username: str) -> tuple[int, int, int]:
    # count, window_start_ts, locked_until_ts
    return _in_memory_admin_login_failures.get(username, (0, 0, 0))


def ensure_admin_not_locked(username: str) -> None:
    settings = get_settings()
    now = int(time.time())
    count, window_start, locked_until = _admin_failure_state(username)

    if locked_until > now:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="admin login temporarily locked")

    if window_start == 0 or now - window_start > settings.admin_login_lock_seconds:
        _in_memory_admin_login_failures[username] = (0, now, 0)


def record_admin_login_failure(username: str) -> None:
    settings = get_settings()
    now = int(time.time())
    count, window_start, locked_until = _admin_failure_state(username)
    if window_start == 0 or now - window_start > settings.admin_login_lock_seconds:
        count = 0
        window_start = now
        locked_until = 0

    count += 1
    if count >= settings.admin_login_fail_limit:
        _in_memory_admin_login_failures[username] = (0, now, now + settings.admin_login_lock_seconds)
    else:
        _in_memory_admin_login_failures[username] = (count, window_start, locked_until)


def clear_admin_login_failures(username: str) -> None:
    now = int(time.time())
    _in_memory_admin_login_failures[username] = (0, now, 0)


def reset_runtime_state_for_tests() -> None:
    _in_memory_rate_limit.clear()
    _in_memory_admin_login_failures.clear()
