from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from ..models import Content, PortalUserMonitorTarget, School, utcnow
from .monitor_target_repair import infer_monitor_target_context
from .nlp import canonicalize_keyword, extract_system_keywords

RECENT_SIGNAL_WINDOW_DAYS = 3
_RECRUITMENT_SIGNAL_TAGS = {
    "调剂",
    "复试",
    "复试线",
    "拟录取",
    "推免",
    "夏令营",
    "招生简章",
    "录取名单",
    "缺额",
}
_RECRUITMENT_SIGNAL_PHRASES = (
    "研招",
    "研究生招生",
    "硕士研究生",
    "博士研究生",
    "硕士招生",
    "博士招生",
    "招生专业",
    "招生目录",
    "招生简章",
    "招生章程",
    "招生考试",
    "报名",
    "复试",
    "调剂",
    "推免",
    "拟录取",
    "录取名单",
)


def _normalize_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_key(value: Any) -> str | None:
    text = _normalize_text(value)
    if text is None:
        return None
    return text.lower()


def _content_effective_at(content: Content):
    return content.published_at or content.updated_at or content.created_at


def _content_scope(content: Content) -> dict[str, str | None]:
    extra = dict(content.extra or {})
    return {
        "school_id": _normalize_text(content.school_id or extra.get("school_id")),
        "school_name": _normalize_text(getattr(getattr(content, "school", None), "name", None) or extra.get("school_name")),
        "department_id": _normalize_text(extra.get("department_id")),
        "department_name": _normalize_text(extra.get("department_name")),
        "site_section_id": _normalize_text(extra.get("site_section_id")),
        "site_section_name": _normalize_text(extra.get("site_section_name")),
    }


def _content_tags(content: Content) -> list[str]:
    raw_tags = dict(content.extra or {}).get("tags") or []
    tags: list[str] = []
    for raw in raw_tags:
        tag = canonicalize_keyword(_normalize_text(raw))
        if tag:
            tags.append(tag)
    return tags


def _is_recruitment_related(content: Content) -> bool:
    tags = set(_content_tags(content))
    if tags & _RECRUITMENT_SIGNAL_TAGS:
        return True

    text = " ".join(
        part
        for part in (
            content.title,
            content.summary,
            (content.body or "")[:1200],
            dict(content.extra or {}).get("department_name"),
            dict(content.extra or {}).get("site_section_name"),
            " ".join(tags),
        )
        if part
    ).lower()
    if any(phrase.lower() in text for phrase in _RECRUITMENT_SIGNAL_PHRASES):
        return True

    extracted = set(extract_system_keywords(text, top_k=12))
    return bool(extracted & _RECRUITMENT_SIGNAL_TAGS)


def _matches_target(content: Content, context: dict[str, str | None], scope_type: str) -> bool:
    content_scope = _content_scope(content)
    target_school_id = _normalize_key(context.get("school_id"))
    target_school_name = _normalize_key(context.get("school_name"))
    target_department_id = _normalize_key(context.get("department_id"))
    target_department_name = _normalize_key(context.get("department_name"))
    target_section_id = _normalize_key(context.get("site_section_id"))
    target_section_name = _normalize_key(context.get("site_section_name"))

    content_school_id = _normalize_key(content_scope.get("school_id"))
    content_school_name = _normalize_key(content_scope.get("school_name"))
    content_department_id = _normalize_key(content_scope.get("department_id"))
    content_department_name = _normalize_key(content_scope.get("department_name"))
    content_section_id = _normalize_key(content_scope.get("site_section_id"))
    content_section_name = _normalize_key(content_scope.get("site_section_name"))

    school_match = False
    if target_school_id and content_school_id:
        school_match = target_school_id == content_school_id
    elif target_school_name and content_school_name:
        school_match = target_school_name == content_school_name
    if not school_match:
        return False

    if scope_type == "school":
        return True

    if scope_type == "department":
        if target_department_id and content_department_id:
            return target_department_id == content_department_id
        if target_department_name and content_department_name:
            return target_department_name == content_department_name
        return False

    if scope_type == "section":
        if target_section_id and content_section_id:
            return target_section_id == content_section_id
        if target_section_name and content_section_name:
            return target_section_name == content_section_name
        return False

    return False


