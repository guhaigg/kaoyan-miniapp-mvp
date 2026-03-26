from __future__ import annotations

from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from .. import models as app_models
from ..models import NotificationOutbox, utcnow
from .classification import get_content_classification
from .nlp import keyword_matches_content, normalize_tag


def _resolve_models() -> tuple[type[Any], type[Any], type[Any]] | None:
    target_model = getattr(app_models, "PortalUserMonitorTarget", None)
    keyword_model = getattr(app_models, "PortalUserMonitorKeyword", None)
    hit_model = getattr(app_models, "PortalUserMonitorHit", None)
    if target_model is None or keyword_model is None or hit_model is None:
        return None
    return target_model, keyword_model, hit_model


def _column_names(model: type[Any]) -> set[str]:
    return {col.key for col in inspect(model).mapper.column_attrs}


def _first_existing(columns: set[str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in columns:
            return name
    return None


def _as_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _build_content_text(content: Any) -> str:
    chunks = [
        _as_text(getattr(content, "title", None)),
        _as_text(getattr(content, "summary", None)),
        _as_text(getattr(content, "body", None)),
    ]
    return " ".join(x.lower() for x in chunks if x)


def _target_matches_scope(target: Any, *, school_id: str | None, department_id: str | None, site_section_id: str | None) -> bool:
    scope_type = _as_text(getattr(target, "scope_type", None)).lower()
    if scope_type == "school":
        return _as_id(getattr(target, "school_id", None)) == school_id
    if scope_type == "department":
        return _as_id(getattr(target, "department_id", None)) == department_id
    if scope_type == "section":
        return _as_id(getattr(target, "site_section_id", None)) == site_section_id
    return False


def _collect_keyword_hits(
    keywords: list[Any],
    content_text: str,
    content_tags: list[str],
    *,
    keyword_value_field: str,
    keyword_mode_field: str,
) -> list[str]:
    matched: list[str] = []
    seen: set[str] = set()
    for keyword_row in keywords:
        mode = _as_text(getattr(keyword_row, keyword_mode_field, None)).lower() or "contains"
        if mode != "contains":
            continue
        keyword = _as_text(getattr(keyword_row, keyword_value_field, None)).lower()
        if not keyword or keyword in seen:
            continue
        if keyword_matches_content(keyword, content_text, content_tags):
            seen.add(keyword)
            matched.append(keyword)
    return matched


def _query_active_rows(db: Session, model: type[Any]) -> list[Any]:
    columns = _column_names(model)
    query = db.query(model)
    if "status" in columns:
        query = query.filter(getattr(model, "status") == "active")
    return query.all()


def _find_existing_monitor_outbox(db: Session, *, content_id: str, user_id: str) -> NotificationOutbox | None:
    rows = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.event_type == "monitor.hit",
            NotificationOutbox.content_id == content_id,
        )
        .all()
    )
    for row in rows:
        payload = dict(row.payload or {})
        if _as_id(payload.get("user_id")) == user_id:
            return row
    return None


