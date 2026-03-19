from __future__ import annotations

import base64
import gzip
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from ..models import (
    HistoricalAdjustmentProfile,
    HistoricalReleaseTimingProfile,
    MentorEvaluation,
    RawDatasetArchive,
    School,
    new_id,
    utcnow,
)


def _strip_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_school_name(value: Any) -> str:
    text = _strip_text(value)
    matched = re.match(r"^\((\d+)\)(.+)$", text)
    if matched:
        return matched.group(2).strip()
    return re.sub(r"\s+", "", text)


def parse_school_code_name(value: Any) -> tuple[str | None, str]:
    text = _strip_text(value)
    matched = re.match(r"^\((\d+)\)(.+)$", text)
    if matched:
        return matched.group(1).strip(), matched.group(2).strip()
    return None, text


def parse_region_name(value: Any) -> str | None:
    text = _strip_text(value)
    matched = re.match(r"^\((\d+)\)(.+)$", text)
    if matched:
        return matched.group(2).strip() or None
    return text or None


def normalize_major_code(value: Any) -> str | None:
    text = _strip_text(value)
    if not text:
        return None
    matched = re.match(r"^\((\d+)\)", text)
    if matched:
        text = matched.group(1)
    digits = re.sub(r"\D+", "", text)
    if not digits:
        return None
    if len(digits) < 6:
        digits = digits.zfill(6)
    return digits


def normalize_major_name(value: Any) -> str | None:
    text = _strip_text(value)
    if not text:
        return None
    matched = re.match(r"^\((\d+)\)(.+)$", text)
    if matched:
        text = matched.group(2).strip()
    text = re.sub(r"\s+", "", text)
    return text or None


def normalize_department_name(value: Any) -> str | None:
    text = _strip_text(value)
    text = re.sub(r"\s+", "", text)
    return text or None


def normalize_study_mode(value: Any) -> str | None:
    text = _strip_text(value)
    if not text:
        return None
    if text in {"1", "全", "全日制"}:
        return "fulltime"
    if text in {"2", "非全", "非全日制"}:
        return "parttime"
    lowered = text.lower()
    if "全" in text and "非" not in text:
        return "fulltime"
    if "非全" in text or "part" in lowered:
        return "parttime"
    return lowered


def normalize_person_name(value: Any) -> str:
    return re.sub(r"\s+", "", _strip_text(value))


def score_to_int(value: Any) -> int | None:
    text = _strip_text(value)
    if not text:
        return None
    matched = re.search(r"-?\d+(?:\.\d+)?", text)
    if not matched:
        return None
    try:
        return int(round(float(matched.group(0))))
    except Exception:
        return None


def decode_raw_archive_bytes(archive: RawDatasetArchive) -> bytes:
    return gzip.decompress(base64.b64decode(archive.raw_file_payload))


def load_archive_dataframe(archive: RawDatasetArchive, *, sheet_name: str | None = None) -> pd.DataFrame:
    data = BytesIO(decode_raw_archive_bytes(archive))
    target_sheet = sheet_name or archive.primary_sheet_name or 0
    if archive.workbook_format == "xls":
        return pd.read_excel(data, sheet_name=target_sheet, engine="xlrd")
    return pd.read_excel(data, sheet_name=target_sheet, engine="openpyxl")


def _parse_datetime(value: Any) -> datetime | None:
    text = _strip_text(value)
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    if isinstance(parsed, pd.Timestamp):
        return parsed.to_pydatetime()
    if isinstance(parsed, datetime):
        return parsed
    return None


def _parse_capture_datetime_from_filename(value: Any) -> datetime | None:
    text = _strip_text(value)
    matched = re.search(r"(\d{2})年(\d{1,2})月(\d{1,2})日(\d{1,2})时(\d{1,2})分", text)
    if not matched:
        return None
    year = 2000 + int(matched.group(1))
    month = int(matched.group(2))
    day = int(matched.group(3))
    hour = int(matched.group(4))
    minute = int(matched.group(5))
    return datetime(year, month, day, hour, minute)


