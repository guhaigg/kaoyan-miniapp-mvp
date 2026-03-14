from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import audit_event
from ..models import Content
from ..schemas import ContentOut, ManualEntryRequest
from ..services.content import upsert_content

router = APIRouter(prefix="/admin", tags=["admin"])


def _check_admin(request: Request) -> None:
    token = request.headers.get("X-Admin-Token", "").strip()
    if token != get_settings().admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")


@router.post("/manual-entry", response_model=ContentOut)
def manual_entry(payload: ManualEntryRequest, request: Request, db: Session = Depends(get_db)) -> ContentOut:
    _check_admin(request)

    if payload.action == "offline":
        if not payload.content_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content_id is required when action=offline")
        content = db.query(Content).filter(Content.id == payload.content_id).one_or_none()
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content not found")
        next_extra = dict(content.extra or {})
        next_extra["offline"] = True
        next_extra["offline_reason"] = payload.reason or "manual offline"
        content.extra = next_extra
        db.commit()
        audit_event(db, request, "admin.offline", None, {"content_id": content.id})
        return ContentOut(id=content.id, status="updated")

    if payload.content is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is required when action=upsert")
    content_data = payload.content.model_copy(update={"source_type": "manual"})
    content, result = upsert_content(db, content_data)
    audit_event(db, request, "admin.manual_upsert", None, {"content_id": content.id, "status": result})
    return ContentOut(id=content.id, status=result)

