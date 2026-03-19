from datetime import datetime, timezone
import re
from uuid import uuid4
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, enforce_rate_limit, get_portal_user_optional
from ..models import AdjustmentOpportunity, Content, CrawlJob, HistoricalAdjustmentProfile, School
from ..schemas import (
    AdjustmentSearchDetailResponse,
    AdjustmentSearchLinkItem,
    AdjustmentSearchRequest,
    AnnouncementSearchRequest,
    SearchItem,
    SearchResponse,
)
from ..services.historical_intelligence import (
    build_search_insight,
    build_release_timing_insight,
    load_mentor_review_excerpts,
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
DEPARTMENT_HINT_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9（）()·、]+?(?:学院|研究院|研究所|中心))")


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


def _build_exact_school_terms(value: str) -> list[str]:
    raw = value.strip()
    compact = re.sub(r"\s+", "", raw)
    return _dedupe_terms([raw, compact])


def _build_keyword_terms(value: str) -> list[str]:
    raw = value.strip()
    compact = re.sub(r"\s+", "", raw)
    split_terms = [part.strip() for part in re.split(r"[\s,，、/|;；]+", raw) if part.strip()]
    return _dedupe_terms([raw, compact, *split_terms])


def _extract_department_hints(*texts: str | None) -> list[str]:
    values: list[str] = []
    for text in texts:
        content = str(text or "").strip()
        if not content:
            continue
        for match in DEPARTMENT_HINT_PATTERN.findall(content):
            normalized = str(match).strip(" ，,、;；:：")
            normalized = re.sub(r"^[\u4e00-\u9fa5A-Za-z0-9（）()·、]+大学", "", normalized)
            if normalized and not normalized.endswith("大学"):
                values.append(normalized)
    return _dedupe_terms(values)


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
        terms = _build_exact_school_terms(payload.school_name.strip())
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
                        Content.region.ilike(f"%{term}%"),
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


def _apply_adjustment_opportunity_filters(query, payload: AdjustmentSearchRequest):
    if payload.school_name:
        terms = _build_exact_school_terms(payload.school_name.strip())
        query = query.filter(or_(*[AdjustmentOpportunity.school_name.ilike(f"%{term}%") for term in terms]))
    if payload.keywords:
        keyword_terms = _build_keyword_terms(payload.keywords.strip())
        query = query.filter(
            and_(
                *[
                    or_(
                        AdjustmentOpportunity.school_name.ilike(f"%{term}%"),
                        AdjustmentOpportunity.department_name.ilike(f"%{term}%"),
                        AdjustmentOpportunity.major_name.ilike(f"%{term}%"),
                        AdjustmentOpportunity.region_name.ilike(f"%{term}%"),
                        AdjustmentOpportunity.title.ilike(f"%{term}%"),
                        AdjustmentOpportunity.summary.ilike(f"%{term}%"),
                    )
                    for term in keyword_terms
                ]
            )
        )
    if payload.major:
        major_terms = _build_major_terms(payload.major.strip())
        query = query.filter(
            or_(
                *[
                    or_(
                        AdjustmentOpportunity.major_name.ilike(f"%{term}%"),
                        AdjustmentOpportunity.major_code.ilike(f"%{term}%"),
                        AdjustmentOpportunity.title.ilike(f"%{term}%"),
                    )
                    for term in major_terms
                ]
            )
        )
    if payload.region:
        query = query.filter(AdjustmentOpportunity.region_name.ilike(f"%{payload.region.strip()}%"))
    return query


def _append_unique_link(links: list[AdjustmentSearchLinkItem], *, label: str, url: str | None, link_type: str | None = None, source: str | None = None):
    normalized = str(url or "").strip()
    if not normalized:
        return
    if any(item.url == normalized for item in links):
        return
    links.append(
        AdjustmentSearchLinkItem(
            label=label,
            url=normalized,
            link_type=link_type,
            source=source,
        )
    )


