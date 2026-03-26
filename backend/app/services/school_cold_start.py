from __future__ import annotations

import json
import re
from datetime import timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, quote

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AnnouncementPortalCache, CrawlJob, School, SiteSection, SiteSectionLink, utcnow
from .announcement_portal import (
    PORTAL_SCOPE_GRADUATE_ADMISSIONS,
    is_graduate_portal_entry_text,
    looks_like_announcement_channel_prefix_page,
    looks_like_announcement_detail_page,
    looks_like_announcement_fragmentary_page,
    page_looks_like_graduate_admissions_portal,
    portal_candidate_host,
    portal_candidate_hosts,
    score_announcement_portal_candidate,
)
from .crawler import _extract_links, _extract_title, _fetch_with_retry
from .site_section_bootstrap import _host_scope, bootstrap_site_sections
from .workflow_v2 import create_scope_rebuild_run

_SEARCH_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
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
_SCHOOL_PREFIX_CONFLICT_SUFFIXES = ("独立学院", "学院", "学部", "研究院", "研究所", "中心", "分校", "校区", "系")
_DEPARTMENT_SCOPE_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()·、]+?(?:学院|学部|系|研究院|研究所|中心))")
_CHANNEL_PREFIX_PATH_RE = re.compile(r"/info/\d+/?$", re.IGNORECASE)
_ANNOUNCEMENT_NAV_TEXT_HINTS = (
    "硕士招生",
    "博士招生",
    "招生简章",
    "专业目录",
    "通知公告",
    "政策文件",
    "调剂",
    "招生工作",
    "硕士研究生招生信息",
    "博士研究生招生信息",
)
_HOMEPAGE_LIKE_SECTION_PATHS = {
    "",
    "/",
    "/index.htm",
    "/index.html",
    "/main.htm",
    "/main.html",
    "/default.htm",
    "/default.html",
    "/default.aspx",
}
_FAMILY_DISCOVERY_COOLDOWN = timedelta(minutes=10)
_ANNOUNCEMENT_PORTAL_CACHE_TTL = timedelta(days=30)
_ANNOUNCEMENT_CANONICAL_SEEDS: dict[str, dict[str, Any]] = {
    "湖北大学": {
        "homepage_url": "https://yz.hubu.edu.cn/",
        "seed_urls": [
            "https://yz.hubu.edu.cn/",
        ],
        "deny_prefixes": [
            "http://yjs.hbut.edu.cn/",
            "https://yjs.hbut.edu.cn/",
            "https://kjcy.hbut.edu.cn/",
            "https://ce.hbut.edu.cn/",
            "https://zs.hbut.edu.cn/",
            "https://yjsy.hbu.edu.cn/",
        ],
    },
    "江西农业大学": {
        "homepage_url": "https://yzb.jxau.edu.cn/",
        "seed_urls": [
            "https://yzb.jxau.edu.cn/sszs.htm",
            "https://yzb.jxau.edu.cn/bszs.htm",
            "https://yzb.jxau.edu.cn/zsjz/sszsjz.htm",
            "https://yzb.jxau.edu.cn/zsjz/bszsjz.htm",
        ],
    },
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


def _coerce_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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
    return looks_like_announcement_detail_page(url)


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
            stripped = compact[: -len(suffix)]
            if len(stripped) >= 3:
                terms.append(stripped)
    return [term for term in _dedupe_texts(terms) if len(term) >= 2]


def _compact_school_text(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _has_school_level_scope_hint(*texts: str | None) -> bool:
    haystack = "".join(str(text or "").strip() for text in texts)
    return any(hint in haystack for hint in _SCHOOL_LEVEL_SCOPE_HINTS)


def _school_prefix_conflict_signal(bound_school_name: str, candidate_text: str | None) -> bool:
    school_name = _compact_school_text(bound_school_name)
    candidate = _compact_school_text(candidate_text)
    if not school_name or not candidate or candidate == school_name:
        return False
    if not candidate.startswith(school_name):
        return False
    remainder = candidate[len(school_name) :]
    if not remainder:
        return False
    return any(remainder.endswith(suffix) and len(remainder) >= len(suffix) for suffix in _SCHOOL_PREFIX_CONFLICT_SUFFIXES)


def _texts_show_school_prefix_conflict(bound_school_name: str, *texts: str | None) -> bool:
    school_name = _compact_school_text(bound_school_name)
    if not school_name:
        return False
    suffix_pattern = "|".join(re.escape(suffix) for suffix in _SCHOOL_PREFIX_CONFLICT_SUFFIXES)
    pattern = re.compile(
        re.escape(school_name) + rf"[\u4e00-\u9fa5A-Za-z0-9（）()·、-]{{1,24}}?(?:{suffix_pattern})"
    )
    for text in texts:
        if _school_prefix_conflict_signal(bound_school_name, text):
            return True
        compact = _compact_school_text(text)
        if compact and pattern.search(compact):
            return True
    return False


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


def _announcement_override_hosts(announcement_override: dict[str, Any] | None) -> set[str]:
    if not announcement_override:
        return set()
    return portal_candidate_hosts(
        [
            announcement_override.get("homepage_url"),
            *(announcement_override.get("seed_urls") or []),
        ]
    )


def _filter_existing_sections_for_preferred_hosts(
    existing_sections: list[SiteSection],
    *,
    families: set[str],
    preferred_hosts: set[str],
) -> list[SiteSection]:
    if families != {"notice", "admissions"}:
        return existing_sections
    if not preferred_hosts:
        return existing_sections
    return [
        section
        for section in existing_sections
        if portal_candidate_host(section.section_url) in preferred_hosts
    ]


def _families_key(families: set[str]) -> str:
    return ",".join(sorted(family for family in families if family in _KNOWN_FAMILIES))


def _job_matches_families(job: CrawlJob, *, school_name: str, families: set[str]) -> bool:
    payload = dict(job.query or {})
    if payload.get("job_kind") != "family_discovery":
        return False
    if str(payload.get("school_name") or "").strip() != school_name.strip():
        return False
    job_families = {
        str(item or "").strip()
        for item in (payload.get("families") or [])
        if str(item or "").strip()
    }
    return job_families == {family for family in families if family in _KNOWN_FAMILIES}


def _find_family_discovery_jobs(
    db: Session,
    *,
    school_name: str,
    families: set[str],
    statuses: set[str] | None = None,
    limit: int = 40,
) -> list[CrawlJob]:
    query = db.query(CrawlJob)
    if statuses:
        query = query.filter(CrawlJob.status.in_(sorted(statuses)))
    rows = query.order_by(CrawlJob.requested_at.desc()).limit(limit).all()
    return [row for row in rows if _job_matches_families(row, school_name=school_name, families=families)]


def _latest_family_discovery_job(
    db: Session,
    *,
    school_name: str,
    families: set[str],
    statuses: set[str] | None = None,
) -> CrawlJob | None:
    rows = _find_family_discovery_jobs(db, school_name=school_name, families=families, statuses=statuses)
    return rows[0] if rows else None


def _looks_like_channel_prefix_page(url: str) -> bool:
    return looks_like_announcement_channel_prefix_page(url)


def _looks_like_fragmentary_seed_url(url: str) -> bool:
    return looks_like_announcement_fragmentary_page(url)


def _is_valid_school_seed_url(url: str, *, families: set[str]) -> bool:
    normalized = _normalize_url(url)
    if not normalized:
        return False
    if _looks_like_detail_section_url(normalized):
        return False
    if _looks_like_channel_prefix_page(normalized):
        return False
    if _looks_like_fragmentary_seed_url(normalized):
        return False
    if families == {"notice", "admissions"} and _looks_department_scoped_text(normalized):
        return False
    return True


def _score_seed_hint_url(url: str) -> int:
    score = score_announcement_portal_candidate(url)
    if _looks_department_scoped_text(url):
        score -= 40
    return score


def _filter_candidate_urls_for_families(
    candidate_urls: list[str],
    *,
    families: set[str],
    deny_prefixes: list[str] | None = None,
    preferred_hosts: set[str] | None = None,
    max_items: int = 5,
) -> list[str]:
    filtered = []
    normalized_preferred_hosts = {
        str(host or "").strip().lower()
        for host in (preferred_hosts or set())
        if str(host or "").strip()
    }
    for url in _dedupe_texts(candidate_urls):
        if deny_prefixes and any(url.startswith(prefix) for prefix in deny_prefixes):
            continue
        if not _is_valid_school_seed_url(url, families=families):
            continue
        filtered.append(url)
    if normalized_preferred_hosts:
        preferred_only = [url for url in filtered if portal_candidate_host(url) in normalized_preferred_hosts]
        if preferred_only:
            filtered = preferred_only
    def _sort_key(item: str) -> tuple[int, int, str]:
        host = portal_candidate_host(item)
        path = (urlparse(item).path or "").strip()
        preferred_homepage_rank = 2
        if normalized_preferred_hosts and host in normalized_preferred_hosts:
            preferred_homepage_rank = 0 if path in {"", "/"} else 1
        score = score_announcement_portal_candidate(item, preferred_hosts=normalized_preferred_hosts)
        if families == {"notice", "admissions"} and _looks_department_scoped_text(item):
            score -= 40
        return (preferred_homepage_rank, -score, item)

    ranked = sorted(filtered, key=_sort_key)
    return ranked[:max_items]


def _job_candidate_urls(job: CrawlJob) -> list[str]:
    payload = dict(job.query or {})
    result_urls = payload.get("result_candidate_urls")
    if isinstance(result_urls, list):
        return _dedupe_texts([str(item or "").strip() for item in result_urls if str(item or "").strip()])
    seed_urls = payload.get("seed_urls")
    if isinstance(seed_urls, list):
        return _dedupe_texts([str(item or "").strip() for item in seed_urls if str(item or "").strip()])
    seed_urls = payload.get("candidate_urls")
    if isinstance(seed_urls, list):
        return _dedupe_texts([str(item or "").strip() for item in seed_urls if str(item or "").strip()])
    return []


def _job_result_state(job: CrawlJob) -> str:
    payload = dict(job.query or {})
    result_state = str(payload.get("result_state") or "").strip()
    if result_state:
        return result_state
    if job.status in {"pending", "running"}:
        return "in_progress"
    if job.status == "failed":
        return "failed"
    return ""


def _build_school_level_page_text(raw_html: str, title: str | None) -> str:
    normalized_html = _SPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", raw_html or " "))
    return " ".join([str(title or "").strip(), normalized_html[:2500]]).strip()


def _page_conflicts_with_school_name(raw_html: str, title: str | None, school_name: str) -> bool:
    normalized_html = _SPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", raw_html or " "))
    scope_text = " ".join([str(title or "").strip(), normalized_html[:600]]).strip()
    return _texts_show_school_prefix_conflict(school_name, scope_text)


def _page_mentions_school(raw_html: str, title: str | None, school_name: str) -> bool:
    page_text = _build_school_level_page_text(raw_html, title)
    if not page_text:
        return False
    compact_page_text = re.sub(r"\s+", "", page_text)
    school_terms = _build_school_validation_terms(school_name)
    return any(term in page_text or term in compact_page_text for term in school_terms)


def _page_looks_school_level(raw_html: str, title: str | None, school_name: str) -> bool:
    if not _page_mentions_school(raw_html, title, school_name):
        return False
    page_text = _build_school_level_page_text(raw_html, title)
    compact_page_text = re.sub(r"\s+", "", page_text)
    if _looks_department_scoped_text(page_text):
        return False
    return _has_school_level_scope_hint(page_text) or "招生" in page_text


def _is_announcement_navigation_link(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    return any(hint in normalized for hint in _ANNOUNCEMENT_NAV_TEXT_HINTS)


def _candidate_link_is_portalish(link_text: str, absolute_url: str) -> bool:
    if _is_announcement_navigation_link(link_text) or is_graduate_portal_entry_text(link_text):
        return True
    return score_announcement_portal_candidate(absolute_url, link_text) > 0


def _announcement_navigation_candidate_urls(
    school_name: str,
    seed_urls: list[str],
    *,
    max_hops: int = 2,
    max_pages: int = 12,
) -> list[str]:
    seed_page_urls: list[tuple[str, bool]] = []
    seen_seed_pages: set[str] = set()
    for seed_url in seed_urls:
        for index, candidate in enumerate((_normalize_url(seed_url), _parent_url(seed_url), _url_origin(seed_url))):
            normalized = _normalize_url(candidate or "")
            if not normalized or normalized in seen_seed_pages:
                continue
            seen_seed_pages.add(normalized)
            seed_page_urls.append((normalized, index == 0))

    queue: list[tuple[str, int, bool]] = [(url, 0, include_current) for url, include_current in seed_page_urls[:max_pages]]
    seen_pages: set[str] = set()
    results: list[str] = []
    seen_result_urls: set[str] = set()

    while queue and len(seen_pages) < max_pages:
        page_url, depth, include_current = queue.pop(0)
        normalized_page_url = _normalize_url(page_url)
        if not normalized_page_url or normalized_page_url in seen_pages:
            continue
        seen_pages.add(normalized_page_url)

        try:
            response = _fetch_with_retry(normalized_page_url)
        except Exception:
            continue

        raw_html = response.text or ""
        title = _extract_title(raw_html) or ""
        page_text = _build_school_level_page_text(raw_html, title)
        if not _page_mentions_school(raw_html, title, school_name):
            continue
        if _page_conflicts_with_school_name(raw_html, title, school_name):
            continue

        if include_current and _page_looks_school_level(raw_html, title, school_name):
            score = score_announcement_portal_candidate(normalized_page_url, title, page_text)
            if score > 0 and _is_valid_school_seed_url(normalized_page_url, families={"notice", "admissions"}):
                if normalized_page_url not in seen_result_urls:
                    seen_result_urls.add(normalized_page_url)
                    results.append(normalized_page_url)

        base_scope = _host_scope(urlparse(normalized_page_url).netloc or "")
        for item in _extract_links(raw_html):
            link_text = str(item.get("text") or "").strip()
            href = str(item.get("href") or "").strip()
            if not href:
                continue
            absolute_url = _normalize_url(urljoin(normalized_page_url, href))
            if not absolute_url:
                continue
            target_scope = _host_scope(urlparse(absolute_url).netloc or "")
            if base_scope and target_scope and base_scope != target_scope:
                continue
            if not _candidate_link_is_portalish(link_text, absolute_url):
                continue
            if _is_valid_school_seed_url(absolute_url, families={"notice", "admissions"}) and absolute_url not in seen_result_urls:
                seen_result_urls.add(absolute_url)
                results.append(absolute_url)
            if depth >= max_hops:
                continue
            if absolute_url not in seen_pages and all(queued_url != absolute_url for queued_url, _depth, _include in queue):
                queue.append((absolute_url, depth + 1, True))

    return results


def _discover_announcement_navigation_seed_urls(
    school_name: str,
    seed_urls: list[str],
    *,
    max_pages: int = 12,
) -> list[str]:
    results = _announcement_navigation_candidate_urls(
        school_name,
        seed_urls,
        max_pages=max_pages,
    )
    return _filter_candidate_urls_for_families(results, families={"notice", "admissions"}, max_items=12)


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
    score = score_announcement_portal_candidate(url)
    if _looks_department_scoped_text(url):
        score -= 40
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
            if _texts_show_school_prefix_conflict(school_name, page_scope_text):
                continue
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
            if not _is_valid_school_seed_url(candidate_url, families={"notice", "admissions"}):
                continue
            score = _score_candidate_url(candidate_url)
            if score <= 0:
                continue
            if not _candidate_page_matches_school_name(candidate_url, school_name):
                continue
            candidates[candidate_url] = max(score, candidates.get(candidate_url, 0))

    ranked = sorted(candidates.items(), key=lambda item: (-item[1], item[0]))
    return [url for url, _score in ranked[:5]]


def _build_announcement_candidate_pool(
    school_name: str,
    *,
    announcement_override: dict[str, Any] | None,
    deny_prefixes: list[str],
    allow_search: bool,
) -> list[str]:
    seed_candidates: list[str] = []

    if announcement_override:
        homepage_url = _normalize_url(str(announcement_override.get("homepage_url") or ""))
        if homepage_url:
            seed_candidates.append(homepage_url)
        seed_candidates.extend(
            _normalize_url(str(url or ""))
            for url in (announcement_override.get("seed_urls") or [])
            if _normalize_url(str(url or ""))
        )
        return _filter_candidate_urls_for_families(
            seed_candidates,
            families={"notice", "admissions"},
            deny_prefixes=deny_prefixes,
            preferred_hosts=_announcement_override_hosts(announcement_override),
            max_items=12,
        )

    search_seed_urls: list[str] = []
    doc_seed_urls = [
        url
        for url in _discover_seed_urls_from_docs(school_name)
        if _is_valid_school_seed_url(url, families={"notice", "admissions"})
    ]
    if doc_seed_urls:
        validated_seed_urls = [url for url in doc_seed_urls if _candidate_page_matches_school_name(url, school_name)]
        if validated_seed_urls:
            doc_seed_urls = validated_seed_urls
    if allow_search and not doc_seed_urls:
        search_seed_urls = _discover_seed_urls_from_search(school_name)
    seed_candidates.extend(doc_seed_urls)
    seed_candidates.extend(search_seed_urls)

    navigation_seed_urls = _discover_announcement_navigation_seed_urls(school_name, seed_candidates)
    return _filter_candidate_urls_for_families(
        [*navigation_seed_urls, *seed_candidates, *search_seed_urls],
        families={"notice", "admissions"},
        deny_prefixes=deny_prefixes,
        max_items=12,
    )


def _resolve_preferred_announcement_hosts(
    candidate_urls: list[str],
    *,
    announcement_override: dict[str, Any] | None,
) -> set[str]:
    override_hosts = _announcement_override_hosts(announcement_override)
    if override_hosts:
        return override_hosts

    host_scores: dict[str, list[int]] = {}
    for candidate_url in candidate_urls:
        host = portal_candidate_host(candidate_url)
        if not host:
            continue
        host_scores.setdefault(host, []).append(_score_candidate_url(candidate_url))

    if not host_scores:
        return set()

    ordered_hosts = sorted(
        host_scores.items(),
        key=lambda item: (-max(item[1]), -len(item[1]), item[0]),
    )
    top_host, top_scores = ordered_hosts[0]
    top_score = max(top_scores)
    next_best_score = max((max(scores) for host, scores in ordered_hosts[1:]), default=0)

    if len(top_scores) >= 2:
        return {top_host}
    if top_score >= 30 and top_score - next_best_score >= 8:
        return {top_host}
    return set()


def _load_announcement_portal_cache(
    db: Session,
    *,
    school_name: str,
    families: set[str],
    deny_prefixes: list[str],
) -> tuple[list[str], set[str], bool]:
    families_key = _families_key(families)
    if families != {"notice", "admissions"} or not families_key:
        return [], set(), False

    cache = (
        db.query(AnnouncementPortalCache)
        .filter(
            AnnouncementPortalCache.school_name == school_name.strip(),
            AnnouncementPortalCache.families_key == families_key,
        )
        .order_by(AnnouncementPortalCache.last_verified_at.desc())
        .first()
    )
    if cache is None:
        return [], set(), False

    verified_at = _coerce_utc(cache.last_verified_at)
    if verified_at is None or verified_at + _ANNOUNCEMENT_PORTAL_CACHE_TTL <= utcnow():
        return [], set(), False

    preferred_hosts = {
        str(host or "").strip().lower()
        for host in (cache.preferred_hosts or [])
        if str(host or "").strip()
    }
    candidate_urls = _filter_candidate_urls_for_families(
        list(cache.candidate_urls or []),
        families=families,
        deny_prefixes=deny_prefixes,
        preferred_hosts=preferred_hosts,
        max_items=12,
    )
    if not candidate_urls:
        return [], set(), False

    candidate_hosts = portal_candidate_hosts(candidate_urls)
    if preferred_hosts:
        preferred_hosts &= candidate_hosts
    if not preferred_hosts:
        preferred_hosts = _resolve_preferred_announcement_hosts(candidate_urls, announcement_override=None)
    return candidate_urls, preferred_hosts, True


def _persist_announcement_portal_cache(
    db: Session,
    *,
    school_name: str,
    families: set[str],
    candidate_urls: list[str],
    preferred_hosts: set[str],
):
    families_key = _families_key(families)
    normalized_school_name = school_name.strip()
    if families != {"notice", "admissions"} or not normalized_school_name or not families_key:
        return

    normalized_preferred_hosts = {
        str(host or "").strip().lower()
        for host in preferred_hosts
        if str(host or "").strip()
    }
    normalized_candidate_urls = _filter_candidate_urls_for_families(
        list(candidate_urls),
        families=families,
        preferred_hosts=normalized_preferred_hosts,
        max_items=12,
    )
    if not normalized_candidate_urls:
        return

    if not normalized_preferred_hosts:
        normalized_preferred_hosts = _resolve_preferred_announcement_hosts(
            normalized_candidate_urls,
            announcement_override=None,
        )

    cache = (
        db.query(AnnouncementPortalCache)
        .filter(
            AnnouncementPortalCache.school_name == normalized_school_name,
            AnnouncementPortalCache.families_key == families_key,
        )
        .one_or_none()
    )
    if cache is None:
        cache = AnnouncementPortalCache(
            school_name=normalized_school_name,
            families_key=families_key,
        )
    cache.candidate_urls = normalized_candidate_urls
    cache.preferred_hosts = sorted(normalized_preferred_hosts)
    cache.last_verified_at = utcnow()
    db.add(cache)


def _build_announcement_seed_urls(
    candidate_urls: list[str],
    *,
    recovery_seed_urls: list[str],
    deny_prefixes: list[str],
    preferred_hosts: set[str],
) -> list[str]:
    preferred_candidate_urls = _filter_candidate_urls_for_families(
        list(candidate_urls),
        families={"notice", "admissions"},
        deny_prefixes=deny_prefixes,
        preferred_hosts=preferred_hosts,
        max_items=12,
    )
    recovery_urls = _filter_candidate_urls_for_families(
        list(recovery_seed_urls),
        families={"notice", "admissions"},
        deny_prefixes=deny_prefixes,
        max_items=12,
    )
    return _dedupe_texts([*preferred_candidate_urls, *recovery_urls])[:12]


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


def _resolve_bootstrap_entrypoint(
    seed_urls: list[str],
    expanded_seed_urls: list[str],
    *,
    preferred_hosts: set[str] | None = None,
) -> tuple[str, list[str]]:
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


def _section_has_announcement_channel_metadata(section: SiteSection) -> bool:
    config = dict(section.list_selector_config or {})
    return any(
        str(config.get(key) or "").strip()
        for key in ("portal_scope", "portal_entry_url", "channel_label", "channel_tier")
    )


def _section_path_looks_homepage_like(section: SiteSection) -> bool:
    path = (urlparse(str(section.section_url or "")).path or "").strip().lower()
    return path in _HOMEPAGE_LIKE_SECTION_PATHS


def _section_is_structured_school_announcement_section(section: SiteSection) -> bool:
    if _section_has_announcement_channel_metadata(section):
        return True
    if _section_path_looks_homepage_like(section):
        return False
    url = str(section.section_url or "").strip()
    if not url:
        return False
    if _looks_like_detail_section_url(url):
        return False
    if _looks_like_channel_prefix_page(url):
        return False
    if _looks_like_fragmentary_seed_url(url):
        return False
    return True


def _select_reusable_sections_for_families(
    sections: list[SiteSection],
    *,
    families: set[str],
) -> list[SiteSection]:
    if families != {"notice", "admissions"}:
        return sections
    structured = [section for section in sections if _section_is_structured_school_announcement_section(section)]
    return structured


def _resolve_announcement_preferred_hosts(
    db: Session,
    *,
    school_name: str,
    families: set[str],
    deny_prefixes: list[str],
    announcement_override: dict[str, Any] | None,
    existing_sections: list[SiteSection],
) -> tuple[set[str], list[str], bool]:
    cached_candidate_urls: list[str] = []
    cached_preferred_hosts: set[str] = set()
    cache_hit = False
    if families == {"notice", "admissions"} and announcement_override is None:
        cached_candidate_urls, cached_preferred_hosts, cache_hit = _load_announcement_portal_cache(
            db,
            school_name=school_name,
            families=families,
            deny_prefixes=deny_prefixes,
        )
    if cache_hit:
        return cached_preferred_hosts, cached_candidate_urls, True
    announcement_candidate_urls = (
        _build_announcement_candidate_pool(
            school_name,
            announcement_override=announcement_override,
            deny_prefixes=deny_prefixes,
            allow_search=not (
                announcement_override is None
                and existing_sections
                and len(
                    {
                        portal_candidate_host(section.section_url)
                        for section in existing_sections
                        if portal_candidate_host(section.section_url)
                    }
                )
                <= 1
            ),
        )
        if families == {"notice", "admissions"}
        else []
    )
    preferred_hosts = (
        _resolve_preferred_announcement_hosts(
            announcement_candidate_urls,
            announcement_override=announcement_override,
        )
        if families == {"notice", "admissions"}
        else set()
    )
    return preferred_hosts, announcement_candidate_urls, False


def announcement_search_requires_asset_upgrade(db: Session, school_name: str) -> bool:
    normalized_school_name = str(school_name or "").strip()
    if not normalized_school_name:
        return False
    families = {"notice", "admissions"}
    announcement_override = _resolve_announcement_seed_override(normalized_school_name)
    deny_prefixes = [
        str(prefix or "").strip()
        for prefix in (announcement_override or {}).get("deny_prefixes") or []
        if str(prefix or "").strip()
    ]
    _school, existing_sections = _load_existing_school_sections(
        db,
        school_name=normalized_school_name,
        deny_prefixes=deny_prefixes,
    )
    raw_reusable_sections = _collect_reusable_sections(
        db,
        existing_sections=existing_sections,
        families=families,
    )
    if not raw_reusable_sections:
        return False
    preferred_hosts, _candidate_urls, _cache_hit = _resolve_announcement_preferred_hosts(
        db,
        school_name=normalized_school_name,
        families=families,
        deny_prefixes=deny_prefixes,
        announcement_override=announcement_override,
        existing_sections=raw_reusable_sections,
    )
    preferred_sections = _filter_existing_sections_for_preferred_hosts(
        raw_reusable_sections,
        families=families,
        preferred_hosts=preferred_hosts,
    )
    if preferred_hosts and not preferred_sections:
        return True
    target_sections = preferred_sections or raw_reusable_sections
    structured_sections = _select_reusable_sections_for_families(target_sections, families=families)
    return not structured_sections


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


def _queue_existing_section_jobs(
    db: Session,
    *,
    school_name: str,
    sections: list[SiteSection],
    bootstrap_origin: str,
) -> list[str]:
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
                "bootstrap_origin": bootstrap_origin,
            },
        )
        db.add(job)
        db.flush()
        job_ids.append(job.id)

    db.commit()
    return job_ids


def _discovery_category_for_families(families: set[str]) -> str:
    return "adjustment" if families == {"adjustment"} else "announcement"


def _bootstrap_origin_for_families(families: set[str]) -> str:
    return "adjustment_search" if families == {"adjustment"} else "announcement_search"


def _load_existing_school_sections(
    db: Session,
    *,
    school_name: str,
    deny_prefixes: list[str],
) -> tuple[School | None, list[SiteSection]]:
    school = db.query(School).filter(School.name == school_name).one_or_none()
    if school is None:
        return None, []
    existing_sections = (
        db.query(SiteSection)
        .filter(SiteSection.school_id == school.id, SiteSection.enabled == 1)
        .order_by(SiteSection.created_at.asc())
        .all()
    )
    if deny_prefixes:
        existing_sections = [
            section
            for section in existing_sections
            if not any(str(section.section_url or "").startswith(prefix) for prefix in deny_prefixes)
        ]
    return school, existing_sections


def _collect_reusable_sections(
    db: Session,
    *,
    existing_sections: list[SiteSection],
    families: set[str],
) -> list[SiteSection]:
    reusable_sections = [section for section in existing_sections if _section_is_compatible_for_families(section, families)]
    if not existing_sections:
        return reusable_sections

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
        if _section_is_compatible_for_families(section, families)
        and not (_looks_like_detail_section_url(section.section_url) and int(link_counts.get(section.id, 0) or 0) == 0)
    ]
    return reusable_sections


