from __future__ import annotations

import base64
import gzip
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import unescape
from io import BytesIO
from typing import Any

import pandas as pd
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..models import (
    AdjustmentOpportunity,
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


def _clean_review_text(value: Any) -> str:
    raw = str(value or "")
    if not raw.strip():
        return ""
    text = re.sub(r"(?i)<br\\s*/?>", "\n", raw)
    text = re.sub(r"(?is)</p\\s*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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


def parse_labeled_name(value: Any) -> tuple[str | None, str | None]:
    text = _strip_text(value)
    if not text:
        return None, None
    matched = re.match(r"^\(([^)]+)\)(.+)$", text)
    if matched:
        return matched.group(1).strip() or None, matched.group(2).strip() or None
    return None, text or None


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


def _parse_capture_datetime(value: Any) -> datetime | None:
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed
    text = _strip_text(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H-%M-%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _normalize_legacy_adjustment_stats_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    columns = [str(col).strip() for col in df.columns]
    first_row = [_strip_text(value) for value in df.iloc[0].tolist()]
    if "年份" not in first_row or "学校" not in first_row:
        return df
    normalized = df.iloc[1:].copy()
    normalized.columns = first_row
    normalized = normalized.reset_index(drop=True)
    return normalized


def _select_archive(
    archives: dict[str, RawDatasetArchive],
    *,
    dataset_keys: tuple[str, ...] = (),
    source_filenames: tuple[str, ...] = (),
) -> RawDatasetArchive | None:
    for key in dataset_keys:
        if key in archives:
            return archives[key]
    wanted = {name.strip().lower() for name in source_filenames if name.strip()}
    if not wanted:
        return None
    for archive in archives.values():
        if (archive.source_filename or "").strip().lower() in wanted:
            return archive
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


def build_opportunity_key(
    *,
    source_dataset_key: str,
    school_name_normalized: str,
    department_name_normalized: str | None,
    major_code: str | None,
    major_name_normalized: str | None,
    source_url: str | None,
    published_at: datetime | None,
) -> str:
    raw = "|".join(
        [
            source_dataset_key,
            school_name_normalized,
            department_name_normalized or "",
            major_code or "",
            major_name_normalized or "",
            (source_url or "").strip(),
            published_at.isoformat() if published_at is not None else "",
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


def _replace_rows_by_unique_key(
    db: Session,
    model,
    rows: list[dict[str, Any]],
    *,
    key_field: str,
    batch_size: int = 5000,
) -> int:
    key_column = getattr(model, key_field)
    existing_keys = {value for (value,) in db.query(key_column).all()}
    desired_keys = {str(row[key_field]) for row in rows if row.get(key_field)}
    stale_keys = [key for key in existing_keys if key not in desired_keys]

    for start in range(0, len(stale_keys), batch_size):
        db.query(model).filter(key_column.in_(stale_keys[start : start + batch_size])).delete(synchronize_session=False)
        db.commit()

    dialect = (db.bind.dialect.name if db.bind is not None else "sqlite").lower()
    for start in range(0, len(rows), batch_size):
        timestamp = utcnow()
        batch = [
            {
                "id": new_id(),
                "created_at": timestamp,
                "updated_at": timestamp,
                **row,
            }
            for row in rows[start : start + batch_size]
        ]
        if not batch:
            continue
        if dialect == "mysql":
            stmt = mysql_insert(model).values(batch)
            update_map = {
                key: getattr(stmt.inserted, key)
                for key in batch[0].keys()
                if key not in {"id", "created_at"}
            }
            db.execute(stmt.on_duplicate_key_update(**update_map))
        elif dialect == "sqlite":
            stmt = sqlite_insert(model).values(batch)
            update_map = {
                key: getattr(stmt.excluded, key)
                for key in batch[0].keys()
                if key not in {"id", "created_at"}
            }
            db.execute(stmt.on_conflict_do_update(index_elements=[key_field], set_=update_map))
        else:
            db.bulk_insert_mappings(model, batch)
        db.commit()
    return len(rows)


def replace_historical_adjustment_profiles(db: Session, profiles: list[dict[str, Any]]) -> dict[str, int]:
    count = _replace_rows_by_unique_key(
        db,
        HistoricalAdjustmentProfile,
        profiles,
        key_field="profile_key",
    )
    return {"profiles": count}


def replace_mentor_evaluations(db: Session, evaluations: list[dict[str, Any]]) -> dict[str, int]:
    count = _replace_rows_by_unique_key(
        db,
        MentorEvaluation,
        evaluations,
        key_field="review_key",
        batch_size=500,
    )
    return {"evaluations": count}


def replace_release_timing_profiles(db: Session, profiles: list[dict[str, Any]]) -> dict[str, int]:
    count = _replace_rows_by_unique_key(
        db,
        HistoricalReleaseTimingProfile,
        profiles,
        key_field="profile_key",
    )
    return {"profiles": count}


def replace_adjustment_opportunities(db: Session, rows: list[dict[str, Any]]) -> dict[str, int]:
    count = _replace_rows_by_unique_key(
        db,
        AdjustmentOpportunity,
        rows,
        key_field="opportunity_key",
        batch_size=2000,
    )
    return {"opportunities": count}


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


def build_adjustment_opportunities_from_archives(db: Session) -> list[dict[str, Any]]:
    archives = {
        row.dataset_key: row
        for row in db.query(RawDatasetArchive).all()
    }
    school_lookup = _school_lookup(db)
    opportunities: list[dict[str, Any]] = []

    def add_row(
        *,
        source_dataset_key: str,
        source_type: str,
        year: int | None,
        school_name: str,
        school_code: str | None,
        region_name: str | None,
        school_tier: str | None,
        department_name: str | None,
        major_code: str | None,
        major_name: str | None,
        study_mode: str | None,
        vacancy_count: int | None,
        min_score: int | None,
        avg_score: float | None,
        max_score: int | None,
        verification_status: str | None,
        title: str,
        summary: str | None,
        source_url: str | None,
        published_at: datetime | None,
        captured_at: datetime | None,
        meta_json: dict[str, Any],
    ) -> None:
        school_name_normalized = normalize_school_name(school_name)
        if not school_name_normalized:
            return
        department_name_normalized = normalize_department_name(department_name)
        major_name_normalized = normalize_major_name(major_name)
        opportunity_key = build_opportunity_key(
            source_dataset_key=source_dataset_key,
            school_name_normalized=school_name_normalized,
            department_name_normalized=department_name_normalized,
            major_code=major_code,
            major_name_normalized=major_name_normalized,
            source_url=source_url,
            published_at=published_at,
        )
        opportunities.append(
            {
                "opportunity_key": opportunity_key,
                "source_dataset_key": source_dataset_key,
                "source_type": source_type,
                "year": year,
                "school_id": school_lookup.get(school_name_normalized),
                "school_name": school_name,
                "school_name_normalized": school_name_normalized,
                "school_code": school_code,
                "region_name": region_name,
                "school_tier": school_tier,
                "department_name": department_name,
                "department_name_normalized": department_name_normalized,
                "major_code": major_code,
                "major_name": major_name,
                "major_name_normalized": major_name_normalized,
                "study_mode": study_mode,
                "vacancy_count": vacancy_count,
                "min_score": min_score,
                "avg_score": avg_score,
                "max_score": max_score,
                "verification_status": verification_status,
                "title": title,
                "summary": summary,
                "source_url": source_url,
                "published_at": published_at,
                "captured_at": captured_at,
                "meta_json": meta_json,
            }
        )

    program2026 = _select_archive(
        archives,
        dataset_keys=("admission_program_catalog_2026_raw",),
        source_filenames=("2026年研究生招生专业信息表.xlsx",),
    )
    if program2026 is not None:
        df = load_archive_dataframe(program2026)
        for row in df.to_dict(orient="records"):
            school_name = _strip_text(row.get("院校名称") or row.get("学校") or row.get("大学"))
            if not school_name:
                continue
            major_code = normalize_major_code(row.get("专业代码") or row.get("专业"))
            major_name = normalize_major_name(row.get("专业名称") or row.get("专业"))
            vacancy_count = _safe_int(row.get("名额"), default=0) or None
            source_url = _strip_text(row.get("链接") or row.get("原始网址") or row.get("网址") or row.get("原文链接")) or None
            published_at = _parse_datetime(row.get("发布时间"))
            region_name = _strip_text(row.get("省份")) or _strip_text(row.get("地区")) or None
            summary_parts = ["2026 招生专业信息"]
            if vacancy_count:
                summary_parts.append(f"名额 {vacancy_count}")
            title = f"{school_name} {major_name or major_code or '招生专业'} 2026 招生信息"
            add_row(
                source_dataset_key=program2026.dataset_key,
                source_type="future_program",
                year=score_to_int(row.get("年份")) or 2026,
                school_name=school_name,
                school_code=_strip_text(row.get("学校代码")) or None,
                region_name=region_name,
                school_tier=None,
                department_name=_strip_text(row.get("学院")) or None,
                major_code=major_code,
                major_name=major_name,
                study_mode=normalize_study_mode(row.get("学习形式")),
                vacancy_count=vacancy_count,
                min_score=None,
                avg_score=None,
                max_score=None,
                verification_status="2026招生专业",
                title=title,
                summary=" · ".join(summary_parts),
                source_url=source_url,
                published_at=published_at,
                captured_at=None,
                meta_json={"dataset_title": program2026.title},
            )

    snapshot_2025 = _select_archive(
        archives,
        dataset_keys=("adjustment_snapshot_2025_0409_raw",),
        source_filenames=("25年4月9日20时03分07秒调剂信息汇总.xlsx",),
    )
    if snapshot_2025 is not None:
        df = load_archive_dataframe(snapshot_2025)
        default_capture = _parse_capture_datetime_from_filename(snapshot_2025.source_filename)
        for row in df.to_dict(orient="records"):
            school_name = _strip_text(row.get("学校") or row.get("大学") or row.get("院校名称"))
            if not school_name:
                continue
            major_code = normalize_major_code(row.get("专业代码") or row.get("专业"))
            major_name = normalize_major_name(row.get("专业名称") or row.get("专业"))
            title = f"{school_name} {major_name or major_code or '调剂'} 调剂信息"
            published_at = _parse_datetime(row.get("最新时间") or row.get("发布时间"))
            source_url = _strip_text(row.get("原始网址") or row.get("链接") or row.get("网址") or row.get("原文链接")) or None
            verification_status = _strip_text(row.get("验证状态")) or None
            vacancy_count = _safe_int(row.get("计划人数"), default=0) or None
            year = score_to_int(row.get("年份")) or 2025
            summary_parts = [f"{year} 年调剂快照"]
            if verification_status:
                summary_parts.append(verification_status)
            if vacancy_count:
                summary_parts.append(f"计划 {vacancy_count}")
            add_row(
                source_dataset_key=snapshot_2025.dataset_key,
                source_type="snapshot",
                year=year,
                school_name=school_name,
                school_code=None,
                region_name=parse_region_name(row.get("地区") or row.get("省份")),
                school_tier=None,
                department_name=_strip_text(row.get("学院")) or None,
                major_code=major_code,
                major_name=major_name,
                study_mode=normalize_study_mode(row.get("学习形式")),
                vacancy_count=vacancy_count,
                min_score=None,
                avg_score=None,
                max_score=None,
                verification_status=verification_status,
                title=title,
                summary=" · ".join(summary_parts),
                source_url=source_url,
                published_at=published_at,
                captured_at=default_capture,
                meta_json={"dataset_title": snapshot_2025.title},
            )

    legacy_balance_2024 = _select_archive(
        archives,
        dataset_keys=("adjustment_opportunity_2024_raw",),
        source_filenames=("24.xlsx",),
    )
    if legacy_balance_2024 is not None:
        df = load_archive_dataframe(legacy_balance_2024)
        for row in df.to_dict(orient="records"):
            school_code, school_name = parse_school_code_name(row.get("招生单位"))
            if not school_name:
                continue
            _department_code, department_name = parse_labeled_name(row.get(" 院系所") or row.get("院系所"))
            major_code = normalize_major_code(row.get(" 专业") or row.get("专业"))
            major_name = normalize_major_name(row.get(" 专业") or row.get("专业"))
            research_direction = _strip_text(row.get(" 研究方向") or row.get("研究方向")) or None
            study_mode = normalize_study_mode(row.get(" 学习方式") or row.get("学习方式"))
            vacancy_count = _safe_int(row.get(" 计划余额") or row.get("计划余额"), default=0) or None
            captured_at = _parse_capture_datetime(row.get("采集时间"))
            score_line = _strip_text(row.get(" 总分") or row.get("总分")) or None
            summary_parts = ["2024 调剂余额表"]
            if department_name:
                summary_parts.append(department_name)
            if research_direction and research_direction != "(00)不区分研究方向":
                summary_parts.append(research_direction)
            if vacancy_count:
                summary_parts.append(f"余额 {vacancy_count}")
            if score_line:
                summary_parts.append(f"总分要求 {score_line}")
            explanation = _strip_text(row.get(" 调剂说明") or row.get("调剂说明")) or None
            if explanation:
                summary_parts.append(explanation[:80])
            title = f"{school_name} {major_name or major_code or '调剂'} 余额信息"
            add_row(
                source_dataset_key=legacy_balance_2024.dataset_key,
                source_type="balance",
                year=2024,
                school_name=school_name,
                school_code=school_code,
                region_name=None,
                school_tier=None,
                department_name=department_name,
                major_code=major_code,
                major_name=major_name,
                study_mode=study_mode,
                vacancy_count=vacancy_count,
                min_score=None,
                avg_score=None,
                max_score=None,
                verification_status=score_line,
                title=title,
                summary=" · ".join(part for part in summary_parts if part),
                source_url=None,
                published_at=None,
                captured_at=captured_at,
                meta_json={"dataset_title": legacy_balance_2024.title},
            )

    snapshot_2024 = _select_archive(
        archives,
        dataset_keys=("adjustment_snapshot_2024_0414_raw",),
        source_filenames=("24年4月14日10时55分调剂信息汇总.xlsx",),
    )
    if snapshot_2024 is not None:
        df = load_archive_dataframe(snapshot_2024)
        default_capture = _parse_capture_datetime_from_filename(snapshot_2024.source_filename)
        for row in df.to_dict(orient="records"):
            school_name = _strip_text(row.get("大学") or row.get("学校") or row.get("院校名称"))
            if not school_name:
                continue
            major_code = normalize_major_code(row.get("专业代码") or row.get("专业"))
            major_name = normalize_major_name(row.get("专业") or row.get("专业名称"))
            department_name = _strip_text(row.get("学院")) or None
            study_mode = normalize_study_mode(row.get("学习形式"))
            vacancy_count = _safe_int(row.get("余额"), default=0) or None
            title = f"{school_name} {major_name or major_code or '调剂'} 调剂信息"
            summary_parts = ["2024 年调剂快照"]
            if department_name:
                summary_parts.append(department_name)
            if vacancy_count:
                summary_parts.append(f"余额 {vacancy_count}")
            note = _strip_text(row.get("备注"))
            if note:
                summary_parts.append(note)
            add_row(
                source_dataset_key=snapshot_2024.dataset_key,
                source_type="snapshot",
                year=2024,
                school_name=school_name,
                school_code=_strip_text(row.get("学校代码")) or None,
                region_name=None,
                school_tier=None,
                department_name=department_name,
                major_code=major_code,
                major_name=major_name,
                study_mode=study_mode,
                vacancy_count=vacancy_count,
                min_score=None,
                avg_score=None,
                max_score=None,
                verification_status=None,
                title=title,
                summary=" · ".join(summary_parts),
                source_url=None,
                published_at=None,
                captured_at=default_capture,
                meta_json={"dataset_title": snapshot_2024.title},
            )

    announcement_2025 = _select_archive(
        archives,
        dataset_keys=("adjustment_announcement_2025_raw",),
        source_filenames=("2025年调剂信息公告.xls", "2025年调剂信息公告.xlsx"),
    )
    if announcement_2025 is not None:
        df = load_archive_dataframe(announcement_2025)
        for row in df.to_dict(orient="records"):
            school_name = _strip_text(row.get("学校") or row.get("大学") or row.get("院校名称"))
            if not school_name:
                continue
            major_code = normalize_major_code(row.get("专业代码") or row.get("专业"))
            major_name = normalize_major_name(row.get("专业名称") or row.get("专业"))
            source_url = _strip_text(row.get("原始网址") or row.get("链接") or row.get("网址") or row.get("原文链接")) or None
            published_at = _parse_datetime(row.get("最新时间") or row.get("发布时间"))
            verification_status = _strip_text(row.get("验证状态")) or None
            title = _strip_text(row.get("标题")) or f"{school_name} {major_name or major_code or '调剂'} 公告"
            add_row(
                source_dataset_key=announcement_2025.dataset_key,
                source_type="adjustment_notice",
                year=score_to_int(row.get("年份")) or 2025,
                school_name=school_name,
                school_code=None,
                region_name=parse_region_name(row.get("地区") or row.get("省份")),
                school_tier=None,
                department_name=_strip_text(row.get("学院")) or None,
                major_code=major_code,
                major_name=major_name,
                study_mode=normalize_study_mode(row.get("学习形式")),
                vacancy_count=_safe_int(row.get("计划人数"), default=0) or None,
                min_score=None,
                avg_score=None,
                max_score=None,
                verification_status=verification_status,
                title=title,
                summary=_strip_text(row.get("备注")) or "历史调剂公告归档",
                source_url=source_url,
                published_at=published_at,
                captured_at=None,
                meta_json={"dataset_title": announcement_2025.title},
            )

    stats25 = _select_archive(
        archives,
        dataset_keys=("adjustment_stats_2025_full_raw",),
        source_filenames=("25 调剂信息统计_完整版（含调剂人数，最低分，平均分）.xlsx",),
    )
    if stats25 is not None:
        df = load_archive_dataframe(stats25, sheet_name="调剂统计（含平均分）")
        for row in df.to_dict(orient="records"):
            school_code, school_name = parse_school_code_name(row.get("推荐院校"))
            if not school_name:
                continue
            major_code = normalize_major_code(row.get("专业"))
            major_name = normalize_major_name(row.get("专业"))
            study_mode = normalize_study_mode(row.get("学习形式"))
            vacancy_count = _safe_int(row.get("25调剂人数"), default=0) or None
            min_score = score_to_int(row.get("25调剂录取最低分"))
            avg_score = _safe_float(row.get("25调剂平均分"))
            title = f"{school_name} {major_name or major_code or '调剂'} 历史统计"
            summary_parts = ["2025 年历史调剂统计"]
            if vacancy_count:
                summary_parts.append(f"调剂人数 {vacancy_count}")
            if min_score is not None:
                summary_parts.append(f"最低 {min_score}")
            if avg_score is not None:
                summary_parts.append(f"均分 {round(avg_score, 1)}")
            add_row(
                source_dataset_key=stats25.dataset_key,
                source_type="stats",
                year=2025,
                school_name=school_name,
                school_code=school_code,
                region_name=None,
                school_tier=None,
                department_name=None,
                major_code=major_code,
                major_name=major_name,
                study_mode=study_mode,
                vacancy_count=vacancy_count,
                min_score=min_score,
                avg_score=avg_score,
                max_score=min_score,
                verification_status="历史统计",
                title=title,
                summary=" · ".join(summary_parts),
                source_url=None,
                published_at=None,
                captured_at=None,
                meta_json={"dataset_title": stats25.title},
            )

    for landing_year, dataset_key, filename in (
        (2024, "adjustment_landing_2024_raw", "24考研调剂上岸名单.xlsx"),
        (2025, "adjustment_landing_2025_raw", "25考研调剂上岸名单.xlsx"),
    ):
        landing_archive = _select_archive(
            archives,
            dataset_keys=(dataset_key,),
            source_filenames=(filename,),
        )
        if landing_archive is None:
            continue
        df = load_archive_dataframe(landing_archive, sheet_name="总表")
        grouped: dict[tuple[str, str | None, str | None, str | None, str | None], dict[str, Any]] = {}
        for row in df.to_dict(orient="records"):
            school_code, school_name = parse_school_code_name(row.get("调剂学校") or row.get("学校"))
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            department_name = _strip_text(row.get("所属学院")) or None
            if department_name == "未区分院系" or department_name == "未区分院系所":
                department_name = None
            region_name = parse_region_name(row.get("地区"))
            school_tier = _strip_text(row.get("院校类别")) or None
            major_code = normalize_major_code(row.get("专业代码") or row.get("专业"))
            major_name = normalize_major_name(row.get("专业名称") or row.get("专业"))
            study_mode = normalize_study_mode(row.get("学习形式"))
            score = score_to_int(row.get("初试总分"))
            group_key = (
                school_name_normalized,
                normalize_department_name(department_name),
                major_code,
                normalize_major_name(major_name),
                study_mode,
            )
            payload = grouped.setdefault(
                group_key,
                {
                    "school_name": school_name,
                    "school_code": school_code,
                    "region_name": region_name,
                    "school_tier": school_tier,
                    "department_name": department_name,
                    "major_code": major_code,
                    "major_name": major_name,
                    "study_mode": study_mode,
                    "scores": [],
                },
            )
            if score is not None:
                payload["scores"].append(score)

        for payload in grouped.values():
            scores = payload.pop("scores")
            sample_count = len(scores) or None
            summary_parts = [f"{landing_year} 年调剂上岸样本"]
            if payload["department_name"]:
                summary_parts.append(payload["department_name"])
            if sample_count:
                summary_parts.append(f"样本 {sample_count}")
            if scores:
                summary_parts.append(f"最低 {min(scores)}")
                summary_parts.append(f"均分 {round(sum(scores) / len(scores))}")
            title = f"{payload['school_name']} {payload['major_name'] or payload['major_code'] or '调剂'} 上岸样本"
            add_row(
                source_dataset_key=landing_archive.dataset_key,
                source_type="landing",
                year=landing_year,
                school_name=payload["school_name"],
                school_code=payload["school_code"],
                region_name=payload["region_name"],
                school_tier=payload["school_tier"],
                department_name=payload["department_name"],
                major_code=payload["major_code"],
                major_name=payload["major_name"],
                study_mode=payload["study_mode"],
                vacancy_count=sample_count,
                min_score=min(scores) if scores else None,
                avg_score=(sum(scores) / len(scores)) if scores else None,
                max_score=max(scores) if scores else None,
                verification_status="调剂上岸样本",
                title=title,
                summary=" · ".join(summary_parts),
                source_url=None,
                published_at=None,
                captured_at=None,
                meta_json={"dataset_title": landing_archive.title},
            )

    stats_2023_2025 = _select_archive(
        archives,
        dataset_keys=("adjustment_stats_2023_2025_raw",),
        source_filenames=("23-25调剂统计数据.xlsx",),
    )
    if stats_2023_2025 is not None:
        df = _normalize_legacy_adjustment_stats_frame(load_archive_dataframe(stats_2023_2025))
        grouped: dict[tuple[int | None, str, str | None, str | None, str | None, str | None], dict[str, Any]] = {}
        for row in df.to_dict(orient="records"):
            year = score_to_int(row.get("年份"))
            school_code, school_name = parse_school_code_name(row.get("学校"))
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            department_name = _strip_text(row.get("所属学院")) or None
            if department_name == "未区分院系":
                department_name = None
            major_code = normalize_major_code(row.get("专业代码"))
            major_name = normalize_major_name(row.get("专业名称"))
            study_mode = normalize_study_mode(row.get("学习形式"))
            region_name = parse_region_name(row.get("地区"))
            school_tier = _strip_text(row.get("院校类别")) or None
            score = score_to_int(row.get("初试总分"))
            group_key = (
                year,
                school_name_normalized,
                normalize_department_name(department_name),
                major_code,
                normalize_major_name(major_name),
                study_mode,
            )
            payload = grouped.setdefault(
                group_key,
                {
                    "school_name": school_name,
                    "school_code": school_code,
                    "region_name": region_name,
                    "school_tier": school_tier,
                    "department_name": department_name,
                    "major_code": major_code,
                    "major_name": major_name,
                    "study_mode": study_mode,
                    "scores": [],
                },
            )
            if score is not None:
                payload["scores"].append(score)
        for year, _school_name_normalized, _dept_norm, _major_code, _major_name_norm, _study_mode in grouped.keys():
            payload = grouped[(year, _school_name_normalized, _dept_norm, _major_code, _major_name_norm, _study_mode)]
            scores = payload.pop("scores")
            sample_count = len(scores) or None
            summary_parts = [f"{year or '未知'} 年历史调剂统计"]
            if payload["department_name"]:
                summary_parts.append(payload["department_name"])
            if sample_count:
                summary_parts.append(f"样本 {sample_count}")
            if scores:
                summary_parts.append(f"最低 {min(scores)}")
                summary_parts.append(f"均分 {round(sum(scores) / len(scores))}")
            title = f"{payload['school_name']} {payload['major_name'] or payload['major_code'] or '调剂'} 历史统计"
            add_row(
                source_dataset_key=stats_2023_2025.dataset_key,
                source_type="stats",
                year=year,
                school_name=payload["school_name"],
                school_code=payload["school_code"],
                region_name=payload["region_name"],
                school_tier=payload["school_tier"],
                department_name=payload["department_name"],
                major_code=payload["major_code"],
                major_name=payload["major_name"],
                study_mode=payload["study_mode"],
                vacancy_count=sample_count,
                min_score=min(scores) if scores else None,
                avg_score=(sum(scores) / len(scores)) if scores else None,
                max_score=max(scores) if scores else None,
                verification_status="历史统计",
                title=title,
                summary=" · ".join(summary_parts),
                source_url=None,
                published_at=None,
                captured_at=None,
                meta_json={"dataset_title": stats_2023_2025.title},
            )

    deduped: dict[str, dict[str, Any]] = {}
    for row in opportunities:
        deduped[row["opportunity_key"]] = row
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
        review_text = _clean_review_text(row.get("评价"))
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
class MentorReviewExcerptResult:
    mentor_name: str
    department_name: str | None
    risk_level: str | None
    review_tags: list[str]
    review_text: str


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


def load_mentor_review_excerpts(
    db: Session,
    *,
    school_name: str | None,
    department_name: str | None = None,
    limit: int = 5,
) -> list[MentorReviewExcerptResult]:
    normalized_school_name = normalize_school_name(school_name)
    if not normalized_school_name:
        return []
    normalized_department_name = normalize_department_name(department_name)
    rows = (
        db.query(MentorEvaluation)
        .filter(MentorEvaluation.school_name_normalized == normalized_school_name)
        .all()
    )
    if not rows:
        return []

    def sort_key(row: MentorEvaluation) -> tuple[int, int, int]:
        department_exact = int(
            bool(
                normalized_department_name
                and row.department_name_normalized
                and row.department_name_normalized == normalized_department_name
            )
        )
        risk_rank = 2 if row.risk_level == "warning" else 1 if row.risk_level == "positive" else 0
        tag_rank = len(row.review_tags or [])
        return (department_exact, risk_rank, tag_rank)

    excerpts: list[MentorReviewExcerptResult] = []
    for row in sorted(rows, key=sort_key, reverse=True)[:limit]:
        review_text = _clean_review_text(row.review_text)
        excerpts.append(
            MentorReviewExcerptResult(
                mentor_name=row.mentor_name,
                department_name=row.department_name,
                risk_level=row.risk_level,
                review_tags=[str(tag) for tag in (row.review_tags or []) if str(tag or "").strip()][:6],
                review_text=review_text[:240].rstrip(),
            )
        )
    return excerpts


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
