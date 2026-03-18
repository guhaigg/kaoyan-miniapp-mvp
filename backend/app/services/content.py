from sqlalchemy.orm import Session

from ..models import Content, ContentSnapshot, NotificationOutbox, School, utcnow
from ..schemas import ContentIn
from .premium_monitoring import evaluate_content_for_premium_monitoring


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


def upsert_content(db: Session, payload: ContentIn) -> tuple[Content, str]:
    school = _resolve_school(db, payload.school_name)
    existing = None
    if payload.source_url:
        existing = db.query(Content).filter(Content.source_url == payload.source_url).one_or_none()

    status = "updated" if existing else "created"
    content = existing or Content()
    content.category = payload.category
    content.title = payload.title
    content.body = payload.body
    content.summary = payload.summary
    content.school_id = school.id if school else None
    content.source_url = payload.source_url
    content.source_type = payload.source_type
    content.published_at = payload.published_at
    content.region = payload.region
    content.major = payload.major
    incoming_extra = dict(payload.extra or {})
    existing_extra = dict(existing.extra or {}) if existing and existing.extra else {}
    existing_extra.update(incoming_extra)
    content.extra = existing_extra

    if existing is None:
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
    return content, status
