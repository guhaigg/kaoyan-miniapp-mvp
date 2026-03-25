import hashlib
import re

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Content, ContentSnapshot, Department, NotificationOutbox, School, SiteSection, utcnow
from ..schemas import ContentIn
from .announcement_portal import (
    announcement_extra_is_visible,
    clear_announcement_portal_metadata,
    derive_announcement_system_tags,
    merge_announcement_tags,
    normalize_portal_tags,
    resolve_announcement_portal_metadata,
)
from .content_repair import infer_non_detail_announcement_reason
from .content_summary import normalize_text_whitespace, summarize_text
from .nlp import extract_adjustment_meta, extract_domain_tags, infer_content_category
from .premium_monitoring import evaluate_content_for_premium_monitoring
from .search_cache import search_response_cache

_ANNOUNCEMENT_PORTAL_KEYS = (
    "portal_scope",
    "portal_entry_url",
    "channel_label",
    "channel_tier",
    "portal_path_evidence",
)
_MAX_SNAPSHOT_RAW_HTML_BYTES = 60_000


def _resolve_school(db: Session, school_name: str | None) -> School | None:
    if not school_name:
        return None
    name = school_name.strip()
    if not name:
        return None

    school = db.query(School).filter(School.name == name).one_or_none()
    if school:
        return school

    school = School(name=name, aliases=[])
    db.add(school)
    db.flush()
    return school


def _resolve_school_by_id(db: Session, school_id: str | None) -> School | None:
    text = str(school_id or "").strip()
    if not text:
        return None
    return db.query(School).filter(School.id == text).one_or_none()


def _resolve_department(
    db: Session,
    *,
    school: School | None,
    department_id: str | None,
    department_name: str | None,
) -> Department | None:
    department_id_text = str(department_id or "").strip()
    if department_id_text:
        department = db.query(Department).filter(Department.id == department_id_text).one_or_none()
        if department is not None:
            return department

    name = str(department_name or "").strip()
    if not name:
        return None

    query = db.query(Department).filter(Department.name == name)
    if school is not None:
        query = query.filter(Department.school_id == school.id)
    rows = query.order_by(Department.updated_at.desc()).limit(2).all()
    if len(rows) != 1:
        return None
    return rows[0]


def _normalize_snapshot_raw_html(raw_html: str | None) -> tuple[str | None, dict[str, int | bool]]:
    text = str(raw_html or "")
    if not text:
        return None, {}
    encoded = text.encode("utf-8")
    meta: dict[str, int | bool] = {"raw_html_original_length": len(text), "raw_html_original_bytes": len(encoded)}
    if len(encoded) <= _MAX_SNAPSHOT_RAW_HTML_BYTES:
        return text, meta
    truncated = encoded[:_MAX_SNAPSHOT_RAW_HTML_BYTES].decode("utf-8", errors="ignore")
    meta["raw_html_truncated"] = True
    meta["raw_html_stored_bytes"] = len(truncated.encode("utf-8"))
    return truncated, meta


def _resolve_site_section(
    db: Session,
    *,
    school: School | None,
    department: Department | None,
    site_section_id: str | None,
    site_section_name: str | None,
) -> SiteSection | None:
    site_section_id_text = str(site_section_id or "").strip()
    if site_section_id_text:
        section = db.query(SiteSection).filter(SiteSection.id == site_section_id_text).one_or_none()
        if section is not None:
            return section

    name = str(site_section_name or "").strip()
    if not name:
        return None

    query = db.query(SiteSection).filter(SiteSection.name == name)
    if school is not None:
        query = query.filter(SiteSection.school_id == school.id)
    if department is not None:
        query = query.filter(SiteSection.department_id == department.id)
    rows = query.order_by(SiteSection.updated_at.desc()).limit(2).all()
    if len(rows) != 1:
        return None
    return rows[0]


