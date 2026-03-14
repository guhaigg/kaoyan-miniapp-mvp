from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import CrawlError, CrawlJob, School, Source
from ..schemas import ContentIn
from .content import upsert_content

CATEGORY_HINTS = {
    "announcement": [
        "\u516c\u544a",
        "\u901a\u77e5",
        "\u7814\u7a76\u751f",
        "\u62db\u751f",
        "\u62db\u8003",
        "admission",
        "graduate",
    ],
    "adjustment": [
        "\u8c03\u5242",
        "\u7f3a\u989d",
        "\u540d\u989d",
        "\u590d\u8bd5",
        "transfer",
        "adjustment",
    ],
}


@dataclass
class CrawlSummary:
    sources_total: int = 0
    sources_succeeded: int = 0
    contents_created: int = 0
    contents_updated: int = 0
    errors: int = 0

    def as_message(self) -> str:
        return (
            f"sources={self.sources_total}, ok={self.sources_succeeded}, "
            f"created={self.contents_created}, updated={self.contents_updated}, errors={self.errors}"
        )


def fetch_html(url: str, timeout_seconds: int = 12) -> str:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def _extract_candidates(
    html: str,
    base_url: str,
    category: str,
    keywords: list[str],
    max_items: int,
) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    page_title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    lowered_keywords = [k.lower() for k in keywords if k]
    hints = CATEGORY_HINTS.get(category, [])

    candidates: list[dict[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            continue

        url = urljoin(base_url, href)
        text = " ".join(anchor.get_text(" ", strip=True).split())
        searchable = f"{text} {url}".lower()

        if lowered_keywords:
            if not any(k in searchable for k in lowered_keywords):
                continue
        elif hints and not any(h.lower() in searchable for h in hints):
            continue

        title = text[:500] if text else (page_title[:500] if page_title else f"{category} update")
        body = f"{title}\nsource page: {base_url}\ntarget link: {url}"
        candidates.append(
            {
                "title": title,
                "summary": f"Auto-captured from {base_url}",
                "body": body,
                "source_url": url,
            }
        )
        if len(candidates) >= max_items:
            break

    if candidates:
        return candidates

    fallback_text = " ".join(soup.get_text(" ", strip=True).split())[:1200]
    return [
        {
            "title": page_title[:500] if page_title else f"{category} update",
            "summary": f"Auto-captured from {base_url}",
            "body": fallback_text or f"Fetched from {base_url}",
            "source_url": base_url,
        }
    ]


def _source_matches_category(source: Source, category: str) -> bool:
    cfg = source.config or {}
    categories = cfg.get("categories")
    if not categories:
        return True
    if isinstance(categories, list):
        normalized = {str(x).strip().lower() for x in categories}
        return category.lower() in normalized
    return True


def _find_sources(db: Session, category: str, query: dict[str, Any]) -> list[Source]:
    settings = get_settings()
    source_query = db.query(Source).filter(Source.enabled == 1)

    school_name = str(query.get("school_name") or "").strip()
    if school_name:
        source_query = source_query.join(School, Source.school_id == School.id).filter(School.name.ilike(f"%{school_name}%"))

    rows = source_query.order_by(Source.updated_at.desc()).limit(settings.worker_max_sources_per_job).all()
    return [x for x in rows if _source_matches_category(x, category)]


def run_refresh_job(db: Session, job: CrawlJob) -> CrawlSummary:
    settings = get_settings()
    category = str(job.category or "").strip().lower()
    query = job.query or {}
    keywords = str(query.get("keywords") or "").strip().split()

    summary = CrawlSummary()
    sources = _find_sources(db, category, query)
    summary.sources_total = len(sources)

    for source in sources:
        try:
            html = fetch_html(source.base_url)
            candidates = _extract_candidates(
                html=html,
                base_url=source.base_url,
                category=category,
                keywords=keywords,
                max_items=settings.worker_max_items_per_source,
            )
            source_ok = False
            for candidate in candidates:
                payload = ContentIn(
                    category="adjustment" if category == "adjustment" else "announcement",
                    title=candidate["title"],
                    body=candidate["body"],
                    summary=candidate.get("summary"),
                    school_name=source.school.name if source.school else None,
                    source_url=candidate["source_url"],
                    source_type="crawler",
                    published_at=datetime.now(UTC),
                    region=str(query.get("region") or "").strip() or None,
                    major=str(query.get("major") or "").strip() or None,
                    extra={"source_id": source.id, "job_id": job.id},
                )
                _, status = upsert_content(db, payload)
                if status == "created":
                    summary.contents_created += 1
                else:
                    summary.contents_updated += 1
                source_ok = True

            if source_ok:
                summary.sources_succeeded += 1
        except Exception as exc:
            summary.errors += 1
            db.add(
                CrawlError(
                    source_id=source.id,
                    source_url=source.base_url,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    payload={"job_id": job.id, "category": category},
                )
            )
            db.commit()

    return summary
