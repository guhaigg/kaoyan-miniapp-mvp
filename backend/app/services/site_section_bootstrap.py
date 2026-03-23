from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from sqlalchemy.orm import Session

from ..models import CrawlJob, Department, School, Source, SiteSection, utcnow
from .crawler import (
    _extract_links,
    _extract_title,
    _fetch_with_retry,
    build_site_section_detail_selector_config,
    build_site_section_list_selector_config,
)

_COMMON_SEED_PATHS = [
    "/",
    "/yjs/",
    "/yjsy/",
    "/yjsc/",
    "/grs/",
    "/graduate/",
    "/yz/",
    "/zs/",
]

_ENTRY_KEYWORDS = [
    "研究生院",
    "研究生招生",
    "研究生",
    "研招",
    "招生信息网",
    "招生工作",
    "硕士招生",
    "博士招生",
]

_ENTRY_EXCLUDE_KEYWORDS = [
    "本科",
    "就业",
    "继续教育",
    "成人教育",
    "留学生",
    "博士后",
    "培训",
]

_SECTION_RULES: list[tuple[str, str, list[str]]] = [
    ("adjustment", "adjustment", ["调剂", "缺额", "意向采集"]),
    ("admissions", "announcement", ["研究生招生", "招生信息", "招生工作", "招生简章", "复试", "录取", "推免"]),
    ("notice", "announcement", ["通知公告", "公告通知", "通知", "公告"]),
]
_DETAIL_URL_PATTERNS = [
    r"/page\.htm(?:l)?$",
    r"/info/\d+/\d+\.htm(?:l)?$",
    r"/c\d+[a-z]?\d+/page\.htm(?:l)?$",
    r"/[a-z0-9_-]{0,12}\d{4,}\.htm(?:l)?$",
]


@dataclass(slots=True)
class CandidateSection:
    url: str
    name: str
    section_type: str
    discovery_category: str
    score: int


def _normalize_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    return text.split("#", 1)[0]


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _host_scope(host: str) -> str:
    labels = [label for label in host.lower().split(".") if label]
    if len(labels) >= 3 and labels[-2:] in (["edu", "cn"], ["ac", "cn"]):
        return ".".join(labels[-3:])
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return host.lower()


def _is_same_site(base_url: str, target_url: str) -> bool:
    base_host = (urlparse(base_url).netloc or "").lower()
    target_host = (urlparse(target_url).netloc or "").lower()
    if not base_host or not target_host:
        return False
    return _host_scope(base_host) == _host_scope(target_host)


