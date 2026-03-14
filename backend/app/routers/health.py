from fastapi import APIRouter, Request
from sqlalchemy import text

from ..config import get_settings
from ..db import SessionLocal
from ..schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    settings = get_settings()
    db_status = "up"
    redis_status = "down"

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        db_status = "down"

    try:
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is not None and redis_client.ping():
            redis_status = "up"
    except Exception:
        redis_status = "down"

    status = "ok" if db_status == "up" else "degraded"
    return HealthResponse(status=status, app_env=settings.app_env, db=db_status, redis=redis_status)
