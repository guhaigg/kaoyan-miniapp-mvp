from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import CrawlJob
from ..schemas import CrawlJobStatusResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=CrawlJobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> CrawlJobStatusResponse:
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")

    return CrawlJobStatusResponse(
        id=job.id,
        category=job.category,
        status=job.status,
        message=job.message,
        query=job.query or {},
        requested_at=job.requested_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )

