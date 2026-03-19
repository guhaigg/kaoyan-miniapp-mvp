from datetime import datetime, timezone
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit, get_portal_user_optional
from ..models import Content, CrawlJob, School
from ..schemas import (
    AdjustmentSearchRequest,
    AnnouncementSearchRequest,
    SearchItem,
    SearchResponse,
)
from ..services.historical_intelligence import (
    build_search_insight,
    build_release_timing_insight,
    load_school_intelligence_for_search,
    load_mentor_radar_for_search,
    load_profiles_for_search,
    load_release_timing_for_search,
    normalize_school_name,
)
from ..services.search_cache import search_response_cache

router = APIRouter(prefix="/search", tags=["search"])
ANONYMOUS_PREVIEW_LIMIT = 2
SCHOOL_SUFFIXES = (
    "大学",
    "学院",
    "研究院",
    "研究所",
    "师范大学",
    "理工大学",
    "工业大学",
    "科技大学",
    "农业大学",
    "中医药大学",
)


def _dedupe_terms(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _build_school_search_terms(value: str) -> list[str]:
    raw = value.strip()
    compact = re.sub(r"\s+", "", raw)
    terms = [raw, compact]
    for suffix in SCHOOL_SUFFIXES:
        if compact.endswith(suffix) and len(compact) > len(suffix) + 1:
            terms.append(compact[: -len(suffix)])
    return _dedupe_terms(terms)


def _build_keyword_terms(value: str) -> list[str]:
    raw = value.strip()
    compact = re.sub(r"\s+", "", raw)
    split_terms = [part.strip() for part in re.split(r"[\s,，、/|;；]+", raw) if part.strip()]
    return _dedupe_terms([raw, compact, *split_terms])


def _build_major_terms(value: str) -> list[str]:
    raw = value.strip()
    compact = re.sub(r"\s+", "", raw)
    digits = re.sub(r"\D+", "", raw)
    terms = [raw, compact]
    if digits:
        terms.append(digits)
        if len(digits) > 4:
            terms.append(digits[:4])
    return _dedupe_terms(terms)


def _apply_common_filters(query, payload: AnnouncementSearchRequest | AdjustmentSearchRequest):
    if payload.school_name or payload.keywords:
        query = query.join(School, isouter=True)
    if payload.school_name:
        terms = _build_school_search_terms(payload.school_name.strip())
        query = query.filter(or_(*[School.name.ilike(f"%{term}%") for term in terms]))
    if payload.keywords:
        keyword_terms = _build_keyword_terms(payload.keywords.strip())
        query = query.filter(
            and_(
                *[
                    or_(
                        Content.title.ilike(f"%{term}%"),
                        Content.body.ilike(f"%{term}%"),
                        Content.major.ilike(f"%{term}%"),
                        School.name.ilike(f"%{term}%"),
                    )
                    for term in keyword_terms
                ]
            )
        )
    if payload.start_date:
        query = query.filter(Content.published_at >= payload.start_date)
    if payload.end_date:
        query = query.filter(Content.published_at <= payload.end_date)
    return query


def _adjustment_outlook_rank(value: str | None) -> int:
    if value == "high":
        return 3
    if value == "reach":
        return 2
    if value == "cautious":
        return 1
    return 0


def _school_confidence_rank(value: str | None) -> int:
    if value == "连续活跃":
        return 3
    if value == "持续关注":
        return 2
    if value == "样本有限":
        return 1
    return 0


def _is_adjustment_urgent(item: SearchItem) -> bool:
    text = " ".join(
        [
            item.title or "",
            item.summary or "",
            item.major or "",
            " ".join(item.tags or []),
        ]
    )
    return bool(text) and any(marker in text for marker in ["紧急", "截止", "补录", "缺额"])


def _adjustment_sort_key(item: SearchItem) -> tuple[int, int, int, int, int, int, int, float]:
    has_reference_link = int(
        bool(item.source_url)
        or bool(item.school_intelligence and item.school_intelligence.reference_urls)
    )
    warning_penalty = -(item.mentor_radar.warning_count if item.mentor_radar is not None else 0)
    published_at = item.published_at or item.updated_at
    published_ts = published_at.timestamp() if published_at is not None else 0.0
    return (
        int(_is_adjustment_urgent(item)),
        _adjustment_outlook_rank(item.historical_adjustment.outlook if item.historical_adjustment is not None else None),
        _school_confidence_rank(item.school_intelligence.confidence_label if item.school_intelligence is not None else None),
        item.historical_adjustment.sample_count if item.historical_adjustment is not None else 0,
        item.release_timing.sample_count if item.release_timing is not None else 0,
        has_reference_link,
        warning_penalty,
        published_ts,
    )


def _to_response(
    db: Session,
    payload: AnnouncementSearchRequest | AdjustmentSearchRequest,
    request_id: str,
    items: list[Content],
    total: int,
    source_breakdown: dict[str, int],
    refresh_job_id: str | None,
    *,
    authenticated: bool,
    access_limited: bool = False,
    preview_limit: int | None = None,
) -> SearchResponse:
    historical_profiles = (
        load_profiles_for_search(
            db,
            [row.school.name if row.school else "" for row in items],
        )
        if isinstance(payload, AdjustmentSearchRequest)
        else {}
    )
    mentor_radar = load_mentor_radar_for_search(db, [row.school.name if row.school else "" for row in items])
    release_timings = load_release_timing_for_search(db, [row.school.name if row.school else "" for row in items])
    school_intelligence = load_school_intelligence_for_search(db, [row.school.name if row.school else "" for row in items])
    serialized = []
    for row in items:
        school_name = row.school.name if row.school else None
        extra = dict(row.extra or {})
        adjustment_meta = dict(extra.get("adjustment_meta") or {})
        historical_adjustment = None
        if isinstance(payload, AdjustmentSearchRequest) and school_name:
            school_profiles = historical_profiles.get(normalize_school_name(school_name), [])
            insight = build_search_insight(
                school_profiles,
                major_codes=[str(code) for code in (adjustment_meta.get("major_codes") or []) if str(code or "").strip()],
                major_name=row.major,
                study_modes=[str(mode) for mode in (adjustment_meta.get("study_modes") or []) if str(mode or "").strip()],
                candidate_score=payload.candidate_score,
            )
            if insight is not None:
                historical_adjustment = insight.__dict__
        mentor_signal = mentor_radar.get(normalize_school_name(school_name)) if school_name else None
        release_timing_signal = (
            build_release_timing_insight(release_timings.get(normalize_school_name(school_name)))
            if school_name
            else None
        )
        school_signal = school_intelligence.get(normalize_school_name(school_name)) if school_name else None
        serialized.append(
            SearchItem(
                id=row.id,
                category=row.category,
                school_name=school_name,
                title=row.title,
                summary=row.summary,
                tags=[str(tag) for tag in (extra.get("tags") or []) if str(tag or "").strip()],
                notice_kind=str((extra.get("notice_kind") or "")).strip() or None,
                pdf_parse_status=str((extra.get("pdf_parse_status") or "")).strip() or None,
                source_url=row.source_url or (school_signal.reference_urls[0] if school_signal and school_signal.reference_urls else None),
                source_type=row.source_type,
                published_at=row.published_at,
                region=row.region,
                major=row.major,
                adjustment_major_codes=[
                    str(code) for code in (adjustment_meta.get("major_codes") or []) if str(code or "").strip()
                ],
                adjustment_study_modes=[
                    str(mode) for mode in (adjustment_meta.get("study_modes") or []) if str(mode or "").strip()
                ],
                adjustment_has_vacancy=(
                    bool(adjustment_meta.get("has_vacancy"))
                    if "has_vacancy" in adjustment_meta
                    else None
                ),
                historical_adjustment=historical_adjustment,
                mentor_radar=mentor_signal.__dict__ if mentor_signal is not None else None,
                release_timing=release_timing_signal.__dict__ if release_timing_signal is not None else None,
                school_intelligence=school_signal.__dict__ if school_signal is not None else None,
                updated_at=row.updated_at,
            )
        )
    last_updated = max((x.updated_at for x in items), default=None)
    if isinstance(payload, AdjustmentSearchRequest):
        serialized.sort(key=_adjustment_sort_key, reverse=True)
    return SearchResponse(
        request_id=request_id,
        mode="hybrid_refresh" if payload.refresh else "cache",
        authenticated=authenticated,
        access_limited=access_limited,
        preview_limit=preview_limit,
        items=serialized,
        total=total,
        page=payload.page,
        page_size=payload.page_size,
        source_breakdown=source_breakdown,
        last_updated_at=last_updated,
        refresh_job_id=refresh_job_id,
    )


def _normalize_public_search_payload(payload: AnnouncementSearchRequest | AdjustmentSearchRequest):
    return payload.model_copy(update={"page": 1, "page_size": ANONYMOUS_PREVIEW_LIMIT, "refresh": False})


def _audit_search_event(
    db: Session,
    request: Request,
    event_type: str,
    request_id: str,
    *,
    refresh: bool,
    cache_hit: bool,
    portal_user_id: str | None,
) -> None:
    audit_event(
        db,
        request,
        event_type,
        None,
        {
            "request_id": request_id,
            "refresh": refresh,
            "cache_hit": cache_hit,
            "portal_user_id": portal_user_id,
        },
    )


def _create_refresh_job(db: Session, category: str, payload: dict, user_id: str | None) -> str:
    job = CrawlJob(
        category=category,
        status="pending",
        query=payload,
        requested_by_user_id=user_id,
        requested_at=datetime.now(timezone.utc),
        message="queued by api",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


@router.post("/announcements", response_model=SearchResponse)
def search_announcements(payload: AnnouncementSearchRequest, request: Request, db: Session = Depends(get_db)) -> SearchResponse:
    user = get_portal_user_optional(request, db)
    effective_payload = payload if user else _normalize_public_search_payload(payload)
    identity = user.id if user else (request.client.host if request.client else "unknown")
    enforce_rate_limit(request, f"search_announcement:{identity}")

    request_id = str(uuid4())
    cached = search_response_cache.get("announcement", effective_payload, request_id=request_id)
    if cached is not None:
        _audit_search_event(
            db,
            request,
            "search.announcements",
            request_id,
            refresh=False,
            cache_hit=True,
            portal_user_id=user.id if user else None,
        )
        return cached
    base_query = db.query(Content).filter(Content.category == "announcement")
    base_query = _apply_common_filters(base_query, effective_payload)

    total = base_query.count()
    rows = (
        base_query.order_by(Content.published_at.is_(None), Content.published_at.desc(), Content.updated_at.desc())
        .offset((effective_payload.page - 1) * effective_payload.page_size)
        .limit(effective_payload.page_size)
        .all()
    )
    stats_rows = base_query.with_entities(Content.source_type, func.count(Content.id)).group_by(Content.source_type).all()
    source_breakdown = {k: int(v) for k, v in stats_rows}

    refresh_job_id = None
    if effective_payload.refresh:
        refresh_job_id = _create_refresh_job(db, "announcement", payload.model_dump(mode="json"), user.id if user else None)
    response = _to_response(
        db,
        effective_payload,
        request_id,
        rows,
        total,
        source_breakdown,
        refresh_job_id,
        authenticated=bool(user),
        access_limited=not bool(user),
        preview_limit=ANONYMOUS_PREVIEW_LIMIT if not user else None,
    )
    search_response_cache.set("announcement", effective_payload, response)
    _audit_search_event(
        db,
        request,
        "search.announcements",
        request_id,
        refresh=effective_payload.refresh,
        cache_hit=False,
        portal_user_id=user.id if user else None,
    )
    return response


@router.post("/adjustments", response_model=SearchResponse)
def search_adjustments(payload: AdjustmentSearchRequest, request: Request, db: Session = Depends(get_db)) -> SearchResponse:
    user = get_portal_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="login required for adjustment search",
        )
    identity = user.id if user else (request.client.host if request.client else "unknown")
    enforce_rate_limit(request, f"search_adjustment:{identity}")

    request_id = str(uuid4())
    cached = search_response_cache.get("adjustment", payload, request_id=request_id)
    if cached is not None:
        _audit_search_event(
            db,
            request,
            "search.adjustments",
            request_id,
            refresh=False,
            cache_hit=True,
            portal_user_id=user.id if user else None,
        )
        return cached
    base_query = db.query(Content).filter(Content.category == "adjustment")
    base_query = _apply_common_filters(base_query, payload)
    if payload.major:
        major_terms = _build_major_terms(payload.major.strip())
        base_query = base_query.filter(
            or_(
                *[
                    or_(
                        Content.major.ilike(f"%{term}%"),
                        Content.title.ilike(f"%{term}%"),
                        Content.body.ilike(f"%{term}%"),
                    )
                    for term in major_terms
                ]
            )
        )
    if payload.region:
        base_query = base_query.filter(Content.region.ilike(f"%{payload.region.strip()}%"))

    total = base_query.count()
    rows = (
        base_query.order_by(Content.published_at.is_(None), Content.published_at.desc(), Content.updated_at.desc())
        .offset((payload.page - 1) * payload.page_size)
        .limit(payload.page_size)
        .all()
    )
    stats_rows = base_query.with_entities(Content.source_type, func.count(Content.id)).group_by(Content.source_type).all()
    source_breakdown = {k: int(v) for k, v in stats_rows}

    refresh_job_id = None
    if payload.refresh:
        refresh_job_id = _create_refresh_job(db, "adjustment", payload.model_dump(mode="json"), user.id if user else None)
    response = _to_response(
        db,
        payload,
        request_id,
        rows,
        total,
        source_breakdown,
        refresh_job_id,
        authenticated=True,
    )
    search_response_cache.set("adjustment", payload, response)
    _audit_search_event(
        db,
        request,
        "search.adjustments",
        request_id,
        refresh=payload.refresh,
        cache_hit=False,
        portal_user_id=user.id if user else None,
    )
    return response
