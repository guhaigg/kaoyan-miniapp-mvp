import re
from datetime import datetime
from html import unescape
from typing import Any

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import CrawlError, CrawlJob, utcnow
from ..schemas import ContentIn
from .content import upsert_content

_UA = "Mozilla/5.0 (compatible; GeWuJianLuCrawler/0.1; +https://gewujl.cloud)"
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _extract_title(raw_html: str) -> str | None:
    match = _TITLE_RE.search(raw_html)
    if not match:
        return None
    title = _SPACE_RE.sub(" ", unescape(match.group(1))).strip()
    return title or None


def _extract_text(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", raw_html)
    text = _SPACE_RE.sub(" ", unescape(text)).strip()
    return text


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


class CrawlEngine:
    def process_job_batch(self) -> int:
        settings = get_settings()
        locked_ids = self._lock_pending_rows(settings.crawl_batch_size)
        if not locked_ids:
            return 0

        processed = 0
        for job_id in locked_ids:
            with SessionLocal() as db:
                job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one_or_none()
                if job is None:
                    continue
                try:
                    content_id, result = self._process_single_job(db, job)
                    job.status = "done"
                    job.finished_at = utcnow()
                    if content_id:
                        job.message = f"{result}: {content_id}"
                    else:
                        job.message = result
                    db.commit()
                    processed += 1
                except Exception as exc:
                    db.rollback()
                    self._mark_failed(job_id, exc)
                    processed += 1
        return processed

    def _lock_pending_rows(self, batch_size: int) -> list[str]:
        with SessionLocal() as db:
            query = db.query(CrawlJob).filter(CrawlJob.status == "pending").order_by(CrawlJob.requested_at.asc()).limit(batch_size)
            dialect_name = (db.bind.dialect.name if db.bind else "").lower()
            if dialect_name != "sqlite":
                query = query.with_for_update(skip_locked=True)
            rows = query.all()
            if not rows:
                return []

            now = utcnow()
            for row in rows:
                row.status = "running"
                row.started_at = now
                row.message = "worker picked up"
            db.commit()
            return [row.id for row in rows]

    def _process_single_job(self, db: Session, job: CrawlJob) -> tuple[str | None, str]:
        query = dict(job.query or {})
        source_url = str(query.get("source_url") or "").strip()
        content_payload = query.get("content")

        if query.get("simulate") is True:
            return self._ingest_simulated(db, job, query)

        if source_url:
            return self._ingest_from_url(db, job, query, source_url)

        if isinstance(content_payload, dict):
            return self._ingest_from_content_dict(db, job, query, content_payload)

        return None, "done(noop): no crawl source provided"

    def _ingest_from_url(
        self,
        db: Session,
        job: CrawlJob,
        query: dict[str, Any],
        source_url: str,
    ) -> tuple[str, str]:
        response = httpx.get(
            source_url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        )
        response.raise_for_status()
        raw_html = response.text or ""
        parsed_text = _extract_text(raw_html)
        if not parsed_text:
            raise ValueError("parsed body is empty")

        title = str(query.get("title") or "").strip() or _extract_title(raw_html) or f"{job.category} crawl {job.id[:8]}"
        body = str(query.get("body") or "").strip() or parsed_text
        summary = str(query.get("summary") or "").strip() or None
        extra = dict(query.get("extra") or {})
        extra["crawl_job_id"] = job.id
        extra["crawl_mode"] = "url_fetch"

        payload = ContentIn(
            category=job.category,
            title=title,
            body=body,
            summary=summary,
            school_name=(str(query.get("school_name") or "").strip() or None),
            source_url=source_url,
            source_type="crawler",
            published_at=_coerce_datetime(query.get("published_at")),
            region=(str(query.get("region") or "").strip() or None),
            major=(str(query.get("major") or "").strip() or None),
            extra=extra,
            raw_html=raw_html,
        )
        content, status = upsert_content(db, payload)
        return content.id, status

    def _ingest_from_content_dict(
        self,
        db: Session,
        job: CrawlJob,
        query: dict[str, Any],
        content_data: dict[str, Any],
    ) -> tuple[str, str]:
        category = str(content_data.get("category") or "").strip() or job.category
        title = str(content_data.get("title") or "").strip()
        body = str(content_data.get("body") or "").strip()
        if not title or not body:
            raise ValueError("content.title and content.body are required")

        source_url = str(content_data.get("source_url") or "").strip() or f"crawl-job://{job.id}"
        raw_html = str(content_data.get("raw_html") or "").strip() or None
        summary = str(content_data.get("summary") or "").strip() or None
        extra = dict(content_data.get("extra") or {})
        extra["crawl_job_id"] = job.id
        extra["crawl_mode"] = "content_payload"

        payload = ContentIn(
            category=category,
            title=title,
            body=body,
            summary=summary,
            school_name=(str(content_data.get("school_name") or "").strip() or None),
            source_url=source_url,
            source_type="crawler",
            published_at=_coerce_datetime(content_data.get("published_at")),
            region=(str(content_data.get("region") or "").strip() or None),
            major=(str(content_data.get("major") or "").strip() or None),
            extra=extra,
            raw_html=raw_html,
        )
        content, status = upsert_content(db, payload)
        return content.id, status

    def _ingest_simulated(self, db: Session, job: CrawlJob, query: dict[str, Any]) -> tuple[str, str]:
        title = str(query.get("title") or "").strip() or f"模拟抓取任务 {job.id[:8]}"
        body = str(query.get("body") or "").strip() or f"模拟抓取正文，任务 {job.id}"
        source_url = str(query.get("source_url") or "").strip() or f"crawl-job://{job.id}"
        raw_html = str(query.get("raw_html") or "").strip() or f"<html><body><h1>{title}</h1><p>{body}</p></body></html>"
        extra = dict(query.get("extra") or {})
        extra["crawl_job_id"] = job.id
        extra["crawl_mode"] = "simulate"

        payload = ContentIn(
            category=job.category,
            title=title,
            body=body,
            summary=(str(query.get("summary") or "").strip() or None),
            school_name=(str(query.get("school_name") or "").strip() or None),
            source_url=source_url,
            source_type="crawler",
            published_at=_coerce_datetime(query.get("published_at")),
            region=(str(query.get("region") or "").strip() or None),
            major=(str(query.get("major") or "").strip() or None),
            extra=extra,
            raw_html=raw_html,
        )
        content, status = upsert_content(db, payload)
        return content.id, status

    def _mark_failed(self, job_id: str, exc: Exception) -> None:
        with SessionLocal() as db:
            job = db.query(CrawlJob).filter(CrawlJob.id == job_id).one_or_none()
            if job is None:
                return
            query_payload = dict(job.query or {})
            source_url = str(query_payload.get("source_url") or "").strip() or None
            db.add(
                CrawlError(
                    source_id=None,
                    content_id=None,
                    source_url=source_url,
                    error_type=exc.__class__.__name__,
                    error_message=str(exc)[:2000],
                    payload={"crawl_job_id": job.id, "query": query_payload},
                )
            )
            job.status = "failed"
            job.finished_at = utcnow()
            job.message = str(exc)[:1000]
            db.commit()


crawl_engine = CrawlEngine()
