from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..models import (
    Content,
    ContentFile,
    ContentSnapshot,
    CrawlError,
    CrawlJob,
    NotificationDelivery,
    NotificationOutbox,
    PortalUserMonitorHit,
    SiteSection,
    SiteSectionLink,
    School,
    utcnow,
)
from .historical_intelligence import normalize_school_name
from .monitor_target_repair import repair_broken_monitor_targets
from .search_cache import search_response_cache

_ANNOUNCEMENT_CRAWL_MODES = {"url_fetch", "pdf_file"}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_url(value: Any) -> str:
    return _normalize_text(value).split("#", 1)[0]


def _matches_school_name(row: Content, school_name: str | None) -> bool:
    normalized_target = normalize_school_name(school_name)
    if not normalized_target:
        return True
    extra = dict(row.extra or {})
    candidates = [
        row.school.name if row.school is not None else None,
        extra.get("school_name"),
    ]
    return any(normalize_school_name(candidate) == normalized_target for candidate in candidates if _normalize_text(candidate))


def _is_rebuild_candidate_content(row: Content, *, school_name: str | None) -> bool:
    if row.category != "announcement" or row.source_type != "crawler":
        return False
    if not _matches_school_name(row, school_name):
        return False
    extra = dict(row.extra or {})
    if _normalize_text(extra.get("site_section_id")) or _normalize_text(extra.get("site_section_link_id")):
        return True
    crawl_mode = _normalize_text(extra.get("crawl_mode"))
    return crawl_mode in _ANNOUNCEMENT_CRAWL_MODES


def _build_replacement_maps(rows: list[Content]) -> tuple[dict[str, Content], dict[str, Content]]:
    by_source_url: dict[str, Content] = {}
    by_fingerprint: dict[str, Content] = {}
    ordered = sorted(rows, key=lambda row: (row.updated_at or utcnow(), row.created_at or utcnow()), reverse=True)
    for row in ordered:
        source_url = _normalize_url(row.source_url)
        if source_url and source_url not in by_source_url:
            by_source_url[source_url] = row
        fingerprint = _normalize_text(row.content_fingerprint)
        if fingerprint and fingerprint not in by_fingerprint:
            by_fingerprint[fingerprint] = row
    return by_source_url, by_fingerprint


def _resolve_replacement(
    row: Content,
    *,
    replacement_by_source_url: dict[str, Content],
    replacement_by_fingerprint: dict[str, Content],
) -> Content | None:
    source_url = _normalize_url(row.source_url)
    if source_url:
        replacement = replacement_by_source_url.get(source_url)
        if replacement is not None and replacement.id != row.id:
            return replacement
    fingerprint = _normalize_text(row.content_fingerprint)
    if fingerprint:
        replacement = replacement_by_fingerprint.get(fingerprint)
        if replacement is not None and replacement.id != row.id:
            return replacement
    return None


def _rebind_outbox_payload(payload: dict[str, Any], replacement: Content) -> dict[str, Any]:
    next_payload = dict(payload or {})
    extra = dict(replacement.extra or {})
    next_payload["content_id"] = replacement.id
    next_payload["category"] = replacement.category
    next_payload["title"] = replacement.title
    next_payload["body"] = replacement.body
    next_payload["summary"] = replacement.summary
    next_payload["school_name"] = replacement.school.name if replacement.school is not None else extra.get("school_name")
    next_payload["department_name"] = extra.get("department_name")
    next_payload["major"] = replacement.major
    next_payload["major_name"] = replacement.major
    adjustment_meta = dict(extra.get("adjustment_meta") or {})
    next_payload["major_code"] = next(
        (str(code).strip() for code in (adjustment_meta.get("major_codes") or []) if _normalize_text(code)),
        None,
    )
    next_payload["region"] = replacement.region
    next_payload["tags"] = list(extra.get("tags") or [])
    next_payload["source_url"] = replacement.source_url
    next_payload["published_at"] = replacement.published_at.isoformat() if replacement.published_at else None
    next_payload["status"] = "rebound"
    return next_payload


def _job_matches_rebuild_scope(job: CrawlJob, *, school_name: str | None, section_ids: set[str]) -> bool:
    if not school_name:
        return True
    payload = dict(job.query or {})
    job_school_name = _normalize_text(payload.get("school_name"))
    if job_school_name and job_school_name == school_name:
        return True
    site_section_id = _normalize_text(payload.get("site_section_id"))
    return bool(site_section_id and site_section_id in section_ids)


