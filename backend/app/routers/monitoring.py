from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError, MultipleResultsFound
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..dependencies import audit_event, require_admin_request, require_premium_or_admin
from ..models import (
    Content,
    Department,
    PortalUserMonitorHit,
    PortalUserMonitorKeyword,
    PortalUserMonitorTarget,
    School,
    SiteSection,
)
from ..schemas import (
    MonitorHitItem,
    MonitorHitListResponse,
    MonitorKeywordBatchCreateRequest,
    MonitorKeywordCreateRequest,
    MonitorKeywordItem,
    MonitorKeywordListResponse,
    MonitorKeywordUpdateRequest,
    MonitorTargetCreateRequest,
    MonitorTargetItem,
    MonitorTargetListResponse,
    MonitorTargetUpdateRequest,
    MonitorScopeDepartmentItem,
    MonitorScopeDepartmentListResponse,
    MonitorScopeSectionItem,
    MonitorScopeSectionListResponse,
)
from ..services.monitor_target_repair import infer_monitor_target_context

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def _normalize_text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _build_target_display_label(
    *,
    scope_type: str,
    school_name: str | None,
    department_name: str | None,
    site_section_name: str | None,
) -> str:
    parts = [school_name, department_name]
    if scope_type == "section":
        parts.append(site_section_name)
    label = " · ".join(part for part in parts if part)
    return label or site_section_name or department_name or school_name or scope_type


def _to_target_item(db: Session, item: PortalUserMonitorTarget) -> MonitorTargetItem:
    context = infer_monitor_target_context(db, item)
    school_name = context.get("school_name")
    department_name = context.get("department_name")
    site_section_name = context.get("site_section_name")
    return MonitorTargetItem(
        id=item.id,
        user_id=item.user_id,
        scope_type=item.scope_type,
        school_id=context.get("school_id"),
        school_name=school_name,
        department_id=context.get("department_id"),
        department_name=department_name,
        site_section_id=context.get("site_section_id"),
        site_section_name=site_section_name,
        display_label=_build_target_display_label(
            scope_type=item.scope_type,
            school_name=school_name,
            department_name=department_name,
            site_section_name=site_section_name,
        ),
        status=item.status,
        check_interval_minutes=item.check_interval_minutes,
        last_checked_at=item.last_checked_at,
        last_hit_at=item.last_hit_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_scope_section_item(item: SiteSection) -> MonitorScopeSectionItem:
    return MonitorScopeSectionItem(
        id=item.id,
        name=item.name,
        section_type=item.section_type,
        discovery_category=item.discovery_category,
        section_url=item.section_url,
        school_id=item.school_id,
        school_name=item.school.name if item.school else None,
        department_id=item.department_id,
        department_name=item.department.name if item.department else None,
    )


def _to_scope_department_item(item: Department) -> MonitorScopeDepartmentItem:
    return MonitorScopeDepartmentItem(
        id=item.id,
        name=item.name,
        department_type=item.department_type,
        school_id=item.school_id,
        school_name=item.school.name if item.school else None,
    )


def _to_keyword_item(item: PortalUserMonitorKeyword) -> MonitorKeywordItem:
    return MonitorKeywordItem(
        id=item.id,
        user_id=item.user_id,
        monitor_target_id=item.monitor_target_id,
        keyword=item.keyword,
        match_mode=item.match_mode,
        weight=item.weight,
        status=item.status,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _to_hit_item(item: PortalUserMonitorHit, content: Content | None) -> MonitorHitItem:
    return MonitorHitItem(
        id=item.id,
        user_id=item.user_id,
        monitor_target_id=item.monitor_target_id,
        content_id=item.content_id,
        site_section_id=item.site_section_id,
        matched_keywords=[str(x) for x in (item.matched_keywords or [])],
        match_score=item.match_score,
        hit_reason=item.hit_reason,
        pushed_inapp=bool(item.pushed_inapp),
        pushed_bark=bool(item.pushed_bark),
        created_at=item.created_at,
        content_title=content.title if content else None,
        content_category=content.category if content else None,
    )


def _resolve_school_id(db: Session, *, school_id: str | None, school_name: str | None) -> str | None:
    normalized_name = _normalize_text(school_name)
    if school_id:
        row = db.query(School.id).filter(School.id == school_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="school not found")
        return school_id
    if normalized_name is None:
        return None
    row = db.query(School).filter(School.name == normalized_name).one_or_none()
    if row is None:
        row = School(name=normalized_name, aliases=[])
        db.add(row)
        db.flush()
    return row.id


def _resolve_department_id(
    db: Session,
    *,
    department_id: str | None,
    department_name: str | None,
    school_id: str | None,
) -> str | None:
    normalized_name = _normalize_text(department_name)
    if department_id:
        row = db.query(Department).filter(Department.id == department_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="department not found")
        return department_id
    if normalized_name is None:
        return None
    query = db.query(Department).filter(Department.name == normalized_name)
    if school_id:
        query = query.filter(Department.school_id == school_id)
    try:
        row = query.one_or_none()
    except MultipleResultsFound as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="department name is ambiguous, please specify the school",
        ) from exc
    if row is None:
        row = Department(name=normalized_name, aliases=[], department_type="college", school_id=school_id)
        db.add(row)
        db.flush()
    return row.id


def _resolve_site_section_id(
    db: Session,
    *,
    site_section_id: str | None,
    site_section_name: str | None,
    school_id: str | None,
    department_id: str | None,
) -> str | None:
    normalized_name = _normalize_text(site_section_name)
    if site_section_id:
        row = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="site section not found")
        return row.id
    if normalized_name is None:
        return None

    query = db.query(SiteSection).filter(SiteSection.name == normalized_name)
    if school_id:
        query = query.filter(SiteSection.school_id == school_id)
    if department_id:
        query = query.filter(SiteSection.department_id == department_id)
    rows = query.order_by(SiteSection.created_at.asc()).limit(2).all()
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="site section not found")
    if len(rows) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="site section name is ambiguous, please narrow by school or department",
        )
    return rows[0].id


