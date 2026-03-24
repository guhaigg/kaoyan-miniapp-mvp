from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from ..models import (
    Content,
    ContentFile,
    ContentSnapshot,
    CrawlError,
    CrawlJob,
    NotificationDelivery,
    NotificationOutbox,
    PortalUserMonitorHit,
    PortalUserMonitorKeyword,
    PortalUserMonitorTarget,
    School,
    SiteSection,
    SiteSectionLink,
    Source,
)
from .school_cold_start import _ANNOUNCEMENT_CANONICAL_SEEDS, _load_school_seed_map
from .search_cache import search_response_cache


def _chunked_ids(values: set[str], *, chunk_size: int = 200) -> list[list[str]]:
    ordered = sorted(str(value).strip() for value in values if str(value).strip())
    return [ordered[index : index + chunk_size] for index in range(0, len(ordered), chunk_size)]


def _delete_rows(query, ids: set[str]) -> int:
    deleted = 0
    for chunk in _chunked_ids(ids):
        deleted += query.filter(query.column_descriptions[0]["entity"].id.in_(chunk)).delete(synchronize_session=False)
    return deleted


def _normalize_host(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    host = (parsed.netloc or parsed.path or "").strip().lower()
    if not host:
        return ""
    return host.split(":", 1)[0]


def _host_owner_key(value: str | None) -> str:
    host = _normalize_host(value)
    if not host:
        return ""
    parts = [part for part in host.split(".") if part]
    if len(parts) >= 3 and ".".join(parts[-2:]) in {"edu.cn", "ac.cn"}:
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _payload_urls(payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    direct = str(payload.get("source_url") or "").strip()
    if direct:
        urls.append(direct)
    for key in ("candidate_urls", "result_candidate_urls"):
        value = payload.get(key)
        if isinstance(value, list):
            urls.extend(str(item or "").strip() for item in value if str(item or "").strip())
    return urls


def _docs_root() -> Path:
    return Path(__file__).resolve().parents[3] / "docs"


def _collect_school_names_from_payload(payload: Any, bucket: set[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "school_name":
                text = str(value or "").strip()
                if text:
                    bucket.add(text)
            else:
                _collect_school_names_from_payload(value, bucket)
        return
    if isinstance(payload, list):
        for item in payload:
            _collect_school_names_from_payload(item, bucket)


def _extra_school_names_from_docs() -> set[str]:
    names: set[str] = set(_ANNOUNCEMENT_CANONICAL_SEEDS.keys())
    docs_root = _docs_root()
    for path in sorted([*docs_root.glob("*.json"), *docs_root.glob("data/*.json")]):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        _collect_school_names_from_payload(payload, names)
    return names


def _school_name_terms(rows: list[School]) -> list[tuple[str, str]]:
    terms: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        candidates = [str(row.name or "").strip(), *[str(item or "").strip() for item in (row.aliases or [])]]
        for candidate in candidates:
            if not candidate:
                continue
            if candidate == row.name or len(candidate) >= 4:
                pair = (candidate, row.name)
                if pair in seen:
                    continue
                seen.add(pair)
                terms.append(pair)
    for name in sorted(_extra_school_names_from_docs()):
        text = str(name or "").strip()
        if not text:
            continue
        pair = (text, text)
        if pair in seen:
            continue
        seen.add(pair)
        terms.append(pair)
    terms.sort(key=lambda item: len(item[0]), reverse=True)
    return terms


def _matching_school_names(texts: list[str], school_terms: list[tuple[str, str]]) -> set[str]:
    haystack = " ".join(str(text or "").strip() for text in texts if str(text or "").strip())
    if not haystack:
        return set()
    matched: set[str] = set()
    for term, owner_name in school_terms:
        if term and term in haystack:
            matched.add(owner_name)
    return matched


def _owner_candidates_from_seed_data() -> dict[str, Counter[str]]:
    owner_candidates: dict[str, Counter[str]] = defaultdict(Counter)
    for school_name, urls in _load_school_seed_map().items():
        for url in urls:
            host_key = _host_owner_key(url)
            if host_key:
                owner_candidates[host_key][school_name] += 1
    for school_name, payload in _ANNOUNCEMENT_CANONICAL_SEEDS.items():
        for url in [str(payload.get("homepage_url") or "").strip(), *[str(item or "").strip() for item in payload.get("seed_urls") or []]]:
            host_key = _host_owner_key(url)
            if host_key:
                owner_candidates[host_key][school_name] += 2
    return owner_candidates


def _collect_host_owner_map(db: Session) -> dict[str, str]:
    schools = db.query(School).all()
    school_terms = _school_name_terms(schools)
    owner_candidates = _owner_candidates_from_seed_data()

    for source, school_name in (
        db.query(Source, School.name)
        .join(School, Source.school_id == School.id)
        .all()
    ):
        host_key = _host_owner_key(source.base_url)
        if not host_key:
            continue
        matched = _matching_school_names([source.name, source.base_url], school_terms)
        if len(matched) == 1:
            owner_candidates[host_key][next(iter(matched))] += 2

    for section, school_name in (
        db.query(SiteSection, School.name)
        .join(School, SiteSection.school_id == School.id)
        .filter(SiteSection.discovery_category == "announcement")
        .all()
    ):
        host_key = _host_owner_key(section.section_url)
        if not host_key:
            continue
        config = dict(section.list_selector_config or {})
        probe_evidence = dict(config.get("probe_evidence") or {})
        matched = _matching_school_names(
            [
                section.name,
                section.section_url,
                str(config.get("probe_heading") or ""),
                str(probe_evidence.get("stable_text") or ""),
                str(config.get("portal_entry_url") or ""),
            ],
            school_terms,
        )
        for owner_name in matched:
            owner_candidates[host_key][owner_name] += 3

    owner_map: dict[str, str] = {}
    for host_key, counter in owner_candidates.items():
        if not counter:
            continue
        owners = counter.most_common()
        if len(owners) == 1 or owners[0][1] > owners[1][1]:
            owner_map[host_key] = owners[0][0]
    return owner_map


def _resolved_content_school_name(content: Content, school_name_by_id: dict[str, str]) -> str:
    school_id = str(content.school_id or "").strip()
    if school_id and school_id in school_name_by_id:
        return school_name_by_id[school_id]
    extra = dict(content.extra or {})
    return str(extra.get("school_name") or "").strip()


def cleanup_polluted_announcement_data(
    db: Session,
    *,
    school_name: str | None = None,
    host_suffixes: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    requested_school_name = str(school_name or "").strip()
    normalized_suffixes = sorted(
        {
            _host_owner_key(value)
            for value in (host_suffixes or [])
            if _host_owner_key(value)
        }
    )
    owner_map = _collect_host_owner_map(db)
    school_rows = db.query(School).all()
    school_name_by_id = {row.id: row.name for row in school_rows}

    polluted_section_ids: set[str] = set()
    polluted_content_ids: set[str] = set()
    polluted_job_ids: set[str] = set()
    polluted_error_ids: set[str] = set()
    polluted_pairs: dict[tuple[str, str, str], dict[str, int]] = defaultdict(lambda: {"sections": 0, "contents": 0, "jobs": 0, "errors": 0})

    def _suffix_allowed(host_key: str) -> bool:
        if not normalized_suffixes:
            return True
        return host_key in normalized_suffixes

    for section in db.query(SiteSection).filter(SiteSection.discovery_category == "announcement").all():
        school_id = str(section.school_id or "").strip()
        bound_school_name = school_name_by_id.get(school_id, "")
        if not bound_school_name:
            continue
        if requested_school_name and bound_school_name != requested_school_name:
            continue
        host_key = _host_owner_key(section.section_url)
        owner_school_name = owner_map.get(host_key, "")
        if not host_key or not owner_school_name or owner_school_name == bound_school_name or not _suffix_allowed(host_key):
            continue
        polluted_section_ids.add(section.id)
        polluted_pairs[(bound_school_name, owner_school_name, host_key)]["sections"] += 1

    for content in db.query(Content).filter(Content.category == "announcement").all():
        bound_school_name = _resolved_content_school_name(content, school_name_by_id)
        if not bound_school_name:
            continue
        if requested_school_name and bound_school_name != requested_school_name:
            continue
        extra = dict(content.extra or {})
        section_id = str(extra.get("site_section_id") or "").strip()
        host_key = _host_owner_key(content.source_url)
        owner_school_name = owner_map.get(host_key, "")
        polluted = section_id in polluted_section_ids
        if not polluted and host_key and owner_school_name and owner_school_name != bound_school_name and _suffix_allowed(host_key):
            polluted = True
        if not polluted:
            continue
        polluted_content_ids.add(content.id)
        if host_key and owner_school_name:
            polluted_pairs[(bound_school_name, owner_school_name, host_key)]["contents"] += 1

    for job in db.query(CrawlJob).filter(CrawlJob.category == "announcement").all():
        payload = dict(job.query or {})
        bound_school_name = str(payload.get("school_name") or "").strip()
        if not bound_school_name:
            continue
        if requested_school_name and bound_school_name != requested_school_name:
            continue
        matched = False
        for url in _payload_urls(payload):
            host_key = _host_owner_key(url)
            owner_school_name = owner_map.get(host_key, "")
            if not host_key or not owner_school_name or owner_school_name == bound_school_name or not _suffix_allowed(host_key):
                continue
            polluted_job_ids.add(job.id)
            polluted_pairs[(bound_school_name, owner_school_name, host_key)]["jobs"] += 1
            matched = True
            break
        if matched:
            continue

    for error in db.query(CrawlError).all():
        if str(error.content_id or "").strip() in polluted_content_ids:
            polluted_error_ids.add(error.id)
            continue
        payload = dict(error.payload or {})
        query_payload = dict(payload.get("query") or {})
        bound_school_name = str(query_payload.get("school_name") or payload.get("school_name") or "").strip()
        if not bound_school_name:
            continue
        if requested_school_name and bound_school_name != requested_school_name:
            continue
        host_key = _host_owner_key(error.source_url or query_payload.get("source_url"))
        owner_school_name = owner_map.get(host_key, "")
        if not host_key or not owner_school_name or owner_school_name == bound_school_name or not _suffix_allowed(host_key):
            continue
        polluted_error_ids.add(error.id)
        polluted_pairs[(bound_school_name, owner_school_name, host_key)]["errors"] += 1

    polluted_link_ids = {
        row.id
        for row in db.query(SiteSectionLink.id).filter(SiteSectionLink.site_section_id.in_(sorted(polluted_section_ids))).all()
    } if polluted_section_ids else set()

    polluted_file_ids = set()
    if polluted_link_ids or polluted_content_ids:
        query = db.query(ContentFile.id)
        if polluted_link_ids and polluted_content_ids:
            query = query.filter(
                (ContentFile.site_section_link_id.in_(sorted(polluted_link_ids)))
                | (ContentFile.content_id.in_(sorted(polluted_content_ids)))
            )
        elif polluted_link_ids:
            query = query.filter(ContentFile.site_section_link_id.in_(sorted(polluted_link_ids)))
        else:
            query = query.filter(ContentFile.content_id.in_(sorted(polluted_content_ids)))
        polluted_file_ids = {row.id for row in query.all()}

    polluted_snapshot_ids = {
        row.id
        for row in db.query(ContentSnapshot.id).filter(ContentSnapshot.content_id.in_(sorted(polluted_content_ids))).all()
    } if polluted_content_ids else set()
    polluted_outbox_ids = {
        row.id
        for row in db.query(NotificationOutbox.id).filter(NotificationOutbox.content_id.in_(sorted(polluted_content_ids))).all()
    } if polluted_content_ids else set()
    polluted_delivery_ids = {
        row.id
        for row in db.query(NotificationDelivery.id).filter(NotificationDelivery.outbox_id.in_(sorted(polluted_outbox_ids))).all()
    } if polluted_outbox_ids else set()
    polluted_monitor_target_ids = {
        row.id
        for row in db.query(PortalUserMonitorTarget.id).filter(PortalUserMonitorTarget.site_section_id.in_(sorted(polluted_section_ids))).all()
    } if polluted_section_ids else set()

    polluted_monitor_hit_ids: set[str] = set()
    if polluted_content_ids or polluted_section_ids or polluted_monitor_target_ids:
        query = db.query(PortalUserMonitorHit.id)
        filters = []
        if polluted_content_ids:
            filters.append(PortalUserMonitorHit.content_id.in_(sorted(polluted_content_ids)))
        if polluted_section_ids:
            filters.append(PortalUserMonitorHit.site_section_id.in_(sorted(polluted_section_ids)))
        if polluted_monitor_target_ids:
            filters.append(PortalUserMonitorHit.monitor_target_id.in_(sorted(polluted_monitor_target_ids)))
        predicate = filters[0]
        for item in filters[1:]:
            predicate = predicate | item
        polluted_monitor_hit_ids = {row.id for row in query.filter(predicate).all()}

    polluted_monitor_keyword_ids = {
        row.id
        for row in db.query(PortalUserMonitorKeyword.id).filter(
            PortalUserMonitorKeyword.monitor_target_id.in_(sorted(polluted_monitor_target_ids))
        ).all()
    } if polluted_monitor_target_ids else set()

    stats: dict[str, Any] = {
        "dry_run": dry_run,
        "restricted_school_name": requested_school_name or None,
        "restricted_host_suffixes": normalized_suffixes,
        "owner_host_count": len(owner_map),
        "polluted_pairs": [
            {
                "bound_school_name": bound_school_name,
                "owner_school_name": owner_school_name,
                "host": host,
                **counts,
            }
            for (bound_school_name, owner_school_name, host), counts in sorted(polluted_pairs.items())
        ],
        "identified": {
            "sections": len(polluted_section_ids),
            "links": len(polluted_link_ids),
            "content_files": len(polluted_file_ids),
            "contents": len(polluted_content_ids),
            "snapshots": len(polluted_snapshot_ids),
            "crawl_jobs": len(polluted_job_ids),
            "crawl_errors": len(polluted_error_ids),
            "monitor_targets": len(polluted_monitor_target_ids),
            "monitor_keywords": len(polluted_monitor_keyword_ids),
            "monitor_hits": len(polluted_monitor_hit_ids),
            "notification_outbox": len(polluted_outbox_ids),
            "notification_deliveries": len(polluted_delivery_ids),
        },
        "deleted": {},
    }

    if dry_run:
        db.rollback()
        return stats

    deleted: dict[str, int] = {}
    deleted["notification_deliveries"] = _delete_rows(db.query(NotificationDelivery), polluted_delivery_ids) if polluted_delivery_ids else 0
    deleted["notification_outbox"] = _delete_rows(db.query(NotificationOutbox), polluted_outbox_ids) if polluted_outbox_ids else 0
    deleted["monitor_hits"] = _delete_rows(db.query(PortalUserMonitorHit), polluted_monitor_hit_ids) if polluted_monitor_hit_ids else 0
    deleted["monitor_keywords"] = _delete_rows(db.query(PortalUserMonitorKeyword), polluted_monitor_keyword_ids) if polluted_monitor_keyword_ids else 0
    deleted["monitor_targets"] = _delete_rows(db.query(PortalUserMonitorTarget), polluted_monitor_target_ids) if polluted_monitor_target_ids else 0
    deleted["crawl_errors"] = _delete_rows(db.query(CrawlError), polluted_error_ids) if polluted_error_ids else 0
    deleted["snapshots"] = _delete_rows(db.query(ContentSnapshot), polluted_snapshot_ids) if polluted_snapshot_ids else 0
    deleted["content_files"] = _delete_rows(db.query(ContentFile), polluted_file_ids) if polluted_file_ids else 0
    deleted["links"] = _delete_rows(db.query(SiteSectionLink), polluted_link_ids) if polluted_link_ids else 0
    deleted["contents"] = _delete_rows(db.query(Content), polluted_content_ids) if polluted_content_ids else 0
    deleted["sections"] = _delete_rows(db.query(SiteSection), polluted_section_ids) if polluted_section_ids else 0
    deleted["crawl_jobs"] = _delete_rows(db.query(CrawlJob), polluted_job_ids) if polluted_job_ids else 0
    db.commit()
    search_response_cache.clear()
    stats["deleted"] = deleted
    return stats