def _build_adjustment_detail_from_content(
    db: Session,
    row: Content,
) -> AdjustmentSearchDetailResponse:
    school_name = row.school.name if row.school else None
    normalized_school_name = normalize_school_name(school_name) if school_name else ""
    extra = dict(row.extra or {})
    adjustment_meta = dict(extra.get("adjustment_meta") or {})
    historical_profiles = load_profiles_for_search(db, [school_name] if school_name else [])
    mentor_radar = load_mentor_radar_for_search(db, [school_name] if school_name else [])
    release_timings = load_release_timing_for_search(db, [school_name] if school_name else [])
    school_intelligence = load_school_intelligence_for_search(db, [school_name] if school_name else [])

    insight = None
    if school_name:
        insight = build_search_insight(
            historical_profiles.get(normalized_school_name, []),
            major_codes=[str(code) for code in (adjustment_meta.get("major_codes") or []) if str(code or "").strip()],
            major_name=row.major,
            study_modes=[str(mode) for mode in (adjustment_meta.get("study_modes") or []) if str(mode or "").strip()],
            candidate_score=None,
        )

    mentor_signal = mentor_radar.get(normalized_school_name) if school_name else None
    mentor_reviews = load_mentor_review_excerpts(
        db,
        school_name=school_name,
        department_name=str(extra.get("department_name") or "").strip() or None,
        limit=5,
    )
    release_signal = build_release_timing_insight(release_timings.get(normalized_school_name)) if school_name else None
    school_signal = school_intelligence.get(normalized_school_name) if school_name else None

    links: list[AdjustmentSearchLinkItem] = []
    _append_unique_link(links, label="原始链接", url=row.source_url, link_type="source", source=row.source_type)
    for item in extra.get("outbound_links") or []:
        if not isinstance(item, dict):
            continue
        _append_unique_link(
            links,
            label=str(item.get("text") or item.get("title") or "正文外链"),
            url=str(item.get("url") or "").strip(),
            link_type=str(item.get("link_type") or "external"),
            source="content_outbound",
        )
    if school_signal is not None:
        for index, url in enumerate(school_signal.reference_urls, start=1):
            _append_unique_link(
                links,
                label=f"历史参考 {index}",
                url=url,
                link_type="reference",
                source="school_intelligence",
            )

    return AdjustmentSearchDetailResponse(
        id=row.id,
        item_kind="content",
        category=row.category,
        notice_kind=str((extra.get("notice_kind") or "")).strip() or None,
        source_type=row.source_type,
        title=row.title,
        school_name=school_name,
        department_name=str(extra.get("department_name") or "").strip() or None,
        region=row.region,
        major=row.major,
        major_code=next((str(code) for code in (adjustment_meta.get("major_codes") or []) if str(code or "").strip()), None),
        school_code=None,
        school_tier=None,
        study_mode=next((str(mode) for mode in (adjustment_meta.get("study_modes") or []) if str(mode or "").strip()), None),
        verification_status=None,
        vacancy_count=None,
        min_score=insight.min_score if insight is not None else None,
        avg_score=insight.avg_score if insight is not None else None,
        max_score=insight.max_score if insight is not None else None,
        published_at=row.published_at,
        captured_at=None,
        updated_at=row.updated_at,
        summary=row.summary,
        body=row.body,
        tags=[str(tag) for tag in (extra.get("tags") or []) if str(tag or "").strip()],
        source_url=row.source_url,
        source_dataset_key=None,
        links=links,
        historical_adjustment=insight.__dict__ if insight is not None else None,
        mentor_radar=mentor_signal.__dict__ if mentor_signal is not None else None,
        mentor_reviews=[review.__dict__ for review in mentor_reviews],
        release_timing=release_signal.__dict__ if release_signal is not None else None,
        school_intelligence=school_signal.__dict__ if school_signal is not None else None,
        meta_json={
            "adjustment_meta": adjustment_meta,
            "detail_extraction_method": extra.get("detail_extraction_method"),
            "pdf_parse_status": extra.get("pdf_parse_status"),
        },
    )


