from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, quote

from sqlalchemy.orm import Session

from ..models import CrawlJob, School, SiteSection, utcnow
from .crawler import _extract_title, _fetch_with_retry
from .site_section_bootstrap import bootstrap_site_sections

_SEARCH_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_HOST_HINTS = ("yjs", "yjsy", "yjsc", "yz", "zhaosheng", "graduate", "grad", "grs", "master")
_SCHOOL_SUFFIXES = ("大学", "学院", "研究院", "研究所")
_DENY_HOST_KEYWORDS = (
    "baidu.com",
    "sogou.com",
    "bing.com",
    "zhihu.com",
    "qq.com",
    "weixin.qq.com",
    "baike",
    "map.qq.com",
    "yuanbao.tencent.com",
    "thepaper.cn",
    "sohu.com",
    "163.com",
    "sina.com",
    "chsi.com.cn",
)
_DOC_SEED_FILES = (
    "adjustment_announcement_2025_summary.json",
    "adjustment_opportunity_2025_snapshot_summary.json",
    "adjustment_supplemental_priority_targets_2024_2025.json",
    "adjustment_expanded_priority_targets_2024_2026.json",
)
_SEARCH_QUERIES = (
    "{school_name} 研究生院",
    "{school_name} 研究生招生",
    "{school_name} 招生信息网",
)


def _docs_data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data"


def _normalize_url(url: str) -> str:
    return str(url or "").strip().split("#", 1)[0]


def _url_origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _parent_url(url: str) -> str | None:
    parsed = urlparse(url)
    path = (parsed.path or "").strip()
    if not path or path == "/":
        return None
    parent_path = path.rsplit("/", 1)[0]
    if not parent_path:
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parent_path if parent_path.endswith('/') else parent_path + '/'}"


@lru_cache(maxsize=1)
def _load_school_seed_map() -> dict[str, list[str]]:
    seeds: dict[str, list[str]] = {}
    for filename in _DOC_SEED_FILES:
        path = _docs_data_dir() / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]]
        if isinstance(payload, dict):
            rows = [row for row in (payload.get("top_schools") or payload.get("schools") or payload.get("items") or []) if isinstance(row, dict)]
        elif isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        else:
            rows = []

        for row in rows:
            school_name = str(row.get("school_name") or "").strip()
            top_url = _normalize_url(str(row.get("top_url") or ""))
            if not school_name or not top_url:
                continue
            bucket = seeds.setdefault(school_name, [])
            if top_url not in bucket:
                bucket.append(top_url)
    return seeds


def _discover_seed_urls_from_docs(school_name: str) -> list[str]:
    return list(_load_school_seed_map().get(school_name.strip(), []))


