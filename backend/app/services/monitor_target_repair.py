from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, joinedload

from ..models import Content, Department, PortalUserMonitorHit, PortalUserMonitorTarget, School, SiteSection


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _clean_id(value: Any) -> str | None:
    text = _clean_text(value)
    return text


def _single_value(values: set[str]) -> str | None:
    cleaned = {value for value in values if value}
    if len(cleaned) == 1:
        return next(iter(cleaned))
    return None


def _load_school_name(db: Session, school_id: str | None) -> str | None:
    if not school_id:
        return None
    return db.query(School.name).filter(School.id == school_id).scalar()


def _load_department(db: Session, department_id: str | None) -> Department | None:
    if not department_id:
        return None
    return (
        db.query(Department)
        .options(joinedload(Department.school))
        .filter(Department.id == department_id)
        .one_or_none()
    )


def _load_site_section(db: Session, site_section_id: str | None) -> SiteSection | None:
    if not site_section_id:
        return None
    return (
        db.query(SiteSection)
        .options(joinedload(SiteSection.school), joinedload(SiteSection.department))
        .filter(SiteSection.id == site_section_id)
        .one_or_none()
    )


def infer_monitor_target_context(db: Session, target: PortalUserMonitorTarget) -> dict[str, str | None]:
    school_id = _clean_id(target.school_id)
    department_id = _clean_id(target.department_id)
    site_section_id = _clean_id(target.site_section_id)
    school_name = _clean_text(getattr(getattr(target, "school", None), "name", None))
    department_name = _clean_text(getattr(getattr(target, "department", None), "name", None))
    site_section_name = _clean_text(getattr(getattr(target, "site_section", None), "name", None))

    if school_id and not school_name:
        school_name = _clean_text(_load_school_name(db, school_id))

    department = target.department if getattr(target, "department", None) is not None else _load_department(db, department_id)
    if department is not None:
        department_id = department.id
        department_name = department_name or _clean_text(department.name)
        school_id = school_id or _clean_id(department.school_id)
        school_name = school_name or _clean_text(getattr(getattr(department, "school", None), "name", None))

    section = target.site_section if getattr(target, "site_section", None) is not None else _load_site_section(db, site_section_id)
    if section is not None:
        site_section_id = section.id
        site_section_name = site_section_name or _clean_text(section.name)
        school_id = school_id or _clean_id(section.school_id)
        department_id = department_id or _clean_id(section.department_id)
        school_name = school_name or _clean_text(getattr(getattr(section, "school", None), "name", None))
        department_name = department_name or _clean_text(getattr(getattr(section, "department", None), "name", None))

    if school_id and not school_name:
        school_name = _clean_text(_load_school_name(db, school_id))

    hit_rows = (
        db.query(PortalUserMonitorHit)
        .options(
            joinedload(PortalUserMonitorHit.site_section).joinedload(SiteSection.school),
            joinedload(PortalUserMonitorHit.site_section).joinedload(SiteSection.department),
            joinedload(PortalUserMonitorHit.content).joinedload(Content.school),
        )
        .filter(PortalUserMonitorHit.monitor_target_id == target.id)
        .order_by(PortalUserMonitorHit.created_at.desc())
        .limit(20)
        .all()
    )

    hit_school_ids: set[str] = set()
    hit_school_names: set[str] = set()
    hit_department_ids: set[str] = set()
    hit_department_names: set[str] = set()
    hit_section_ids: set[str] = set()
    hit_section_names: set[str] = set()

    for hit in hit_rows:
        if hit.site_section_id:
            hit_section_ids.add(hit.site_section_id)
        if hit.site_section is not None:
            hit_section_names.add(hit.site_section.name)
            if hit.site_section.school_id:
                hit_school_ids.add(hit.site_section.school_id)
            if hit.site_section.department_id:
                hit_department_ids.add(hit.site_section.department_id)
            if hit.site_section.school is not None and hit.site_section.school.name:
                hit_school_names.add(hit.site_section.school.name)
            if hit.site_section.department is not None and hit.site_section.department.name:
                hit_department_names.add(hit.site_section.department.name)

        content = hit.content
        if content is None:
            continue
        extra = dict(content.extra or {})
        if content.school_id:
            hit_school_ids.add(content.school_id)
        if content.school is not None and content.school.name:
            hit_school_names.add(content.school.name)
        school_name_value = _clean_text(extra.get("school_name"))
        if school_name_value:
            hit_school_names.add(school_name_value)
        school_id_value = _clean_id(extra.get("school_id"))
        if school_id_value:
            hit_school_ids.add(school_id_value)
        department_id_value = _clean_id(extra.get("department_id"))
        if department_id_value:
            hit_department_ids.add(department_id_value)
        department_name_value = _clean_text(extra.get("department_name"))
        if department_name_value:
            hit_department_names.add(department_name_value)
        site_section_id_value = _clean_id(extra.get("site_section_id"))
        if site_section_id_value:
            hit_section_ids.add(site_section_id_value)
        site_section_name_value = _clean_text(extra.get("site_section_name"))
        if site_section_name_value:
            hit_section_names.add(site_section_name_value)

    school_id = school_id or _single_value(hit_school_ids)
    department_id = department_id or _single_value(hit_department_ids)
    site_section_id = site_section_id or _single_value(hit_section_ids)
    school_name = school_name or _single_value(hit_school_names)
    department_name = department_name or _single_value(hit_department_names)
    site_section_name = site_section_name or _single_value(hit_section_names)

    if site_section_id:
        section = _load_site_section(db, site_section_id)
        if section is not None:
            site_section_name = site_section_name or _clean_text(section.name)
            school_id = school_id or _clean_id(section.school_id)
            department_id = department_id or _clean_id(section.department_id)
            school_name = school_name or _clean_text(getattr(getattr(section, "school", None), "name", None))
            department_name = department_name or _clean_text(getattr(getattr(section, "department", None), "name", None))

    if department_id:
        department = _load_department(db, department_id)
        if department is not None:
            department_name = department_name or _clean_text(department.name)
            school_id = school_id or _clean_id(department.school_id)
            school_name = school_name or _clean_text(getattr(getattr(department, "school", None), "name", None))

    if school_id and not school_name:
        school_name = _clean_text(_load_school_name(db, school_id))

    return {
        "school_id": school_id,
        "school_name": school_name,
        "department_id": department_id,
        "department_name": department_name,
        "site_section_id": site_section_id,
        "site_section_name": site_section_name,
    }