def _ensure_scope_refs(
    db: Session,
    *,
    scope_type: str,
    school_id: str | None,
    school_name: str | None,
    department_id: str | None,
    department_name: str | None,
    site_section_id: str | None,
    site_section_name: str | None,
) -> tuple[str | None, str | None, str | None]:
    if scope_type not in {"school", "department", "section"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid scope_type")

    school_id = _resolve_school_id(db, school_id=school_id, school_name=school_name)
    department_id = _resolve_department_id(
        db,
        department_id=department_id,
        department_name=department_name,
        school_id=school_id,
    )
    site_section_id = _resolve_site_section_id(
        db,
        site_section_id=site_section_id,
        site_section_name=site_section_name,
        school_id=school_id,
        department_id=department_id,
    )

    if scope_type == "school":
        if not school_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="school_id is required for school scope")
        department_id = None
        site_section_id = None
    elif scope_type == "department":
        if not department_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="department_id is required for department scope")
        site_section_id = None
    elif scope_type == "section":
        if not site_section_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_section_id is required for section scope")
        section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
        if section is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="site section not found")
        if school_id is None and section.school_id:
            school_id = section.school_id
        if department_id is None and section.department_id:
            department_id = section.department_id

    return school_id, department_id, site_section_id


def _ensure_owned_target(db: Session, *, target_id: str, user_id: str) -> PortalUserMonitorTarget:
    target = (
        db.query(PortalUserMonitorTarget)
        .filter(
            PortalUserMonitorTarget.id == target_id,
            PortalUserMonitorTarget.user_id == user_id,
        )
        .one_or_none()
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor target not found")
    return target


def _find_same_scope_target(
    db: Session,
    *,
    user_id: str,
    scope_type: str,
    school_id: str | None,
    department_id: str | None,
    site_section_id: str | None,
    exclude_id: str | None = None,
) -> PortalUserMonitorTarget | None:
    query = db.query(PortalUserMonitorTarget).filter(
        PortalUserMonitorTarget.user_id == user_id,
        PortalUserMonitorTarget.scope_type == scope_type,
        PortalUserMonitorTarget.status != "deleted",
    )
    if exclude_id:
        query = query.filter(PortalUserMonitorTarget.id != exclude_id)
    if school_id is None:
        query = query.filter(PortalUserMonitorTarget.school_id.is_(None))
    else:
        query = query.filter(PortalUserMonitorTarget.school_id == school_id)
    if department_id is None:
        query = query.filter(PortalUserMonitorTarget.department_id.is_(None))
    else:
        query = query.filter(PortalUserMonitorTarget.department_id == department_id)
    if site_section_id is None:
        query = query.filter(PortalUserMonitorTarget.site_section_id.is_(None))
    else:
        query = query.filter(PortalUserMonitorTarget.site_section_id == site_section_id)
    return query.one_or_none()


@router.post("/targets", response_model=MonitorTargetItem)
def create_monitor_target(payload: MonitorTargetCreateRequest, request: Request, db: Session = Depends(get_db)) -> MonitorTargetItem:
    user = require_premium_or_admin(request, db)
    school_id, department_id, site_section_id = _ensure_scope_refs(
        db,
        scope_type=payload.scope_type,
        school_id=payload.school_id,
        school_name=payload.school_name,
        department_id=payload.department_id,
        department_name=payload.department_name,
        site_section_id=payload.site_section_id,
        site_section_name=payload.site_section_name,
    )
    existed = _find_same_scope_target(
        db,
        user_id=user.id,
        scope_type=payload.scope_type,
        school_id=school_id,
        department_id=department_id,
        site_section_id=site_section_id,
    )
    if existed is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="monitor target already exists")

    item = PortalUserMonitorTarget(
        user_id=user.id,
        scope_type=payload.scope_type,
        school_id=school_id,
        department_id=department_id,
        site_section_id=site_section_id,
        status=payload.status or "active",
        check_interval_minutes=payload.check_interval_minutes,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="monitor target already exists")
    db.refresh(item)
    audit_event(db, request, "monitoring.target.create", None, {"target_id": item.id, "portal_user_id": user.id})
    return _to_target_item(db, item)