def _normalize_scope_extra(db: Session, *, school: School | None, incoming_extra: dict) -> tuple[School | None, dict, SiteSection | None]:
    normalized_extra = dict(incoming_extra)
    resolved_school = school or _resolve_school_by_id(db, normalized_extra.get("school_id"))
    department = _resolve_department(
        db,
        school=resolved_school,
        department_id=normalized_extra.get("department_id"),
        department_name=normalized_extra.get("department_name"),
    )
    section = _resolve_site_section(
        db,
        school=resolved_school,
        department=department,
        site_section_id=normalized_extra.get("site_section_id"),
        site_section_name=normalized_extra.get("site_section_name"),
    )

    if section is not None:
        normalized_extra["site_section_id"] = section.id
        normalized_extra["site_section_name"] = section.name
        if resolved_school is None and section.school_id:
            resolved_school = db.query(School).filter(School.id == section.school_id).one_or_none()
        if department is None and section.department_id:
            department = db.query(Department).filter(Department.id == section.department_id).one_or_none()

    if department is not None:
        normalized_extra["department_id"] = department.id
        normalized_extra["department_name"] = department.name
        if resolved_school is None and department.school_id:
            resolved_school = db.query(School).filter(School.id == department.school_id).one_or_none()

    if resolved_school is not None:
        normalized_extra["school_id"] = resolved_school.id

    return resolved_school, normalized_extra, section


def _normalize_fingerprint_part(value: str | None, *, strip_all_spaces: bool = False) -> str:
    text = (value or "").strip().lower()
    if strip_all_spaces:
        return re.sub(r"\s+", "", text)
    return re.sub(r"\s+", " ", text)


def _build_content_fingerprint(payload: ContentIn, school_name: str | None, *, category: str) -> str:
    title = _normalize_fingerprint_part(payload.title, strip_all_spaces=True)
    school = _normalize_fingerprint_part(school_name, strip_all_spaces=True)
    body_teaser = _normalize_fingerprint_part(payload.body, strip_all_spaces=True)[:240]
    if payload.published_at:
        published_at = payload.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=utcnow().tzinfo)
        published = published_at.astimezone(utcnow().tzinfo).date().isoformat()
    else:
        published = "none"
    region = _normalize_fingerprint_part(payload.region, strip_all_spaces=True)
    major = _normalize_fingerprint_part(payload.major, strip_all_spaces=True)
    raw = "|".join([category, school, title, published, major, region, body_teaser])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _resolve_content_summary(summary: str | None, body: str) -> str | None:
    normalized_summary = normalize_text_whitespace(summary)
    if normalized_summary:
        return normalized_summary
    return summarize_text(body)


def _apply_payload_to_content(
    content: Content,
    payload: ContentIn,
    *,
    category: str,
    summary: str | None,
    school_id: str | None,
    merged_extra: dict,
    content_fingerprint: str,
) -> None:
    content.category = category
    content.title = payload.title
    content.body = payload.body
    content.summary = summary
    content.school_id = school_id
    content.source_url = payload.source_url
    content.source_type = payload.source_type
    content.published_at = payload.published_at
    content.region = payload.region
    content.major = payload.major
    content.content_fingerprint = content_fingerprint
    content.extra = merged_extra


def _merge_explicit_announcement_portal_overrides(extra: dict) -> tuple[dict, list[str], list[str]]:
    explicit = dict(extra or {})
    portal_overrides: dict[str, object] = {}
    for key in _ANNOUNCEMENT_PORTAL_KEYS:
        value = explicit.get(key)
        if isinstance(value, dict):
            if value:
                portal_overrides[key] = dict(value)
            continue
        text = str(value or "").strip()
        if text:
            portal_overrides[key] = text

    channel_keywords = normalize_portal_tags(explicit.get("channel_keywords") or [])
    system_tags = normalize_portal_tags(explicit.get("system_tags") or [])
    return portal_overrides, channel_keywords, system_tags


def _preserve_announcement_scope_meta(extra: dict, *, section: SiteSection | None) -> dict[str, str]:
    preserved: dict[str, str] = {}
    if section is not None:
        preserved["site_section_id"] = section.id
        preserved["site_section_name"] = section.name
        return preserved

    for key in ("site_section_id", "site_section_name"):
        text = str(extra.get(key) or "").strip()
        if text:
            preserved[key] = text
    return preserved


