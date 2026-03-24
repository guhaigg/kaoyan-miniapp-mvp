from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, quote

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import CrawlJob, School, SiteSection, SiteSectionLink, utcnow
from .crawler import _extract_links, _extract_title, _fetch_with_retry
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
_DEPARTMENT_ENTRY_RE = re.compile(r"(学院|学部|系|研究院)")
_KNOWN_FAMILIES = {"notice", "admissions", "adjustment"}
_SEARCH_QUERIES = (
    "{school_name} 研究生院",
    "{school_name} 研究生招生",
    "{school_name} 招生信息网",
)
_DETAIL_SECTION_URL_PATTERNS = [
    r"/page\.htm(?:l)?$",
    r"/info/\d+/\d+\.htm(?:l)?$",
    r"/c\d+[a-z]?\d+/page\.htm(?:l)?$",
    r"/[a-z0-9_-]{0,12}\d{4,}\.htm(?:l)?$",
]
_SCHOOL_LEVEL_SCOPE_HINTS = ("研究生院", "研工部", "研究生招生", "研招", "招生工作", "硕士研究生", "博士研究生")
_DEPARTMENT_SCOPE_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()·、]+?(?:学院|学部|系|研究院|研究所|中心))")
_ANNOUNCEMENT_CANONICAL_SEEDS: dict[str, dict[str, Any]] = {
    "上海师范大学": {
        "homepage_url": "https://yjsc.shnu.edu.cn/",
        "seed_urls": [
            "https://yjsc.shnu.edu.cn/17204/list.htm",
            "https://yjsc.shnu.edu.cn/17205/list.htm",
            "https://yjsc.shnu.edu.cn/17206/list.htm",
        ],
        "deny_prefixes": [
            "http://web.shnu.edu.cn/yjspyzx/",
            "https://web.shnu.edu.cn/yjspyzx/",
        ],
    }
}


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


def _looks_like_detail_section_url(url: str) -> bool:
    path = (urlparse(url).path or "").lower()
    if not path or path.endswith("/"):
        return False
    return any(re.search(pattern, path) for pattern in _DETAIL_SECTION_URL_PATTERNS)


def _derive_recovery_seed_urls_from_section_url(url: str) -> list[str]:
    normalized = _normalize_url(url)
    if not normalized:
        return []
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return []
    segments = [segment for segment in parsed.path.split("/") if segment]
    seeds: list[str] = [normalized]
    if segments:
        root_prefix = f"{parsed.scheme}://{parsed.netloc}/{segments[0]}/"
        seeds.extend([urljoin(root_prefix, "main.htm"), root_prefix])
    parent = _parent_url(normalized)
    if parent:
        seeds.append(parent)
    seeds.append(_url_origin(normalized))
    return _dedupe_texts(seeds)


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


def _has_school_level_scope_hint(*texts: str | None) -> bool:
    haystack = "".join(str(text or "").strip() for text in texts)
    return any(hint in haystack for hint in _SCHOOL_LEVEL_SCOPE_HINTS)


def _looks_department_scoped_text(*texts: str | None) -> bool:
    combined = " ".join(str(text or "").strip() for text in texts if str(text or "").strip())
    if not combined:
        return False
    if _has_school_level_scope_hint(combined):
        return False
    return bool(_DEPARTMENT_SCOPE_PATTERN.search(combined))


def _section_looks_department_scoped(section: SiteSection) -> bool:
    if section.department_id:
        return True
    list_config = dict(section.list_selector_config or {})
    probe_heading = str(list_config.get("probe_heading") or "").strip()
    probe_evidence = dict(list_config.get("probe_evidence") or {})
    stable_text = " ".join(
        [
            str(section.name or "").strip(),
            str(section.section_url or "").strip(),
            probe_heading,
            str(probe_evidence.get("stable_text") or "").strip(),
        ]
    )
    return _looks_department_scoped_text(stable_text)