@router.get("/targets", response_model=MonitorTargetListResponse)
def list_monitor_targets(request: Request, db: Session = Depends(get_db)) -> MonitorTargetListResponse:
    user = require_premium_or_admin(request, db)
    rows = (
        db.query(PortalUserMonitorTarget)
        .options(
            joinedload(PortalUserMonitorTarget.school),
            joinedload(PortalUserMonitorTarget.department),
            joinedload(PortalUserMonitorTarget.site_section),
        )
        .filter(
            PortalUserMonitorTarget.user_id == user.id,
            PortalUserMonitorTarget.status != "deleted",
        )
        .order_by(PortalUserMonitorTarget.created_at.desc())
        .all()
    )
    return MonitorTargetListResponse(total=len(rows), items=[_to_target_item(db, x) for x in rows])


@router.get("/scope-sections", response_model=MonitorScopeSectionListResponse)
def list_monitor_scope_sections(
    request: Request,
    db: Session = Depends(get_db),
    school_name: str | None = Query(default=None),
    department_name: str | None = Query(default=None),
    section_name: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> MonitorScopeSectionListResponse:
    require_premium_or_admin(request, db)

    query = (
        db.query(SiteSection)
        .options(joinedload(SiteSection.school), joinedload(SiteSection.department))
        .filter(SiteSection.enabled == 1)
    )
    if school_name:
        query = query.join(School, SiteSection.school_id == School.id, isouter=True).filter(
            School.name.ilike(f"%{school_name.strip()}%")
        )
    if department_name:
        query = query.join(Department, SiteSection.department_id == Department.id, isouter=True).filter(
            Department.name.ilike(f"%{department_name.strip()}%")
        )
    if section_name:
        query = query.filter(SiteSection.name.ilike(f"%{section_name.strip()}%"))

    rows = query.order_by(SiteSection.updated_at.desc()).limit(limit).all()
    return MonitorScopeSectionListResponse(total=len(rows), items=[_to_scope_section_item(row) for row in rows])


@router.get("/scope-departments", response_model=MonitorScopeDepartmentListResponse)
def list_monitor_scope_departments(
    request: Request,
    db: Session = Depends(get_db),
    school_name: str | None = Query(default=None),
    department_name: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> MonitorScopeDepartmentListResponse:
    require_premium_or_admin(request, db)

    query = (
        db.query(Department)
        .options(joinedload(Department.school))
        .filter(Department.enabled == 1)
    )
    if school_name:
        query = query.join(School, Department.school_id == School.id, isouter=True).filter(
            School.name.ilike(f"%{school_name.strip()}%")
        )
    if department_name:
        query = query.filter(Department.name.ilike(f"%{department_name.strip()}%"))

    rows = query.order_by(Department.updated_at.desc()).limit(limit).all()
    return MonitorScopeDepartmentListResponse(total=len(rows), items=[_to_scope_department_item(row) for row in rows])


@router.patch("/targets/{target_id}", response_model=MonitorTargetItem)
def update_monitor_target(
    target_id: str,
    payload: MonitorTargetUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MonitorTargetItem:
    user = require_premium_or_admin(request, db)
    target = _ensure_owned_target(db, target_id=target_id, user_id=user.id)

    if payload.status is not None:
        target.status = payload.status
    if payload.check_interval_minutes is not None:
        target.check_interval_minutes = payload.check_interval_minutes

    scope_changed = (
        payload.scope_type is not None
        or "school_id" in payload.model_fields_set
        or "school_name" in payload.model_fields_set
        or "department_id" in payload.model_fields_set
        or "department_name" in payload.model_fields_set
        or "site_section_id" in payload.model_fields_set
        or "site_section_name" in payload.model_fields_set
    )
    if scope_changed:
        final_scope = payload.scope_type if payload.scope_type is not None else target.scope_type
        final_school_id = (
            payload.school_id
            if "school_id" in payload.model_fields_set
            else (None if "school_name" in payload.model_fields_set else target.school_id)
        )
        final_school_name = payload.school_name if "school_name" in payload.model_fields_set else None
        final_department_id = (
            payload.department_id
            if "department_id" in payload.model_fields_set
            else (None if "department_name" in payload.model_fields_set else target.department_id)
        )
        final_department_name = payload.department_name if "department_name" in payload.model_fields_set else None
        final_site_section_id = (
            payload.site_section_id
            if "site_section_id" in payload.model_fields_set
            else (None if "site_section_name" in payload.model_fields_set else target.site_section_id)
        )
        final_site_section_name = payload.site_section_name if "site_section_name" in payload.model_fields_set else None
        final_school_id, final_department_id, final_site_section_id = _ensure_scope_refs(
            db,
            scope_type=final_scope,
            school_id=final_school_id,
            school_name=final_school_name,
            department_id=final_department_id,
            department_name=final_department_name,
            site_section_id=final_site_section_id,
            site_section_name=final_site_section_name,
        )
        target.scope_type = final_scope
        target.school_id = final_school_id
        target.department_id = final_department_id
        target.site_section_id = final_site_section_id
        duplicate = _find_same_scope_target(
            db,
            user_id=user.id,
            scope_type=target.scope_type,
            school_id=target.school_id,
            department_id=target.department_id,
            site_section_id=target.site_section_id,
            exclude_id=target.id,
        )
        if duplicate is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="monitor target already exists")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="monitor target already exists")
    db.refresh(target)
    audit_event(db, request, "monitoring.target.update", None, {"target_id": target.id, "portal_user_id": user.id})
    return _to_target_item(db, target)


@router.post("/targets/{target_id}/keywords", response_model=MonitorKeywordItem)
def create_monitor_keyword(
    target_id: str,
    payload: MonitorKeywordCreateRequest | MonitorKeywordBatchCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MonitorKeywordItem:
    user = require_premium_or_admin(request, db)
    target = _ensure_owned_target(db, target_id=target_id, user_id=user.id)
    if target.status == "deleted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot add keyword to deleted target")

    if isinstance(payload, MonitorKeywordBatchCreateRequest):
        raw_keywords = payload.keywords
        match_mode = payload.match_mode
        weight = payload.weight
    else:
        raw_keywords = [payload.keyword]
        match_mode = payload.match_mode
        weight = payload.weight

    normalized_keywords = [x.strip() for x in raw_keywords if (x or "").strip()]
    if not normalized_keywords:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="keyword cannot be empty")

    first_item: PortalUserMonitorKeyword | None = None
    for keyword in normalized_keywords:
        item = (
            db.query(PortalUserMonitorKeyword)
            .filter(
                PortalUserMonitorKeyword.monitor_target_id == target.id,
                PortalUserMonitorKeyword.keyword == keyword,
                PortalUserMonitorKeyword.match_mode == match_mode,
            )
            .one_or_none()
        )
        if item is None:
            item = PortalUserMonitorKeyword(
                user_id=user.id,
                monitor_target_id=target.id,
                keyword=keyword,
                match_mode=match_mode,
                weight=weight,
                status="active",
            )
            db.add(item)
        else:
            item.status = "active"
            item.weight = weight
        if first_item is None:
            first_item = item

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="keyword already exists")

    if first_item is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="keyword cannot be empty")
    db.refresh(first_item)
    audit_event(
        db,
        request,
        "monitoring.keyword.create",
        None,
        {"keyword_id": first_item.id, "target_id": target.id, "portal_user_id": user.id},
    )
    return _to_keyword_item(first_item)