def _hour_bucket(hour: int | None) -> str | None:
    if hour is None:
        return None
    if 18 <= hour <= 23:
        return "晚间"
    if 12 <= hour <= 17:
        return "下午"
    if 6 <= hour <= 11:
        return "上午"
    return "凌晨"


def _month_day(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return f"{dt.month:02d}-{dt.day:02d}"


def _safe_int(value: Any, *, default: int = 0) -> int:
    parsed = score_to_int(value)
    return parsed if parsed is not None else default


def _safe_float(value: Any) -> float | None:
    text = _strip_text(value)
    if not text:
        return None
    matched = re.search(r"-?\d+(?:\.\d+)?", text)
    if not matched:
        return None
    try:
        return float(matched.group(0))
    except Exception:
        return None


def _school_lookup(db: Session) -> dict[str, str]:
    return {normalize_school_name(row.name): row.id for row in db.query(School).all() if normalize_school_name(row.name)}


def build_profile_key(
    *,
    year: int,
    source_type: str,
    school_name_normalized: str,
    major_code: str | None,
    major_name_normalized: str | None,
    study_mode: str | None,
) -> str:
    raw = "|".join(
        [
            str(year),
            source_type,
            school_name_normalized,
            major_code or "",
            major_name_normalized or "",
            study_mode or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_review_key(
    *,
    source_dataset_key: str,
    school_name_normalized: str,
    department_name_normalized: str | None,
    mentor_name_normalized: str,
    review_text: str,
) -> str:
    raw = "|".join(
        [
            source_dataset_key,
            school_name_normalized,
            department_name_normalized or "",
            mentor_name_normalized,
            re.sub(r"\s+", "", review_text)[:300],
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _risk_tags_and_level(review_text: str) -> tuple[list[str], str | None]:
    text = review_text.lower()
    tags: list[str] = []
    risk_level = None
    strong_negative_markers = ["延毕", "压榨", "辱骂", "没经费", "养不活", "push", "雷", "不推荐"]
    positive_markers = ["好老师", "经费充足", "不强制延毕", "相处融洽"]
    for marker in strong_negative_markers:
        if marker in review_text or marker in text:
            tags.append(marker)
    for marker in positive_markers:
        if marker in review_text or marker in text:
            tags.append(marker)
    if any(marker in review_text or marker in text for marker in strong_negative_markers):
        risk_level = "warning"
    elif any(marker in review_text or marker in text for marker in positive_markers):
        risk_level = "positive"
    return tags[:8], risk_level


def replace_historical_adjustment_profiles(db: Session, profiles: list[dict[str, Any]]) -> dict[str, int]:
    db.query(HistoricalAdjustmentProfile).delete()
    db.commit()
    batch_size = 5000
    for start in range(0, len(profiles), batch_size):
        timestamp = utcnow()
        batch = []
        for row in profiles[start : start + batch_size]:
            batch.append(
                {
                    "id": new_id(),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    **row,
                }
            )
        db.bulk_insert_mappings(HistoricalAdjustmentProfile, batch)
        db.commit()
    return {"profiles": len(profiles)}


def replace_mentor_evaluations(db: Session, evaluations: list[dict[str, Any]]) -> dict[str, int]:
    db.query(MentorEvaluation).delete()
    db.commit()
    batch_size = 5000
    for start in range(0, len(evaluations), batch_size):
        timestamp = utcnow()
        batch = []
        for row in evaluations[start : start + batch_size]:
            batch.append(
                {
                    "id": new_id(),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    **row,
                }
            )
        db.bulk_insert_mappings(MentorEvaluation, batch)
        db.commit()
    return {"evaluations": len(evaluations)}


def replace_release_timing_profiles(db: Session, profiles: list[dict[str, Any]]) -> dict[str, int]:
    db.query(HistoricalReleaseTimingProfile).delete()
    db.commit()
    timestamp = utcnow()
    batch = []
    for row in profiles:
        batch.append(
            {
                "id": new_id(),
                "created_at": timestamp,
                "updated_at": timestamp,
                **row,
            }
        )
    if batch:
        db.bulk_insert_mappings(HistoricalReleaseTimingProfile, batch)
    db.commit()
    return {"profiles": len(profiles)}


def build_historical_profiles_from_archives(db: Session) -> list[dict[str, Any]]:
    archives = {
        row.dataset_key: row
        for row in db.query(RawDatasetArchive)
        .filter(
            RawDatasetArchive.dataset_key.in_(
                [
                    "adjustment_stats_2025_full_raw",
                    "adjustment_landing_2024_raw",
                    "adjustment_landing_2025_raw",
                    "admission_program_catalog_2026_raw",
                    "adjustment_snapshot_2025_0409_raw",
                    "adjustment_announcement_2025_raw",
                ]
            )
        )
        .all()
    }
    school_lookup = _school_lookup(db)
    profiles: list[dict[str, Any]] = []

    stats25 = archives.get("adjustment_stats_2025_full_raw")
    if stats25 is not None:
        df = load_archive_dataframe(stats25, sheet_name="调剂统计（含平均分）")
        for row in df.to_dict(orient="records"):
            school_code, school_name = parse_school_code_name(row.get("推荐院校"))
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            major_code = normalize_major_code(row.get("专业"))
            major_name = normalize_major_name(row.get("专业"))
            study_mode = normalize_study_mode(row.get("学习形式"))
            vacancy_count = _safe_int(row.get("25调剂人数"), default=0)
            min_score = score_to_int(row.get("25调剂录取最低分"))
            avg_score = _safe_float(row.get("25调剂平均分"))
            profile_key = build_profile_key(
                year=2025,
                source_type="adjustment_stats",
                school_name_normalized=school_name_normalized,
                major_code=major_code,
                major_name_normalized=major_name,
                study_mode=study_mode,
            )
            profiles.append(
                {
                    "profile_key": profile_key,
                    "year": 2025,
                    "source_type": "adjustment_stats",
                    "source_dataset_key": stats25.dataset_key,
                    "school_id": school_lookup.get(school_name_normalized),
                    "school_name": school_name,
                    "school_name_normalized": school_name_normalized,
                    "school_code": school_code,
                    "region_name": None,
                    "school_tier": None,
                    "department_name": None,
                    "department_name_normalized": None,
                    "major_code": major_code,
                    "major_name": major_name,
                    "major_name_normalized": major_name,
                    "study_mode": study_mode,
                    "sample_count": vacancy_count,
                    "vacancy_count": vacancy_count,
                    "min_score": min_score,
                    "avg_score": avg_score,
                    "max_score": min_score,
                    "meta_json": {"title": "2025 调剂统计完整版"},
                }
            )

    for year, dataset_key in ((2024, "adjustment_landing_2024_raw"), (2025, "adjustment_landing_2025_raw")):
        archive = archives.get(dataset_key)
        if archive is None:
            continue
        df = load_archive_dataframe(archive, sheet_name="总表")
        grouped: dict[tuple[str, str | None, str | None, str | None], dict[str, Any]] = {}
        for row in df.to_dict(orient="records"):
            school_code, school_name = parse_school_code_name(row.get("调剂学校") or row.get("学校"))
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            department_name = _strip_text(row.get("所属学院")) or None
            department_name_normalized = normalize_department_name(department_name)
            region_name = parse_region_name(row.get("地区"))
            school_tier = _strip_text(row.get("院校类别")) or None
            major_code = normalize_major_code(row.get("专业代码") or row.get("专业"))
            major_name = normalize_major_name(row.get("专业名称") or row.get("专业"))
            study_mode = normalize_study_mode(row.get("学习形式"))
            score = score_to_int(row.get("初试总分"))
            if score is None:
                continue
            group_key = (school_name_normalized, major_code, major_name, study_mode)
            current = grouped.setdefault(
                group_key,
                {
                    "school_name": school_name,
                    "school_name_normalized": school_name_normalized,
                    "school_code": school_code,
                    "region_name": region_name,
                    "school_tier": school_tier,
                    "department_name": department_name,
                    "department_name_normalized": department_name_normalized,
                    "major_code": major_code,
                    "major_name": major_name,
                    "major_name_normalized": major_name,
                    "study_mode": study_mode,
                    "scores": [],
                },
            )
            current["scores"].append(score)
        for payload in grouped.values():
            scores = payload.pop("scores")
            sample_count = len(scores)
            profile_key = build_profile_key(
                year=year,
                source_type="landing",
                school_name_normalized=payload["school_name_normalized"],
                major_code=payload["major_code"],
                major_name_normalized=payload["major_name_normalized"],
                study_mode=payload["study_mode"],
            )
            profiles.append(
                {
                    "profile_key": profile_key,
                    "year": year,
                    "source_type": "landing",
                    "source_dataset_key": archive.dataset_key,
                    "school_id": school_lookup.get(payload["school_name_normalized"]),
                    **payload,
                    "sample_count": sample_count,
                    "vacancy_count": None,
                    "min_score": min(scores) if scores else None,
                    "avg_score": round(sum(scores) / sample_count, 2) if scores else None,
                    "max_score": max(scores) if scores else None,
                    "meta_json": {"title": f"{year} 调剂上岸名单"},
                }
            )

    program2026 = archives.get("admission_program_catalog_2026_raw")
    if program2026 is not None:
        df = load_archive_dataframe(program2026)
        for row in df.to_dict(orient="records"):
            school_name = _strip_text(row.get("院校名称"))
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            major_code = normalize_major_code(row.get("专业代码"))
            major_name = normalize_major_name(row.get("专业名称"))
            vacancy_count = _safe_int(row.get("名额"), default=0)
            profile_key = build_profile_key(
                year=2026,
                source_type="future_program",
                school_name_normalized=school_name_normalized,
                major_code=major_code,
                major_name_normalized=major_name,
                study_mode=None,
            )
            profiles.append(
                {
                    "profile_key": profile_key,
                    "year": 2026,
                    "source_type": "future_program",
                    "source_dataset_key": program2026.dataset_key,
                    "school_id": school_lookup.get(school_name_normalized),
                    "school_name": school_name,
                    "school_name_normalized": school_name_normalized,
                    "school_code": None,
                    "region_name": _strip_text(row.get("省份")) or None,
                    "school_tier": None,
                    "department_name": None,
                    "department_name_normalized": None,
                    "major_code": major_code,
                    "major_name": major_name,
                    "major_name_normalized": major_name,
                    "study_mode": None,
                    "sample_count": vacancy_count,
                    "vacancy_count": vacancy_count,
                    "min_score": None,
                    "avg_score": None,
                    "max_score": None,
                    "meta_json": {
                        "title": "2026 招生专业信息表",
                        "published_at": _strip_text(row.get("发布时间")) or None,
                        "source_url": _strip_text(row.get("链接")) or None,
                    },
                }
            )

    for dataset_key, title in (
        ("adjustment_snapshot_2025_0409_raw", "2025 调剂快照参考链接"),
        ("adjustment_announcement_2025_raw", "2025 调剂公告参考链接"),
    ):
        archive = archives.get(dataset_key)
        if archive is None:
            continue
        df = load_archive_dataframe(archive)
        grouped_links: dict[str, dict[str, Any]] = {}
        for row in df.to_dict(orient="records"):
            school_name = _strip_text(row.get("学校") or row.get("大学") or row.get("院校名称"))
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            current = grouped_links.setdefault(
                school_name_normalized,
                {
                    "school_name": school_name,
                    "region_name": parse_region_name(row.get("地区") or row.get("省份")),
                    "urls": Counter(),
                    "count": 0,
                },
            )
            current["count"] += 1
            url = _strip_text(row.get("原始网址") or row.get("链接") or row.get("网址") or row.get("原文链接"))
            if url:
                current["urls"][url] += 1
        for school_name_normalized, payload in grouped_links.items():
            reference_urls = [url for url, _count in payload["urls"].most_common(3)]
            if not reference_urls:
                continue
            profile_key = build_profile_key(
                year=2025,
                source_type="notice_reference",
                school_name_normalized=school_name_normalized,
                major_code=None,
                major_name_normalized=None,
                study_mode=None,
            )
            profiles.append(
                {
                    "profile_key": profile_key,
                    "year": 2025,
                    "source_type": "notice_reference",
                    "source_dataset_key": archive.dataset_key,
                    "school_id": school_lookup.get(school_name_normalized),
                    "school_name": payload["school_name"],
                    "school_name_normalized": school_name_normalized,
                    "school_code": None,
                    "region_name": payload["region_name"],
                    "school_tier": None,
                    "department_name": None,
                    "department_name_normalized": None,
                    "major_code": None,
                    "major_name": None,
                    "major_name_normalized": None,
                    "study_mode": None,
                    "sample_count": int(payload["count"]),
                    "vacancy_count": None,
                    "min_score": None,
                    "avg_score": None,
                    "max_score": None,
                    "meta_json": {
                        "title": title,
                        "top_source_url": reference_urls[0],
                        "reference_urls": reference_urls,
                    },
                }
            )

    deduped: dict[str, dict[str, Any]] = {}
    for row in profiles:
        deduped[row["profile_key"]] = row
    return list(deduped.values())


def build_mentor_evaluations_from_archives(db: Session) -> list[dict[str, Any]]:
    archive = (
        db.query(RawDatasetArchive)
        .filter(RawDatasetArchive.dataset_key == "mentor_reviews_raw")
        .one_or_none()
    )
    if archive is None:
        return []
    df = load_archive_dataframe(archive)
    rows: list[dict[str, Any]] = []
    for row in df.to_dict(orient="records"):
        school_name = _strip_text(row.get("学校"))
        mentor_name = _strip_text(row.get("姓名"))
        review_text = _strip_text(row.get("评价"))
        if not school_name or school_name == "-" or not mentor_name or mentor_name == "-" or not review_text:
            continue
        school_name_normalized = normalize_school_name(school_name)
        department_name = _strip_text(row.get("学院")) or None
        if department_name == "-":
            department_name = None
        department_name_normalized = normalize_department_name(department_name)
        mentor_name_normalized = normalize_person_name(mentor_name)
        review_tags, risk_level = _risk_tags_and_level(review_text)
        review_key = build_review_key(
            source_dataset_key=archive.dataset_key,
            school_name_normalized=school_name_normalized,
            department_name_normalized=department_name_normalized,
            mentor_name_normalized=mentor_name_normalized,
            review_text=review_text,
        )
        rows.append(
            {
                "review_key": review_key,
                "source_dataset_key": archive.dataset_key,
                "school_name": school_name,
                "school_name_normalized": school_name_normalized,
                "department_name": department_name,
                "department_name_normalized": department_name_normalized,
                "mentor_name": mentor_name,
                "mentor_name_normalized": mentor_name_normalized,
                "review_text": review_text,
                "review_tags": review_tags,
                "risk_level": risk_level,
                "meta_json": {},
            }
        )
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped[row["review_key"]] = row
    return list(deduped.values())


@dataclass
class HistoricalAdjustmentInsightResult:
    sample_years: list[int]
    source_types: list[str]
    sample_count: int
    min_score: int | None
    avg_score: float | None
    max_score: int | None
    candidate_score: int | None
    outlook: str | None
    outlook_label: str | None
    future_program_count: int | None


@dataclass
class MentorRadarInsightResult:
    review_count: int
    mentor_count: int
    warning_count: int
    positive_count: int
    top_tags: list[str]
    risk_label: str | None


@dataclass
class ReleaseTimingInsightResult:
    sample_count: int
    sample_years: list[int]
    peak_hour: int | None
    peak_hour_bucket: str | None
    window_start_md: str | None
    window_end_md: str | None
    signal_label: str | None
    signal_detail: str | None


@dataclass
class SchoolIntelligenceInsightResult:
    profile_count: int
    active_years: list[int]
    source_types: list[str]
    future_program_count: int
    reference_urls: list[str]
    confidence_label: str
    signal_detail: str


def _match_profile(
    profile: HistoricalAdjustmentProfile,
    *,
    major_codes: list[str],
    major_name_normalized: str | None,
    study_modes: list[str],
) -> bool:
    if profile.source_type == "future_program":
        return True
    code_match = bool(major_codes and profile.major_code and profile.major_code in major_codes)
    name_match = bool(major_name_normalized and profile.major_name_normalized == major_name_normalized)
    if major_codes or major_name_normalized:
        if not (code_match or name_match):
            return False
    if study_modes and profile.study_mode and profile.study_mode not in study_modes:
        return False
    return True


def build_search_insight(
    profiles: list[HistoricalAdjustmentProfile],
    *,
    major_codes: list[str],
    major_name: str | None,
    study_modes: list[str],
    candidate_score: int | None,
) -> HistoricalAdjustmentInsightResult | None:
    normalized_codes = [code for code in (normalize_major_code(code) for code in major_codes) if code]
    normalized_name = normalize_major_name(major_name)
    normalized_modes = [mode for mode in (normalize_study_mode(mode) for mode in study_modes) if mode]
    matched = [
        row
        for row in profiles
        if _match_profile(
            row,
            major_codes=normalized_codes,
            major_name_normalized=normalized_name,
            study_modes=normalized_modes,
        )
    ]
    if not matched:
        return None
    score_profiles = [row for row in matched if row.source_type in {"adjustment_stats", "landing"}]
    future_profiles = [row for row in matched if row.source_type == "future_program"]
    years = sorted({row.year for row in score_profiles})
    source_types = sorted({row.source_type for row in score_profiles})
    sample_count = sum(max(1, row.sample_count) for row in score_profiles)
    min_candidates = [row.min_score for row in score_profiles if row.min_score is not None]
    max_candidates = [row.max_score for row in score_profiles if row.max_score is not None]
    weighted_avg_num = 0.0
    weighted_avg_den = 0
    for row in score_profiles:
        if row.avg_score is None:
            continue
        weight = max(1, row.sample_count)
        weighted_avg_num += row.avg_score * weight
        weighted_avg_den += weight
    avg_score = round(weighted_avg_num / weighted_avg_den, 1) if weighted_avg_den else None
    min_score = min(min_candidates) if min_candidates else None
    max_score = max(max_candidates) if max_candidates else None

    outlook = None
    outlook_label = None
    if candidate_score is not None:
        if avg_score is not None and candidate_score >= avg_score:
            outlook = "high"
            outlook_label = "胜率较高"
        elif min_score is not None and candidate_score >= min_score:
            outlook = "reach"
            outlook_label = "可以冲刺"
        else:
            outlook = "cautious"
            outlook_label = "谨慎尝试"

    future_program_count = sum(max(0, row.vacancy_count or row.sample_count) for row in future_profiles) or None
    if not years and avg_score is None and min_score is None and future_program_count is None:
        return None
    return HistoricalAdjustmentInsightResult(
        sample_years=years,
        source_types=source_types,
        sample_count=sample_count,
        min_score=min_score,
        avg_score=avg_score,
        max_score=max_score,
        candidate_score=candidate_score,
        outlook=outlook,
        outlook_label=outlook_label,
        future_program_count=future_program_count,
    )


def load_profiles_for_search(db: Session, school_names: list[str]) -> dict[str, list[HistoricalAdjustmentProfile]]:
    normalized_names = sorted({normalize_school_name(name) for name in school_names if normalize_school_name(name)})
    if not normalized_names:
        return {}
    rows = (
        db.query(HistoricalAdjustmentProfile)
        .filter(HistoricalAdjustmentProfile.school_name_normalized.in_(normalized_names))
        .all()
    )
    grouped: dict[str, list[HistoricalAdjustmentProfile]] = defaultdict(list)
    for row in rows:
        grouped[row.school_name_normalized].append(row)
    return grouped


def load_school_intelligence_for_search(
    db: Session, school_names: list[str]
) -> dict[str, SchoolIntelligenceInsightResult]:
    normalized_names = sorted({normalize_school_name(name) for name in school_names if normalize_school_name(name)})
    if not normalized_names:
        return {}
    rows = (
        db.query(HistoricalAdjustmentProfile)
        .filter(HistoricalAdjustmentProfile.school_name_normalized.in_(normalized_names))
        .all()
    )
    grouped: dict[str, list[HistoricalAdjustmentProfile]] = defaultdict(list)
    for row in rows:
        grouped[row.school_name_normalized].append(row)

    result: dict[str, SchoolIntelligenceInsightResult] = {}
    for school_name_normalized, profiles in grouped.items():
        active_years = sorted({int(row.year) for row in profiles if row.year})
        source_types = sorted({str(row.source_type) for row in profiles if row.source_type})
        future_program_count = sum(
            max(0, int(row.vacancy_count or row.sample_count or 0))
            for row in profiles
            if row.source_type == "future_program"
        )
        reference_urls: list[str] = []
        for row in profiles:
            meta = row.meta_json or {}
            raw_urls: list[str] = []
            if isinstance(meta.get("reference_urls"), list):
                raw_urls.extend([str(value or "").strip() for value in meta.get("reference_urls") or []])
            raw_urls.extend(
                [
                    str(meta.get("top_source_url") or "").strip(),
                    str(meta.get("source_url") or "").strip(),
                ]
            )
            for url in raw_urls:
                if url and url not in reference_urls:
                    reference_urls.append(url)
        profile_count = len(profiles)

        if len(active_years) >= 3 or profile_count >= 40:
            confidence_label = "连续活跃"
        elif len(active_years) >= 2 or profile_count >= 15:
            confidence_label = "持续关注"
        else:
            confidence_label = "样本有限"

        year_text = " / ".join(str(value) for value in active_years[:4]) if active_years else "暂无年份"
        source_text = " / ".join(source_types[:3]) if source_types else "暂无来源"
        signal_detail = f"历史覆盖 {year_text}，累计 {profile_count} 组画像，来源 {source_text}"
        if future_program_count > 0:
            signal_detail += f"，2026 招生专业 {future_program_count} 个"
        if reference_urls:
            signal_detail += f"，可回溯链接 {len(reference_urls)} 条"

        result[school_name_normalized] = SchoolIntelligenceInsightResult(
            profile_count=profile_count,
            active_years=active_years,
            source_types=source_types,
            future_program_count=future_program_count,
            reference_urls=reference_urls[:3],
            confidence_label=confidence_label,
            signal_detail=signal_detail,
        )
    return result


def load_mentor_radar_for_search(db: Session, school_names: list[str]) -> dict[str, MentorRadarInsightResult]:
    normalized_names = sorted({normalize_school_name(name) for name in school_names if normalize_school_name(name)})
    if not normalized_names:
        return {}
    rows = (
        db.query(MentorEvaluation)
        .filter(MentorEvaluation.school_name_normalized.in_(normalized_names))
        .all()
    )
    grouped: dict[str, list[MentorEvaluation]] = defaultdict(list)
    for row in rows:
        grouped[row.school_name_normalized].append(row)

    result: dict[str, MentorRadarInsightResult] = {}
    for school_name_normalized, evaluations in grouped.items():
        mentor_names = {
            row.mentor_name_normalized
            for row in evaluations
            if row.mentor_name_normalized
        }
        warning_count = sum(1 for row in evaluations if row.risk_level == "warning")
        positive_count = sum(1 for row in evaluations if row.risk_level == "positive")
        tag_counter: Counter[str] = Counter()
        for row in evaluations:
            for tag in row.review_tags or []:
                clean_tag = str(tag or "").strip()
                if clean_tag:
                    tag_counter[clean_tag] += 1
        risk_label = None
        if warning_count >= 5:
            risk_label = "导师预警较多"
        elif warning_count > 0:
            risk_label = "有导师预警"
        elif positive_count > 0:
            risk_label = "存在正向评价"
        result[school_name_normalized] = MentorRadarInsightResult(
            review_count=len(evaluations),
            mentor_count=len(mentor_names),
            warning_count=warning_count,
            positive_count=positive_count,
            top_tags=[label for label, _count in tag_counter.most_common(4)],
            risk_label=risk_label,
        )
    return result


def build_release_timing_profiles_from_archives(db: Session) -> list[dict[str, Any]]:
    school_lookup = _school_lookup(db)
    archives = (
        db.query(RawDatasetArchive)
        .filter(
            RawDatasetArchive.dataset_key.in_(
                [
                    "adjustment_snapshot_2024_0414_raw",
                    "adjustment_snapshot_2025_0409_raw",
                    "adjustment_announcement_2025_raw",
                ]
            )
        )
        .all()
    )
    grouped_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for archive in archives:
        df = load_archive_dataframe(archive)
        capture_dt = _parse_capture_datetime_from_filename(archive.source_filename)
        for row in df.to_dict(orient="records"):
            school_name = _strip_text(row.get("学校") or row.get("大学"))
            if not school_name:
                continue
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            published_dt = _parse_datetime(row.get("最新时间") or row.get("发布时间"))
            if published_dt is None and capture_dt is not None:
                elapsed_minutes = score_to_int(row.get("距离开网已过时间（分）"))
                if elapsed_minutes is not None and elapsed_minutes >= 0:
                    published_dt = capture_dt - timedelta(minutes=elapsed_minutes)
            if published_dt is None:
                continue
            grouped_events[school_name_normalized].append(
                {
                    "school_name": school_name_normalized,
                    "display_name": school_name,
                    "published_dt": published_dt,
                    "year": published_dt.year,
                    "source_dataset_key": archive.dataset_key,
                }
            )

    profiles: list[dict[str, Any]] = []
    for school_name_normalized, events in grouped_events.items():
        events.sort(key=lambda item: item["published_dt"])
        hours = Counter(event["published_dt"].hour for event in events)
        peak_hour, peak_count = hours.most_common(1)[0]
        month_days = [_month_day(event["published_dt"]) for event in events if _month_day(event["published_dt"])]
        years = sorted({int(event["year"]) for event in events})
        source_dataset_keys = sorted({str(event["source_dataset_key"]) for event in events})
        profile_key = hashlib.sha256(f"timing|{school_name_normalized}".encode("utf-8")).hexdigest()
        profiles.append(
            {
                "profile_key": profile_key,
                "school_id": school_lookup.get(school_name_normalized),
                "school_name": events[0]["display_name"],
                "school_name_normalized": school_name_normalized,
                "sample_count": len(events),
                "peak_hour": peak_hour,
                "peak_hour_bucket": _hour_bucket(peak_hour),
                "window_start_md": min(month_days) if month_days else None,
                "window_end_md": max(month_days) if month_days else None,
                "consistency_ratio": round(peak_count / len(events), 4) if events else None,
                "meta_json": {
                    "sample_years": years,
                    "source_dataset_keys": source_dataset_keys,
                    "top_hours": [[hour, count] for hour, count in hours.most_common(4)],
                },
            }
        )
    return profiles


def load_release_timing_for_search(db: Session, school_names: list[str]) -> dict[str, HistoricalReleaseTimingProfile]:
    normalized_names = sorted({normalize_school_name(name) for name in school_names if normalize_school_name(name)})
    if not normalized_names:
        return {}
    rows = (
        db.query(HistoricalReleaseTimingProfile)
        .filter(HistoricalReleaseTimingProfile.school_name_normalized.in_(normalized_names))
        .all()
    )
    return {row.school_name_normalized: row for row in rows}


def build_release_timing_insight(profile: HistoricalReleaseTimingProfile | None) -> ReleaseTimingInsightResult | None:
    if profile is None or profile.sample_count <= 0:
        return None
    years = [int(value) for value in (profile.meta_json or {}).get("sample_years", []) if str(value).strip()]
    bucket = profile.peak_hour_bucket
    label = None
    if bucket and profile.sample_count >= 3:
        label = f"{bucket}高发"
    elif bucket:
        label = f"{bucket}信号"
    detail = None
    if profile.window_start_md and profile.window_end_md and bucket and profile.peak_hour is not None:
        detail = f"历史样本 {profile.sample_count} 条，多在 {profile.window_start_md} - {profile.window_end_md} 的{bucket}{profile.peak_hour:02d}点左右发布。"
    elif profile.peak_hour is not None:
        detail = f"历史样本 {profile.sample_count} 条，当前高频时段约为 {profile.peak_hour:02d}:00。"
    return ReleaseTimingInsightResult(
        sample_count=profile.sample_count,
        sample_years=years,
        peak_hour=profile.peak_hour,
        peak_hour_bucket=bucket,
        window_start_md=profile.window_start_md,
        window_end_md=profile.window_end_md,
        signal_label=label,
        signal_detail=detail,
    )
