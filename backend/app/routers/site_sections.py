from datetime import datetime, timezone
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, require_admin_request
from ..models import ContentFile, CrawlJob, Department, School, SiteSection, SiteSectionLink, utcnow
from ..schemas import (
    ContentFileItem,
    ContentFileListResponse,
    ContentFileRetryParseResponse,
    SiteSectionBootstrapRequest,
    SiteSectionBootstrapResponse,
    SiteSectionBackfillSelectorConfigRequest,
    SiteSectionBackfillSelectorConfigResponse,
    SiteSectionCreateRequest,
    SiteSectionDiscoverRequest,
    SiteSectionDiscoverResponse,
    SiteSectionItem,
    SiteSectionLinkItem,
    SiteSectionLinkListResponse,
    SiteSectionListResponse,
    SiteSectionSelectorPreviewLinkItem,
    SiteSectionSelectorPreviewRequest,
    SiteSectionSelectorPreviewResponse,
    SiteSectionUpdateRequest,
)
from ..services import crawler as crawler_service
from ..services.crawler import build_site_section_detail_selector_config, build_site_section_list_selector_config
from ..services.site_section_bootstrap import bootstrap_site_sections as bootstrap_site_sections_service

router = APIRouter(prefix="/site-sections", tags=["site-sections"])


def _build_selector_preview_suggestions(
    *,
    list_match_count: int,
    detail_preview_url: str | None,
    detail_excerpt: str | None,
    detail_method: str | None,
    used_fallback_links: bool,
    list_config: dict,
    detail_config: dict,
) -> list[str]:
    suggestions: list[str] = []

    if list_match_count == 0:
        if list_config.get("css_selector") or list_config.get("xpath"):
            suggestions.append("列表规则当前没有命中任何公告链接。先用浏览器定位真实公告列表容器，再把选择器收窄到该区域下的 <a>。")
        else:
            suggestions.append("先补一个列表页规则。优先填写公告列表容器的 CSS Selector，例如 `.news-list a`。")
    elif used_fallback_links:
        suggestions.append("当前命中依赖全页链接扫描。建议补齐列表页 CSS/XPath，把范围限制在公告列表区域，避免抓到导航和页脚。")

    if detail_preview_url and detail_preview_url.lower().endswith(".pdf"):
        suggestions.append("当前样本是 PDF。详情正文预览只适合 HTML 页面，先改用一条 HTML 公告链接测试正文选择器。")
    elif detail_preview_url and not detail_excerpt:
        if detail_config.get("css_selector") or detail_config.get("xpath"):
            suggestions.append("详情规则没有抽到正文。检查选择器是否直接指向正文容器，而不是整页 wrapper、面包屑或附件区域。")
        else:
            suggestions.append("先补一个详情页正文规则。优先填写公告正文容器的 CSS Selector，例如 `.article-content`。")
    elif detail_preview_url and detail_method == "readability":
        suggestions.append("当前正文是 Readability 兜底抽出来的。为了稳定抓取，建议补一个精确的正文容器选择器。")

    return suggestions


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
        detail_selector_config=section.detail_selector_config or {},
        suggested_list_selector_config=crawler_service._suggest_default_list_selector_config(section),
        suggested_detail_selector_config=crawler_service._suggest_default_detail_selector_config(section),
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


def _to_content_file_item(file_record: ContentFile) -> ContentFileItem:
    link = file_record.site_section_link
    section = link.site_section if link else None
    school = section.school if section else None
    content = file_record.content
    text_excerpt = (file_record.text_extracted or "").strip()
    if text_excerpt:
        text_excerpt = text_excerpt[:180].rstrip()
    else:
        text_excerpt = None

    return ContentFileItem(
        id=file_record.id,
        content_id=file_record.content_id,
        site_section_link_id=file_record.site_section_link_id,
        site_section_id=section.id if section else None,
        site_section_name=section.name if section else None,
        school_name=school.name if school else None,
        link_title=link.title if link else None,
        content_title=content.title if content else None,
        file_url=file_record.file_url,
        file_type=file_record.file_type,
        mime_type=file_record.mime_type,
        text_excerpt=text_excerpt,
        parse_status=file_record.parse_status,
        ocr_status=file_record.ocr_status,
        file_meta=file_record.file_meta or {},
        created_at=file_record.created_at,
        updated_at=file_record.updated_at,
    )


