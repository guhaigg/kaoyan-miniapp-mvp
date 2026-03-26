from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

ANNOUNCEMENT_FAMILIES = ("admissions", "notice")
_DOC_SEED_FILES = (
    "adjustment_announcement_2025_summary.json",
    "adjustment_opportunity_2025_snapshot_summary.json",
    "adjustment_supplemental_priority_targets_2024_2025.json",
    "adjustment_expanded_priority_targets_2024_2026.json",
)
_ANNOUNCEMENT_CANONICAL_SEED_PAYLOADS: dict[str, dict[str, Any]] = {
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
    },
}


@dataclass(frozen=True)
class CanonicalScopeSeed:
    scope_type: str
    school_name: str
    department_name: str | None
    families: tuple[str, ...]
    homepage_url: str
    seed_urls: tuple[str, ...]
    deny_prefixes: tuple[str, ...] = ()
    notes: str | None = None


def _docs_data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data"


def _normalize_url(url: str | None) -> str:
    return str(url or "").strip().split("#", 1)[0]


def _dedupe_texts(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _normalize_url(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


@lru_cache(maxsize=1)
def _load_doc_school_seed_map() -> dict[str, tuple[str, ...]]:
    seeds: dict[str, list[str]] = {}
    for filename in _DOC_SEED_FILES:
        path = _docs_data_dir() / filename
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows: list[dict[str, Any]]
        if isinstance(payload, dict):
            rows = [
                row
                for row in (payload.get("top_schools") or payload.get("schools") or payload.get("items") or [])
                if isinstance(row, dict)
            ]
        elif isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        else:
            rows = []

        for row in rows:
            school_name = str(row.get("school_name") or "").strip()
            top_url = _normalize_url(row.get("top_url"))
            if not school_name or not top_url:
                continue
            bucket = seeds.setdefault(school_name, [])
            if top_url not in bucket:
                bucket.append(top_url)
    return {school_name: tuple(urls) for school_name, urls in seeds.items()}


def get_doc_school_seed_urls(school_name: str) -> tuple[str, ...]:
    return _load_doc_school_seed_map().get(str(school_name or "").strip(), ())


def list_doc_school_seed_map() -> dict[str, tuple[str, ...]]:
    return dict(_load_doc_school_seed_map())


@lru_cache(maxsize=1)
def _announcement_school_seed_registry() -> dict[str, CanonicalScopeSeed]:
    registry: dict[str, CanonicalScopeSeed] = {}
    for school_name, payload in _ANNOUNCEMENT_CANONICAL_SEED_PAYLOADS.items():
        homepage_url = _normalize_url(payload.get("homepage_url"))
        seed_urls = _dedupe_texts([homepage_url, *(payload.get("seed_urls") or [])])
        if not homepage_url or not seed_urls:
            continue
        registry[school_name] = CanonicalScopeSeed(
            scope_type="school",
            school_name=school_name,
            department_name=None,
            families=ANNOUNCEMENT_FAMILIES,
            homepage_url=homepage_url,
            seed_urls=seed_urls,
            deny_prefixes=_dedupe_texts(payload.get("deny_prefixes") or []),
        )
    for school_name, doc_seed_urls in _load_doc_school_seed_map().items():
        if school_name in registry or not doc_seed_urls:
            continue
        registry[school_name] = CanonicalScopeSeed(
            scope_type="school",
            school_name=school_name,
            department_name=None,
            families=ANNOUNCEMENT_FAMILIES,
            homepage_url=doc_seed_urls[0],
            seed_urls=_dedupe_texts(doc_seed_urls),
        )
    return registry


def get_announcement_school_seed(school_name: str) -> CanonicalScopeSeed | None:
    return _announcement_school_seed_registry().get(str(school_name or "").strip())


def list_announcement_school_seeds() -> dict[str, CanonicalScopeSeed]:
    return dict(_announcement_school_seed_registry())


def resolve_announcement_school_seed(
    school_name: str,
    *,
    homepage_url: str | None = None,
    seed_urls: Iterable[str] | None = None,
) -> CanonicalScopeSeed | None:
    normalized_school_name = str(school_name or "").strip()
    if not normalized_school_name:
        return None

    explicit_homepage_url = _normalize_url(homepage_url)
    explicit_seed_urls = _dedupe_texts(seed_urls or ())
    registry_entry = get_announcement_school_seed(normalized_school_name)

    if explicit_homepage_url or explicit_seed_urls:
        resolved_homepage_url = explicit_homepage_url or (explicit_seed_urls[0] if explicit_seed_urls else "")
        if not resolved_homepage_url:
            return None
        resolved_seed_urls = _dedupe_texts([resolved_homepage_url, *explicit_seed_urls])
        return CanonicalScopeSeed(
            scope_type="school",
            school_name=normalized_school_name,
            department_name=None,
            families=ANNOUNCEMENT_FAMILIES,
            homepage_url=resolved_homepage_url,
            seed_urls=resolved_seed_urls,
            deny_prefixes=registry_entry.deny_prefixes if registry_entry is not None else (),
        )

    return registry_entry