def _dedupe_texts(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _build_school_validation_terms(school_name: str) -> list[str]:
    raw = str(school_name or "").strip()
    compact = re.sub(r"\s+", "", raw)
    terms = [raw, compact]
    for suffix in _SCHOOL_SUFFIXES:
        if compact.endswith(suffix) and len(compact) > len(suffix) + 1:
            terms.append(compact[: -len(suffix)])
    return [term for term in _dedupe_texts(terms) if len(term) >= 2]


def _extract_candidate_urls_from_search_result(raw_html: str) -> list[str]:
    urls: list[str] = []
    for match in _SEARCH_URL_RE.findall(raw_html):
        normalized = _normalize_url(match.rstrip(").,;"))
        if not normalized:
            continue
        parsed = urlparse(normalized)
        host = (parsed.netloc or "").lower()
        if not host:
            continue
        if any(keyword in host for keyword in _DENY_HOST_KEYWORDS):
            continue
        if not (host.endswith(".edu.cn") or host.endswith(".ac.cn")):
            continue
        if normalized not in urls:
            urls.append(normalized)
    return urls


def _score_candidate_url(url: str) -> int:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = (parsed.path or "").lower()
    score = 0
    if host.endswith(".edu.cn"):
        score += 10
    if host.endswith(".ac.cn"):
        score += 8
    if any(hint in host or hint in path for hint in _HOST_HINTS):
        score += 6
    if path and path not in {"", "/"}:
        score += 2
    if host.count(".") >= 2:
        score += 1
    return score


def _candidate_page_matches_school_name(candidate_url: str, school_name: str) -> bool:
    terms = _build_school_validation_terms(school_name)
    if not terms:
        return False

    probe_urls = _dedupe_texts([candidate_url, _url_origin(candidate_url)])
    for probe_url in probe_urls:
        try:
            response = _fetch_with_retry(probe_url)
        except Exception:
            continue
        raw_html = response.text or ""
        title = _extract_title(raw_html) or ""
        normalized_html = _SPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", raw_html))
        haystacks = [
            title,
            re.sub(r"\s+", "", title),
            normalized_html[:4000],
            re.sub(r"\s+", "", normalized_html[:4000]),
        ]
        if any(term in haystack for term in terms for haystack in haystacks if haystack):
            return True
    return False


def _discover_seed_urls_from_search(school_name: str) -> list[str]:
    candidates: dict[str, int] = {}
    for template in _SEARCH_QUERIES:
        query = template.format(school_name=school_name.strip())
        url = f"https://www.sogou.com/web?query={quote(query)}"
        try:
            response = _fetch_with_retry(url)
        except Exception:
            continue
        raw_html = response.text or ""
        for candidate_url in _extract_candidate_urls_from_search_result(raw_html):
            score = _score_candidate_url(candidate_url)
            if score <= 0:
                continue
            if not _candidate_page_matches_school_name(candidate_url, school_name):
                continue
            candidates[candidate_url] = max(score, candidates.get(candidate_url, 0))

    ranked = sorted(candidates.items(), key=lambda item: (-item[1], item[0]))
    return [url for url, _score in ranked[:5]]


def _expand_seed_urls(seed_urls: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for seed_url in seed_urls:
        normalized = _normalize_url(seed_url)
        if not normalized:
            continue
        for candidate in (normalized, _parent_url(normalized), _url_origin(normalized)):
            text = _normalize_url(candidate or "")
            if not text or text in seen:
                continue
            seen.add(text)
            expanded.append(text)
    return expanded


def _resolve_bootstrap_entrypoint(seed_urls: list[str], expanded_seed_urls: list[str]) -> tuple[str, list[str]]:
    ordered = expanded_seed_urls or seed_urls
    if not ordered:
        return "", []
    primary_seed = _normalize_url(seed_urls[0] if seed_urls else ordered[0])
    homepage_url = _url_origin(primary_seed) or _normalize_url(ordered[0])
    extra_seed_urls: list[str] = []
    seen: set[str] = {homepage_url}
    for candidate in [primary_seed, *ordered]:
        normalized = _normalize_url(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        extra_seed_urls.append(normalized)
    return homepage_url, extra_seed_urls


def _find_pending_discovery_jobs(db: Session, school_name: str, section_ids: set[str]) -> list[CrawlJob]:
    rows = (
        db.query(CrawlJob)
        .filter(CrawlJob.status.in_(["pending", "running"]))
        .order_by(CrawlJob.requested_at.desc())
        .limit(200)
        .all()
    )
    result: list[CrawlJob] = []
    normalized_school_name = school_name.strip()
    for row in rows:
        payload = dict(row.query or {})
        if payload.get("job_kind") != "site_section_discovery":
            continue
        section_id = str(payload.get("site_section_id") or "").strip()
        job_school_name = str(payload.get("school_name") or "").strip()
        if section_id in section_ids and job_school_name == normalized_school_name:
            result.append(row)
    return result


def _queue_existing_section_jobs(db: Session, *, school_name: str, sections: list[SiteSection]) -> list[str]:
    if not sections:
        return []
    section_ids = {section.id for section in sections}
    existing_jobs = _find_pending_discovery_jobs(db, school_name, section_ids)
    already_queued_ids = {
        str((job.query or {}).get("site_section_id") or "").strip()
        for job in existing_jobs
    }
    job_ids = [job.id for job in existing_jobs]

    school = sections[0].school if sections[0].school is not None else None
    school_id = school.id if school is not None else None
    department_name = sections[0].department.name if sections[0].department is not None else None
    department_id = sections[0].department.id if sections[0].department is not None else None

    for section in sections:
        if section.id in already_queued_ids:
            continue
        job = CrawlJob(
            category=section.discovery_category,
            status="pending",
            requested_at=utcnow(),
            message=f"queued by announcement search for site section {section.id}",
            query={
                "job_kind": "site_section_discovery",
                "site_section_id": section.id,
                "source_url": section.section_url,
                "school_name": school_name.strip(),
                "department_name": department_name,
                "school_id": school_id,
                "department_id": department_id,
                "bootstrap_origin": "announcement_search",
            },
        )
        db.add(job)
        db.flush()
        job_ids.append(job.id)

    db.commit()
    return job_ids


def ensure_announcement_search_bootstrap(db: Session, school_name: str) -> dict[str, Any] | None:
    normalized_school_name = str(school_name or "").strip()
    if not normalized_school_name:
        return None

    school = db.query(School).filter(School.name == normalized_school_name).one_or_none()
    existing_sections: list[SiteSection] = []
    if school is not None:
        existing_sections = (
            db.query(SiteSection)
            .filter(SiteSection.school_id == school.id, SiteSection.enabled == 1)
            .order_by(SiteSection.created_at.asc())
            .all()
        )

    if existing_sections:
        section_ids = {section.id for section in existing_sections}
        pending_jobs = _find_pending_discovery_jobs(db, normalized_school_name, section_ids)
        if pending_jobs:
            return {
                "state": "in_progress",
                "school_name": normalized_school_name,
                "message": f"已自动启动 {normalized_school_name} 的公告补抓，正在拉取官网栏目，请稍后自动刷新。",
                "candidate_urls": [section.section_url for section in existing_sections[:5]],
                "job_ids": [job.id for job in pending_jobs],
            }

        job_ids = _queue_existing_section_jobs(db, school_name=normalized_school_name, sections=existing_sections)
        return {
            "state": "queued",
            "school_name": normalized_school_name,
            "message": f"已发现 {normalized_school_name} 的现有栏目资产，正在补抓最新公告，请稍后自动刷新。",
            "candidate_urls": [section.section_url for section in existing_sections[:5]],
            "job_ids": job_ids,
        }

    seed_urls = _discover_seed_urls_from_docs(normalized_school_name)
    if not seed_urls:
        seed_urls = _discover_seed_urls_from_search(normalized_school_name)
    expanded_seed_urls = _expand_seed_urls(seed_urls)
    if not expanded_seed_urls:
        return {
            "state": "no_candidate",
            "school_name": normalized_school_name,
            "message": f"系统还没定位到 {normalized_school_name} 的官网候选，当前无法自动补抓这所学校的公告。",
            "candidate_urls": [],
            "job_ids": [],
        }

    homepage_url, extra_seed_urls = _resolve_bootstrap_entrypoint(seed_urls, expanded_seed_urls)
    result = bootstrap_site_sections(
        db,
        school_name=normalized_school_name,
        homepage_url=homepage_url,
        department_name=None,
        department_type="graduate_school",
        seed_urls=extra_seed_urls,
        enabled=True,
        queue_discovery=True,
        max_sections=8,
    )
    job_ids = list(result.get("job_ids") or [])
    state = "queued" if job_ids else "in_progress"
    message = f"已自动为 {normalized_school_name} 启动陌生院校冷启动，正在发现官网栏目并补抓公告，请稍后自动刷新。"
    return {
        "state": state,
        "school_name": normalized_school_name,
        "message": message,
        "candidate_urls": expanded_seed_urls[:5],
        "job_ids": job_ids,
    }
