from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from sqlalchemy.orm import Session

from ..models import CrawlJob, Department, School, Source, SiteSection, utcnow
from .crawler import _extract_links, _extract_title, _fetch_with_retry, build_site_section_detail_selector_config, build_site_section_list_selector_config
from .site_section_probe import (
    ContainerCandidate,
    build_list_selector_overrides,
    family_to_discovery_category,
    family_to_section_type,
    probe_section_page,
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

_KNOWN_FAMILIES = {"admissions", "adjustment", "notice"}
_FAMILY_PRIORITY = {"adjustment": 30, "admissions": 20, "notice": 10}


@dataclass(slots=True)
class CandidateSection:
    page_url: str
    name: str
    section_type: str
    discovery_category: str
    score: int
    probe_candidate: ContainerCandidate


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
    return any(
        re.search(pattern, path)
        for pattern in [
            r"/page\.htm(?:l)?$",
            r"/info/\d+/\d+\.htm(?:l)?$",
            r"/c\d+[a-z]?\d+/page\.htm(?:l)?$",
            r"/[a-z0-9_-]{0,12}\d{4,}\.htm(?:l)?$",
        ]
    )


def _looks_like_channel_prefix_page_url(url: str) -> bool:
    path = (urlparse(url).path or "").rstrip("/")
    return bool(path) and bool(re.search(r"/info/\d+$", path))


def _looks_like_fragmentary_page_url(url: str) -> bool:
    path = (urlparse(url).path or "").strip("/")
    if not path:
        return False
    if "/" in path:
        return False
    return len(path) <= 1 and "." not in path


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


def _candidate_score(candidate: ContainerCandidate) -> int:
    score = _FAMILY_PRIORITY.get(candidate.family, 0)
    score += max(1, int(candidate.detail_link_count or 0)) * 5
    if candidate.audience_scope == "masters":
        score += 6
    elif candidate.audience_scope == "general":
        score += 4
    elif candidate.audience_scope == "unknown":
        score += 2
    return score


def _build_candidate_section(candidate: ContainerCandidate, *, page_title: str | None) -> CandidateSection:
    name = _normalize_label(candidate.heading_text or page_title or "", candidate.page_url)
    return CandidateSection(
        page_url=candidate.page_url,
        name=name,
        section_type=family_to_section_type(candidate.family),
        discovery_category=family_to_discovery_category(candidate.family),
        score=_candidate_score(candidate),
        probe_candidate=candidate,
    )


def _normalize_families(families: set[str] | None) -> set[str] | None:
    if not families:
        return None
    normalized = {str(family or "").strip() for family in families if str(family or "").strip() in _KNOWN_FAMILIES}
    return normalized or None


def _section_container_signature(section: SiteSection) -> str:
    list_config = dict(section.list_selector_config or {})
    return str(list_config.get("container_signature") or "").strip()


def _find_existing_section(
    db: Session,
    *,
    school: School,
    department: Department | None,
    candidate: CandidateSection,
) -> SiteSection | None:
    query = db.query(SiteSection).filter(
        SiteSection.school_id == school.id,
        SiteSection.section_url == candidate.page_url,
        SiteSection.section_type == candidate.section_type,
    )
    if department is None:
        query = query.filter(SiteSection.department_id.is_(None))
    else:
        query = query.filter(SiteSection.department_id == department.id)
    rows = query.order_by(SiteSection.created_at.asc()).all()
    if not rows:
        return None

    signature = candidate.probe_candidate.container_signature
    for row in rows:
        if _section_container_signature(row) == signature:
            return row

    legacy_rows = [row for row in rows if not _section_container_signature(row)]
    if len(rows) == 1 and legacy_rows:
        return legacy_rows[0]
    return None


def _build_list_config_for_candidate(section: SiteSection, candidate: CandidateSection) -> dict[str, Any]:
    overrides = dict(section.list_selector_config or {})
    overrides.update(build_list_selector_overrides(candidate.probe_candidate))
    if not overrides.get("allowed_path_prefixes"):
        overrides["allowed_path_prefixes"] = _build_allowed_path_prefixes(candidate.page_url)
    return build_site_section_list_selector_config(section, overrides)


def _probe_seed_page(seed_url: str, *, families: set[str] | None) -> tuple[list[CandidateSection], list[str]]:
    raw_html, page_title = _fetch_html(seed_url)
    result = probe_section_page(
        seed_url,
        raw_html=raw_html,
        page_title=page_title,
        fetch_html=_fetch_html,
        family_filter=families,
        allow_browser=True,
    )

    candidates: list[CandidateSection] = []
    for item in result.candidates:
        if item.role != "leaf":
            continue
        if _looks_like_channel_prefix_page_url(item.page_url) or _looks_like_fragmentary_page_url(item.page_url):
            continue
        candidates.append(_build_candidate_section(item, page_title=page_title))

    frontier_urls: list[str] = []
    seen_frontier: set[str] = set()
    for url in result.frontier_urls:
        normalized = _normalize_url(url)
        if not normalized or normalized in seen_frontier:
            continue
        if not _is_same_site(seed_url, normalized) or looks_like_detail_page_url(normalized):
            continue
        seen_frontier.add(normalized)
        frontier_urls.append(normalized)

    return candidates, frontier_urls


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
    families: set[str] | None = None,
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

    normalized_families = _normalize_families(families)
    source = _ensure_source(db, school=school, homepage_url=homepage_urls[0])
    seed_pool = _collect_seed_urls(
        homepage_urls=homepage_urls,
        extra_seed_urls=seed_urls + _discover_entry_pages(homepage_urls=homepage_urls, max_extra_pages=6),
        max_seed_pages=max_seed_pages,
    )

    candidate_map: dict[tuple[str, str, str], CandidateSection] = {}
    queue = list(seed_pool)
    seen_pages: set[str] = set()
    max_probe_pages = max(max_seed_pages, len(seed_pool)) + max_sections
    while queue and len(seen_pages) < max_probe_pages:
        seed_url = _normalize_url(queue.pop(0))
        if not seed_url or seed_url in seen_pages:
            continue
        seen_pages.add(seed_url)
        try:
            candidates, frontier_urls = _probe_seed_page(seed_url, families=normalized_families)
        except Exception:
            continue

        for candidate in candidates:
            key = (
                candidate.page_url,
                candidate.section_type,
                candidate.probe_candidate.container_signature,
            )
            current = candidate_map.get(key)
            if current is None or candidate.score > current.score:
                candidate_map[key] = candidate

        for frontier_url in frontier_urls:
            if frontier_url in seen_pages or frontier_url in queue:
                continue
            queue.insert(0, frontier_url)

    ranked_candidates = sorted(candidate_map.values(), key=lambda item: (-item.score, item.page_url))[:max_sections]
    created_sections = 0
    existing_sections = 0
    job_ids: list[str] = []
    touched_sections: list[SiteSection] = []

    for candidate in ranked_candidates:
        section = _find_existing_section(db, school=school, department=department, candidate=candidate)
        if section is None:
            section = SiteSection(
                school_id=school.id,
                department_id=department.id if department else None,
                source_id=source.id,
                name=candidate.name,
                section_type=candidate.section_type,
                section_url=candidate.page_url,
                discovery_category=candidate.discovery_category,
                enabled=1 if enabled else 0,
                list_selector_config={},
                detail_selector_config={},
            )
            section.list_selector_config = _build_list_config_for_candidate(section, candidate)
            section.detail_selector_config = build_site_section_detail_selector_config(section, {})
            db.add(section)
            db.flush()
            created_sections += 1
        else:
            existing_sections += 1
            section.name = section.name or candidate.name
            section.source_id = section.source_id or source.id
            section.discovery_category = candidate.discovery_category
            section.enabled = 1 if enabled else section.enabled
            section.list_selector_config = _build_list_config_for_candidate(section, candidate)
            section.detail_selector_config = build_site_section_detail_selector_config(section, section.detail_selector_config or {})
            db.flush()

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
    candidate_urls: list[str] = []
    seen_candidate_urls: set[str] = set()
    for section in touched_sections:
        url = _normalize_url(section.section_url)
        if not url or url in seen_candidate_urls:
            continue
        seen_candidate_urls.add(url)
        candidate_urls.append(url)

    return {
        "school": school,
        "homepage_url": homepage_urls[0],
        "seed_urls": seed_pool,
        "candidate_count": len(candidate_map),
        "candidate_urls": candidate_urls,
        "created_sections": created_sections,
        "existing_sections": existing_sections,
        "job_ids": job_ids,
        "items": touched_sections,
    }
