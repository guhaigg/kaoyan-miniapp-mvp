import hashlib

from sqlalchemy.orm import Session

from ..models import Content, ContentSnapshot, School
from ..schemas import ContentIn


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
    normalized_source_url = str(payload.source_url or "").strip() if payload.source_url else None
    source_url_hash = hashlib.sha256(normalized_source_url.encode("utf-8")).hexdigest() if normalized_source_url else None

    existing = None
    if source_url_hash:
        existing = db.query(Content).filter(Content.source_url_hash == source_url_hash).one_or_none()

    status = "updated" if existing else "created"
    content = existing or Content()
    content.category = payload.category
    content.title = payload.title
    content.body = payload.body
    content.summary = payload.summary
    content.school_id = school.id if school else None
    content.source_url = normalized_source_url
    content.source_url_hash = source_url_hash
    content.source_type = payload.source_type
    content.published_at = payload.published_at
    content.region = payload.region
    content.major = payload.major
    content.extra = payload.extra or {}

    if existing is None:
        db.add(content)
    db.flush()

    if payload.raw_html:
        snapshot = ContentSnapshot(content_id=content.id, raw_html=payload.raw_html, raw_text=payload.body, snapshot_meta={})
        db.add(snapshot)
    db.commit()
    db.refresh(content)
    return content, status