def _resolve_announcement_seed_override(school_name: str) -> dict[str, Any] | None:
    return _ANNOUNCEMENT_CANONICAL_SEEDS.get(str(school_name or "").strip())


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
            page_scope_text = " ".join([title, normalized_html[:400]])
            if _looks_department_scoped_text(page_scope_text):
                continue
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
    parsed_primary = urlparse(primary_seed)
    primary_path = (parsed_primary.path or "").lower()
    if primary_path.endswith(("main.htm", "index.htm", "list.htm")) or primary_path.endswith("/"):
        homepage_url = primary_seed
    else:
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


def _section_probe_family(section: SiteSection) -> str:
    config = dict(section.list_selector_config or {})
    return str(config.get("probe_family") or section.section_type or "").strip()


def _section_probe_scope(section: SiteSection) -> str:
    config = dict(section.list_selector_config or {})
    return str(config.get("probe_scope") or "").strip()


def _section_probe_role(section: SiteSection) -> str:
    config = dict(section.list_selector_config or {})
    return str(config.get("probe_role") or "").strip()


def _section_is_compatible_for_families(section: SiteSection, families: set[str]) -> bool:
    family = _section_probe_family(section)
    if family not in families:
        return False

    if families == {"notice", "admissions"} and _section_looks_department_scoped(section):
        return False

    role = _section_probe_role(section)
    if role and role != "leaf":
        return False

    if families == {"notice", "admissions"} and family == "admissions":
        scope = _section_probe_scope(section)
        if scope == "doctoral":
            return False
    return True


def _discover_department_seed_urls(seed_urls: list[str], *, max_seed_pages: int = 8, max_results: int = 16) -> list[str]:
    results: list[str] = []
    seen_urls: set[str] = set()
    for seed_url in seed_urls[:max_seed_pages]:
        try:
            response = _fetch_with_retry(seed_url)
        except Exception:
            continue
        raw_html = response.text or ""
        for item in _extract_links(raw_html):
            href = str(item.get("href") or "").strip()
            text = str(item.get("text") or "").strip()
            if not href or not text or not _DEPARTMENT_ENTRY_RE.search(text):
                continue
            absolute_url = _normalize_url(urljoin(seed_url, href))
            if not absolute_url or absolute_url in seen_urls:
                continue
            if _looks_like_detail_section_url(absolute_url):
                continue
            if _url_origin(seed_url) and not absolute_url.startswith(_url_origin(seed_url)) and _host_scope(urlparse(seed_url).netloc or "") != _host_scope(urlparse(absolute_url).netloc or ""):
                continue
            seen_urls.add(absolute_url)
            results.append(absolute_url)
            if len(results) >= max_results:
                return results
    return results


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


