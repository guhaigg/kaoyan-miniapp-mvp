from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, joinedload

from ..models import Content, SiteSection, SiteSectionLink
from .announcement_portal import (
    derive_announcement_system_tags,
    extract_announcement_portal_metadata,
    merge_announcement_tags,
    normalize_portal_tags,
    normalize_portal_text,
)


def _resolve_section_lookup(db: Session, rows: list[Content]) -> dict[str, SiteSection]:
    section_ids: set[str] = set()
    link_ids: set[str] = set()
    for row in rows:
        extra = dict(row.extra or {})
        site_section_id = normalize_portal_text(extra.get("site_section_id"))
        site_section_link_id = normalize_portal_text(extra.get("site_section_link_id"))
        if site_section_id:
            section_ids.add(site_section_id)
        if site_section_link_id:
            link_ids.add(site_section_link_id)

    if link_ids:
        link_rows = db.query(SiteSectionLink).filter(SiteSectionLink.id.in_(sorted(link_ids))).all()
        section_ids.update(
            normalize_portal_text(link.site_section_id)
            for link in link_rows
            if normalize_portal_text(link.site_section_id)
        )

    if not section_ids:
        return {}

    sections = (
        db.query(SiteSection)
        .options(joinedload(SiteSection.school))
        .filter(SiteSection.id.in_(sorted(section_ids)))
        .all()
    )
    return {section.id: section for section in sections}


def _resolve_content_section(row: Content, section_lookup: dict[str, SiteSection], link_lookup: dict[str, str]) -> SiteSection | None:
    extra = dict(row.extra or {})
    site_section_id = normalize_portal_text(extra.get("site_section_id"))
    if site_section_id:
        return section_lookup.get(site_section_id)

    site_section_link_id = normalize_portal_text(extra.get("site_section_link_id"))
    if not site_section_link_id:
        return None
    linked_section_id = link_lookup.get(site_section_link_id)
    if not linked_section_id:
        return None
    return section_lookup.get(linked_section_id)


def backfill_announcement_portal_metadata(
    db: Session,
    *,
    school_name: str | None = None,
    limit: int = 0,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    normalized_school_name = normalize_portal_text(school_name)
    query = (
        db.query(Content)
        .options(joinedload(Content.school))
        .filter(Content.category == "announcement")
        .order_by(Content.created_at.asc(), Content.id.asc())
    )
    if limit and limit > 0:
        query = query.limit(limit)
    rows = query.all()

    section_lookup = _resolve_section_lookup(db, rows)
    link_lookup: dict[str, str] = {}
    if section_lookup:
        section_ids = set(section_lookup.keys())
        link_rows = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id.in_(sorted(section_ids))).all()
        link_lookup = {
            link.id: normalize_portal_text(link.site_section_id)
            for link in link_rows
            if normalize_portal_text(link.site_section_id)
        }

    scanned = 0
    matched = 0
    updated = 0
    skipped_no_section = 0
    skipped_school = 0

    for row in rows:
        scanned += 1
        extra = dict(row.extra or {})
        row_school_name = normalize_portal_text(
            row.school.name if row.school is not None else extra.get("school_name")
        )
        if normalized_school_name and row_school_name != normalized_school_name:
            skipped_school += 1
            continue

        section = _resolve_content_section(row, section_lookup, link_lookup)
        if section is None:
            skipped_no_section += 1
            continue
        matched += 1

        next_extra = dict(extra)
        metadata = extract_announcement_portal_metadata(
            dict(section.list_selector_config or {}),
            site_section_id=section.id,
            site_section_name=section.name,
        )
        for key, value in metadata.items():
            if key == "channel_keywords":
                current = normalize_portal_tags(next_extra.get(key) or [])
                incoming = normalize_portal_tags(value or [])
                if overwrite or not current:
                    next_extra[key] = incoming
                elif incoming:
                    next_extra[key] = normalize_portal_tags([*current, *incoming])
                continue
            if key == "portal_path_evidence":
                current = next_extra.get(key)
                if overwrite or not isinstance(current, dict) or not current:
                    next_extra[key] = dict(value or {})
                continue
            if overwrite or not normalize_portal_text(next_extra.get(key)):
                next_extra[key] = value

        next_extra["site_section_id"] = section.id
        next_extra["site_section_name"] = section.name
        if row_school_name and not normalize_portal_text(next_extra.get("school_name")):
            next_extra["school_name"] = row_school_name

        channel_label = normalize_portal_text(next_extra.get("channel_label"))
        channel_tier = normalize_portal_text(next_extra.get("channel_tier"))
        channel_keywords = normalize_portal_tags(next_extra.get("channel_keywords") or [])

        system_tags = normalize_portal_tags(next_extra.get("system_tags") or [])
        if overwrite or not system_tags:
            system_tags = derive_announcement_system_tags(
                row.title,
                row.summary,
                row.body,
                channel_label=channel_label,
                channel_tier=channel_tier,
                channel_keywords=channel_keywords,
            )
        next_extra["system_tags"] = system_tags
        next_extra["tags"] = merge_announcement_tags(
            next_extra.get("tags") or [],
            system_tags,
            channel_label=channel_label,
        )

        if next_extra == extra:
            continue
        updated += 1
        if not dry_run:
            row.extra = next_extra

    if dry_run:
        db.rollback()
    else:
        db.commit()

    return {
        "scanned": scanned,
        "matched": matched,
        "updated": updated,
        "skipped_no_section": skipped_no_section,
        "skipped_school": skipped_school,
        "dry_run": dry_run,
    }