def _queue_section_discovery_jobs(db: Session, sections: list[SiteSection]) -> int:
    queued = 0
    for section in sections:
        job = CrawlJob(
            category=section.discovery_category,
            status="pending",
            requested_at=utcnow(),
            message=f"queued by announcement asset rebuild for site section {section.id}",
            query={
                "job_kind": "site_section_discovery",
                "site_section_id": section.id,
                "source_url": section.section_url,
                "school_name": section.school.name if section.school is not None else None,
                "department_name": section.department.name if section.department is not None else None,
                "school_id": section.school_id,
                "department_id": section.department_id,
                "rebuild_origin": "announcement_asset_rebuild",
            },
        )
        db.add(job)
        queued += 1
    return queued


def rebuild_announcement_assets(db: Session, *, school_name: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    normalized_school_name = _normalize_text(school_name) or None
    sections_query = (
        db.query(SiteSection)
        .options(joinedload(SiteSection.school), joinedload(SiteSection.department))
        .filter(SiteSection.discovery_category == "announcement")
        .order_by(SiteSection.created_at.asc())
    )
    if normalized_school_name:
        school = db.query(School).filter(School.name == normalized_school_name).one_or_none()
        if school is not None:
            sections_query = sections_query.filter(SiteSection.school_id == school.id)
        else:
            sections_query = sections_query.filter(SiteSection.id == "")
    sections = sections_query.all()
    section_ids = [section.id for section in sections]
    section_id_set = set(section_ids)

    link_rows = []
    if section_ids:
        link_rows = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id.in_(section_ids)).all()
    link_ids = [row.id for row in link_rows]

    content_rows = (
        db.query(Content)
        .options(joinedload(Content.school))
        .filter(Content.category == "announcement")
        .order_by(Content.created_at.asc())
        .all()
    )
    deleted_contents = [row for row in content_rows if _is_rebuild_candidate_content(row, school_name=normalized_school_name)]
    deleted_content_ids = [row.id for row in deleted_contents]
    deleted_content_id_set = set(deleted_content_ids)
    surviving_contents = [row for row in content_rows if row.id not in deleted_content_id_set]
    replacement_by_source_url, replacement_by_fingerprint = _build_replacement_maps(surviving_contents)

    content_files = []
    if link_ids or deleted_content_ids:
        filters = []
        if link_ids:
            filters.append(ContentFile.site_section_link_id.in_(link_ids))
        if deleted_content_ids:
            filters.append(ContentFile.content_id.in_(deleted_content_ids))
        content_files = db.query(ContentFile).filter(or_(*filters)).all()
    content_file_ids = [row.id for row in content_files]

    snapshots = []
    if deleted_content_ids:
        snapshots = db.query(ContentSnapshot).filter(ContentSnapshot.content_id.in_(deleted_content_ids)).all()
    snapshot_ids = [row.id for row in snapshots]

    announcement_jobs = [
        row
        for row in db.query(CrawlJob).filter(CrawlJob.category == "announcement").all()
        if _job_matches_rebuild_scope(row, school_name=normalized_school_name, section_ids=section_id_set)
    ]
    announcement_job_ids = [row.id for row in announcement_jobs]

    snapshot = {
        "school_name": normalized_school_name,
        "section_count": len(section_ids),
        "link_count": len(link_ids),
        "content_file_count": len(content_file_ids),
        "announcement_content_count": len(deleted_content_ids),
        "snapshot_count": len(snapshot_ids),
        "job_count": len(announcement_job_ids),
    }
    if dry_run:
        return {
            "snapshot": snapshot,
            "rebound_monitor_hits": 0,
            "deleted_monitor_hits": 0,
            "rebound_outboxes": 0,
            "deleted_outboxes": 0,
            "deleted_deliveries": 0,
            "deleted_crawl_errors": 0,
            "queued_discovery_jobs": 0,
            "repair_stats": {},
        }

    deleted_outboxes = 0
    deleted_deliveries = 0
    rebound_outboxes = 0
    deleted_monitor_hits = 0
    rebound_monitor_hits = 0
    deleted_crawl_errors = 0

    replacement_by_deleted_id: dict[str, Content] = {}
    for row in deleted_contents:
        replacement = _resolve_replacement(
            row,
            replacement_by_source_url=replacement_by_source_url,
            replacement_by_fingerprint=replacement_by_fingerprint,
        )
        if replacement is not None:
            replacement_by_deleted_id[row.id] = replacement

    hit_rows = []
    if deleted_content_ids:
        hit_rows = db.query(PortalUserMonitorHit).filter(PortalUserMonitorHit.content_id.in_(deleted_content_ids)).all()
    for hit in hit_rows:
        replacement = replacement_by_deleted_id.get(hit.content_id)
        if replacement is None:
            db.delete(hit)
            deleted_monitor_hits += 1
            continue
        duplicate = (
            db.query(PortalUserMonitorHit)
            .filter(
                PortalUserMonitorHit.user_id == hit.user_id,
                PortalUserMonitorHit.monitor_target_id == hit.monitor_target_id,
                PortalUserMonitorHit.content_id == replacement.id,
            )
            .one_or_none()
        )
        if duplicate is not None and duplicate.id != hit.id:
            if duplicate.site_section_id is None:
                replacement_extra = dict(replacement.extra or {})
                duplicate.site_section_id = _normalize_text(replacement_extra.get("site_section_id")) or None
            db.delete(hit)
            deleted_monitor_hits += 1
            continue
        replacement_extra = dict(replacement.extra or {})
        hit.content_id = replacement.id
        hit.site_section_id = _normalize_text(replacement_extra.get("site_section_id")) or None
        rebound_monitor_hits += 1

    outboxes = []
    if deleted_content_ids:
        outboxes = db.query(NotificationOutbox).filter(NotificationOutbox.content_id.in_(deleted_content_ids)).all()
    for outbox in outboxes:
        delivery_rows = db.query(NotificationDelivery).filter(NotificationDelivery.outbox_id == outbox.id).all()
        replacement = replacement_by_deleted_id.get(outbox.content_id)
        if replacement is None:
            for delivery in delivery_rows:
                db.delete(delivery)
                deleted_deliveries += 1
            db.delete(outbox)
            deleted_outboxes += 1
            continue
        outbox.content_id = replacement.id
        next_payload = _rebind_outbox_payload(outbox.payload or {}, replacement)
        outbox.payload = next_payload
        for delivery in delivery_rows:
            delivery.payload = dict(next_payload)
        rebound_outboxes += 1

    error_rows = []
    if deleted_content_ids:
        error_rows = db.query(CrawlError).filter(CrawlError.content_id.in_(deleted_content_ids)).all()
    for error_row in error_rows:
        replacement = replacement_by_deleted_id.get(_normalize_text(error_row.content_id))
        if replacement is None:
            db.delete(error_row)
            deleted_crawl_errors += 1
            continue
        error_row.content_id = replacement.id

    if snapshot_ids:
        db.query(ContentSnapshot).filter(ContentSnapshot.id.in_(snapshot_ids)).delete(synchronize_session=False)
    if content_file_ids:
        db.query(ContentFile).filter(ContentFile.id.in_(content_file_ids)).delete(synchronize_session=False)
    if deleted_content_ids:
        db.query(Content).filter(Content.id.in_(deleted_content_ids)).delete(synchronize_session=False)
    if link_ids:
        db.query(SiteSectionLink).filter(SiteSectionLink.id.in_(link_ids)).delete(synchronize_session=False)
    if announcement_job_ids:
        db.query(CrawlJob).filter(CrawlJob.id.in_(announcement_job_ids)).delete(synchronize_session=False)

    queued_discovery_jobs = _queue_section_discovery_jobs(
        db,
        [section for section in sections if bool(section.enabled)],
    )
    repair_stats = repair_broken_monitor_targets(db)
    db.commit()
    search_response_cache.clear()

    return {
        "snapshot": snapshot,
        "rebound_monitor_hits": rebound_monitor_hits,
        "deleted_monitor_hits": deleted_monitor_hits,
        "rebound_outboxes": rebound_outboxes,
        "deleted_outboxes": deleted_outboxes,
        "deleted_deliveries": deleted_deliveries,
        "deleted_crawl_errors": deleted_crawl_errors,
        "queued_discovery_jobs": queued_discovery_jobs,
        "repair_stats": repair_stats,
    }
