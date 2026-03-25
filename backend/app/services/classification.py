from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..models import Content, ContentClassification
from .announcement_portal import announcement_extra_is_visible

RULE_VERSION = "crawler_v2_scope_v1"
SCOPE_CONFLICT_SUFFIXES = ("学院", "学部", "系", "研究院", "研究所", "中心", "分校", "校区")


@dataclass
class ClassificationSnapshot:
    scope_type: str
    scope_key: str
    visibility: str
    classification_state: str
    is_visible: bool
    explain_payload: dict[str, Any]


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def _resolve_scope(content: Content) -> tuple[str, str, str | None, str | None, dict[str, Any]]:
    extra = dict(content.extra or {})
    school_name = _compact_text(getattr(getattr(content, "school", None), "name", None) or extra.get("school_name"))
    department_name = _compact_text(extra.get("department_name"))
    if department_name:
        scope_key = "::".join(part for part in [school_name, department_name] if part) or str(extra.get("department_id") or "")
        return "department", scope_key or content.id, school_name or None, department_name or None, extra
    return "school", school_name or str(content.school_id or content.id), school_name or None, None, extra


def _looks_like_scope_conflict(content: Content, *, school_name: str | None, department_name: str | None, extra: dict[str, Any]) -> bool:
    if department_name:
        return False
    school = _compact_text(school_name)
    if not school:
        return False
    combined = _compact_text(
        " ".join(
            [
                str(getattr(content, "title", "") or ""),
                str(getattr(content, "summary", "") or ""),
                str(getattr(content, "body", "") or ""),
                str(getattr(content, "source_url", "") or ""),
                str(extra.get("site_section_name") or ""),
            ]
        )
    )
    return any(f"{school}{suffix}" in combined for suffix in SCOPE_CONFLICT_SUFFIXES)


def build_content_classification(content: Content) -> ClassificationSnapshot:
    scope_type, scope_key, school_name, department_name, extra = _resolve_scope(content)
    category = str(getattr(content, "category", "") or "").strip()
    visible = False
    classification_state = "non_announcement"
    visibility = "hidden"
    triggered_rules: list[str] = []

    if category == "announcement":
        if _looks_like_scope_conflict(
            content,
            school_name=school_name,
            department_name=department_name,
            extra=extra,
        ):
            classification_state = "hidden_scope_conflict"
            visibility = "hidden"
            triggered_rules.append("scope_conflict")
        elif announcement_extra_is_visible(extra):
            visible = True
            visibility = "visible"
            classification_state = "department_visible" if scope_type == "department" else "school_visible"
            triggered_rules.append("announcement_visible")
        else:
            classification_state = "hidden_non_admissions"
            visibility = "hidden"
            triggered_rules.append("non_admissions")

    explain_payload = {
        "rule_version": RULE_VERSION,
        "scope_type": scope_type,
        "scope_key": scope_key,
        "school_name": school_name,
        "department_name": department_name,
        "triggered_rules": triggered_rules,
        "evidence": {
            "portal_scope": str(extra.get("portal_scope") or ""),
            "channel_label": str(extra.get("channel_label") or ""),
            "channel_tier": str(extra.get("channel_tier") or ""),
            "system_tags": list(extra.get("system_tags") or []),
            "site_section_id": str(extra.get("site_section_id") or ""),
            "site_section_name": str(extra.get("site_section_name") or ""),
            "source_url": str(getattr(content, "source_url", "") or ""),
        },
    }
    return ClassificationSnapshot(
        scope_type=scope_type,
        scope_key=scope_key,
        visibility=visibility,
        classification_state=classification_state,
        is_visible=visible,
        explain_payload=explain_payload,
    )


def get_content_classification(db: Session, content_id: str) -> ContentClassification | None:
    return db.query(ContentClassification).filter(ContentClassification.content_id == content_id).one_or_none()


def get_effective_content_classification(db: Session, content: Content) -> ContentClassification | ClassificationSnapshot:
    persisted = get_content_classification(db, content.id)
    if persisted is not None:
        return persisted
    return build_content_classification(content)


def sync_content_classification(db: Session, content: Content) -> ContentClassification:
    snapshot = build_content_classification(content)
    row = get_content_classification(db, content.id)
    if row is None:
        row = ContentClassification(content_id=content.id)
        db.add(row)
    row.scope_type = snapshot.scope_type
    row.scope_key = snapshot.scope_key
    row.visibility = snapshot.visibility
    row.classification_state = snapshot.classification_state
    row.is_visible = 1 if snapshot.is_visible else 0
    row.rule_version = RULE_VERSION
    row.explain_payload = snapshot.explain_payload
    db.flush()
    return row