def looks_like_detail_page_url(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    if not path or path.endswith("/"):
        return False
    return any(re.search(pattern, path) for pattern in _DETAIL_URL_PATTERNS)


def _normalize_label(text: str, fallback_url: str) -> str:
    label = " ".join(str(text or "").split()).strip()
    if label:
        return label[:255]
    path = urlparse(fallback_url).path.rstrip("/")
    return (path.split("/")[-1] or fallback_url)[:255]


def _entry_score(text: str, absolute_url: str) -> int:
    haystack = f"{text} {absolute_url}".lower()
    if any(keyword.lower() in haystack for keyword in _ENTRY_EXCLUDE_KEYWORDS):
        return 0
    score = 0
    for keyword in _ENTRY_KEYWORDS:
        if keyword.lower() in haystack:
            score += len(keyword)
    return score


def _classify_section(text: str, absolute_url: str) -> tuple[str, str, int] | None:
    haystack = f"{text} {absolute_url}".lower()
    best: tuple[str, str, int] | None = None
    for section_type, discovery_category, keywords in _SECTION_RULES:
        score = 0
        for keyword in keywords:
            if keyword.lower() in haystack:
                score += len(keyword)
        if score <= 0:
            continue
        candidate = (section_type, discovery_category, score)
        if best is None or candidate[2] > best[2]:
            best = candidate
    return best


def _build_allowed_path_prefixes(section_url: str) -> list[str]:
    path = (urlparse(section_url).path or "").strip()
    if not path or path == "/":
        return []
    if path.endswith("/"):
        return [path]
    prefix = path.rsplit("/", 1)[0]
    if not prefix:
        return []
    return [prefix if prefix.endswith("/") else f"{prefix}/"]


def _resolve_school(db: Session, school_name: str) -> School:
    name = school_name.strip()
    school = db.query(School).filter(School.name == name).one_or_none()
    if school is not None:
        return school
    school = School(name=name, aliases=[])
    db.add(school)
    db.flush()
    return school


def _resolve_department(
    db: Session,
    *,
    school: School,
    department_name: str | None,
    department_type: str,
) -> Department | None:
    name = str(department_name or "").strip()
    if not name:
        return None
    department = (
        db.query(Department)
        .filter(Department.school_id == school.id, Department.name == name)
        .one_or_none()
    )
    if department is not None:
        return department
    department = Department(
        school_id=school.id,
        name=name,
        aliases=[],
        department_type=department_type,
    )
    db.add(department)
    db.flush()
    return department


def _ensure_source(db: Session, *, school: School, homepage_url: str) -> Source:
    existing = (
        db.query(Source)
        .filter(Source.school_id == school.id, Source.base_url == homepage_url)
        .order_by(Source.created_at.asc())
        .first()
    )
    if existing is not None:
        return existing
    source = Source(
        school_id=school.id,
        name=f"{school.name}官网",
        source_type="official",
        base_url=homepage_url,
        config={},
        enabled=1,
    )
    db.add(source)
    db.flush()
    return source


def _fetch_html(url: str) -> tuple[str, str | None]:
    response = _fetch_with_retry(url)
    raw_html = response.text or ""
    return raw_html, _extract_title(raw_html)


def _collect_seed_urls(*, homepage_urls: list[str], extra_seed_urls: list[str], max_seed_pages: int) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    def _push(url: str) -> None:
        normalized = _normalize_url(url)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        ordered.append(normalized)

    for url in homepage_urls:
        _push(url)
        origin = _origin(url)
        for path in _COMMON_SEED_PATHS:
            _push(urljoin(origin or url, path))

    for url in extra_seed_urls:
        _push(url)

    return ordered[:max_seed_pages]


def _discover_entry_pages(*, homepage_urls: list[str], max_extra_pages: int) -> list[str]:
    scored: dict[str, int] = {}
    for homepage_url in homepage_urls:
        try:
            raw_html, _ = _fetch_html(homepage_url)
        except Exception:
            continue
        for item in _extract_links(raw_html):
            href = str(item.get("href") or "").strip()
            if not href:
                continue
            absolute_url = _normalize_url(urljoin(homepage_url, href))
            if not absolute_url or not _is_same_site(homepage_url, absolute_url):
                continue
            score = _entry_score(str(item.get("text") or ""), absolute_url)
            if score <= 0:
                continue
            scored[absolute_url] = max(score, scored.get(absolute_url, 0))

    return [url for url, _score in sorted(scored.items(), key=lambda item: (-item[1], item[0]))[:max_extra_pages]]


def _discover_candidate_sections(seed_url: str) -> list[CandidateSection]:
    raw_html, page_title = _fetch_html(seed_url)
    candidates: dict[str, CandidateSection] = {}

    page_match = _classify_section(page_title or "", seed_url)
    if page_match is not None and not looks_like_detail_page_url(seed_url):
        section_type, discovery_category, score = page_match
        candidates[seed_url] = CandidateSection(
            url=seed_url,
            name=_normalize_label(page_title or "", seed_url),
            section_type=section_type,
            discovery_category=discovery_category,
            score=score,
        )

    for item in _extract_links(raw_html):
        href = str(item.get("href") or "").strip()
        if not href or href.startswith("javascript:") or href.startswith("#"):
            continue
        absolute_url = _normalize_url(urljoin(seed_url, href))
        if not absolute_url or not _is_same_site(seed_url, absolute_url):
            continue
        if looks_like_detail_page_url(absolute_url):
            continue
        text = str(item.get("text") or "").strip()
        match = _classify_section(text, absolute_url)
        if match is None:
            continue
        section_type, discovery_category, score = match
        current = candidates.get(absolute_url)
        if current is not None and current.score >= score:
            continue
        candidates[absolute_url] = CandidateSection(
            url=absolute_url,
            name=_normalize_label(text, absolute_url),
            section_type=section_type,
            discovery_category=discovery_category,
            score=score,
        )

    return list(candidates.values())


def bootstrap_site_sections(
    db: Session,
    *,
    school_name: str,
    homepage_url: str | None,
    department_name: str | None,
    department_type: str,
    seed_urls: list[str],
    enabled: bool,
    queue_discovery: bool,
    max_sections: int,
    max_seed_pages: int = 10,
) -> dict[str, Any]:
    school = _resolve_school(db, school_name)
    department = _resolve_department(
        db,
        school=school,
        department_name=department_name,
        department_type=department_type,
    )

    homepage_urls: list[str] = []
    normalized_homepage = _normalize_url(homepage_url or "")
    if normalized_homepage:
        homepage_urls.append(normalized_homepage)
    else:
        homepage_urls.extend(
            row.base_url
            for row in db.query(Source)
            .filter(Source.school_id == school.id, Source.enabled == 1)
            .order_by(Source.created_at.asc())
            .all()
            if str(row.base_url or "").strip()
        )

    homepage_urls = list(dict.fromkeys(_normalize_url(url) for url in homepage_urls if _normalize_url(url)))
    if not homepage_urls:
        raise ValueError("homepage_url is required when the school has no existing source")

    source = _ensure_source(db, school=school, homepage_url=homepage_urls[0])
    seed_pool = _collect_seed_urls(
        homepage_urls=homepage_urls,
        extra_seed_urls=seed_urls + _discover_entry_pages(homepage_urls=homepage_urls, max_extra_pages=6),
        max_seed_pages=max_seed_pages,
    )

    candidate_map: dict[str, CandidateSection] = {}
    for seed_url in seed_pool:
        try:
            items = _discover_candidate_sections(seed_url)
        except Exception:
            continue
        for item in items:
            current = candidate_map.get(item.url)
            if current is not None and current.score >= item.score:
                continue
            candidate_map[item.url] = item

    ranked_candidates = sorted(candidate_map.values(), key=lambda item: (-item.score, item.url))[:max_sections]
    created_sections = 0
    existing_sections = 0
    job_ids: list[str] = []
    touched_sections: list[SiteSection] = []

    for candidate in ranked_candidates:
        section = db.query(SiteSection).filter(SiteSection.section_url == candidate.url).one_or_none()
        if section is None:
            section = SiteSection(
                school_id=school.id,
                department_id=department.id if department else None,
                source_id=source.id,
                name=candidate.name,
                section_type=candidate.section_type,
                section_url=candidate.url,
                discovery_category=candidate.discovery_category,
                enabled=1 if enabled else 0,
                list_selector_config={},
                detail_selector_config={},
            )
            list_config = build_site_section_list_selector_config(section, {"allowed_path_prefixes": _build_allowed_path_prefixes(candidate.url)})
            detail_config = build_site_section_detail_selector_config(section, {})
            section.list_selector_config = list_config
            section.detail_selector_config = detail_config
            db.add(section)
            db.flush()
            created_sections += 1
        else:
            existing_sections += 1

        touched_sections.append(section)
        if queue_discovery and bool(section.enabled):
            job = CrawlJob(
                category=section.discovery_category,
                status="pending",
                requested_at=utcnow(),
                message=f"queued by bootstrap for site section {section.id}",
                query={
                    "job_kind": "site_section_discovery",
                    "site_section_id": section.id,
                    "source_url": section.section_url,
                    "school_name": school.name,
                    "department_name": department.name if department else None,
                    "school_id": school.id,
                    "department_id": department.id if department else None,
                },
            )
            db.add(job)
            db.flush()
            job_ids.append(job.id)

    db.commit()
    return {
        "school": school,
        "homepage_url": homepage_urls[0],
        "seed_urls": seed_pool,
        "candidate_count": len(ranked_candidates),
        "created_sections": created_sections,
        "existing_sections": existing_sections,
        "job_ids": job_ids,
        "items": touched_sections,
    }
