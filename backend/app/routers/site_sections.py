from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, require_admin_request
from ..models import CrawlJob, Department, School, SiteSection, SiteSectionLink
from ..schemas import (
    SiteSectionCreateRequest,
    SiteSectionDiscoverRequest,
    SiteSectionDiscoverResponse,
    SiteSectionItem,
    SiteSectionLinkItem,
    SiteSectionLinkListResponse,
    SiteSectionListResponse,
)

router = APIRouter(prefix="/site-sections", tags=["site-sections"])


def _resolve_school(db: Session, school_name: str | None) -> School | None:
    name = (school_name or "").strip()
    if not name:
        return None

    school = db.query(School).filter(School.name == name).one_or_none()
    if school is not None:
        return school

    school = School(name=name, aliases=[])
    db.add(school)
    db.flush()
    return school


def _resolve_department(
    db: Session,
    *,
    school: School | None,
    department_name: str | None,
    department_type: str,
) -> Department | None:
    name = (department_name or "").strip()
    if not name:
        return None

    query = db.query(Department).filter(Department.name == name)
    if school is not None:
        query = query.filter(Department.school_id == school.id)
    else:
        query = query.filter(Department.school_id.is_(None))

    department = query.one_or_none()
    if department is not None:
        return department

    department = Department(
        school_id=school.id if school else None,
        name=name,
        aliases=[],
        department_type=department_type,
    )
    db.add(department)
    db.flush()
    return department


def _to_site_section_item(section: SiteSection) -> SiteSectionItem:
    return SiteSectionItem(
        id=section.id,
        name=section.name,
        section_type=section.section_type,
        section_url=section.section_url,
        school_name=section.school.name if section.school else None,
        department_name=section.department.name if section.department else None,
        department_type=section.department.department_type if section.department else None,
        discovery_category=section.discovery_category,
        enabled=bool(section.enabled),
        list_selector_config=section.list_selector_config or {},
        last_discovered_at=section.last_discovered_at,
        last_discovery_status=section.last_discovery_status,
        last_error=section.last_error,
        created_at=section.created_at,
        updated_at=section.updated_at,
    )


def _to_link_item(link: SiteSectionLink) -> SiteSectionLinkItem:
    return SiteSectionLinkItem(
        id=link.id,
        site_section_id=link.site_section_id,
        link_url=link.link_url,
        title=link.title,
        link_type=link.link_type,
        status=link.status,
        crawl_job_id=link.crawl_job_id,
        published_at=link.published_at,
        snapshot_meta=link.snapshot_meta or {},
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


@router.post("", response_model=SiteSectionItem)
def create_site_section(
    payload: SiteSectionCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SiteSectionItem:
    require_admin_request(request)

    school = _resolve_school(db, payload.school_name)
    department = _resolve_department(
        db,
        school=school,
        department_name=payload.department_name,
        department_type=payload.department_type,
    )

    section = SiteSection(
        school_id=school.id if school else None,
        department_id=department.id if department else None,
        source_id=payload.source_id,
        name=payload.name.strip(),
        section_type=payload.section_type.strip(),
        section_url=payload.section_url.strip(),
        discovery_category=payload.discovery_category,
        enabled=1 if payload.enabled else 0,
        list_selector_config=payload.list_selector_config,
    )
    db.add(section)
    db.commit()
    db.refresh(section)
    audit_event(db, request, "site_section.create", None, {"site_section_id": section.id})
    return _to_site_section_item(section)


@router.get("", response_model=SiteSectionListResponse)
def list_site_sections(
    request: Request,
    db: Session = Depends(get_db),
    school_name: str | None = Query(default=None),
    department_name: str | None = Query(default=None),
    section_type: str | None = Query(default=None),
    enabled_only: bool = Query(default=False),
) -> SiteSectionListResponse:
    require_admin_request(request)
    query = db.query(SiteSection)
    if school_name:
        query = query.join(School, isouter=True).filter(School.name.ilike(f"%{school_name.strip()}%"))
    if department_name:
        query = query.join(Department, isouter=True).filter(Department.name.ilike(f"%{department_name.strip()}%"))
    if section_type:
        query = query.filter(SiteSection.section_type == section_type.strip())
    if enabled_only:
        query = query.filter(SiteSection.enabled == 1)

    rows = query.order_by(SiteSection.created_at.desc()).all()
    return SiteSectionListResponse(total=len(rows), items=[_to_site_section_item(row) for row in rows])


@router.post("/discover", response_model=SiteSectionDiscoverResponse)
def discover_site_sections(
    payload: SiteSectionDiscoverRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SiteSectionDiscoverResponse:
    require_admin_request(request)
    query = db.query(SiteSection)
    if payload.school_name:
        query = query.join(School, isouter=True).filter(School.name.ilike(f"%{payload.school_name.strip()}%"))
    if payload.department_name:
        query = query.join(Department, isouter=True).filter(Department.name.ilike(f"%{payload.department_name.strip()}%"))
    if payload.section_type:
        query = query.filter(SiteSection.section_type == payload.section_type.strip())
    if payload.enabled_only:
        query = query.filter(SiteSection.enabled == 1)

    sections = query.order_by(SiteSection.created_at.asc()).all()
    job_ids: list[str] = []
    now = datetime.now(timezone.utc)
    for section in sections:
        job = CrawlJob(
            category=section.discovery_category,
            status="pending",
            requested_at=now,
            message=f"queued discovery for site section {section.id}",
            query={
                "job_kind": "site_section_discovery",
                "site_section_id": section.id,
                "source_url": section.section_url,
                "section_type": section.section_type,
            },
        )
        db.add(job)
        db.flush()
        job_ids.append(job.id)

    db.commit()
    audit_event(db, request, "site_section.discover", None, {"job_ids": job_ids})
    return SiteSectionDiscoverResponse(total_sections=len(sections), job_ids=job_ids)


@router.get("/{site_section_id}/links", response_model=SiteSectionLinkListResponse)
def list_site_section_links(
    site_section_id: str,
    request: Request,
    db: Session = Depends(get_db),
    link_type: str | None = Query(default=None),
) -> SiteSectionLinkListResponse:
    require_admin_request(request)
    query = db.query(SiteSectionLink).filter(SiteSectionLink.site_section_id == site_section_id)
    if link_type:
        query = query.filter(SiteSectionLink.link_type == link_type.strip())
    rows = query.order_by(SiteSectionLink.created_at.desc()).all()
    return SiteSectionLinkListResponse(total=len(rows), items=[_to_link_item(row) for row in rows])
