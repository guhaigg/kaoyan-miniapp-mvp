import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal, get_db
from ..dependencies import enforce_rate_limit, get_portal_user_optional
from ..services.notifications import notification_engine

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _require_portal_user(request: Request, db: Session):
    user = get_portal_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user login required")
    return user


def _sse_encode(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/pending")
def list_pending_notifications(request: Request, db: Session = Depends(get_db)) -> dict:
    user = _require_portal_user(request, db)
    enforce_rate_limit(request, f"notification_pending:{user.id}")
    rows = notification_engine.fetch_and_mark_user_deliveries(user.id, limit=20)
    return {"total": len(rows), "items": rows}


@router.get("/stream")
async def stream_notifications(request: Request):
    with SessionLocal() as db:
        user = _require_portal_user(request, db)
    enforce_rate_limit(request, f"notification_stream:{user.id}")
    settings = get_settings()
    poll_interval = max(0.5, float(settings.notification_sse_poll_seconds))
    shutdown_event = getattr(request.app.state, "shutdown_event", None)

    async def event_generator():
        yield ": connected\n\n"
        try:
            while True:
                if shutdown_event is not None and shutdown_event.is_set():
                    break
                if await request.is_disconnected():
                    break

                items = await asyncio.to_thread(notification_engine.fetch_and_mark_user_deliveries, user.id, limit=20)
                if items:
                    for item in items:
                        yield _sse_encode("notice", item)
                else:
                    ping_payload = {"ts": datetime.now(timezone.utc).isoformat()}
                    yield _sse_encode("ping", ping_payload)

                await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            return

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)
