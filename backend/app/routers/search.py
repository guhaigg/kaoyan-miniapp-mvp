from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit, get_current_user_optional
from ..models import Content, CrawlJob, School
from ..schemas import (
    AdjustmentSearchRequest,
    AnnouncementSearchRequest,
    SearchItem,
    SearchResponse,
)

router = APIRouter(prefix="/search", tags=["search"])


def _apply_common_filters(query, payload: AnnouncementSearchRequest | AdjustmentSearchRequest):
    if payload.school_name:
        query = query.join(School, isouter=True).filter(School.name.ilike(f"%{payload.school_name.strip()}%"))
    if payload.keywords:
        keyword = payload.keywords.strip()
        query = query.filter((Content.title.ilike(f"%{keyword}%")) | (Content.body.ilike(f"%{keyword}%")))
    if payload.start_date:
        query = query.filter(Content.published_at >= payload.start_date)
    if payload.end_date:
        query = query.filter(Content.published_at <= payload.end_date)
    return query


def _to_response(
    payload: AnnouncementSearchRequest | AdjustmentSearchRequest,
    request_id: str,
    items: list[Content],
    total: int,
    source_breakdown: dict[str, int],
    refresh_job_id: str | None,
) -> SearchResponse:
    serialized = []
    for row in items:
        school_name = row.school.name if row.school else None
        serialized.append(
            SearchItem(
                id=row.id,
                category=row.category,
                school_name=school_name,
                title=row.title,
                summary=row.summary,
                source_url=row.source_url,
                source_type=row.source_type,
                published_at=row.published_at,
                region=row.region,
                major=row.major,
                updated_at=row.updated_at,
            )
        )
    last_updated = max((x.updated_at for x in items), default=None)
    return SearchResponse(
        request_id=request_id,
        mode="hybrid_refresh" if payload.refresh else "cache",
        items=serialized,
        total=total,
        page=payload.page,
        page_size=payload.page_size,
        source_breakdown=source_breakdown,
        last_updated_at=last_updated,
        refresh_job_id=refresh_job_id,
    )


def _create_refresh_job(db: Session, category: str, payload: dict, user_id: str | None) -> str:
    job = CrawlJob(
        category=category,
        status="pending",
        query=payload,
        requested_by_user_id=user_id,
        requested_at=datetime.now(UTC),
        message="queued by api",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


@router.post("/announcements", response_model=SearchResponse)
def search_announcements(payload: AnnouncementSearchRequest, request: Request, db: Session = Depends(get_db)) -> SearchResponse:
    user = get_current_user_optional(request, db)
    identity = user.id if user else (request.client.host if request.client else "unknown")
    enforce_rate_limit(request, f"search_announcement:{identity}")

    request_id = str(uuid4())
    base_query = db.query(Content).filter(Content.category == "announcement")
    base_query = _apply_common_filters(base_query, payload)

    total = base_query.count()
    rows = (
        base_query.order_by(Content.published_at.is_(None), Content.published_at.desc(), Content.updated_at.desc())
        .offset((payload.page - 1) * payload.page_size)
        .limit(payload.page_size)
        .all()
    )
    stats_rows = base_query.with_entities(Content.source_type, func.count(Content.id)).group_by(Content.source_type).all()
    source_breakdown = {k: int(v) for k, v in stats_rows}

    refresh_job_id = None
    if payload.refresh:
        refresh_job_id = _create_refresh_job(db, "announcement", payload.model_dump(mode="json"), user.id if user else None)
    audit_event(db, request, "search.announcements", user.id if user else None, {"request_id": request_id, "refresh": payload.refresh})
    return _to_response(payload, request_id, rows, total, source_breakdown, refresh_job_id)


@router.post("/adjustments", response_model=SearchResponse)
def search_adjustments(payload: AdjustmentSearchRequest, request: Request, db: Session = Depends(get_db)) -> SearchResponse:
    user = get_current_user_optional(request, db)
    identity = user.id if user else (request.client.host if request.client else "unknown")
    enforce_rate_limit(request, f"search_adjustment:{identity}")

    request_id = str(uuid4())
    base_query = db.query(Content).filter(Content.category == "adjustment")
    base_query = _apply_common_filters(base_query, payload)
    if payload.major:
        base_query = base_query.filter(Content.major.ilike(f"%{payload.major.strip()}%"))
    if payload.region:
        base_query = base_query.filter(Content.region.ilike(f"%{payload.region.strip()}%"))

    total = base_query.count()
    rows = (
        base_query.order_by(Content.published_at.is_(None), Content.published_at.desc(), Content.updated_at.desc())
        .offset((payload.page - 1) * payload.page_size)
        .limit(payload.page_size)
        .all()
    )
    stats_rows = base_query.with_entities(Content.source_type, func.count(Content.id)).group_by(Content.source_type).all()
    source_breakdown = {k: int(v) for k, v in stats_rows}

    refresh_job_id = None
    if payload.refresh:
        refresh_job_id = _create_refresh_job(db, "adjustment", payload.model_dump(mode="json"), user.id if user else None)
    audit_event(db, request, "search.adjustments", user.id if user else None, {"request_id": request_id, "refresh": payload.refresh})
    return _to_response(payload, request_id, rows, total, source_breakdown, refresh_job_id)