def _build_adjustment_detail_from_opportunity(
    db: Session,
    row: AdjustmentOpportunity,
) -> AdjustmentSearchDetailResponse:
    merged_rows = _load_merged_adjustment_opportunity_rows(db, row)
    merged = _merge_adjustment_opportunity_rows(merged_rows or [row])[0]
    row = merged["primary"]
    display_departments = _resolve_adjustment_departments(db, row, merged["department_names"])
    normalized_school_name = normalize_school_name(row.school_name)
    historical_profiles = load_profiles_for_search(db, [row.school_name])
    mentor_radar = load_mentor_radar_for_search(db, [row.school_name])
    release_timings = load_release_timing_for_search(db, [row.school_name])
    school_intelligence = load_school_intelligence_for_search(db, [row.school_name])
    insight = build_search_insight(
        historical_profiles.get(normalized_school_name, []),
        major_codes=[row.major_code] if row.major_code else [],
        major_name=row.major_name,
        study_modes=[row.study_mode] if row.study_mode else [],
        candidate_score=None,
    )
    mentor_signal = mentor_radar.get(normalized_school_name)
    mentor_reviews = load_mentor_review_excerpts(
        db,
        school_name=row.school_name,
        department_name=row.department_name,
        limit=5,
    )
    release_signal = build_release_timing_insight(release_timings.get(normalized_school_name))
    school_signal = school_intelligence.get(normalized_school_name)
    meta = dict(merged["meta_json"] or {})
    links: list[AdjustmentSearchLinkItem] = []
    _append_unique_link(links, label="原始链接", url=row.source_url, link_type="source", source=row.source_type)
    for index, url in enumerate([str(url) for url in (merged["reference_urls"] or []) if str(url or "").strip()], start=1):
        _append_unique_link(links, label=f"表格参考 {index}", url=url, link_type="reference", source="table_reference")
    if school_signal is not None:
        for index, url in enumerate(school_signal.reference_urls, start=1):
            _append_unique_link(links, label=f"历史参考 {index}", url=url, link_type="reference", source="school_intelligence")

    return AdjustmentSearchDetailResponse(
        id=row.id,
        item_kind="opportunity",
        category="adjustment",
        notice_kind="historical_opportunity",
        source_type=f"historical_{row.source_type}",
        title=row.title,
        school_name=row.school_name,
        department_name=" / ".join(display_departments) if display_departments else row.department_name,
        region=row.region_name,
        major=row.major_name,
        major_code=row.major_code,
        school_code=row.school_code,
        school_tier=row.school_tier,
        study_mode=row.study_mode,
        verification_status=" / ".join(merged["verification_statuses"]) if merged["verification_statuses"] else row.verification_status,
        vacancy_count=row.vacancy_count,
        min_score=merged["min_score"],
        avg_score=merged["avg_score"],
        max_score=merged["max_score"],
        published_at=row.published_at,
        captured_at=row.captured_at,
        updated_at=row.updated_at,
        summary=_build_adjustment_opportunity_summary(row, insight),
        body=row.summary,
        tags=[
            str(tag)
            for tag in [
                _historical_source_label(row.source_type),
                row.region_name,
                row.major_name,
                row.major_code,
                row.school_tier,
            ]
            if str(tag or "").strip()
        ],
        source_url=row.source_url,
        source_dataset_key=row.source_dataset_key,
        links=links,
        historical_adjustment=insight.__dict__ if insight is not None else None,
        mentor_radar=mentor_signal.__dict__ if mentor_signal is not None else None,
        mentor_reviews=[review.__dict__ for review in mentor_reviews],
        release_timing=release_signal.__dict__ if release_signal is not None else None,
        school_intelligence=school_signal.__dict__ if school_signal is not None else None,
        meta_json=meta,
    )


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
                item_kind="content",
                category=row.category,
                school_name=school_name,
                department_name=str(extra.get("department_name") or "").strip() or None,
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
                merged_count=1,
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


