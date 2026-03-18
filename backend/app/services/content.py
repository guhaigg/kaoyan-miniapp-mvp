import hashlib
import re

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Content, ContentSnapshot, NotificationOutbox, School, utcnow
from ..schemas import ContentIn
from .nlp import extract_domain_tags
from .premium_monitoring import evaluate_content_for_premium_monitoring
from .search_cache import search_response_cache


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


def _normalize_fingerprint_part(value: str | None, *, strip_all_spaces: bool = False) -> str:
    text = (value or "").strip().lower()
    if strip_all_spaces:
        return re.sub(r"\s+", "", text)
    return re.sub(r"\s+", " ", text)


def _build_content_fingerprint(payload: ContentIn, school_name: str | None) -> str:
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
    raw = "|".join([payload.category, school, title, published, major, region, body_teaser])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _apply_payload_to_content(
    content: Content,
    payload: ContentIn,
    *,
    school_id: str | None,
    merged_extra: dict,
    content_fingerprint: str,
) -> None:
    content.category = payload.category
    content.title = payload.title
    content.body = payload.body
    content.summary = payload.summary
    content.school_id = school_id
    content.source_url = payload.source_url
    content.source_type = payload.source_type
    content.published_at = payload.published_at
    content.region = payload.region
    content.major = payload.major
    content.content_fingerprint = content_fingerprint
    content.extra = merged_extra


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
    incoming_extra = dict(payload.extra or {})
    if not incoming_extra.get("tags"):
        incoming_extra["tags"] = extract_domain_tags(
            " ".join(
                part for part in [payload.title, payload.summary or "", payload.body] if part
            ),
            top_k=5,
        )
    school = _resolve_school(db, payload.school_name)
    content_fingerprint = _build_content_fingerprint(payload, school.name if school else payload.school_name)
    content = Content()
    merged_extra = dict(incoming_extra)
    _apply_payload_to_content(
        content,
        payload,
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
        existing = _find_existing_content(db, source_url=payload.source_url, content_fingerprint=content_fingerprint)
        if existing is None:
            raise
        merged_extra = dict(existing.extra or {})
        merged_extra.update(incoming_extra)
        _apply_payload_to_content(
            existing,
            payload,
            school_id=school.id if school else None,
            merged_extra=merged_extra,
            content_fingerprint=content_fingerprint,
        )
        content = existing
        status = "updated"
        db.add(content)
        db.flush()

    if payload.raw_html:
        snapshot = ContentSnapshot(content_id=content.id, raw_html=payload.raw_html, raw_text=payload.body, snapshot_meta={})
        db.add(snapshot)

    evaluate_content_for_premium_monitoring(db, content, trigger_status=status)

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
            "major": content.major,
            "region": content.region,
            "tags": list((content.extra or {}).get("tags") or []),
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
