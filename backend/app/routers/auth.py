import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit
from ..models import User, utcnow
from ..schemas import SilentLoginRequest, SilentLoginResponse
from ..security import create_visitor_token
from ..services.wechat import WechatService

router = APIRouter(prefix="/auth", tags=["auth"])


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