def _historical_source_label(source_type: str) -> str:
    labels = {
        "adjustment_stats": "历史调剂统计",
        "landing": "调剂上岸样本",
        "future_program": "2026 招生专业",
        "notice_reference": "历史调剂来源",
        "snapshot": "历史调剂快照",
        "adjustment_notice": "表格调剂公告",
        "stats": "历史调剂统计",
    }
    return labels.get(source_type, source_type)

def _build_adjustment_opportunity_summary(row: AdjustmentOpportunity, insight) -> str:
    parts = []
    if row.year:
        parts.append(f"{row.year} 年 {_historical_source_label(row.source_type)}")
    else:
        parts.append(_historical_source_label(row.source_type))
    if row.region_name:
        parts.append(row.region_name)
    if row.verification_status:
        parts.append(row.verification_status)
    if row.vacancy_count:
        parts.append(f"计划 {row.vacancy_count}")
    if row.min_score is not None:
        parts.append(f"最低 {row.min_score}")
    if row.avg_score is not None:
        parts.append(f"均分 {round(row.avg_score)}")
    if insight is not None and insight.outlook_label:
        parts.append(insight.outlook_label)
    if row.summary:
        parts.append(row.summary)
    return " · ".join(parts)


def _normalize_merge_major_token(row: AdjustmentOpportunity) -> str:
    return (row.major_code or row.major_name_normalized or "").strip()


def _build_adjustment_opportunity_merge_key(row: AdjustmentOpportunity) -> str:
    return "|".join(
        [
            row.school_name_normalized or "",
            str(row.year or ""),
            _normalize_merge_major_token(row),
            str(row.vacancy_count if row.vacancy_count is not None else ""),
        ]
    )


def _load_merged_adjustment_opportunity_rows(db: Session, row: AdjustmentOpportunity) -> list[AdjustmentOpportunity]:
    query = db.query(AdjustmentOpportunity).filter(
        AdjustmentOpportunity.school_name_normalized == row.school_name_normalized,
    )
    if row.year is None:
        query = query.filter(AdjustmentOpportunity.year.is_(None))
    else:
        query = query.filter(AdjustmentOpportunity.year == row.year)

    if row.major_code:
        query = query.filter(AdjustmentOpportunity.major_code == row.major_code)
    elif row.major_name_normalized:
        query = query.filter(AdjustmentOpportunity.major_name_normalized == row.major_name_normalized)
    else:
        query = query.filter(
            or_(
                AdjustmentOpportunity.major_code.is_(None),
                AdjustmentOpportunity.major_code == "",
            )
        ).filter(
            or_(
                AdjustmentOpportunity.major_name_normalized.is_(None),
                AdjustmentOpportunity.major_name_normalized == "",
            )
        )

    if row.vacancy_count is None:
        query = query.filter(AdjustmentOpportunity.vacancy_count.is_(None))
    else:
        query = query.filter(AdjustmentOpportunity.vacancy_count == row.vacancy_count)

    rows = query.all()
    return [candidate for candidate in rows if _build_adjustment_opportunity_merge_key(candidate) == _build_adjustment_opportunity_merge_key(row)]


def _resolve_adjustment_departments(
    db: Session,
    row: AdjustmentOpportunity,
    department_names: list[str],
) -> list[str]:
    if department_names:
        return department_names

    inferred = _extract_department_hints(row.title, row.summary)
    if inferred:
        return inferred

    query = db.query(AdjustmentOpportunity.department_name).filter(
        AdjustmentOpportunity.school_name_normalized == row.school_name_normalized,
        AdjustmentOpportunity.department_name.is_not(None),
    )
    if row.major_code:
        query = query.filter(AdjustmentOpportunity.major_code == row.major_code)
    elif row.major_name_normalized:
        query = query.filter(AdjustmentOpportunity.major_name_normalized == row.major_name_normalized)
    rows = query.limit(10).all()
    fallback = _dedupe_terms([value for (value,) in rows if str(value or "").strip()])
    return fallback[:3]