def ensure_family_search_bootstrap(db: Session, school_name: str, families: set[str]) -> dict[str, Any] | None:
    normalized_school_name = str(school_name or "").strip()
    if not normalized_school_name:
        return None
    normalized_families = {family for family in families if family in _KNOWN_FAMILIES}
    if not normalized_families:
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

    reusable_sections = [section for section in existing_sections if _section_is_compatible_for_families(section, normalized_families)]
    recovery_seed_urls: list[str] = []
    if existing_sections:
        link_counts = {
            section_id: count
            for section_id, count in (
                db.query(SiteSectionLink.site_section_id, func.count(SiteSectionLink.id))
                .filter(SiteSectionLink.site_section_id.in_([section.id for section in existing_sections]))
                .group_by(SiteSectionLink.site_section_id)
                .all()
            )
        }
        reusable_sections = [
            section
            for section in existing_sections
            if _section_is_compatible_for_families(section, normalized_families)
            and not (_looks_like_detail_section_url(section.section_url) and int(link_counts.get(section.id, 0) or 0) == 0)
        ]
        if not reusable_sections:
            for section in existing_sections:
                recovery_seed_urls.extend(_derive_recovery_seed_urls_from_section_url(section.section_url))

    if reusable_sections:
        section_ids = {section.id for section in reusable_sections}
        pending_jobs = _find_pending_discovery_jobs(db, normalized_school_name, section_ids)
        if pending_jobs:
            return {
                "state": "in_progress",
                "school_name": normalized_school_name,
                "message": f"已自动启动 {normalized_school_name} 的栏目补抓，正在拉取官网栏目，请稍后自动刷新。",
                "candidate_urls": _dedupe_texts([section.section_url for section in reusable_sections[:5]]),
                "job_ids": [job.id for job in pending_jobs],
            }

        job_ids = _queue_existing_section_jobs(db, school_name=normalized_school_name, sections=reusable_sections)
        return {
            "state": "queued",
            "school_name": normalized_school_name,
            "message": f"已发现 {normalized_school_name} 的现有栏目资产，正在补抓最新内容，请稍后自动刷新。",
            "candidate_urls": _dedupe_texts([section.section_url for section in reusable_sections[:5]]),
            "job_ids": job_ids,
        }

    announcement_override = (
        _resolve_announcement_seed_override(normalized_school_name)
        if normalized_families == {"notice", "admissions"}
        else None
    )
    seed_urls = list(announcement_override.get("seed_urls") or []) if announcement_override else _discover_seed_urls_from_docs(normalized_school_name)
    if normalized_families == {"notice", "admissions"} and seed_urls and not announcement_override:
        validated_seed_urls = [url for url in seed_urls if _candidate_page_matches_school_name(url, normalized_school_name)]
        if validated_seed_urls:
            seed_urls = validated_seed_urls
    if not seed_urls:
        seed_urls = _discover_seed_urls_from_search(normalized_school_name)
    if recovery_seed_urls:
        seed_urls = _dedupe_texts([*seed_urls, *recovery_seed_urls])
    deny_prefixes = [str(prefix or "").strip() for prefix in (announcement_override or {}).get("deny_prefixes") or [] if str(prefix or "").strip()]
    if deny_prefixes:
        seed_urls = [url for url in seed_urls if not any(url.startswith(prefix) for prefix in deny_prefixes)]
    expanded_seed_urls = _expand_seed_urls(seed_urls)
    if "adjustment" in normalized_families:
        expanded_seed_urls = _dedupe_texts([*expanded_seed_urls, *_discover_department_seed_urls(expanded_seed_urls or seed_urls)])
    if not expanded_seed_urls:
        return {
            "state": "no_candidate",
            "school_name": normalized_school_name,
            "message": f"系统还没定位到 {normalized_school_name} 的官网候选，当前无法自动补抓这所学校的栏目。",
            "candidate_urls": [],
            "job_ids": [],
        }

    homepage_url, extra_seed_urls = _resolve_bootstrap_entrypoint(seed_urls, expanded_seed_urls)
    if announcement_override:
        homepage_url = str(announcement_override.get("homepage_url") or homepage_url or "").strip() or homepage_url
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
        families=normalized_families,
    )
    job_ids = list(result.get("job_ids") or [])
    state = "queued" if job_ids else "in_progress"
    message = f"已自动为 {normalized_school_name} 启动陌生院校冷启动，正在发现官网栏目并补抓内容，请稍后自动刷新。"
    visible_sections = [
        section
        for section in list(result.get("items") or [])
        if isinstance(section, SiteSection) and _section_is_compatible_for_families(section, normalized_families)
    ]
    candidate_urls = (
        _dedupe_texts([section.section_url for section in visible_sections])
        if visible_sections
        else list(result.get("candidate_urls") or expanded_seed_urls[:5])
    )
    if deny_prefixes:
        candidate_urls = [url for url in candidate_urls if not any(str(url or "").startswith(prefix) for prefix in deny_prefixes)]
    if normalized_families == {"notice", "admissions"}:
        candidate_urls = [
            url
            for url in candidate_urls
            if not _looks_like_detail_section_url(url)
            and not _looks_department_scoped_text(url)
        ]
    return {
        "state": state,
        "school_name": normalized_school_name,
        "message": message,
        "candidate_urls": candidate_urls,
        "job_ids": job_ids,
    }


def ensure_announcement_search_bootstrap(db: Session, school_name: str) -> dict[str, Any] | None:
    return ensure_family_search_bootstrap(db, school_name, {"notice", "admissions"})


def ensure_adjustment_search_bootstrap(db: Session, school_name: str) -> dict[str, Any] | None:
    return ensure_family_search_bootstrap(db, school_name, {"adjustment"})
