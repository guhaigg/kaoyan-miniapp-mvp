import hashlib
import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import SessionLocal
from ..models import ContentFile, CrawlError, CrawlJob, SiteSection, SiteSectionLink, utcnow
from ..schemas import ContentIn
from .content import upsert_content

_UA = "Mozilla/5.0 (compatible; GeWuJianLuCrawler/0.1; +https://gewujl.cloud)"
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._active_href: str | None = None
        self._active_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_map = {key.lower(): value for key, value in attrs}
        href = (attrs_map.get("href") or "").strip()
        if not href:
            return
        self._active_href = href
        self._active_chunks = []

    def handle_data(self, data: str) -> None:
        if self._active_href is None:
            return
        text = data.strip()
        if text:
            self._active_chunks.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._active_href is None:
            return
        self.links.append(
            {
                "href": self._active_href,
                "text": _SPACE_RE.sub(" ", " ".join(self._active_chunks)).strip(),
            }
        )
        self._active_href = None
        self._active_chunks = []


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


def _extract_links(raw_html: str) -> list[dict[str, str]]:
    parser = _AnchorParser()
    parser.feed(raw_html)
    return parser.links


def _is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(".pdf")


def _fallback_link_title(url: str) -> str:
    path = urlparse(url).path or url
    name = path.rstrip("/").split("/")[-1]
    return name or url


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


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

        if query.get("job_kind") == "site_section_discovery":
            return self._discover_site_section(db, job, query)

        if query.get("simulate") is True:
            return self._ingest_simulated(db, job, query)

        if source_url:
            return self._ingest_from_url(db, job, query, source_url)

        if isinstance(content_payload, dict):
            return self._ingest_from_content_dict(db, job, query, content_payload)

        return None, "done(noop): no crawl source provided"

    def _discover_site_section(self, db: Session, job: CrawlJob, query: dict[str, Any]) -> tuple[None, str]:
        site_section_id = str(query.get("site_section_id") or "").strip()
        if not site_section_id:
            raise ValueError("site_section_id is required for discovery job")

        section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
        if section is None:
            raise ValueError("site section not found")

        section_url = str(query.get("source_url") or section.section_url or "").strip()
        if not section_url:
            raise ValueError("site section url is empty")

        response = httpx.get(
            section_url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        )
        response.raise_for_status()
        raw_html = response.text or ""
        discovered_links = _extract_links(raw_html)
        if not discovered_links:
            section.last_discovered_at = utcnow()
            section.last_discovery_status = "done"
            section.last_error = None
            return None, "discovery done: 0 new links"

        existing_url_hashes = {
            row[0]
            for row in db.query(SiteSectionLink.link_url_hash)
            .filter(SiteSectionLink.site_section_id == section.id)
            .all()
        }
        html_jobs = 0
        pdf_files = 0
        new_links = 0

        for item in discovered_links:
            href = (item.get("href") or "").strip()
            if not href or href.startswith("javascript:") or href.startswith("#"):
                continue

            absolute_url = urljoin(section_url, href)
            url_hash = _url_hash(absolute_url)
            if url_hash in existing_url_hashes:
                continue

            link_type = "pdf" if _is_pdf_url(absolute_url) else "html"
            title = (item.get("text") or "").strip() or _fallback_link_title(absolute_url)
            link = SiteSectionLink(
                site_section_id=section.id,
                link_url=absolute_url,
                link_url_hash=url_hash,
                title=title,
                link_type=link_type,
                status="discovered",
                snapshot_meta={
                    "crawl_job_id": job.id,
                    "section_url": section_url,
                    "section_type": section.section_type,
                },
            )
            db.add(link)
            db.flush()
            existing_url_hashes.add(url_hash)
            new_links += 1

            if link_type == "pdf":
                file_record = ContentFile(
                    site_section_link_id=link.id,
                    file_url=absolute_url,
                    file_url_hash=_url_hash(absolute_url),
                    file_type="pdf",
                    mime_type="application/pdf",
                    parse_status="pending",
                    ocr_status="not_started",
                    file_meta={
                        "crawl_job_id": job.id,
                        "site_section_id": section.id,
                        "section_url": section_url,
                    },
                )
                db.add(file_record)
                link.status = "file_recorded"
                pdf_files += 1
                continue

            child_job = CrawlJob(
                category=section.discovery_category,
                status="pending",
                requested_at=utcnow(),
                message=f"queued by site section discovery {section.id}",
                query={
                    "job_kind": "detail_fetch",
                    "site_section_id": section.id,
                    "site_section_link_id": link.id,
                    "source_url": absolute_url,
                    "title": title,
                    "school_name": section.school.name if section.school else None,
                    "department_name": section.department.name if section.department else None,
                    "section_type": section.section_type,
                },
            )
            db.add(child_job)
            db.flush()
            link.crawl_job_id = child_job.id
            link.status = "enqueued"
            html_jobs += 1

        section.last_discovered_at = utcnow()
        section.last_discovery_status = "done"
        section.last_error = None
        return None, f"discovery done: {new_links} links, {html_jobs} html jobs, {pdf_files} pdf files"

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
            site_section_id = str(query_payload.get("site_section_id") or "").strip() or None
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
            if site_section_id and query_payload.get("job_kind") == "site_section_discovery":
                section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
                if section is not None:
                    section.last_discovered_at = utcnow()
                    section.last_discovery_status = "failed"
                    section.last_error = str(exc)[:1000]
            job.status = "failed"
            job.finished_at = utcnow()
            job.message = str(exc)[:1000]
            db.commit()


crawl_engine = CrawlEngine()
