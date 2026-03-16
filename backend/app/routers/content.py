from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit, get_current_user_optional
from ..schemas import ContentIn, ContentOut
from ..services.content import upsert_content

router = APIRouter(prefix="/content", tags=["content"])


def _check_content_ingest_auth(request: Request) -> None:
    token = request.headers.get("X-Admin-Token", "").strip()
    if token != get_settings().admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")


@router.post("", response_model=ContentOut)
def ingest_content(payload: ContentIn, request: Request, db: Session = Depends(get_db)) -> ContentOut:
    _check_content_ingest_auth(request)
    current_user = get_current_user_optional(request, db)
    identity = current_user.id if current_user else (request.client.host if request.client else "unknown")
    enforce_rate_limit(request, f"content:{identity}")

    content, status = upsert_content(db, payload)
    audit_event(db, request, "content.upsert", current_user.id if current_user else None, {"content_id": content.id, "status": status})
    return ContentOut(id=content.id, status=status)