def evaluate_content_for_premium_monitoring(db: Session, content: Any, *, trigger_status: str) -> None:
    if trigger_status != "created":
        return

    models = _resolve_models()
    if models is None:
        return
    target_model, keyword_model, hit_model = models

    content_id = _as_id(getattr(content, "id", None))
    if not content_id:
        return

    extra = dict(getattr(content, "extra", None) or {})
    raw_content_tags = [
        *list(extra.get("tags") or []),
        *list(extra.get("system_tags") or []),
        _as_text(extra.get("channel_label")),
    ]
    content_tags = [normalize_tag(tag) for tag in raw_content_tags]
    content_tags = [tag for tag in content_tags if tag]
    if _as_text(getattr(content, "category", None)) == "announcement":
        classification = get_content_classification(db, content_id=content_id)
        if classification is None or not bool(getattr(classification, "is_visible", 0)):
            return
    school_id = _as_id(extra.get("school_id")) or _as_id(getattr(content, "school_id", None))
    department_id = _as_id(extra.get("department_id"))
    site_section_id = _as_id(extra.get("site_section_id"))
    content_text = _build_content_text(content)
    if not content_text:
        return

    target_rows = _query_active_rows(db, target_model)
    if not target_rows:
        return
    keyword_rows = _query_active_rows(db, keyword_model)

    target_columns = _column_names(target_model)
    keyword_columns = _column_names(keyword_model)
    hit_columns = _column_names(hit_model)

    target_id_field = _first_existing(target_columns, ("id",))
    target_user_field = _first_existing(target_columns, ("user_id",))
    keyword_target_field = _first_existing(keyword_columns, ("monitor_target_id", "target_id"))
    keyword_value_field = _first_existing(keyword_columns, ("keyword", "value"))
    keyword_mode_field = _first_existing(keyword_columns, ("match_mode",))
    hit_target_field = _first_existing(hit_columns, ("monitor_target_id", "target_id"))
    hit_keywords_field = _first_existing(hit_columns, ("matched_keywords",))

    if (
        target_id_field is None
        or target_user_field is None
        or keyword_target_field is None
        or keyword_value_field is None
        or keyword_mode_field is None
        or hit_target_field is None
        or "user_id" not in hit_columns
        or "content_id" not in hit_columns
    ):
        return

    keywords_by_target: dict[str, list[Any]] = {}
    for keyword in keyword_rows:
        target_id = _as_id(getattr(keyword, keyword_target_field, None))
        if not target_id:
            continue
        keywords_by_target.setdefault(target_id, []).append(keyword)

    school_name = _as_text(getattr(getattr(content, "school", None), "name", None)) or _as_text(extra.get("school_name"))
    department_name = _as_text(extra.get("department_name"))
    site_section_name = _as_text(extra.get("site_section_name"))
    category = _as_text(getattr(content, "category", None))
    title = _as_text(getattr(content, "title", None))
    source_url = _as_text(getattr(content, "source_url", None))
    major = _as_text(getattr(content, "major", None))
    region = _as_text(getattr(content, "region", None))

    for target in target_rows:
        if not _target_matches_scope(
            target,
            school_id=school_id,
            department_id=department_id,
            site_section_id=site_section_id,
        ):
            continue

        target_id = _as_id(getattr(target, target_id_field, None))
        user_id = _as_id(getattr(target, target_user_field, None))
        if not target_id or not user_id:
            continue

        target_keywords = keywords_by_target.get(target_id, [])
        if target_keywords:
            matched_keywords = _collect_keyword_hits(
                target_keywords,
                content_text,
                content_tags,
                keyword_value_field=keyword_value_field,
                keyword_mode_field=keyword_mode_field,
            )
            if not matched_keywords:
                continue
            score = len(matched_keywords)
            reason = f"contains:{','.join(matched_keywords)}"
        else:
            matched_keywords = []
            score = 1
            reason = f"scope_match:{_as_text(getattr(target, 'scope_type', None)).lower() or 'unknown'}"

        existing_hit = (
            db.query(hit_model)
            .filter(
                getattr(hit_model, "user_id") == user_id,
                getattr(hit_model, hit_target_field) == target_id,
                getattr(hit_model, "content_id") == content_id,
            )
            .one_or_none()
        )
        if existing_hit is not None:
            continue

        hit_payload: dict[str, Any] = {
            "user_id": user_id,
            hit_target_field: target_id,
            "content_id": content_id,
            "match_score": score,
            "hit_reason": reason,
        }
        if "site_section_id" in hit_columns:
            hit_payload["site_section_id"] = site_section_id
        if hit_keywords_field is not None:
            hit_payload[hit_keywords_field] = matched_keywords
        if "pushed_inapp" in hit_columns:
            hit_payload["pushed_inapp"] = 0
        if "pushed_bark" in hit_columns:
            hit_payload["pushed_bark"] = 0
        hit_row = hit_model(**hit_payload)
        db.add(hit_row)
        if hasattr(target, "last_hit_at"):
            setattr(target, "last_hit_at", utcnow())
        db.flush()

        if _find_existing_monitor_outbox(db, content_id=content_id, user_id=user_id) is not None:
            continue

        target_school_name = _as_text(getattr(getattr(target, "school", None), "name", None))
        target_department_name = _as_text(getattr(getattr(target, "department", None), "name", None))
        target_site_section_name = _as_text(getattr(getattr(target, "site_section", None), "name", None))
        scope_type = _as_text(getattr(target, "scope_type", None)).lower() or None
        outbox = NotificationOutbox(
            content_id=content_id,
            event_type="monitor.hit",
            payload={
                "content_id": content_id,
                "user_id": user_id,
                "target_id": target_id,
                "scope_type": scope_type,
                "matched_keywords": matched_keywords,
                "match_score": score,
                "hit_reason": reason,
                "title": title,
                "source_url": source_url,
                "category": category,
                "school_name": school_name or target_school_name or None,
                "department_name": department_name or target_department_name or None,
                "site_section_id": site_section_id or None,
                "site_section_name": site_section_name or target_site_section_name or None,
                "major": major or None,
                "region": region or None,
                "tags": content_tags,
                "system_tags": list(extra.get("system_tags") or []),
                "channel_label": _as_text(extra.get("channel_label")) or None,
                "channel_tier": _as_text(extra.get("channel_tier")) or None,
                "hit_id": _as_id(getattr(hit_row, "id", None)),
            },
            status="pending",
            available_at=utcnow(),
        )
        db.add(outbox)
