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
from ..services.sse_manager import SSE_DISCONNECT_SENTINEL, manager

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
    keepalive_interval = max(0.5, float(settings.notification_sse_poll_seconds))
    shutdown_event = getattr(request.app.state, "shutdown_event", None)
    queue = await manager.connect(user.id)

    async def event_generator():
        yield ": connected\n\n"
        try:
            initial_items = await asyncio.to_thread(notification_engine.fetch_and_mark_user_deliveries, user.id, limit=20)
            for item in initial_items:
                yield _sse_encode("notice", item)

            while True:
                if shutdown_event is not None and shutdown_event.is_set():
                    break
                if await request.is_disconnected():
                    break

                try:
                    item = await asyncio.wait_for(queue.get(), timeout=keepalive_interval)
                except asyncio.TimeoutError:
                    ping_payload = {"ts": datetime.now(timezone.utc).isoformat()}
                    yield _sse_encode("ping", ping_payload)
                    continue

                if item is SSE_DISCONNECT_SENTINEL:
                    break
                delivery_id = str(item.get("id") or "").strip() if isinstance(item, dict) else ""
                if not delivery_id:
                    continue
                claimed = await asyncio.to_thread(notification_engine.mark_inapp_delivery_sent, user.id, delivery_id)
                if not claimed:
                    continue
                yield _sse_encode("notice", item)

        except asyncio.CancelledError:
            return
        finally:
            manager.disconnect(user.id, queue)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)
