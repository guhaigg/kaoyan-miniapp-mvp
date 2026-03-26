from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import httpx
from lxml import html

from ..models import sha256_hex, utcnow

ANNOUNCEMENT_FOUNDATION_SCOPE_KEY = "announcement-foundation"
DEFAULT_FOUNDATION_SOURCES = ("chsi", "official_rosters", "school_homepages")
CHSI_SCHOOL_CATALOG_URL = "https://yz.chsi.com.cn/sch/"
SCHOOL_HOMEPAGE_SOURCE_URL = (
    "https://raw.githubusercontent.com/lcandy2/Chinese-Universities-with-Website/main/chinese_universities_with_website.json"
)
OFFICIAL_SEED_ROSTER_SOURCES: tuple[dict[str, str], ...] = (
    {
        "source_key": "zhejiang_2025_roster",
        "source_url": "https://yz.chsi.com.cn/kyzx/kydt/202410/20241015/2293344059.html",
        "source_label": "Zhejiang 2025 graduate admission roster",
    },
)
SCHOOL_CATALOG_FILENAME = "school_catalog_snapshot.json"
DEPARTMENT_CATALOG_FILENAME = "department_catalog_snapshot.json"
MAJOR_CATALOG_FILENAME = "major_catalog_snapshot.json"
ANNOUNCEMENT_SEED_REGISTRY_FILENAME = "announcement_seed_registry.json"
ANNOUNCEMENT_SCHOOL_HOMEPAGES_FILENAME = "announcement_school_homepages.json"
ANNOUNCEMENT_OFFICIAL_SEED_CANDIDATES_FILENAME = "announcement_official_seed_candidates.json"
ANNOUNCEMENT_DEPARTMENT_CANDIDATES_FILENAME = "announcement_department_seed_candidates.json"
ANNOUNCEMENT_DEPARTMENT_OVERRIDES_FILENAME = "announcement_department_seed_overrides.json"
ANNOUNCEMENT_SEED_DIFF_FILENAME = "announcement_seed_registry_diff.json"
SCHOOL_DETAIL_LIKE_TEXT = re.compile(r"(研究生招生|招生信息网|研招|招生网|硕士招生|博士招生)")
DEPARTMENT_NAME_RE = re.compile(r"(学院|研究院|研究所|学部|中心|系|部|书院)$")
MAJOR_LINE_RE = re.compile(r"^\*?\s*(?P<name>.+?)\[(?P<code>[A-Za-z0-9]+)\]\s*$")


@dataclass(frozen=True)
class FoundationPaths:
    base_dir: Path
    school_catalog: Path
    department_catalog: Path
    major_catalog: Path
    school_homepages: Path
    official_seed_candidates: Path
    department_candidates: Path
    department_overrides: Path
    seed_registry: Path
    seed_diff: Path


def _foundation_base_dir(base_dir: str | Path | None = None) -> Path:
    if base_dir is not None:
        return Path(base_dir).resolve()
    env_value = os.getenv("ANNOUNCEMENT_FOUNDATION_DATA_DIR", "").strip()
    if env_value:
        return Path(env_value).resolve()
    return Path(__file__).resolve().parents[3] / "docs" / "data"


def foundation_paths(base_dir: str | Path | None = None) -> FoundationPaths:
    root = _foundation_base_dir(base_dir)
    return FoundationPaths(
        base_dir=root,
        school_catalog=root / SCHOOL_CATALOG_FILENAME,
        department_catalog=root / DEPARTMENT_CATALOG_FILENAME,
        major_catalog=root / MAJOR_CATALOG_FILENAME,
        school_homepages=root / ANNOUNCEMENT_SCHOOL_HOMEPAGES_FILENAME,
        official_seed_candidates=root / ANNOUNCEMENT_OFFICIAL_SEED_CANDIDATES_FILENAME,
        department_candidates=root / ANNOUNCEMENT_DEPARTMENT_CANDIDATES_FILENAME,
        department_overrides=root / ANNOUNCEMENT_DEPARTMENT_OVERRIDES_FILENAME,
        seed_registry=root / ANNOUNCEMENT_SEED_REGISTRY_FILENAME,
        seed_diff=root / ANNOUNCEMENT_SEED_DIFF_FILENAME,
    )