def _merge_adjustment_opportunity_rows(rows: list[AdjustmentOpportunity]) -> list[dict]:
    grouped: dict[str, list[AdjustmentOpportunity]] = defaultdict(list)
    for row in rows:
        grouped[_build_adjustment_opportunity_merge_key(row)].append(row)

    merged_rows: list[dict] = []
    for grouped_rows in grouped.values():
        ordered = sorted(
            grouped_rows,
            key=lambda row: (
                int(bool((row.source_url or "").strip())),
                row.published_at or datetime.min.replace(tzinfo=timezone.utc),
                row.updated_at,
            ),
            reverse=True,
        )
        primary = ordered[0]
        department_names = [row.department_name for row in ordered if str(row.department_name or "").strip()]
        unique_departments: list[str] = []
        seen_departments: set[str] = set()
        for value in department_names:
            text = str(value).strip()
            if text and text not in seen_departments:
                seen_departments.add(text)
                unique_departments.append(text)

        verification_values = [row.verification_status for row in ordered if str(row.verification_status or "").strip()]
        unique_verification: list[str] = []
        seen_verification: set[str] = set()
        for value in verification_values:
            text = str(value).strip()
            if text and text not in seen_verification:
                seen_verification.add(text)
                unique_verification.append(text)

        reference_urls: list[str] = []
        seen_urls: set[str] = set()
        for row in ordered:
            meta = dict(row.meta_json or {})
            urls = [row.source_url, meta.get("source_url"), meta.get("top_source_url"), *(meta.get("reference_urls") or [])]
            for candidate in urls:
                url = str(candidate or "").strip()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    reference_urls.append(url)

        dataset_keys = sorted({str(row.source_dataset_key) for row in ordered if str(row.source_dataset_key or "").strip()})
        source_types = sorted({str(row.source_type) for row in ordered if str(row.source_type or "").strip()})

        min_scores = [row.min_score for row in ordered if row.min_score is not None]
        avg_scores = [row.avg_score for row in ordered if row.avg_score is not None]
        max_scores = [row.max_score for row in ordered if row.max_score is not None]

        merged_meta = dict(primary.meta_json or {})
        merged_meta["reference_urls"] = reference_urls
        merged_meta["source_dataset_keys"] = dataset_keys
        merged_meta["source_types"] = source_types
        merged_meta["merged_row_ids"] = [row.id for row in ordered]
        merged_meta["merged_departments"] = unique_departments
        merged_meta["merged_verification_statuses"] = unique_verification

        merged_rows.append(
            {
                "primary": primary,
                "rows": ordered,
                "department_names": unique_departments,
                "verification_statuses": unique_verification,
                "reference_urls": reference_urls,
                "dataset_keys": dataset_keys,
                "source_types": source_types,
                "min_score": min(min_scores) if min_scores else None,
                "avg_score": (sum(avg_scores) / len(avg_scores)) if avg_scores else None,
                "max_score": max(max_scores) if max_scores else None,
                "merged_count": len(ordered),
                "meta_json": merged_meta,
            }
        )
    return merged_rows