def _signal_item(content: Content) -> dict[str, Any]:
    scope = _content_scope(content)
    return {
        "content_id": content.id,
        "title": content.title,
        "summary": content.summary,
        "source_url": content.source_url,
        "published_at": _content_effective_at(content),
        "school_name": scope.get("school_name"),
        "department_name": scope.get("department_name"),
        "site_section_name": scope.get("site_section_name"),
        "tags": _content_tags(content),
    }


def _empty_target_signal(window_days: int) -> dict[str, Any]:
    return {
        "window_days": window_days,
        "recent_announcement_count": 0,
        "recruitment_announcement_count": 0,
        "has_recent_announcements": False,
        "has_recruitment_announcements": False,
        "latest_announcement": None,
    }


def build_monitor_target_recent_signals(
    db: Session,
    targets: list[PortalUserMonitorTarget],
    *,
    window_days: int = RECENT_SIGNAL_WINDOW_DAYS,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    target_contexts: dict[str, dict[str, Any]] = {}
    school_ids: set[str] = set()
    school_names: set[str] = set()
    target_signals = {target.id: _empty_target_signal(window_days) for target in targets}

    for target in targets:
        context = infer_monitor_target_context(db, target)
        context["scope_type"] = target.scope_type
        target_contexts[target.id] = context
        school_id = _normalize_text(context.get("school_id"))
        school_name = _normalize_text(context.get("school_name"))
        if school_id:
            school_ids.add(school_id)
        elif school_name:
            school_names.add(school_name)

    overview = {
        "window_days": window_days,
        "tracked_target_count": len(targets),
        "active_target_count": 0,
        "recruitment_target_count": 0,
        "total_recent_announcements": 0,
        "total_recruitment_announcements": 0,
        "latest_announcement": None,
    }

    if not school_ids and not school_names:
        return target_signals, overview

    window_start = utcnow() - timedelta(days=window_days)
    effective_at = func.coalesce(Content.published_at, Content.updated_at, Content.created_at)
    query = (
        db.query(Content)
        .options(joinedload(Content.school))
        .filter(Content.category == "announcement", effective_at >= window_start)
    )

    school_filters = []
    if school_ids:
        school_filters.append(Content.school_id.in_(sorted(school_ids)))
    if school_names:
        query = query.join(School, Content.school_id == School.id, isouter=True)
        school_filters.append(School.name.in_(sorted(school_names)))
    query = query.filter(or_(*school_filters)).order_by(effective_at.desc(), Content.created_at.desc())

    recent_content_ids: set[str] = set()
    recruitment_content_ids: set[str] = set()

    for content in query.all():
        if dict(content.extra or {}).get("content_quality") == "non_detail_page":
            continue

        matched_target_ids = [
            target_id
            for target_id, context in target_contexts.items()
            if _matches_target(content, context, context.get("scope_type") or "")
        ]
        if not matched_target_ids:
            continue

        signal_item = _signal_item(content)
        is_recruitment_related = _is_recruitment_related(content)
        recent_content_ids.add(content.id)
        if is_recruitment_related:
            recruitment_content_ids.add(content.id)
        if overview["latest_announcement"] is None:
            overview["latest_announcement"] = signal_item

        for target_id in matched_target_ids:
            signal = target_signals[target_id]
            signal["recent_announcement_count"] += 1
            if signal["latest_announcement"] is None:
                signal["latest_announcement"] = signal_item
            if is_recruitment_related:
                signal["recruitment_announcement_count"] += 1

    for signal in target_signals.values():
        signal["has_recent_announcements"] = signal["recent_announcement_count"] > 0
        signal["has_recruitment_announcements"] = signal["recruitment_announcement_count"] > 0

    overview["active_target_count"] = sum(1 for signal in target_signals.values() if signal["has_recent_announcements"])
    overview["recruitment_target_count"] = sum(
        1 for signal in target_signals.values() if signal["has_recruitment_announcements"]
    )
    overview["total_recent_announcements"] = len(recent_content_ids)
    overview["total_recruitment_announcements"] = len(recruitment_content_ids)

    return target_signals, overview
