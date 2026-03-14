from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import audit_event
from ..models import Content, School, Source
from ..schemas import AdminSourceUpsertRequest, AdminSourceUpsertResponse, ContentOut, ManualEntryRequest
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


@router.post("/sources", response_model=AdminSourceUpsertResponse)
def upsert_source(payload: AdminSourceUpsertRequest, request: Request, db: Session = Depends(get_db)) -> AdminSourceUpsertResponse:
    _check_admin(request)
    school_name = payload.school_name.strip()
    school = db.query(School).filter(School.name == school_name).one_or_none()
    if school is None:
        school = School(name=school_name, aliases=[])
        db.add(school)
        db.flush()

    source = None
    if payload.source_id:
        source = db.query(Source).filter(Source.id == payload.source_id).one_or_none()
    if source is None:
        source = db.query(Source).filter(Source.school_id == school.id, Source.base_url == payload.base_url).one_or_none()

    status_value = "updated" if source else "created"
    source = source or Source()
    source.school_id = school.id
    source.name = payload.name.strip()
    source.base_url = payload.base_url.strip()
    source.source_type = payload.source_type
    source.enabled = 1 if payload.enabled else 0
    source.config = payload.config or {}
    if status_value == "created":
        db.add(source)
    db.commit()
    db.refresh(source)
    audit_event(db, request, "admin.source_upsert", None, {"source_id": source.id, "status": status_value})
    return AdminSourceUpsertResponse(id=source.id, status=status_value)