def is_monitor_target_broken(target: PortalUserMonitorTarget, context: dict[str, str | None] | None = None) -> bool:
    scope_type = _clean_text(target.scope_type) or ""
    context = context or {}
    if scope_type == "school":
        return not (_clean_id(context.get("school_id") or target.school_id) and _clean_text(context.get("school_name")))
    if scope_type == "department":
        return not (_clean_id(context.get("department_id") or target.department_id) and _clean_text(context.get("department_name")))
    if scope_type == "section":
        return not (_clean_id(context.get("site_section_id") or target.site_section_id) and _clean_text(context.get("site_section_name")))
    return True


def repair_broken_monitor_targets(db: Session) -> dict[str, int]:
    rows = (
        db.query(PortalUserMonitorTarget)
        .options(
            joinedload(PortalUserMonitorTarget.school),
            joinedload(PortalUserMonitorTarget.department).joinedload(Department.school),
            joinedload(PortalUserMonitorTarget.site_section).joinedload(SiteSection.school),
            joinedload(PortalUserMonitorTarget.site_section).joinedload(SiteSection.department),
        )
        .filter(PortalUserMonitorTarget.status != "deleted")
        .order_by(PortalUserMonitorTarget.created_at.asc())
        .all()
    )

    repaired = 0
    removed = 0
    unchanged = 0

    for target in rows:
        context = infer_monitor_target_context(db, target)
        scope_type = _clean_text(target.scope_type) or ""

        if scope_type == "school":
            next_school_id = _clean_id(context.get("school_id"))
            next_school_name = _clean_text(context.get("school_name"))
            if next_school_id and next_school_name:
                changed = target.school_id != next_school_id or target.department_id is not None or target.site_section_id is not None
                target.school_id = next_school_id
                target.department_id = None
                target.site_section_id = None
                repaired += 1 if changed else 0
                unchanged += 0 if changed else 1
                continue
        elif scope_type == "department":
            next_school_id = _clean_id(context.get("school_id"))
            next_department_id = _clean_id(context.get("department_id"))
            next_department_name = _clean_text(context.get("department_name"))
            if next_department_id and next_department_name:
                changed = (
                    target.school_id != next_school_id
                    or target.department_id != next_department_id
                    or target.site_section_id is not None
                )
                target.school_id = next_school_id
                target.department_id = next_department_id
                target.site_section_id = None
                repaired += 1 if changed else 0
                unchanged += 0 if changed else 1
                continue
        elif scope_type == "section":
            next_school_id = _clean_id(context.get("school_id"))
            next_department_id = _clean_id(context.get("department_id"))
            next_site_section_id = _clean_id(context.get("site_section_id"))
            next_site_section_name = _clean_text(context.get("site_section_name"))
            if next_site_section_id and next_site_section_name:
                changed = (
                    target.school_id != next_school_id
                    or target.department_id != next_department_id
                    or target.site_section_id != next_site_section_id
                )
                target.school_id = next_school_id
                target.department_id = next_department_id
                target.site_section_id = next_site_section_id
                repaired += 1 if changed else 0
                unchanged += 0 if changed else 1
                continue

        if target.status != "deleted":
            target.status = "deleted"
            removed += 1
        else:
            unchanged += 1

    db.commit()

    return {
        "scanned": len(rows),
        "repaired": repaired,
        "removed": removed,
        "unchanged": unchanged,
    }