def _find_existing_file_parse_job(db: Session, *, content_file_id: str) -> CrawlJob | None:
    rows = db.query(CrawlJob).filter(CrawlJob.status.in_(["pending", "running"])).order_by(CrawlJob.requested_at.desc()).all()
    for row in rows:
        query_payload = dict(row.query or {})
        if query_payload.get("job_kind") != "file_parse":
            continue
        if str(query_payload.get("content_file_id") or "").strip() == content_file_id:
            return row
    return None


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
        list_selector_config={},
        detail_selector_config={},
    )
    section.list_selector_config = build_site_section_list_selector_config(section, payload.list_selector_config)
    section.detail_selector_config = build_site_section_detail_selector_config(section, payload.detail_selector_config)
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


@router.post("/backfill-selector-config", response_model=SiteSectionBackfillSelectorConfigResponse)
def backfill_site_section_selector_config(
    payload: SiteSectionBackfillSelectorConfigRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SiteSectionBackfillSelectorConfigResponse:
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
    updated_ids: list[str] = []
    for section in sections:
        existing_list_config = section.list_selector_config or {}
        existing_detail_config = section.detail_selector_config or {}
        if existing_list_config and existing_detail_config and not payload.overwrite_existing:
            continue
        next_list_config = build_site_section_list_selector_config(
            section,
            {} if payload.overwrite_existing else existing_list_config,
        )
        next_detail_config = build_site_section_detail_selector_config(
            section,
            {} if payload.overwrite_existing else existing_detail_config,
        )
        if next_list_config == existing_list_config and next_detail_config == existing_detail_config:
            continue
        section.list_selector_config = next_list_config
        section.detail_selector_config = next_detail_config
        updated_ids.append(section.id)

    db.commit()
    audit_event(db, request, "site_section.backfill_selector_config", None, {"site_section_ids": updated_ids})
    return SiteSectionBackfillSelectorConfigResponse(
        total_sections=len(sections),
        updated_sections=len(updated_ids),
        items=[_to_site_section_item(section) for section in sections],
    )


@router.post("/bootstrap", response_model=SiteSectionBootstrapResponse)
def bootstrap_site_sections(
    payload: SiteSectionBootstrapRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SiteSectionBootstrapResponse:
    require_admin_request(request)
    try:
        result = bootstrap_site_sections_service(
            db,
            school_name=payload.school_name,
            homepage_url=payload.homepage_url,
            department_name=payload.department_name,
            department_type=payload.department_type,
            seed_urls=payload.seed_urls,
            enabled=payload.enabled,
            queue_discovery=payload.queue_discovery,
            max_sections=payload.max_sections,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit_event(
        db,
        request,
        "site_section.bootstrap",
        None,
        {
            "school_name": payload.school_name,
            "created_sections": result["created_sections"],
            "existing_sections": result["existing_sections"],
            "job_ids": result["job_ids"],
        },
    )
    return SiteSectionBootstrapResponse(
        school_name=result["school"].name,
        homepage_url=result["homepage_url"],
        total_seed_urls=len(result["seed_urls"]),
        total_candidate_sections=result["candidate_count"],
        created_sections=result["created_sections"],
        existing_sections=result["existing_sections"],
        job_ids=result["job_ids"],
        items=[_to_site_section_item(section) for section in result["items"]],
    )


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


@router.patch("/{site_section_id}", response_model=SiteSectionItem)
def update_site_section(
    site_section_id: str,
    payload: SiteSectionUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SiteSectionItem:
    require_admin_request(request)
    section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="site section not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        section.name = payload.name.strip()  # type: ignore[union-attr]
    if "section_type" in updates:
        section.section_type = payload.section_type.strip()  # type: ignore[union-attr]
    if "section_url" in updates:
        section.section_url = payload.section_url.strip()  # type: ignore[union-attr]
    if "discovery_category" in updates:
        section.discovery_category = payload.discovery_category  # type: ignore[assignment]
    if "source_id" in updates:
        section.source_id = payload.source_id
    if "enabled" in updates:
        section.enabled = 1 if payload.enabled else 0
    if "list_selector_config" in updates:
        section.list_selector_config = build_site_section_list_selector_config(section, payload.list_selector_config or {})
    if "detail_selector_config" in updates:
        section.detail_selector_config = build_site_section_detail_selector_config(
            section,
            payload.detail_selector_config or {},
        )

    db.commit()
    db.refresh(section)
    audit_event(db, request, "site_section.update", None, {"site_section_id": section.id})
    return _to_site_section_item(section)


@router.post("/{site_section_id}/preview-selectors", response_model=SiteSectionSelectorPreviewResponse)
def preview_site_section_selectors(
    site_section_id: str,
    payload: SiteSectionSelectorPreviewRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SiteSectionSelectorPreviewResponse:
    require_admin_request(request)
    section = db.query(SiteSection).filter(SiteSection.id == site_section_id).one_or_none()
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="site section not found")

    section_url = str(section.section_url or "").strip()
    if not section_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site section url is empty")

    list_config = build_site_section_list_selector_config(section, payload.list_selector_config or {})
    detail_config = build_site_section_detail_selector_config(section, payload.detail_selector_config or {})
    suggested_list_config = crawler_service._suggest_default_list_selector_config(section)
    suggested_detail_config = crawler_service._suggest_default_detail_selector_config(section)
    warnings: list[str] = []

    try:
        response = crawler_service._fetch_with_retry(section_url)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"failed to fetch section page: {exc}") from exc

    raw_html = response.text or ""
    discovered_links = crawler_service._extract_links_by_selector(raw_html, list_config)
    used_fallback_links = False
    if not discovered_links and list_config.get("fallback_to_all_links"):
        discovered_links = crawler_service._extract_links(raw_html)
        used_fallback_links = True
        warnings.append("列表选择器未命中，预览已退回到全页链接扫描。")

    preview_items: list[SiteSectionSelectorPreviewLinkItem] = []
    seen_urls: set[str] = set()
    for item in discovered_links:
        href = str(item.get("href") or "").strip()
        if not href:
            continue
        absolute_url = urljoin(section_url, href)
        link_text = crawler_service._normalize_link_text(str(item.get("text") or ""), absolute_url)
        if not link_text:
            continue
        if not used_fallback_links and not crawler_service._link_matches_selector_config(
            section_url=section_url,
            absolute_url=absolute_url,
            text=link_text,
            config=list_config,
        ):
            continue
        if absolute_url in seen_urls:
            continue
        seen_urls.add(absolute_url)
        link_type = "pdf" if absolute_url.lower().endswith(".pdf") else "html"
        preview_items.append(SiteSectionSelectorPreviewLinkItem(url=absolute_url, text=link_text, link_type=link_type))
        if len(preview_items) >= 5:
            break

    if not preview_items:
        warnings.append("当前规则没有匹配到可用列表链接。")

    detail_preview_url = (payload.sample_link_url or "").strip() or None
    if not detail_preview_url:
        first_html_item = next((item for item in preview_items if item.link_type == "html"), None)
        detail_preview_url = first_html_item.url if first_html_item else None

    detail_title: str | None = None
    detail_excerpt: str | None = None
    detail_method: str | None = None
    if detail_preview_url:
        if detail_preview_url.lower().endswith(".pdf"):
            warnings.append("当前选中的详情链接是 PDF，正文预览仅支持 HTML 页面。")
        else:
            try:
                detail_response = crawler_service._fetch_with_retry(detail_preview_url)
                detail_raw_html = detail_response.text or ""
                detail_body, detail_method, readability_title = crawler_service._extract_detail_body(
                    detail_raw_html,
                    detail_selector_config=detail_config,
                )
                detail_title = (
                    crawler_service._extract_title(detail_raw_html)
                    or readability_title
                    or next((item.text for item in preview_items if item.url == detail_preview_url), None)
                )
                normalized_detail = " ".join(str(detail_body or "").split())
                detail_excerpt = normalized_detail[:500].rstrip() or None
                if not detail_excerpt:
                    warnings.append("详情选择器没有抽到有效正文，请检查正文区域选择器。")
            except Exception as exc:
                warnings.append(f"详情页预览失败：{exc}")

    suggestions = _build_selector_preview_suggestions(
        list_match_count=len(preview_items),
        detail_preview_url=detail_preview_url,
        detail_excerpt=detail_excerpt,
        detail_method=detail_method,
        used_fallback_links=used_fallback_links,
        list_config=list_config,
        detail_config=detail_config,
    )

    audit_event(db, request, "site_section.preview_selector_config", None, {"site_section_id": section.id})
    return SiteSectionSelectorPreviewResponse(
        section_url=section_url,
        suggested_list_selector_config=suggested_list_config,
        suggested_detail_selector_config=suggested_detail_config,
        list_match_count=len(preview_items),
        list_preview_items=preview_items,
        detail_preview_url=detail_preview_url,
        detail_title=detail_title,
        detail_excerpt=detail_excerpt,
        detail_extraction_method=detail_method,
        warnings=warnings,
        suggestions=suggestions,
    )


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


@router.get("/content-files", response_model=ContentFileListResponse)
def list_content_files(
    request: Request,
    db: Session = Depends(get_db),
    parse_status: str | None = Query(default=None),
    ocr_status: str | None = Query(default=None),
    site_section_id: str | None = Query(default=None),
    file_type: str | None = Query(default="pdf"),
    page_size: int = Query(default=20, ge=1, le=100),
) -> ContentFileListResponse:
    require_admin_request(request)
    query = db.query(ContentFile)
    if parse_status:
        query = query.filter(ContentFile.parse_status == parse_status.strip())
    if ocr_status:
        query = query.filter(ContentFile.ocr_status == ocr_status.strip())
    if site_section_id:
        query = query.filter(ContentFile.site_section_link_id.is_not(None)).join(SiteSectionLink).filter(
            SiteSectionLink.site_section_id == site_section_id
        )
    if file_type:
        query = query.filter(ContentFile.file_type == file_type.strip())

    total = query.count()
    rows = query.order_by(ContentFile.updated_at.desc()).limit(page_size).all()
    return ContentFileListResponse(total=total, items=[_to_content_file_item(row) for row in rows])


@router.post("/content-files/{content_file_id}/retry-parse", response_model=ContentFileRetryParseResponse)
def retry_content_file_parse(
    content_file_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ContentFileRetryParseResponse:
    require_admin_request(request)
    file_record = db.query(ContentFile).filter(ContentFile.id == content_file_id).one_or_none()
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="content file not found")

    existing_job = _find_existing_file_parse_job(db, content_file_id=content_file_id)
    if existing_job is not None:
        return ContentFileRetryParseResponse(
            content_file_id=file_record.id,
            job_id=existing_job.id,
            status="existing",
            parse_status=file_record.parse_status,
        )

    link = file_record.site_section_link
    section = link.site_section if link else None
    job = CrawlJob(
        category=section.discovery_category if section else "announcement",
        status="pending",
        requested_at=utcnow(),
        message=f"queued manual retry parse for content file {file_record.id}",
        query={
            "job_kind": "file_parse",
            "content_file_id": file_record.id,
            "site_section_id": section.id if section else None,
            "site_section_link_id": link.id if link else None,
            "source_url": file_record.file_url,
            "title": link.title if link else None,
            "school_name": section.school.name if section and section.school else None,
            "department_name": section.department.name if section and section.department else None,
            "section_type": section.section_type if section else None,
        },
    )
    db.add(job)
    db.flush()

    file_record.parse_status = "pending"
    file_record.ocr_status = "not_started"
    file_record.file_meta = {
        **dict(file_record.file_meta or {}),
        "retry_parse_job_id": job.id,
        "retry_requested_at": utcnow().isoformat(),
    }
    if link is not None:
        link.crawl_job_id = job.id
        link.status = "file_recorded"

    db.commit()
    audit_event(db, request, "site_section.content_file.retry_parse", None, {"content_file_id": file_record.id, "job_id": job.id})
    return ContentFileRetryParseResponse(
        content_file_id=file_record.id,
        job_id=job.id,
        status="queued",
        parse_status=file_record.parse_status,
    )