def _collect_recovery_seed_urls(existing_sections: list[SiteSection]) -> list[str]:
    recovery_seed_urls: list[str] = []
    for section in existing_sections:
        recovery_seed_urls.extend(_derive_recovery_seed_urls_from_section_url(section.section_url))
    return _dedupe_texts(recovery_seed_urls)


def _build_local_candidate_hints(
    school_name: str,
    *,
    families: set[str],
    deny_prefixes: list[str],
    recovery_seed_urls: list[str],
    announcement_candidate_urls: list[str] | None = None,
    preferred_hosts: set[str] | None = None,
) -> list[str]:
    hints: list[str] = []
    if families == {"notice", "admissions"}:
        hints.extend(list(announcement_candidate_urls or []))
        if preferred_hosts:
            hints.extend(
                url
                for url in recovery_seed_urls
                if portal_candidate_host(url) in preferred_hosts
            )
        else:
            hints.extend(recovery_seed_urls)
    else:
        hints.extend(_discover_seed_urls_from_docs(school_name))
        hints.extend(recovery_seed_urls)
    return _filter_candidate_urls_for_families(
        hints,
        families=families,
        deny_prefixes=deny_prefixes,
        preferred_hosts=preferred_hosts,
    )


def _queue_family_discovery_job(
    db: Session,
    *,
    school_name: str,
    families: set[str],
    candidate_urls: list[str],
    bootstrap_origin: str,
    homepage_url: str | None = None,
    seed_urls: list[str] | None = None,
    workflow_handoff: str | None = None,
) -> CrawlJob:
    normalized_seed_urls = _dedupe_texts([str(url or "").strip() for url in (seed_urls or []) if str(url or "").strip()])
    job = CrawlJob(
        category=_discovery_category_for_families(families),
        status="pending",
        requested_at=utcnow(),
        message=f"queued family discovery for {school_name.strip()}",
        query={
            "job_kind": "family_discovery",
            "school_name": school_name.strip(),
            "families": sorted(families),
            "bootstrap_origin": bootstrap_origin,
            "candidate_urls": list(candidate_urls),
            "homepage_url": str(homepage_url or "").strip() or None,
            "seed_urls": normalized_seed_urls,
            "workflow_handoff": str(workflow_handoff or "").strip() or None,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _build_no_candidate_response(
    school_name: str,
    *,
    message: str,
    candidate_urls: list[str],
) -> dict[str, Any]:
    return {
        "state": "no_candidate",
        "school_name": school_name,
        "message": message,
        "candidate_urls": candidate_urls,
        "job_ids": [],
    }


def _completed_family_discovery_response(
    school_name: str,
    *,
    job: CrawlJob,
    candidate_urls: list[str],
) -> dict[str, Any]:
    result_state = _job_result_state(job)
    if result_state == "failed" or job.status == "failed":
        return _build_no_candidate_response(
            school_name,
            message=f"{school_name} 的陌生院校冷启动刚执行过一次，但本轮执行失败，请稍后再试。",
            candidate_urls=candidate_urls,
        )
    return _build_no_candidate_response(
        school_name,
        message=f"系统刚完成一次 {school_name} 的官网探测，但还没定位到稳定栏目，请稍后再试。",
        candidate_urls=candidate_urls,
    )


def _resolve_seed_urls_for_family_discovery(
    school_name: str,
    *,
    families: set[str],
    deny_prefixes: list[str],
    recovery_seed_urls: list[str],
    announcement_candidate_urls: list[str] | None = None,
    preferred_hosts: set[str] | None = None,
) -> list[str]:
    if families == {"notice", "admissions"}:
        return _build_announcement_seed_urls(
            list(announcement_candidate_urls or []),
            recovery_seed_urls=recovery_seed_urls,
            deny_prefixes=deny_prefixes,
            preferred_hosts=preferred_hosts or set(),
        )

    seed_urls = _discover_seed_urls_from_docs(school_name)
    if deny_prefixes:
        seed_urls = [url for url in seed_urls if not any(url.startswith(prefix) for prefix in deny_prefixes)]
    if not seed_urls:
        search_seed_urls = _discover_seed_urls_from_search(school_name)
        if deny_prefixes:
            search_seed_urls = [url for url in search_seed_urls if not any(url.startswith(prefix) for prefix in deny_prefixes)]
        seed_urls = _dedupe_texts(search_seed_urls)
    return _dedupe_texts([*seed_urls, *recovery_seed_urls])


def _resolve_v2_family_handoff_inputs(
    school_name: str,
    *,
    families: set[str],
    query: dict[str, Any],
) -> tuple[str | None, list[str]]:
    homepage_url = _normalize_url(str(query.get("homepage_url") or ""))
    seed_urls = _dedupe_texts(
        [
            _normalize_url(str(url or ""))
            for url in (query.get("seed_urls") or [])
            if _normalize_url(str(url or ""))
        ]
    )
    if not homepage_url and seed_urls:
        homepage_url = seed_urls[0]

    if families == {"notice", "admissions"}:
        override = _resolve_announcement_seed_override(school_name) or {}
        override_homepage = _normalize_url(str(override.get("homepage_url") or ""))
        override_seed_urls = _dedupe_texts(
            [
                _normalize_url(str(url or ""))
                for url in (override.get("seed_urls") or [])
                if _normalize_url(str(url or ""))
            ]
        )
        if not homepage_url and override_homepage:
            homepage_url = override_homepage
        if override_seed_urls:
            seed_urls = _dedupe_texts([*seed_urls, *override_seed_urls])

    doc_seed_urls = _dedupe_texts(_load_school_seed_map().get(school_name, []))
    if doc_seed_urls:
        seed_urls = _dedupe_texts([*seed_urls, *doc_seed_urls])
        if not homepage_url:
            homepage_url = doc_seed_urls[0]

    if homepage_url and homepage_url not in seed_urls:
        seed_urls = _dedupe_texts([homepage_url, *seed_urls])
    return (homepage_url or None), seed_urls


def _handoff_family_discovery_job_to_v2(
    db: Session,
    *,
    job: CrawlJob,
    school_name: str,
    families: set[str],
    query: dict[str, Any],
) -> tuple[None, str]:
    homepage_url, seed_urls = _resolve_v2_family_handoff_inputs(
        school_name,
        families=families,
        query=query,
    )
    next_query = dict(job.query or {})
    next_query["families"] = sorted(families)
    next_query["workflow_handoff"] = "v2"
    next_query["workflow_scope_type"] = "school"

    if not homepage_url:
        next_query["result_state"] = "no_candidate"
        next_query["result_candidate_urls"] = []
        next_query["result_job_ids"] = []
        job.query = next_query
        return None, f"family discovery handoff skipped: explicit seeds missing for {school_name}"

    run, step = create_scope_rebuild_run(
        db,
        scope_type="school",
        school_name=school_name,
        homepage_url=homepage_url,
        seed_urls=seed_urls,
        actor_username=None,
        families=families,
        max_sections=max(1, int(query.get("max_sections") or 12)),
    )
    next_query["homepage_url"] = homepage_url
    next_query["seed_urls"] = seed_urls
    next_query["result_state"] = "workflow_handoff"
    next_query["result_candidate_urls"] = seed_urls
    next_query["result_job_ids"] = [run.id]
    next_query["workflow_run_id"] = run.id
    next_query["workflow_step_id"] = step.id
    job.query = next_query
    return None, f"family discovery handed off to crawler v2 workflow {run.id}"


def _bootstrap_family_sections(
    db: Session,
    *,
    school_name: str,
    families: set[str],
    bootstrap_origin: str,
) -> dict[str, Any]:
    announcement_override = _resolve_announcement_seed_override(school_name) if families == {"notice", "admissions"} else None
    deny_prefixes = [
        str(prefix or "").strip()
        for prefix in (announcement_override or {}).get("deny_prefixes") or []
        if str(prefix or "").strip()
    ]
    _school, existing_sections = _load_existing_school_sections(
        db,
        school_name=school_name,
        deny_prefixes=deny_prefixes,
    )
    preliminary_reusable_sections = _select_reusable_sections_for_families(
        _collect_reusable_sections(
            db,
            existing_sections=existing_sections,
            families=families,
        ),
        families=families,
    )
    cached_candidate_urls: list[str] = []
    cached_preferred_hosts: set[str] = set()
    cache_hit = False
    if families == {"notice", "admissions"} and announcement_override is None:
        cached_candidate_urls, cached_preferred_hosts, cache_hit = _load_announcement_portal_cache(
            db,
            school_name=school_name,
            families=families,
            deny_prefixes=deny_prefixes,
        )
    announcement_candidate_urls = (
        cached_candidate_urls
        if cache_hit
        else (
            _build_announcement_candidate_pool(
                school_name,
                announcement_override=announcement_override,
                deny_prefixes=deny_prefixes,
                allow_search=not (
                    announcement_override is None
                    and preliminary_reusable_sections
                    and len(
                        {
                            portal_candidate_host(section.section_url)
                            for section in preliminary_reusable_sections
                            if portal_candidate_host(section.section_url)
                        }
                    )
                    <= 1
                ),
            )
            if families == {"notice", "admissions"}
            else []
        )
    )
    preferred_hosts = (
        cached_preferred_hosts
        if cache_hit
        else (
            _resolve_preferred_announcement_hosts(
                announcement_candidate_urls,
                announcement_override=announcement_override,
            )
            if families == {"notice", "admissions"}
            else set()
        )
    )
    if families == {"notice", "admissions"} and announcement_override is None and announcement_candidate_urls and not cache_hit:
        _persist_announcement_portal_cache(
            db,
            school_name=school_name,
            families=families,
            candidate_urls=announcement_candidate_urls,
            preferred_hosts=preferred_hosts,
        )
    recovery_seed_urls = _collect_recovery_seed_urls(existing_sections)
    existing_sections = _filter_existing_sections_for_preferred_hosts(
        existing_sections,
        families=families,
        preferred_hosts=preferred_hosts,
    )
    reusable_sections = _select_reusable_sections_for_families(
        _collect_reusable_sections(
            db,
            existing_sections=existing_sections,
            families=families,
        ),
        families=families,
    )

    if reusable_sections:
        section_ids = {section.id for section in reusable_sections}
        pending_jobs = _find_pending_discovery_jobs(db, school_name, section_ids)
        if pending_jobs:
            return {
                "state": "queued",
                "school_name": school_name,
                "message": f"已自动启动 {school_name} 的栏目补抓，正在拉取官网栏目，请稍后自动刷新。",
                "candidate_urls": _dedupe_texts([section.section_url for section in reusable_sections[:5]]),
                "job_ids": [job.id for job in pending_jobs],
            }
        job_ids = _queue_existing_section_jobs(
            db,
            school_name=school_name,
            sections=reusable_sections,
            bootstrap_origin=bootstrap_origin,
        )
        return {
            "state": "queued",
            "school_name": school_name,
            "message": f"已发现 {school_name} 的现有栏目资产，正在补抓最新内容，请稍后自动刷新。",
            "candidate_urls": _dedupe_texts([section.section_url for section in reusable_sections[:5]]),
            "job_ids": job_ids,
        }

    seed_urls = _resolve_seed_urls_for_family_discovery(
        school_name,
        families=families,
        deny_prefixes=deny_prefixes,
        recovery_seed_urls=recovery_seed_urls,
        announcement_candidate_urls=announcement_candidate_urls,
        preferred_hosts=preferred_hosts,
    )
    expanded_seed_urls = _expand_seed_urls(seed_urls)
    if "adjustment" in families:
        expanded_seed_urls = _dedupe_texts([*expanded_seed_urls, *_discover_department_seed_urls(expanded_seed_urls or seed_urls)])

    if not expanded_seed_urls:
        return {
            "state": "no_candidate",
            "school_name": school_name,
            "message": f"系统还没定位到 {school_name} 的官网候选，当前无法自动补抓这所学校的栏目。",
            "candidate_urls": [],
            "job_ids": [],
        }

    homepage_url, extra_seed_urls = _resolve_bootstrap_entrypoint(
        seed_urls,
        expanded_seed_urls,
        preferred_hosts=preferred_hosts,
    )
    if announcement_override:
        homepage_url = str(announcement_override.get("homepage_url") or homepage_url or "").strip() or homepage_url
    result = bootstrap_site_sections(
        db,
        school_name=school_name,
        homepage_url=homepage_url,
        department_name=None,
        department_type="graduate_school",
        seed_urls=extra_seed_urls,
        enabled=True,
        queue_discovery=True,
        max_sections=8,
        families=families,
        portal_entry_url=homepage_url if families == {"notice", "admissions"} else None,
        portal_scope=PORTAL_SCOPE_GRADUATE_ADMISSIONS if families == {"notice", "admissions"} else None,
        preferred_hosts=preferred_hosts,
    )
    job_ids = list(result.get("job_ids") or [])
    visible_sections = [
        section
        for section in list(result.get("items") or [])
        if isinstance(section, SiteSection) and _section_is_compatible_for_families(section, families)
    ]
    candidate_urls = _filter_candidate_urls_for_families(
        _dedupe_texts(
            [section.section_url for section in visible_sections]
            if visible_sections
            else list(result.get("candidate_urls") or expanded_seed_urls[:5])
        ),
        families=families,
        deny_prefixes=deny_prefixes,
        preferred_hosts=preferred_hosts,
    )
    if not job_ids and not candidate_urls:
        return {
            "state": "empty",
            "school_name": school_name,
            "message": f"已完成 {school_name} 的官网探测，但还没定位到稳定栏目。",
            "candidate_urls": [],
            "job_ids": [],
        }
    return {
        "state": "queued" if job_ids else "empty",
        "school_name": school_name,
        "message": f"已自动为 {school_name} 启动陌生院校冷启动，正在发现官网栏目并补抓内容，请稍后自动刷新。",
        "candidate_urls": candidate_urls,
        "job_ids": job_ids,
    }


def run_family_discovery_job(db: Session, job: CrawlJob, query: dict[str, Any]) -> tuple[None, str]:
    school_name = str(query.get("school_name") or "").strip()
    families = {
        str(item or "").strip()
        for item in (query.get("families") or [])
        if str(item or "").strip() in _KNOWN_FAMILIES
    }
    if not school_name or not families:
        raise ValueError("family discovery job requires school_name and families")

    if str(query.get("workflow_handoff") or "").strip().lower() == "v2":
        return _handoff_family_discovery_job_to_v2(
            db,
            job=job,
            school_name=school_name,
            families=families,
            query=query,
        )

    result = _bootstrap_family_sections(
        db,
        school_name=school_name,
        families=families,
        bootstrap_origin=str(query.get("bootstrap_origin") or "family_discovery").strip() or "family_discovery",
    )
    next_query = dict(job.query or {})
    next_query["families"] = sorted(families)
    next_query["result_state"] = result.get("state")
    next_query["result_candidate_urls"] = list(result.get("candidate_urls") or [])
    next_query["result_job_ids"] = list(result.get("job_ids") or [])
    if not next_query.get("candidate_urls"):
        next_query["candidate_urls"] = list(result.get("candidate_urls") or [])
    job.query = next_query
    return None, str(result.get("message") or "family discovery finished")


def ensure_family_search_bootstrap(db: Session, school_name: str, families: set[str]) -> dict[str, Any] | None:
    normalized_school_name = str(school_name or "").strip()
    if not normalized_school_name:
        return None
    normalized_families = {family for family in families if family in _KNOWN_FAMILIES}
    if not normalized_families:
        return None
    announcement_override = (
        _resolve_announcement_seed_override(normalized_school_name)
        if normalized_families == {"notice", "admissions"}
        else None
    )
    deny_prefixes = [str(prefix or "").strip() for prefix in (announcement_override or {}).get("deny_prefixes") or [] if str(prefix or "").strip()]
    _school, existing_sections = _load_existing_school_sections(
        db,
        school_name=normalized_school_name,
        deny_prefixes=deny_prefixes,
    )
    preliminary_reusable_sections = _select_reusable_sections_for_families(
        _collect_reusable_sections(
            db,
            existing_sections=existing_sections,
            families=normalized_families,
        ),
        families=normalized_families,
    )
    preferred_hosts, announcement_candidate_urls, cache_hit = _resolve_announcement_preferred_hosts(
        db,
        school_name=normalized_school_name,
        families=normalized_families,
        deny_prefixes=deny_prefixes,
        announcement_override=announcement_override,
        existing_sections=preliminary_reusable_sections,
    )
    recovery_seed_urls = _collect_recovery_seed_urls(existing_sections)
    existing_sections = _filter_existing_sections_for_preferred_hosts(
        existing_sections,
        families=normalized_families,
        preferred_hosts=preferred_hosts,
    )
    reusable_sections = _select_reusable_sections_for_families(
        _collect_reusable_sections(
            db,
            existing_sections=existing_sections,
            families=normalized_families,
        ),
        families=normalized_families,
    )
    local_candidate_hints = _build_local_candidate_hints(
        normalized_school_name,
        families=normalized_families,
        deny_prefixes=deny_prefixes,
        recovery_seed_urls=recovery_seed_urls,
        announcement_candidate_urls=announcement_candidate_urls,
        preferred_hosts=preferred_hosts,
    )
    v2_homepage_url, v2_seed_urls = _resolve_v2_family_handoff_inputs(
        normalized_school_name,
        families=normalized_families,
        query={},
    )
    bootstrap_origin = _bootstrap_origin_for_families(normalized_families)

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

        job_ids = _queue_existing_section_jobs(
            db,
            school_name=normalized_school_name,
            sections=reusable_sections,
            bootstrap_origin=bootstrap_origin,
        )
        return {
            "state": "queued",
            "school_name": normalized_school_name,
            "message": f"已发现 {normalized_school_name} 的现有栏目资产，正在补抓最新内容，请稍后自动刷新。",
            "candidate_urls": _dedupe_texts([section.section_url for section in reusable_sections[:5]]),
            "job_ids": job_ids,
        }

    active_job = _latest_family_discovery_job(
        db,
        school_name=normalized_school_name,
        families=normalized_families,
        statuses={"pending", "running"},
    )
    if active_job is not None:
        return {
            "state": "in_progress",
            "school_name": normalized_school_name,
            "message": f"已自动为 {normalized_school_name} 启动陌生院校冷启动，正在发现官网栏目并补抓内容，请稍后自动刷新。",
            "candidate_urls": _job_candidate_urls(active_job) or local_candidate_hints,
            "job_ids": [active_job.id],
        }

    latest_job = _latest_family_discovery_job(
        db,
        school_name=normalized_school_name,
        families=normalized_families,
        statuses={"done", "failed"},
    )
    if latest_job is not None:
        latest_finished_at = _coerce_utc(latest_job.finished_at or latest_job.updated_at or latest_job.requested_at)
        cooldown_deadline = (latest_finished_at or utcnow()) + _FAMILY_DISCOVERY_COOLDOWN
        if cooldown_deadline > utcnow():
            if _job_result_state(latest_job) in {"empty", "no_candidate", "failed"} or latest_job.status == "failed":
                candidate_urls = _job_candidate_urls(latest_job) or local_candidate_hints
                return _completed_family_discovery_response(
                    normalized_school_name,
                    job=latest_job,
                    candidate_urls=candidate_urls,
                )

    queued_job = _queue_family_discovery_job(
        db,
        school_name=normalized_school_name,
        families=normalized_families,
        candidate_urls=local_candidate_hints,
        bootstrap_origin=bootstrap_origin,
        homepage_url=v2_homepage_url,
        seed_urls=v2_seed_urls,
        workflow_handoff="v2" if v2_homepage_url else None,
    )
    return {
        "state": "queued",
        "school_name": normalized_school_name,
        "message": f"已自动为 {normalized_school_name} 启动陌生院校冷启动，正在发现官网栏目并补抓内容，请稍后自动刷新。",
        "candidate_urls": local_candidate_hints or v2_seed_urls,
        "job_ids": [queued_job.id],
    }


def ensure_announcement_search_bootstrap(db: Session, school_name: str) -> dict[str, Any] | None:
    return ensure_family_search_bootstrap(db, school_name, {"notice", "admissions"})


def ensure_adjustment_search_bootstrap(db: Session, school_name: str) -> dict[str, Any] | None:
    return ensure_family_search_bootstrap(db, school_name, {"adjustment"})