def _to_adjustment_opportunity_response(
    db: Session,
    payload: AdjustmentSearchRequest,
    request_id: str,
    rows: list[AdjustmentOpportunity],
    total: int,
    source_breakdown: dict[str, int],
    refresh_job_id: str | None,
    *,
    authenticated: bool,
) -> SearchResponse:
    school_names = [row.school_name for row in rows if row.school_name]
    historical_profiles = load_profiles_for_search(db, school_names)
    mentor_radar = load_mentor_radar_for_search(db, school_names)
    release_timings = load_release_timing_for_search(db, school_names)
    school_intelligence = load_school_intelligence_for_search(db, school_names)
    merged_rows = _merge_adjustment_opportunity_rows(rows)
    serialized: list[SearchItem] = []
    for merged in merged_rows:
        row = merged["primary"]
        display_departments = _resolve_adjustment_departments(db, row, merged["department_names"])
        school_name = row.school_name
        normalized_school_name = normalize_school_name(school_name)
        school_profiles = historical_profiles.get(normalized_school_name, [])
        insight = build_search_insight(
            school_profiles,
            major_codes=[row.major_code] if row.major_code else [],
            major_name=row.major_name,
            study_modes=[row.study_mode] if row.study_mode else [],
            candidate_score=payload.candidate_score,
        )
        mentor_signal = mentor_radar.get(normalized_school_name)
        release_timing_signal = build_release_timing_insight(release_timings.get(normalized_school_name))
        school_signal = school_intelligence.get(normalized_school_name)
        meta = dict(merged["meta_json"] or {})
        reference_urls = [str(url) for url in (merged["reference_urls"] or []) if str(url or "").strip()]
        source_url = (
            (row.source_url or "").strip()
            or
            str(meta.get("source_url") or "").strip()
            or str(meta.get("top_source_url") or "").strip()
            or (reference_urls[0] if reference_urls else "")
            or (school_signal.reference_urls[0] if school_signal and school_signal.reference_urls else "")
        ) or None
        tags = [
            str(tag)
            for tag in [
                _historical_source_label(row.source_type),
                row.region_name,
                row.major_name,
                row.major_code,
                row.school_tier,
            ]
            if str(tag or "").strip()
        ]
        serialized.append(
            SearchItem(
                id=row.id,
                item_kind="opportunity",
                category="adjustment",
                school_name=school_name,
                department_name=" / ".join(display_departments[:2]) if display_departments else row.department_name,
                title=row.title,
                summary=_build_adjustment_opportunity_summary(row, insight),
                tags=tags,
                notice_kind="historical_opportunity",
                pdf_parse_status=None,
                source_url=source_url,
                source_type=f"historical_{row.source_type}",
                published_at=row.published_at,
                region=row.region_name,
                major=row.major_name,
                adjustment_major_codes=[row.major_code] if row.major_code else [],
                adjustment_study_modes=[row.study_mode] if row.study_mode else [],
                adjustment_has_vacancy=(row.vacancy_count > 0) if row.vacancy_count is not None else None,
                historical_adjustment=insight.__dict__ if insight is not None else None,
                mentor_radar=mentor_signal.__dict__ if mentor_signal is not None else None,
                release_timing=release_timing_signal.__dict__ if release_timing_signal is not None else None,
                school_intelligence=school_signal.__dict__ if school_signal is not None else None,
                merged_count=int(merged["merged_count"]),
                updated_at=row.updated_at,
            )
        )
    serialized.sort(key=_adjustment_sort_key, reverse=True)
    last_updated = max((row["primary"].updated_at for row in merged_rows), default=None)
    return SearchResponse(
        request_id=request_id,
        mode="hybrid_refresh" if payload.refresh else "cache",
        authenticated=authenticated,
        access_limited=False,
        preview_limit=None,
        items=serialized,
        total=len(serialized),
        page=payload.page,
        page_size=payload.page_size,
        source_breakdown=source_breakdown,
        last_updated_at=last_updated,
        refresh_job_id=refresh_job_id,
    )


