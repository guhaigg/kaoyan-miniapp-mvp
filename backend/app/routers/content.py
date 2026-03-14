from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit, get_current_user_optional
from ..schemas import ContentIn, ContentOut
from ..services.content import upsert_content

router = APIRouter(prefix="/content", tags=["content"])


@router.post("", response_model=ContentOut)
def ingest_content(payload: ContentIn, request: Request, db: Session = Depends(get_db)) -> ContentOut:
    current_user = get_current_user_optional(request, db)
    identity = current_user.id if current_user else (request.client.host if request.client else "unknown")
    enforce_rate_limit(request, f"content:{identity}")

    content, status = upsert_content(db, payload)
    audit_event(db, request, "content.upsert", current_user.id if current_user else None, {"content_id": content.id, "status": status})
    return ContentOut(id=content.id, status=status)