def _normalize_url(url: str | None) -> str:
    return str(url or "").strip().split("#", 1)[0]


def _dedupe_texts(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw_value in values:
        value = _normalize_url(raw_value)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_school_name(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def normalize_department_name(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _read_json(path: Path, *, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def load_announcement_seed_registry(base_dir: str | Path | None = None) -> list[dict[str, Any]]:
    return list(_read_json(foundation_paths(base_dir).seed_registry, default=[]))


def load_department_seed_overrides(base_dir: str | Path | None = None) -> list[dict[str, Any]]:
    return list(_read_json(foundation_paths(base_dir).department_overrides, default=[]))


def _fetch_text(url: str, *, timeout: int = 20) -> str:
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    return response.text


def _fetch_json(url: str, *, timeout: int = 20) -> Any:
    response = httpx.get(url, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.json()


def _squash_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _page_count_from_catalog(doc: html.HtmlElement) -> int:
    page_numbers = [
        int(text)
        for text in (
            _squash_text(anchor.text_content())
            for anchor in doc.xpath("//a[normalize-space()]")
        )
        if text.isdigit()
    ]
    return max(page_numbers) if page_numbers else 1


def _parse_school_catalog_page(page_url: str, html_text: str) -> tuple[list[dict[str, Any]], int]:
    doc = html.fromstring(html_text)
    entries: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for anchor in doc.xpath("//a[contains(@href,'/sch/schoolInfo--schId-')]"):
        school_name = _squash_text(anchor.text_content())
        detail_url = urljoin(page_url, anchor.get("href") or "")
        if not school_name or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        container = anchor
        for _ in range(4):
            if container is None:
                break
            text = _squash_text(container.text_content())
            if "主管部门" in text:
                break
            container = container.getparent()
        container_text = _squash_text(container.text_content() if container is not None else "")
        province_match = re.search(r"([^\s：]+)\s+主管部门", container_text)
        chsi_school_id_match = re.search(r"schId-([0-9]+)", detail_url)
        entries.append(
            {
                "school_code": chsi_school_id_match.group(1) if chsi_school_id_match else sha256_hex(school_name)[:12],
                "school_name": school_name,
                "aliases": [],
                "province": province_match.group(1) if province_match else None,
                "official_homepage": None,
                "chsi_school_url": detail_url,
                "source_meta": {
                    "source_type": "chsi_school_catalog",
                    "detail_url": detail_url,
                    "catalog_page_url": page_url,
                    "catalog_context": container_text[:500],
                    "catalog_page_count": _page_count_from_catalog(doc),
                },
            }
        )
    return entries, _page_count_from_catalog(doc)


def fetch_chsi_school_catalog(*, school_names: list[str] | None = None) -> list[dict[str, Any]]:
    requested_names = {normalize_school_name(name) for name in (school_names or []) if normalize_school_name(name)}
    first_page = _fetch_text(CHSI_SCHOOL_CATALOG_URL)
    entries, page_count = _parse_school_catalog_page(CHSI_SCHOOL_CATALOG_URL, first_page)
    for page_number in range(2, page_count + 1):
        start = (page_number - 1) * 20
        page_url = f"{CHSI_SCHOOL_CATALOG_URL}?start={start}"
        page_entries, _ = _parse_school_catalog_page(page_url, _fetch_text(page_url))
        entries.extend(page_entries)
    deduped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = normalize_school_name(entry["school_name"])
        if requested_names and key not in requested_names:
            continue
        deduped[key] = entry
    return list(deduped.values())


def _external_links_from_page(page_url: str, html_text: str) -> list[str]:
    doc = html.fromstring(html_text)
    urls: list[str] = []
    for anchor in doc.xpath("//a[@href]"):
        href = urljoin(page_url, anchor.get("href") or "")
        host = urlparse(href).hostname or ""
        if href and not host.endswith("chsi.com.cn"):
            urls.append(href)
    return _dedupe_texts(urls)


def _extract_seed_hint_urls(detail_doc: html.HtmlElement, detail_url: str) -> list[str]:
    urls: list[str] = []
    for anchor in detail_doc.xpath("//a[@href]"):
        text = _squash_text(anchor.text_content())
        href = urljoin(detail_url, anchor.get("href") or "")
        host = urlparse(href).hostname or ""
        if not href or host.endswith("chsi.com.cn"):
            if SCHOOL_DETAIL_LIKE_TEXT.search(text) and href:
                try:
                    urls.extend(_external_links_from_page(href, _fetch_text(href)))
                except Exception:
                    continue
            continue
        if SCHOOL_DETAIL_LIKE_TEXT.search(text):
            urls.append(href)
    return _dedupe_texts(urls)


def _category_page_url(detail_doc: html.HtmlElement, detail_url: str, label: str) -> str | None:
    anchor = next(
        (
            item
            for item in detail_doc.xpath("//a[@href]")
            if _squash_text(item.text_content()) == label
        ),
        None,
    )
    if anchor is None:
        return None
    return urljoin(detail_url, anchor.get("href") or "")


def enrich_school_catalog_snapshot(
    schools: list[dict[str, Any]],
    *,
    paths: FoundationPaths,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for school in schools:
        detail_url = str(school.get("chsi_school_url") or "").strip()
        if not detail_url:
            enriched.append(school)
            continue
        detail_text = _fetch_text(detail_url)
        detail_doc = html.fromstring(detail_text)
        source_meta = dict(school.get("source_meta") or {})
        source_meta["seed_hint_urls"] = _extract_seed_hint_urls(detail_doc, detail_url)
        source_meta["department_page_url"] = _category_page_url(detail_doc, detail_url, "院系设置")
        source_meta["major_page_url"] = _category_page_url(detail_doc, detail_url, "专业介绍")
        school["source_meta"] = source_meta
        enriched.append(school)
    _write_json(paths.school_catalog, enriched)
    return enriched


def _lines_from_html_text(html_text: str) -> list[str]:
    doc = html.fromstring(html_text)
    return [line.strip() for line in doc.text_content().splitlines() if line.strip()]


def fetch_chsi_major_catalog(
    schools: list[dict[str, Any]],
    *,
    paths: FoundationPaths,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for school in schools:
        source_meta = dict(school.get("source_meta") or {})
        major_page_url = str(source_meta.get("major_page_url") or "").strip()
        if not major_page_url:
            continue
        current_degree_type: str | None = None
        current_discipline_name: str | None = None
        for line in _lines_from_html_text(_fetch_text(major_page_url)):
            if line == "硕士专业":
                current_degree_type = "master"
                current_discipline_name = None
                continue
            if line == "博士专业":
                current_degree_type = "doctor"
                current_discipline_name = None
                continue
            match = MAJOR_LINE_RE.match(line)
            if match and current_degree_type:
                major_code = match.group("code").strip()
                records.append(
                    {
                        "major_code": major_code,
                        "major_name": match.group("name").strip(),
                        "degree_type": current_degree_type,
                        "discipline_code": major_code[:2],
                        "discipline_name": current_discipline_name,
                        "school_refs": [
                            {
                                "school_code": school.get("school_code"),
                                "school_name": school.get("school_name"),
                            }
                        ],
                        "department_refs": [],
                        "source_meta": {
                            "source_type": "chsi_major_catalog",
                            "major_page_url": major_page_url,
                        },
                    }
                )
                continue
            if current_degree_type and len(line) <= 32 and "[" not in line and "北京大学" not in line:
                current_discipline_name = line
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("major_code") or "").strip(), str(record.get("degree_type") or "").strip())
        existing = merged.get(key)
        if existing is None:
            merged[key] = record
            continue
        school_refs = list(existing.get("school_refs") or [])
        seen_refs = {(item.get("school_code"), item.get("school_name")) for item in school_refs}
        for item in record.get("school_refs") or []:
            ref_key = (item.get("school_code"), item.get("school_name"))
            if ref_key in seen_refs:
                continue
            seen_refs.add(ref_key)
            school_refs.append(item)
        existing["school_refs"] = school_refs
    result = list(merged.values())
    _write_json(paths.major_catalog, result)
    return result


def fetch_school_homepages(*, paths: FoundationPaths) -> list[dict[str, Any]]:
    payload = _fetch_json(SCHOOL_HOMEPAGE_SOURCE_URL)
    records: list[dict[str, Any]] = []
    items = payload if isinstance(payload, list) else payload.get("data") or payload.get("items") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        school_name = _squash_text(item.get("school_name") or item.get("name") or item.get("university_name"))
        homepage_url = _normalize_url(item.get("website") or item.get("homepage") or item.get("url"))
        if not school_name or not homepage_url:
            continue
        records.append(
            {
                "school_name": school_name,
                "official_homepage": homepage_url,
                "source_meta": {
                    "source_type": "school_homepage_fallback",
                    "source_url": SCHOOL_HOMEPAGE_SOURCE_URL,
                },
            }
        )
    _write_json(paths.school_homepages, records)
    return records


def fetch_official_seed_rosters(*, paths: FoundationPaths) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source in OFFICIAL_SEED_ROSTER_SOURCES:
        source_url = str(source.get("source_url") or "").strip()
        if not source_url:
            continue
        doc = html.fromstring(_fetch_text(source_url))
        for anchor in doc.xpath("//a[@href]"):
            text = _squash_text(anchor.text_content())
            href = urljoin(source_url, anchor.get("href") or "")
            if not text or not href:
                continue
            if "大学" not in text and "学院" not in text:
                continue
            if not SCHOOL_DETAIL_LIKE_TEXT.search(text) and "网址" not in text and "研招" not in text:
                continue
            school_name_match = re.match(r"^(.+?(大学|学院))", text)
            school_name = school_name_match.group(1).strip() if school_name_match else ""
            if not school_name:
                continue
            records.append(
                {
                    "school_name": school_name,
                    "homepage_url": href,
                    "seed_urls": [href],
                    "source_type": "official_roster",
                    "confidence": "high",
                    "source_meta": {
                        "source_key": source.get("source_key"),
                        "source_label": source.get("source_label"),
                        "source_url": source_url,
                    },
                }
            )
    _write_json(paths.official_seed_candidates, records)
    return records


def _parse_department_listing_page(page_url: str, html_text: str, school_name: str) -> list[dict[str, Any]]:
    doc = html.fromstring(html_text)
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in doc.xpath("//a[@href]"):
        department_name = _squash_text(anchor.text_content())
        if len(department_name) < 2 or len(department_name) > 40:
            continue
        if not DEPARTMENT_NAME_RE.search(department_name):
            continue
        href = urljoin(page_url, anchor.get("href") or "")
        normalized = normalize_department_name(department_name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        records.append(
            {
                "school_name": school_name,
                "department_code": sha256_hex(f"{school_name}:{department_name}")[:16],
                "department_name": department_name,
                "aliases": [],
                "major_count": 0,
                "source_meta": {
                    "source_type": "department_listing_page",
                    "listing_url": page_url,
                    "candidate_url": href,
                },
            }
        )
    return records


def build_department_candidates(
    schools: list[dict[str, Any]],
    *,
    paths: FoundationPaths,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    departments: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for school in schools:
        source_meta = dict(school.get("source_meta") or {})
        department_page_url = str(source_meta.get("department_page_url") or "").strip()
        if not department_page_url:
            continue
        parsed_departments = _parse_department_listing_page(
            department_page_url,
            _fetch_text(department_page_url),
            str(school.get("school_name") or ""),
        )
        for item in parsed_departments:
            departments.append(
                {
                    "school_code": school.get("school_code"),
                    "school_name": school.get("school_name"),
                    "department_code": item["department_code"],
                    "department_name": item["department_name"],
                    "aliases": [],
                    "major_count": 0,
                    "source_meta": item["source_meta"],
                }
            )
            candidates.append(
                {
                    "scope_type": "department",
                    "school_name": school.get("school_name"),
                    "department_name": item["department_name"],
                    "homepage_url": item["source_meta"]["candidate_url"],
                    "seed_urls": [item["source_meta"]["candidate_url"]],
                    "source_type": "department_candidate",
                    "confidence": "medium",
                    "review_status": "pending",
                    "notes": "generated from school department listing page",
                }
            )
    _write_json(paths.department_catalog, departments)
    _write_json(paths.department_candidates, candidates)
    return departments, candidates


def _build_homepage_seed_candidates(homepage_url: str) -> list[str]:
    doc = html.fromstring(_fetch_text(homepage_url))
    candidates: list[str] = []
    homepage_host = urlparse(homepage_url).hostname or ""
    explicit_paths = ["/yjs/", "/yjsy/", "/yjsc/", "/yz/", "/graduate/", "/zs/"]
    for path in explicit_paths:
        candidates.append(urljoin(homepage_url, path))
    for anchor in doc.xpath("//a[@href]"):
        text = _squash_text(anchor.text_content())
        href = urljoin(homepage_url, anchor.get("href") or "")
        if not href:
            continue
        href_host = urlparse(href).hostname or ""
        if homepage_host and href_host and homepage_host != href_host:
            continue
        if SCHOOL_DETAIL_LIKE_TEXT.search(text):
            candidates.append(href)
    return _dedupe_texts(candidates)


def _registry_key(record: dict[str, Any]) -> str:
    return "|".join(
        [
            str(record.get("scope_type") or "").strip(),
            normalize_school_name(record.get("school_name")),
            normalize_department_name(record.get("department_name")),
        ]
    )


def merge_announcement_seed_registry(
    *,
    paths: FoundationPaths,
    dry_run: bool,
) -> dict[str, Any]:
    schools = list(_read_json(paths.school_catalog, default=[]))
    homepage_rows = list(_read_json(paths.school_homepages, default=[]))
    official_rows = list(_read_json(paths.official_seed_candidates, default=[]))
    department_candidates = list(_read_json(paths.department_candidates, default=[]))
    department_overrides = list(_read_json(paths.department_overrides, default=[]))
    existing_registry = list(_read_json(paths.seed_registry, default=[]))
    official_by_school = {
        normalize_school_name(row.get("school_name")): row
        for row in official_rows
        if normalize_school_name(row.get("school_name"))
    }
    homepage_by_school = {
        normalize_school_name(row.get("school_name")): row
        for row in homepage_rows
        if normalize_school_name(row.get("school_name"))
    }
    new_registry: list[dict[str, Any]] = []
    for school in schools:
        school_name = str(school.get("school_name") or "").strip()
        if not school_name:
            continue
        source_meta = dict(school.get("source_meta") or {})
        official_seed = official_by_school.get(normalize_school_name(school_name))
        if official_seed is not None:
            entry = {
                "scope_type": "school",
                "school_name": school_name,
                "department_name": None,
                "homepage_url": official_seed.get("homepage_url"),
                "seed_urls": _dedupe_texts(official_seed.get("seed_urls") or [official_seed.get("homepage_url") or ""]),
                "source_type": "official_roster",
                "confidence": "high",
                "deny_prefixes": [],
                "notes": official_seed.get("source_meta", {}).get("source_label"),
                "last_verified_at": utcnow().isoformat(),
            }
            new_registry.append(entry)
            continue
        seed_hint_urls = _dedupe_texts(source_meta.get("seed_hint_urls") or [])
        if seed_hint_urls:
            new_registry.append(
                {
                    "scope_type": "school",
                    "school_name": school_name,
                    "department_name": None,
                    "homepage_url": seed_hint_urls[0],
                    "seed_urls": seed_hint_urls,
                    "source_type": "chsi_verified_seed",
                    "confidence": "high",
                    "deny_prefixes": [],
                    "notes": "derived from CHSI school detail bulletins",
                    "last_verified_at": utcnow().isoformat(),
                }
            )
            continue
        homepage_row = homepage_by_school.get(normalize_school_name(school_name))
        if homepage_row is None:
            continue
        homepage_url = str(homepage_row.get("official_homepage") or "").strip()
        if not homepage_url:
            continue
        new_registry.append(
            {
                "scope_type": "school",
                "school_name": school_name,
                "department_name": None,
                "homepage_url": homepage_url,
                "seed_urls": _build_homepage_seed_candidates(homepage_url),
                "source_type": "school_homepage_fallback",
                "confidence": "medium",
                "deny_prefixes": [],
                "notes": "derived from official homepage fallback",
                "last_verified_at": utcnow().isoformat(),
            }
        )
    for row in department_overrides:
        school_name = str(row.get("school_name") or "").strip()
        department_name = str(row.get("department_name") or "").strip()
        homepage_url = str(row.get("homepage_url") or "").strip()
        if not school_name or not department_name or not homepage_url:
            continue
        new_registry.append(
            {
                "scope_type": "department",
                "school_name": school_name,
                "department_name": department_name,
                "homepage_url": homepage_url,
                "seed_urls": _dedupe_texts(row.get("seed_urls") or [homepage_url]),
                "source_type": str(row.get("source_type") or "manual_override").strip() or "manual_override",
                "confidence": str(row.get("confidence") or "high").strip() or "high",
                "deny_prefixes": _dedupe_texts(row.get("deny_prefixes") or []),
                "notes": str(row.get("notes") or "department override").strip() or None,
                "last_verified_at": utcnow().isoformat(),
            }
        )
    existing_keys = {_registry_key(item): item for item in existing_registry}
    new_keys = {_registry_key(item): item for item in new_registry}
    diff_payload = {
        "added": sorted(key for key in new_keys if key not in existing_keys),
        "removed": sorted(key for key in existing_keys if key not in new_keys),
        "updated": sorted(
            key
            for key, value in new_keys.items()
            if key in existing_keys and json.dumps(value, ensure_ascii=False, sort_keys=True) != json.dumps(existing_keys[key], ensure_ascii=False, sort_keys=True)
        ),
        "department_candidate_count": len(department_candidates),
        "promoted_count": len([item for item in new_registry if item.get("scope_type") == "department"]),
        "school_count": len([item for item in new_registry if item.get("scope_type") == "school"]),
    }
    _write_json(paths.seed_diff, diff_payload)
    if not dry_run:
        _write_json(paths.seed_registry, new_registry)
    return diff_payload


def refresh_announcement_foundation(
    *,
    base_dir: str | Path | None = None,
    school_names: list[str] | None = None,
    dry_run: bool = False,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    paths = foundation_paths(base_dir)
    enabled_sources = {
        str(item).strip()
        for item in (sources or list(DEFAULT_FOUNDATION_SOURCES))
        if str(item).strip()
    } or set(DEFAULT_FOUNDATION_SOURCES)
    schools = fetch_chsi_school_catalog(school_names=school_names) if "chsi" in enabled_sources else []
    schools = enrich_school_catalog_snapshot(schools, paths=paths)
    majors = fetch_chsi_major_catalog(schools, paths=paths) if "chsi" in enabled_sources else []
    official_rows = fetch_official_seed_rosters(paths=paths) if "official_rosters" in enabled_sources else []
    homepage_rows = fetch_school_homepages(paths=paths) if "school_homepages" in enabled_sources else []
    departments, candidates = build_department_candidates(schools, paths=paths)
    diff_payload = merge_announcement_seed_registry(paths=paths, dry_run=dry_run)
    return {
        "school_count": len(schools),
        "department_count": len(departments),
        "major_count": len(majors),
        "official_seed_candidate_count": len(official_rows),
        "homepage_count": len(homepage_rows),
        "department_candidate_count": len(candidates),
        "registry_diff": diff_payload,
        "base_dir": str(paths.base_dir),
        "dry_run": dry_run,
        "sources": sorted(enabled_sources),
    }
