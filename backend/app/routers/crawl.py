from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, require_admin_request
from ..models import CrawlJob
from ..schemas import CrawlJobCreateRequest, CrawlJobCreateResponse, CrawlJobItem, CrawlJobListResponse

router = APIRouter(prefix="/crawl-jobs", tags=["crawl"])


def _normalize_job_status(status_value: str | None) -> str:
    value = (status_value or "").strip().lower()
    if value in {"pending", "running", "done", "failed"}:
        return value
    if value in {"completed", "success"}:
        return "done"
    if value in {"error"}:
        return "failed"
    return "failed"


def _to_job_item(job: CrawlJob) -> CrawlJobItem:
    return CrawlJobItem(
        id=job.id,
        category=job.category,
        query=job.query or {},
        status=_normalize_job_status(job.status),
        message=job.message,
        requested_by_user_id=job.requested_by_user_id,
        requested_at=job.requested_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.post("", response_model=CrawlJobCreateResponse)
def create_crawl_job(payload: CrawlJobCreateRequest, request: Request, db: Session = Depends(get_db)) -> CrawlJobCreateResponse:
    require_admin_request(request)
    job = CrawlJob(
        category=payload.category,
        query=payload.query,
        status="pending",
        message="queued by api",
        requested_by_user_id=None,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    audit_event(db, request, "crawl.job_create", None, {"crawl_job_id": job.id, "category": job.category})
    return CrawlJobCreateResponse(job_id=job.id, status="pending")


@router.get("", response_model=CrawlJobListResponse)
def list_crawl_jobs(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
) -> CrawlJobListResponse:
    require_admin_request(request)
    query = db.query(CrawlJob)
    if status_filter:
        query = query.filter(CrawlJob.status == status_filter.strip())
    total = query.count()
    rows = query.order_by(CrawlJob.requested_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return CrawlJobListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_job_item(job) for job in rows],
    )


@router.get("/{job_id}", response_model=CrawlJobItem)
def get_crawl_job(job_id: str, request: Request, db: Session = Depends(get_db)) -> CrawlJobItem:
    require_admin_request(request)
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="crawl job not found")
    return _to_job_item(job)