def _normalize_announcement_extra(
    *,
    extra: dict,
    source_url: str | None,
    title: str | None,
    summary: str | None,
    body: str | None,
    section: SiteSection | None,
) -> dict:
    explicit_portal_overrides, explicit_channel_keywords, explicit_system_tags = _merge_explicit_announcement_portal_overrides(
        extra
    )
    preserved_scope_meta = _preserve_announcement_scope_meta(extra, section=section)
    next_extra = clear_announcement_portal_metadata(extra)
    next_extra.update(preserved_scope_meta)
    next_extra.update(
        resolve_announcement_portal_metadata(
            source_url=source_url,
            title=title,
            summary=summary,
            body=body,
            section_config=dict(section.list_selector_config or {}) if section is not None else None,
            site_section_id=section.id if section is not None else None,
            site_section_name=section.name if section is not None else None,
        )
    )
    next_extra.update(preserved_scope_meta)
    next_extra.update(explicit_portal_overrides)
    if explicit_channel_keywords:
        next_extra["channel_keywords"] = normalize_portal_tags(
            [*list(next_extra.get("channel_keywords") or []), *explicit_channel_keywords]
        )

    if explicit_system_tags:
        system_tags = explicit_system_tags
    else:
        system_tags = derive_announcement_system_tags(
            title,
            summary,
            body,
            channel_label=str(next_extra.get("channel_label") or ""),
            channel_tier=str(next_extra.get("channel_tier") or ""),
            channel_keywords=[
                str(item)
                for item in (next_extra.get("channel_keywords") or [])
                if str(item or "").strip()
            ],
        )

    next_extra["system_tags"] = system_tags
    next_extra["tags"] = merge_announcement_tags(
        next_extra.get("tags") or [],
        system_tags,
        channel_label=str(next_extra.get("channel_label") or ""),
        prepend_channel_label=bool(section is not None or explicit_portal_overrides.get("channel_label")),
    )
    return next_extra


def _find_existing_content(db: Session, *, source_url: str | None, content_fingerprint: str) -> Content | None:
    filters = [Content.content_fingerprint == content_fingerprint]
    if source_url:
        filters.append(Content.source_url == source_url)
    return (
        db.query(Content)
        .filter(or_(*filters))
        .order_by(Content.updated_at.desc())
        .first()
    )


