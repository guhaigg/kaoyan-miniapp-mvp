import time

from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal, init_db
from .models import CrawlJob, utcnow
from .services.crawler import run_refresh_job


def _claim_pending_job(db: Session) -> CrawlJob | None:
    job = (
        db.query(CrawlJob)
        .filter(CrawlJob.status == "pending")
        .order_by(CrawlJob.requested_at.asc())
        .first()
    )
    if not job:
        return None
    job.status = "running"
    job.started_at = utcnow()
    job.message = "worker is processing"
    db.commit()
    db.refresh(job)
    return job


def process_single_pending_job() -> bool:
    with SessionLocal() as db:
        job = _claim_pending_job(db)
        if job is None:
            return False
        try:
            summary = run_refresh_job(db, job)
            job.status = "completed"
            job.finished_at = utcnow()
            job.message = summary.as_message()
            db.commit()
            return True
        except Exception as exc:  # pragma: no cover - defensive
            job.status = "failed"
            job.finished_at = utcnow()
            job.message = str(exc)
            db.commit()
            return True


def run_worker_forever() -> None:
    settings = get_settings()
    init_db()
    while True:
        has_job = process_single_pending_job()
        if not has_job:
            time.sleep(max(1, settings.worker_poll_interval_seconds))


if __name__ == "__main__":
    run_worker_forever()