def _merge_adjustment_search_responses(
    request_id: str,
    payload: AdjustmentSearchRequest,
    refresh_job_id: str | None,
    responses: list[SearchResponse],
) -> SearchResponse:
    all_items: list[SearchItem] = []
    source_breakdown: dict[str, int] = {}
    total = 0
    last_updated_candidates = []
    for response in responses:
        total += response.total
        all_items.extend(response.items)
        if response.last_updated_at is not None:
            last_updated_candidates.append(response.last_updated_at)
        for key, value in response.source_breakdown.items():
            source_breakdown[key] = source_breakdown.get(key, 0) + int(value)
    deduped: dict[str, SearchItem] = {}
    for item in all_items:
        deduped[item.id] = item
    merged_items = sorted(deduped.values(), key=_adjustment_sort_key, reverse=True)
    start = (payload.page - 1) * payload.page_size
    end = start + payload.page_size
    return SearchResponse(
        request_id=request_id,
        mode="hybrid_refresh" if payload.refresh else "cache",
        authenticated=True,
        access_limited=False,
        preview_limit=None,
        items=merged_items[start:end],
        total=len(merged_items),
        page=payload.page,
        page_size=payload.page_size,
        source_breakdown=source_breakdown,
        last_updated_at=max(last_updated_candidates, default=None),
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
    content_query = db.query(Content).filter(Content.category == "adjustment")
    content_query = _apply_common_filters(content_query, payload)
    if payload.major:
        major_terms = _build_major_terms(payload.major.strip())
        content_query = content_query.filter(
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
        content_query = content_query.filter(Content.region.ilike(f"%{payload.region.strip()}%"))

    refresh_job_id = None
    if payload.refresh:
        refresh_job_id = _create_refresh_job(db, "adjustment", payload.model_dump(mode="json"), user.id if user else None)
    page_window = payload.page * payload.page_size

    content_total = content_query.count()
    content_rows = (
        content_query.order_by(Content.published_at.is_(None), Content.published_at.desc(), Content.updated_at.desc())
        .limit(page_window)
        .all()
    )
    content_stats_rows = content_query.with_entities(Content.source_type, func.count(Content.id)).group_by(Content.source_type).all()
    content_source_breakdown = {k: int(v) for k, v in content_stats_rows}
    content_response = _to_response(
        db,
        payload,
        request_id,
        content_rows,
        content_total,
        content_source_breakdown,
        refresh_job_id,
        authenticated=True,
    )

    opportunity_query = db.query(AdjustmentOpportunity)
    opportunity_query = _apply_adjustment_opportunity_filters(opportunity_query, payload)
    opportunity_total = opportunity_query.count()
    opportunity_rows = (
        opportunity_query.order_by(
            AdjustmentOpportunity.published_at.is_(None),
            AdjustmentOpportunity.published_at.desc(),
            AdjustmentOpportunity.year.desc(),
            AdjustmentOpportunity.vacancy_count.is_(None),
            AdjustmentOpportunity.vacancy_count.desc(),
            AdjustmentOpportunity.updated_at.desc(),
        )
        .limit(page_window)
        .all()
    )
    opportunity_stats_rows = (
        opportunity_query.with_entities(AdjustmentOpportunity.source_type, func.count(AdjustmentOpportunity.id))
        .group_by(AdjustmentOpportunity.source_type)
        .all()
    )
    opportunity_source_breakdown = {f"historical_{k}": int(v) for k, v in opportunity_stats_rows}
    opportunity_response = _to_adjustment_opportunity_response(
        db,
        payload,
        request_id,
        opportunity_rows,
        opportunity_total,
        opportunity_source_breakdown,
        refresh_job_id,
        authenticated=True,
    )
    response = _merge_adjustment_search_responses(
        request_id,
        payload,
        refresh_job_id,
        [content_response, opportunity_response],
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


@router.get("/adjustments/items/{item_id}", response_model=AdjustmentSearchDetailResponse)
def get_adjustment_item_detail(
    item_id: str,
    item_kind: str,
    request: Request,
    db: Session = Depends(get_db),
) -> AdjustmentSearchDetailResponse:
    user = get_portal_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="login required for adjustment detail",
        )
    if item_kind == "content":
        row = db.query(Content).filter(Content.id == item_id, Content.category == "adjustment").first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="adjustment content not found")
        return _build_adjustment_detail_from_content(db, row)
    if item_kind == "opportunity":
        row = db.query(AdjustmentOpportunity).filter(AdjustmentOpportunity.id == item_id).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="adjustment opportunity not found")
        return _build_adjustment_detail_from_opportunity(db, row)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unsupported adjustment item kind")
