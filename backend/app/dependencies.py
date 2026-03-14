import time
import uuid
from collections import defaultdict

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import get_settings
from .models import User, UserEvent
from .security import parse_visitor_token

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


def enforce_rate_limit(request: Request, identity: str) -> None:
    settings = get_settings()
    window = int(time.time() // 60)
    key = f"rl:{identity}:{request.url.path}:{window}"
    redis_client = getattr(request.app.state, "redis", None)

    if redis_client is not None:
        value = redis_client.incr(key)
        if value == 1:
            redis_client.expire(key, 120)
        if value > settings.rate_limit_per_minute:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
        return

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