@router.get("/targets/{target_id}/keywords", response_model=MonitorKeywordListResponse)
def list_monitor_keywords(target_id: str, request: Request, db: Session = Depends(get_db)) -> MonitorKeywordListResponse:
    user = require_premium_or_admin(request, db)
    target = _ensure_owned_target(db, target_id=target_id, user_id=user.id)
    rows = (
        db.query(PortalUserMonitorKeyword)
        .filter(
            PortalUserMonitorKeyword.user_id == user.id,
            PortalUserMonitorKeyword.monitor_target_id == target.id,
        )
        .order_by(PortalUserMonitorKeyword.created_at.desc())
        .all()
    )
    return MonitorKeywordListResponse(total=len(rows), items=[_to_keyword_item(x) for x in rows])


@router.patch("/keywords/{keyword_id}", response_model=MonitorKeywordItem)
def update_monitor_keyword(
    keyword_id: str,
    payload: MonitorKeywordUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MonitorKeywordItem:
    user = require_premium_or_admin(request, db)
    item = (
        db.query(PortalUserMonitorKeyword)
        .join(PortalUserMonitorTarget, PortalUserMonitorTarget.id == PortalUserMonitorKeyword.monitor_target_id)
        .filter(
            PortalUserMonitorKeyword.id == keyword_id,
            PortalUserMonitorKeyword.user_id == user.id,
            PortalUserMonitorTarget.user_id == user.id,
        )
        .one_or_none()
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="monitor keyword not found")

    if payload.status is not None:
        item.status = payload.status
    if payload.weight is not None:
        item.weight = payload.weight
    db.commit()
    db.refresh(item)
    audit_event(
        db,
        request,
        "monitoring.keyword.update",
        None,
        {"keyword_id": item.id, "portal_user_id": user.id},
    )
    return _to_keyword_item(item)


@router.get("/hits", response_model=MonitorHitListResponse)
def list_monitor_hits(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> MonitorHitListResponse:
    user = require_premium_or_admin(request, db)
    query = db.query(PortalUserMonitorHit).filter(PortalUserMonitorHit.user_id == user.id)
    total = query.count()
    rows = (
        query.order_by(PortalUserMonitorHit.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    content_ids = [x.content_id for x in rows]
    contents = {
        x.id: x
        for x in db.query(Content)
        .filter(Content.id.in_(content_ids))
        .all()
    } if content_ids else {}
    return MonitorHitListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_hit_item(x, contents.get(x.content_id)) for x in rows],
    )


@router.get("/admin/hits", response_model=MonitorHitListResponse)
def list_admin_monitor_hits(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user_id: str | None = Query(default=None),
    monitor_target_id: str | None = Query(default=None),
) -> MonitorHitListResponse:
    require_admin_request(request)

    query = db.query(PortalUserMonitorHit)
    if user_id:
        query = query.filter(PortalUserMonitorHit.user_id == user_id.strip())
    if monitor_target_id:
        query = query.filter(PortalUserMonitorHit.monitor_target_id == monitor_target_id.strip())

    total = query.count()
    rows = (
        query.order_by(PortalUserMonitorHit.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    content_ids = [x.content_id for x in rows]
    contents = {
        x.id: x
        for x in db.query(Content)
        .filter(Content.id.in_(content_ids))
        .all()
    } if content_ids else {}
    return MonitorHitListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_hit_item(x, contents.get(x.content_id)) for x in rows],
    )