def upsert_content(db: Session, payload: ContentIn) -> tuple[Content, str]:
    effective_summary = _resolve_content_summary(payload.summary, payload.body)
    incoming_extra = dict(payload.extra or {})
    if not incoming_extra.get("tags"):
        incoming_extra["tags"] = extract_domain_tags(
            " ".join(part for part in [payload.title, effective_summary or "", payload.body] if part),
            top_k=5,
        )
    resolved_category = infer_content_category(
        title=payload.title,
        summary=effective_summary,
        body=payload.body,
        tags=incoming_extra.get("tags") or [],
        existing_category=payload.category,
    )
    if resolved_category == "adjustment":
        incoming_extra.pop("system_tags", None)
        incoming_extra["adjustment_meta"] = extract_adjustment_meta(
            title=payload.title,
            summary=effective_summary,
            body=payload.body,
            tags=incoming_extra.get("tags") or [],
        )
        incoming_extra.pop("content_quality", None)
        incoming_extra.pop("content_quality_reason", None)
    else:
        incoming_extra.pop("adjustment_meta", None)
        system_tags = normalize_portal_tags(incoming_extra.get("system_tags") or [])
        if not system_tags:
            system_tags = derive_announcement_system_tags(
                payload.title,
                effective_summary,
                payload.body,
                channel_label=str(incoming_extra.get("channel_label") or ""),
                channel_tier=str(incoming_extra.get("channel_tier") or ""),
                channel_keywords=[
                    str(item)
                    for item in (incoming_extra.get("channel_keywords") or [])
                    if str(item or "").strip()
                ],
            )
        incoming_extra["system_tags"] = system_tags
        incoming_extra["tags"] = merge_announcement_tags(
            incoming_extra.get("tags") or [],
            system_tags,
            channel_label=str(incoming_extra.get("channel_label") or ""),
        )
        non_detail_reason = infer_non_detail_announcement_reason(
            title=payload.title,
            body=payload.body,
            source_url=payload.source_url,
        )
        if non_detail_reason:
            incoming_extra["content_quality"] = "non_detail_page"
            incoming_extra["content_quality_reason"] = non_detail_reason
        else:
            incoming_extra.pop("content_quality", None)
            incoming_extra.pop("content_quality_reason", None)
    school = _resolve_school(db, payload.school_name)
    school, incoming_extra, section = _normalize_scope_extra(db, school=school, incoming_extra=incoming_extra)
    if resolved_category == "announcement":
        incoming_extra = _normalize_announcement_extra(
            extra=incoming_extra,
            source_url=payload.source_url,
            title=payload.title,
            summary=effective_summary,
            body=payload.body,
            section=section,
        )
    content_fingerprint = _build_content_fingerprint(
        payload,
        school.name if school else payload.school_name,
        category=resolved_category,
    )
    content = Content()
    merged_extra = dict(incoming_extra)
    _apply_payload_to_content(
        content,
        payload,
        category=resolved_category,
        summary=effective_summary,
        school_id=school.id if school else None,
        merged_extra=merged_extra,
        content_fingerprint=content_fingerprint,
    )
    status = "created"
    db.add(content)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        school = _resolve_school(db, payload.school_name)
        school, incoming_extra, section = _normalize_scope_extra(db, school=school, incoming_extra=incoming_extra)
        if resolved_category == "announcement":
            incoming_extra = _normalize_announcement_extra(
                extra=incoming_extra,
                source_url=payload.source_url,
                title=payload.title,
                summary=effective_summary,
                body=payload.body,
                section=section,
            )
        existing = _find_existing_content(db, source_url=payload.source_url, content_fingerprint=content_fingerprint)
        if existing is None:
            raise
        merged_extra = dict(existing.extra or {})
        merged_extra.update(incoming_extra)
        _apply_payload_to_content(
            existing,
            payload,
            category=resolved_category,
            summary=effective_summary,
            school_id=school.id if school else None,
            merged_extra=merged_extra,
            content_fingerprint=content_fingerprint,
        )
        content = existing
        status = "updated"
        db.add(content)
        db.flush()

    normalized_snapshot_html, snapshot_meta = _normalize_snapshot_raw_html(payload.raw_html)
    if normalized_snapshot_html:
        snapshot = ContentSnapshot(
            content_id=content.id,
            raw_html=normalized_snapshot_html,
            raw_text=payload.body,
            snapshot_meta=snapshot_meta,
        )
        db.add(snapshot)

    evaluate_content_for_premium_monitoring(db, content, trigger_status=status)

    content_extra = dict(content.extra or {})
    adjustment_meta = dict(content_extra.get("adjustment_meta") or {})
    major_code = next((str(code).strip() for code in (adjustment_meta.get("major_codes") or []) if str(code or "").strip()), None)
    department_name = str(content_extra.get("department_name") or "").strip() or None

    if content.category != "announcement" or announcement_extra_is_visible(content_extra):
        outbox = NotificationOutbox(
            content_id=content.id,
            event_type="content.upsert",
            payload={
                "content_id": content.id,
                "category": content.category,
                "title": content.title,
                "body": content.body,
                "summary": content.summary,
                "school_name": school.name if school else None,
                "department_name": department_name,
                "major": content.major,
                "major_name": content.major,
                "major_code": major_code,
                "region": content.region,
                "tags": list(content_extra.get("tags") or []),
                "system_tags": list(content_extra.get("system_tags") or []),
                "channel_label": str(content_extra.get("channel_label") or "").strip() or None,
                "channel_tier": str(content_extra.get("channel_tier") or "").strip() or None,
                "source_url": content.source_url,
                "published_at": content.published_at.isoformat() if content.published_at else None,
                "status": status,
            },
            status="pending",
            available_at=utcnow(),
        )
        db.add(outbox)
    db.commit()
    db.refresh(content)
    search_response_cache.clear()
    return content, status
