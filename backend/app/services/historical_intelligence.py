from __future__ import annotations

import base64
import gzip
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from html import unescape
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, load_only

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

ENGINEERING_CARE_PREFIXES = ("0801", "0806", "0807", "0815", "0818", "0819", "0824", "0825", "0826", "0827", "0828")
SCORE_COLUMN_ALIASES = {
    "initial": (
        "初试总分",
        "初试成绩",
        "初始成绩",
        "初试分数",
        "总分",
    ),
    "adjustment": (
        "调剂成绩",
        "调剂总成绩",
        "调剂录取成绩",
        "拟录取成绩",
        "录取成绩",
        "复试成绩",
        "总成绩",
    ),
}
NATIONAL_LINES = {
    2023: {
        "philosophy": {"label": "哲学", "zone_a": 323, "zone_b": 313},
        "economics": {"label": "经济学", "zone_a": 346, "zone_b": 336},
        "law": {"label": "法学", "zone_a": 326, "zone_b": 316},
        "education": {"label": "教育学", "zone_a": 350, "zone_b": 340},
        "sports": {"label": "体育学/体育", "zone_a": 305, "zone_b": 295},
        "literature": {"label": "文学", "zone_a": 363, "zone_b": 353},
        "history": {"label": "历史学", "zone_a": 336, "zone_b": 326},
        "science": {"label": "理学", "zone_a": 279, "zone_b": 269},
        "engineering": {"label": "工学", "zone_a": 273, "zone_b": 263},
        "engineering_care": {"label": "工学照顾专业", "zone_a": 260, "zone_b": 250},
        "agriculture": {"label": "农学", "zone_a": 251, "zone_b": 241},
        "medicine": {"label": "医学", "zone_a": 296, "zone_b": 286},
        "medicine_tcm": {"label": "中医类照顾专业", "zone_a": 295, "zone_b": 285},
        "military": {"label": "军事学", "zone_a": 260, "zone_b": 250},
        "management": {"label": "管理学", "zone_a": 340, "zone_b": 330},
        "mba": {"label": "工商管理/旅游管理", "zone_a": 167, "zone_b": 157},
        "mpa": {"label": "公共管理", "zone_a": 175, "zone_b": 165},
        "accounting": {"label": "会计/审计", "zone_a": 197, "zone_b": 187},
        "library_info": {"label": "图书情报", "zone_a": 198, "zone_b": 188},
        "engineering_mgmt": {"label": "工程管理", "zone_a": 178, "zone_b": 168},
        "art": {"label": "艺术学/艺术", "zone_a": 362, "zone_b": 352},
        "interdisciplinary": {"label": "交叉学科", "zone_a": 265, "zone_b": 255},
    },
    2024: {
        "philosophy": {"label": "哲学", "zone_a": 333, "zone_b": 323},
        "economics": {"label": "经济学", "zone_a": 338, "zone_b": 328},
        "law": {"label": "法学", "zone_a": 331, "zone_b": 321},
        "education": {"label": "教育学/教育专硕", "zone_a": 350, "zone_b": 340},
        "sports": {"label": "体育学/体育", "zone_a": 313, "zone_b": 303},
        "literature": {"label": "文学", "zone_a": 365, "zone_b": 355},
        "history": {"label": "历史学", "zone_a": 345, "zone_b": 335},
        "science": {"label": "理学", "zone_a": 288, "zone_b": 278},
        "engineering": {"label": "工学", "zone_a": 273, "zone_b": 263},
        "engineering_care": {"label": "工学照顾专业", "zone_a": 260, "zone_b": 250},
        "agriculture": {"label": "农学", "zone_a": 251, "zone_b": 241},
        "medicine": {"label": "医学", "zone_a": 304, "zone_b": 294},
        "medicine_tcm": {"label": "中医学/中西医结合/中医", "zone_a": 303, "zone_b": 293},
        "military": {"label": "军事学", "zone_a": 260, "zone_b": 250},
        "management": {"label": "管理学", "zone_a": 347, "zone_b": 337},
        "mba": {"label": "工商管理/旅游管理", "zone_a": 162, "zone_b": 152},
        "tourism": {"label": "旅游管理", "zone_a": 162, "zone_b": 152},
        "mpa": {"label": "公共管理", "zone_a": 173, "zone_b": 163},
        "accounting": {"label": "会计/审计", "zone_a": 201, "zone_b": 191},
        "library_info": {"label": "图书情报", "zone_a": 198, "zone_b": 188},
        "engineering_mgmt": {"label": "工程管理", "zone_a": 176, "zone_b": 166},
        "art": {"label": "艺术学/艺术", "zone_a": 362, "zone_b": 352},
        "interdisciplinary": {"label": "交叉学科", "zone_a": 275, "zone_b": 265},
    },
    2025: {
        "philosophy": {"label": "哲学", "zone_a": 321, "zone_b": 311},
        "economics": {"label": "经济学", "zone_a": 323, "zone_b": 313},
        "law": {"label": "法学", "zone_a": 323, "zone_b": 313},
        "education": {"label": "教育学/教育专硕", "zone_a": 341, "zone_b": 331},
        "sports": {"label": "体育学/体育", "zone_a": 304, "zone_b": 294},
        "literature": {"label": "文学", "zone_a": 351, "zone_b": 341},
        "history": {"label": "历史学", "zone_a": 336, "zone_b": 326},
        "science": {"label": "理学", "zone_a": 274, "zone_b": 264},
        "engineering": {"label": "工学", "zone_a": 260, "zone_b": 250},
        "engineering_care": {"label": "工学照顾专业", "zone_a": 251, "zone_b": 241},
        "agriculture": {"label": "农学", "zone_a": 245, "zone_b": 235},
        "medicine": {"label": "医学", "zone_a": 293, "zone_b": 283},
        "military": {"label": "军事学", "zone_a": 260, "zone_b": 250},
        "management": {"label": "管理学", "zone_a": 333, "zone_b": 323},
        "mba": {"label": "工商管理", "zone_a": 151, "zone_b": 141},
        "tourism": {"label": "旅游管理", "zone_a": 151, "zone_b": 141},
        "mpa": {"label": "公共管理", "zone_a": 164, "zone_b": 154},
        "accounting": {"label": "会计/审计", "zone_a": 194, "zone_b": 184},
        "library_info": {"label": "图书情报", "zone_a": 191, "zone_b": 181},
        "engineering_mgmt": {"label": "工程管理", "zone_a": 162, "zone_b": 152},
        "art": {"label": "艺术学/艺术", "zone_a": 351, "zone_b": 341},
        "interdisciplinary": {"label": "交叉学科", "zone_a": 266, "zone_b": 256},
    },
    2026: {
        "philosophy": {"label": "哲学", "zone_a": 326, "zone_b": 316},
        "economics": {"label": "经济学", "zone_a": 324, "zone_b": 314},
        "law": {"label": "法学", "zone_a": 321, "zone_b": 311},
        "education": {"label": "教育学/教育专硕", "zone_a": 347, "zone_b": 337},
        "sports": {"label": "体育学/体育", "zone_a": 310, "zone_b": 300},
        "literature": {"label": "文学", "zone_a": 354, "zone_b": 344},
        "history": {"label": "历史学", "zone_a": 341, "zone_b": 331},
        "science": {"label": "理学", "zone_a": 275, "zone_b": 265},
        "engineering": {"label": "工学", "zone_a": 264, "zone_b": 254},
        "engineering_care": {"label": "工学照顾专业", "zone_a": 251, "zone_b": 241},
        "agriculture": {"label": "农学", "zone_a": 240, "zone_b": 230},
        "medicine": {"label": "医学", "zone_a": 294, "zone_b": 284},
        "military": {"label": "军事学", "zone_a": 260, "zone_b": 250},
        "management": {"label": "管理学", "zone_a": 332, "zone_b": 322},
        "mba": {"label": "工商管理", "zone_a": 146, "zone_b": 136},
        "tourism": {"label": "旅游管理", "zone_a": 151, "zone_b": 141},
        "mpa": {"label": "公共管理", "zone_a": 168, "zone_b": 158},
        "accounting": {"label": "会计/图书情报/审计", "zone_a": 199, "zone_b": 189},
        "library_info": {"label": "会计/图书情报/审计", "zone_a": 199, "zone_b": 189},
        "engineering_mgmt": {"label": "工程管理", "zone_a": 166, "zone_b": 156},
        "art": {"label": "艺术学/艺术", "zone_a": 354, "zone_b": 344},
        "interdisciplinary": {"label": "交叉学科", "zone_a": 266, "zone_b": 256},
    },
}


def _strip_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    return text


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


def _compact_place_name(value: str | None) -> str | None:
    text = _strip_text(value)
    if not text:
        return None
    text = re.sub(r"(省|市|壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|地区|自治州|盟)$", "", text)
    return text or None


def parse_region_parts(value: Any) -> tuple[str | None, str | None]:
    text = parse_region_name(value)
    if not text:
        return None, None
    province_match = re.match(r"^(.*?(?:省|市|自治区|特别行政区|壮族自治区|回族自治区|维吾尔自治区))(.*)$", text)
    if province_match:
        province = _compact_place_name(province_match.group(1))
        tail = province_match.group(2).strip()
        if tail:
            city_match = re.match(r"^(.*?(?:市|地区|自治州|盟)).*$", tail)
            city = _compact_place_name(city_match.group(1) if city_match else tail)
            return province, city
        return province, province
    compact = _compact_place_name(text)
    return compact, compact


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


def normalize_mentor_department_name(value: Any, *, school_name: Any | None = None) -> str | None:
    text = normalize_department_name(value)
    if not text:
        return None
    normalized_school_name = normalize_school_name(school_name)
    if normalized_school_name and text.startswith(normalized_school_name):
        text = text[len(normalized_school_name):]
    text = text.strip("（）()[]【】")
    matched = re.search(r"([\u4e00-\u9fa5A-Za-z0-9·]+?(?:学院|研究院|研究所|中心))", text)
    if matched:
        text = matched.group(1)
    text = re.sub(r"(学院|研究院|研究所|中心).*$", r"\1", text)
    return text or None


def canonicalize_reference_url(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = urlsplit(text)
    except Exception:
        return text.rstrip("/") or text
    if not parsed.scheme or not parsed.netloc:
        return text.rstrip("/") or text
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))


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


def _extract_score_from_columns(row: dict[str, Any], *columns: str) -> int | None:
    for column in columns:
        if column in row:
            parsed = score_to_int(row.get(column))
            if parsed is not None:
                return parsed
    return None


def _extract_initial_score(row: dict[str, Any]) -> int | None:
    return _extract_score_from_columns(row, *SCORE_COLUMN_ALIASES["initial"])


def _extract_adjustment_score(row: dict[str, Any]) -> int | None:
    return _extract_score_from_columns(row, *SCORE_COLUMN_ALIASES["adjustment"])


def _resolve_city_name(row: dict[str, Any], *, region_value: Any = None) -> str | None:
    for column in ("城市", "城市名称", "市", "地级市"):
        text = _compact_place_name(row.get(column))
        if text:
            return text
    _province, city = parse_region_parts(region_value)
    return city


def _resolve_region_and_city(row: dict[str, Any], *columns: str) -> tuple[str | None, str | None]:
    for column in columns:
        if column in row:
            region_name = parse_region_name(row.get(column))
            city_name = _resolve_city_name(row, region_value=row.get(column))
            if region_name or city_name:
                return region_name, city_name
    explicit_city = _resolve_city_name(row)
    return None, explicit_city


def decode_raw_archive_bytes(archive: RawDatasetArchive) -> bytes:
    source_path = Path(str(archive.source_path or "").strip()).expanduser()
    if source_path and source_path.exists() and source_path.is_file():
        return source_path.read_bytes()
    return gzip.decompress(base64.b64decode(archive.raw_file_payload))


def _load_archives_by_keys(
    db: Session,
    dataset_keys: list[str],
) -> dict[str, RawDatasetArchive]:
    if not dataset_keys:
        return {}
    rows = (
        db.query(RawDatasetArchive)
        .options(
            load_only(
                RawDatasetArchive.dataset_key,
                RawDatasetArchive.title,
                RawDatasetArchive.dataset_type,
                RawDatasetArchive.source_filename,
                RawDatasetArchive.source_path,
                RawDatasetArchive.workbook_format,
                RawDatasetArchive.primary_sheet_name,
            )
        )
        .filter(RawDatasetArchive.dataset_key.in_(dataset_keys))
        .all()
    )
    return {row.dataset_key: row for row in rows}


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


def _score_bounds(values: list[int]) -> tuple[int | None, int | None]:
    cleaned = [value for value in values if value is not None]
    if not cleaned:
        return None, None
    return min(cleaned), max(cleaned)


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
    department_name_normalized: str | None,
    major_code: str | None,
    major_name_normalized: str | None,
    study_mode: str | None,
) -> str:
    raw = "|".join(
        [
            str(year),
            source_type,
            school_name_normalized,
            department_name_normalized or "",
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
    physical_columns = {column.name for column in model.__table__.columns}
    for start in range(0, len(rows), batch_size):
        timestamp = utcnow()
        batch = [
            {
                "id": new_id(),
                "created_at": timestamp,
                "updated_at": timestamp,
                **{
                    key: value
                    for key, value in row.items()
                    if key in physical_columns
                },
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
                if key not in {"id", "created_at"} and key in physical_columns
            }
            db.execute(stmt.on_duplicate_key_update(**update_map))
        elif dialect == "sqlite":
            stmt = sqlite_insert(model).values(batch)
            update_map = {
                key: getattr(stmt.excluded, key)
                for key in batch[0].keys()
                if key not in {"id", "created_at"} and key in physical_columns
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


def _split_records_by_department_scope(
    records: list[Any],
    *,
    department_getter,
) -> list[list[Any]]:
    if not records:
        return []
    explicit_groups: dict[str, list[Any]] = defaultdict(list)
    missing_records: list[Any] = []
    for record in records:
        department_name_normalized = normalize_department_name(department_getter(record))
        if department_name_normalized:
            explicit_groups[department_name_normalized].append(record)
        else:
            missing_records.append(record)
    if not explicit_groups:
        return [records]
    if len(explicit_groups) == 1:
        only_group = next(iter(explicit_groups.values()))
        return [only_group + missing_records]
    scoped_groups = list(explicit_groups.values())
    if missing_records:
        scoped_groups.append(missing_records)
    return scoped_groups


def _apply_department_scope(
    rows: list[Any],
    *,
    department_name: str | None,
    department_getter,
) -> list[Any]:
    normalized_department_name = normalize_mentor_department_name(department_name)
    if not normalized_department_name:
        return rows
    exact_rows = [
        row
        for row in rows
        if normalize_department_name(department_getter(row)) == normalized_department_name
    ]
    if exact_rows:
        school_level_rows = [
            row
            for row in rows
            if not normalize_department_name(department_getter(row))
        ]
        return exact_rows + school_level_rows
    return [
        row
        for row in rows
        if not normalize_department_name(department_getter(row))
    ]


def _apply_mentor_department_scope(
    rows: list[MentorEvaluation],
    *,
    department_name: str | None,
) -> list[MentorEvaluation]:
    normalized_department_name = normalize_mentor_department_name(department_name)
    if normalized_department_name:
        return [
            row
            for row in rows
            if normalize_mentor_department_name(
                row.department_name_normalized or row.department_name,
                school_name=row.school_name_normalized or row.school_name,
            ) == normalized_department_name
        ]
    return [
        row
        for row in rows
        if not normalize_department_name(row.department_name_normalized or row.department_name)
    ]


def _apply_school_level_mentor_scope(rows: list[MentorEvaluation]) -> list[MentorEvaluation]:
    return rows


def _apply_exact_department_mentor_scope(
    rows: list[MentorEvaluation],
    *,
    department_name: str | None,
) -> list[MentorEvaluation]:
    normalized_department_name = normalize_mentor_department_name(department_name)
    if normalized_department_name:
        return [
            row
            for row in rows
            if normalize_mentor_department_name(
                row.department_name_normalized or row.department_name,
                school_name=row.school_name_normalized or row.school_name,
            ) == normalized_department_name
        ]
    return []


HISTORY_BACKED_OPPORTUNITY_SOURCE_TYPES = {"stats", "landing", "adjustment_stats"}
LONG_TRACK_MIN_YEARS = 3
LONG_TRACK_MIN_ROWS = 40


def _build_adjustment_search_facet_base_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("school_name_normalized") or "").strip(),
        str(normalize_major_code(row.get("major_code")) or "").strip(),
        str(normalize_major_name(row.get("major_name")) or row.get("major_name_normalized") or "").strip(),
        str(normalize_study_mode(row.get("study_mode")) or "").strip(),
    )


def _collect_adjustment_reference_link_count(rows: list[dict[str, Any]]) -> int:
    seen_urls: set[str] = set()
    for row in rows:
        meta = row.get("meta_json") if isinstance(row.get("meta_json"), dict) else {}
        raw_urls: list[str | None] = [row.get("source_url")]
        if isinstance(meta, dict):
            raw_urls.extend([meta.get("source_url"), meta.get("top_source_url")])
            if isinstance(meta.get("reference_urls"), list):
                raw_urls.extend(meta.get("reference_urls") or [])
        for candidate in raw_urls:
            canonical = canonicalize_reference_url(candidate)
            if canonical:
                seen_urls.add(canonical)
    return len(seen_urls)


def _build_adjustment_row_score_floor(row: dict[str, Any], *, target_year: int) -> int | None:
    raw_min = score_to_int(row.get("initial_score_min"))
    if raw_min is None and row.get("adjustment_score_min") is None:
        raw_min = score_to_int(row.get("min_score"))
    if raw_min is None:
        return None

    year = score_to_int(row.get("year"))
    if year is None:
        return raw_min

    converted = convert_score_between_years(
        score=raw_min,
        from_year=year,
        to_year=target_year,
        major_code=row.get("major_code"),
        area=resolve_score_area(row.get("region_name")),
    )
    if converted is None:
        return raw_min
    return int(round(converted))


def _annotate_adjustment_search_facets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows

    target_year = max(NATIONAL_ADJUSTMENT_LINES)
    school_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        school_key = str(row.get("school_name_normalized") or "").strip()
        if school_key:
            school_rows[school_key].append(row)

    long_track_by_school: dict[str, int] = {}
    for school_key, scoped_rows in school_rows.items():
        active_years = {int(year) for year in (score_to_int(row.get("year")) for row in scoped_rows) if year}
        long_track_by_school[school_key] = int(
            len(active_years) >= LONG_TRACK_MIN_YEARS or len(scoped_rows) >= LONG_TRACK_MIN_ROWS
        )

    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_build_adjustment_search_facet_base_key(row)].append(row)

    for grouped_rows in grouped.values():
        for scoped_rows in _split_records_by_department_scope(
            grouped_rows,
            department_getter=lambda row: row.get("department_name_normalized") or row.get("department_name"),
        ):
            has_history = int(
                any(str(row.get("source_type") or "").strip() in HISTORY_BACKED_OPPORTUNITY_SOURCE_TYPES for row in scoped_rows)
            )
            reference_link_count = _collect_adjustment_reference_link_count(scoped_rows)
            score_floor_candidates = [
                value
                for value in (
                    _build_adjustment_row_score_floor(row, target_year=target_year)
                    for row in scoped_rows
                )
                if value is not None
            ]
            min_score_required = min(score_floor_candidates) if score_floor_candidates else None
            for row in scoped_rows:
                row["has_history"] = has_history
                row["reference_link_count"] = reference_link_count
                row["min_score_required"] = min_score_required

    for row in rows:
        school_key = str(row.get("school_name_normalized") or "").strip()
        row["is_long_track"] = long_track_by_school.get(school_key, 0)
        row.setdefault("has_history", 0)
        row.setdefault("reference_link_count", 0)
        row.setdefault("min_score_required", None)
    return rows


def build_historical_profiles_from_archives(db: Session) -> list[dict[str, Any]]:
    archives = _load_archives_by_keys(
        db,
        [
            "adjustment_stats_2025_full_raw",
            "adjustment_stats_2023_2025_raw",
            "adjustment_landing_2024_raw",
            "adjustment_landing_2025_raw",
            "admission_program_catalog_2026_raw",
            "adjustment_snapshot_2025_0409_raw",
            "adjustment_announcement_2025_raw",
        ],
    )
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
            max_score = score_to_int(row.get("25调剂录取最高分")) or min_score
            avg_score = _safe_float(row.get("25调剂平均分"))
            profile_key = build_profile_key(
                year=2025,
                source_type="adjustment_stats",
                school_name_normalized=school_name_normalized,
                department_name_normalized=None,
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
                    "city_name": None,
                    "school_tier": None,
                    "department_name": None,
                    "department_name_normalized": None,
                    "major_code": major_code,
                    "major_name": major_name,
                    "major_name_normalized": major_name,
                    "study_mode": study_mode,
                    "sample_count": vacancy_count,
                    "vacancy_count": vacancy_count,
                    "initial_score_min": None,
                    "initial_score_max": None,
                    "adjustment_score_min": min_score,
                    "adjustment_score_max": max_score,
                    "min_score": min_score,
                    "avg_score": avg_score,
                    "max_score": max_score,
                    "meta_json": {"title": "2025 调剂统计完整版"},
                }
            )

    stats_2023_2025 = archives.get("adjustment_stats_2023_2025_raw")
    if stats_2023_2025 is not None:
        df = _normalize_legacy_adjustment_stats_frame(load_archive_dataframe(stats_2023_2025))
        grouped: dict[tuple[int | None, str, str | None, str | None, str | None], list[dict[str, Any]]] = defaultdict(list)
        for row in df.to_dict(orient="records"):
            year = score_to_int(row.get("年份"))
            school_code, school_name = parse_school_code_name(row.get("学校"))
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            department_name = _strip_text(row.get("所属学院")) or None
            if department_name == "未区分院系":
                department_name = None
            department_name_normalized = normalize_department_name(department_name)
            region_name, city_name = _resolve_region_and_city(row, "地区", "省份")
            school_tier = _strip_text(row.get("院校类别")) or None
            major_code = normalize_major_code(row.get("专业代码"))
            major_name = normalize_major_name(row.get("专业名称"))
            study_mode = normalize_study_mode(row.get("学习形式"))
            initial_score = _extract_initial_score(row)
            adjustment_score = _extract_adjustment_score(row)
            if initial_score is None and adjustment_score is None:
                continue
            group_key = (year, school_name_normalized, major_code, major_name, study_mode)
            grouped[group_key].append(
                {
                    "school_name": school_name,
                    "school_name_normalized": school_name_normalized,
                    "school_code": school_code,
                    "region_name": region_name,
                    "city_name": city_name,
                    "school_tier": school_tier,
                    "department_name": department_name,
                    "department_name_normalized": department_name_normalized,
                    "major_code": major_code,
                    "major_name": major_name,
                    "major_name_normalized": major_name,
                    "study_mode": study_mode,
                    "initial_score": initial_score,
                    "adjustment_score": adjustment_score,
                }
            )
        for (year, _school_name_normalized, _major_code, _major_name, _study_mode), records in grouped.items():
            for scoped_records in _split_records_by_department_scope(
                records,
                department_getter=lambda record: record.get("department_name_normalized"),
            ):
                payload = dict(scoped_records[0])
                explicit_department = next(
                    (
                        record
                        for record in scoped_records
                        if record.get("department_name_normalized")
                    ),
                    None,
                )
                if explicit_department is not None:
                    payload["department_name"] = explicit_department.get("department_name")
                    payload["department_name_normalized"] = explicit_department.get("department_name_normalized")
                initial_scores = [
                    int(record["initial_score"])
                    for record in scoped_records
                    if record.get("initial_score") is not None
                ]
                adjustment_scores = [
                    int(record["adjustment_score"])
                    for record in scoped_records
                    if record.get("adjustment_score") is not None
                ]
                initial_min, initial_max = _score_bounds(initial_scores)
                adjustment_min, adjustment_max = _score_bounds(adjustment_scores)
                sample_count = max(len(initial_scores), len(adjustment_scores))
                avg_score = round(sum(initial_scores) / sample_count, 2) if initial_scores and sample_count else None
                profile_key = build_profile_key(
                    year=year or 0,
                    source_type="adjustment_stats",
                    school_name_normalized=payload["school_name_normalized"],
                    department_name_normalized=payload.get("department_name_normalized"),
                    major_code=payload["major_code"],
                    major_name_normalized=payload["major_name_normalized"],
                    study_mode=payload["study_mode"],
                )
                profiles.append(
                    {
                        "profile_key": profile_key,
                        "year": year or 0,
                        "source_type": "adjustment_stats",
                        "source_dataset_key": stats_2023_2025.dataset_key,
                        "school_id": school_lookup.get(payload["school_name_normalized"]),
                        **payload,
                        "sample_count": sample_count,
                        "vacancy_count": sample_count,
                        "initial_score_min": initial_min,
                        "initial_score_max": initial_max,
                        "adjustment_score_min": adjustment_min,
                        "adjustment_score_max": adjustment_max,
                        "min_score": initial_min,
                        "avg_score": avg_score,
                        "max_score": initial_max,
                        "meta_json": {"title": "23-25 调剂统计数据"},
                    }
                )

    for year, dataset_key in ((2024, "adjustment_landing_2024_raw"), (2025, "adjustment_landing_2025_raw")):
        archive = archives.get(dataset_key)
        if archive is None:
            continue
        df = load_archive_dataframe(archive, sheet_name="总表")
        grouped: dict[tuple[str, str | None, str | None, str | None], list[dict[str, Any]]] = defaultdict(list)
        for row in df.to_dict(orient="records"):
            school_code, school_name = parse_school_code_name(row.get("调剂学校") or row.get("学校"))
            school_name_normalized = normalize_school_name(school_name)
            if not school_name_normalized:
                continue
            department_name = _strip_text(row.get("所属学院")) or None
            department_name_normalized = normalize_department_name(department_name)
            region_name, city_name = _resolve_region_and_city(row, "地区", "省份")
            school_tier = _strip_text(row.get("院校类别")) or None
            major_code = normalize_major_code(row.get("专业代码") or row.get("专业"))
            major_name = normalize_major_name(row.get("专业名称") or row.get("专业"))
            study_mode = normalize_study_mode(row.get("学习形式"))
            initial_score = _extract_initial_score(row)
            adjustment_score = _extract_adjustment_score(row)
            if initial_score is None and adjustment_score is None:
                continue
            group_key = (school_name_normalized, major_code, major_name, study_mode)
            grouped[group_key].append(
                {
                    "school_name": school_name,
                    "school_name_normalized": school_name_normalized,
                    "school_code": school_code,
                    "region_name": region_name,
                    "city_name": city_name,
                    "school_tier": school_tier,
                    "department_name": department_name,
                    "department_name_normalized": department_name_normalized,
                    "major_code": major_code,
                    "major_name": major_name,
                    "major_name_normalized": major_name,
                    "study_mode": study_mode,
                    "initial_score": initial_score,
                    "adjustment_score": adjustment_score,
                }
            )
        for records in grouped.values():
            for scoped_records in _split_records_by_department_scope(
                records,
                department_getter=lambda record: record.get("department_name_normalized"),
            ):
                payload = dict(scoped_records[0])
                explicit_department = next(
                    (
                        record
                        for record in scoped_records
                        if record.get("department_name_normalized")
                    ),
                    None,
                )
                if explicit_department is not None:
                    payload["department_name"] = explicit_department.get("department_name")
                    payload["department_name_normalized"] = explicit_department.get("department_name_normalized")
                initial_scores = [
                    int(record["initial_score"])
                    for record in scoped_records
                    if record.get("initial_score") is not None
                ]
                adjustment_scores = [
                    int(record["adjustment_score"])
                    for record in scoped_records
                    if record.get("adjustment_score") is not None
                ]
                sample_count = max(len(initial_scores), len(adjustment_scores))
                initial_min, initial_max = _score_bounds(initial_scores)
                adjustment_min, adjustment_max = _score_bounds(adjustment_scores)
                avg_score = round(sum(initial_scores) / sample_count, 2) if initial_scores and sample_count else None
                profile_key = build_profile_key(
                    year=year,
                    source_type="landing",
                    school_name_normalized=payload["school_name_normalized"],
                    department_name_normalized=payload.get("department_name_normalized"),
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
                        "initial_score_min": initial_min,
                        "initial_score_max": initial_max,
                        "adjustment_score_min": adjustment_min,
                        "adjustment_score_max": adjustment_max,
                        "min_score": initial_min,
                        "avg_score": avg_score,
                        "max_score": initial_max,
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
            department_name = _strip_text(row.get("学院")) or None
            department_name_normalized = normalize_department_name(department_name)
            major_code = normalize_major_code(row.get("专业代码"))
            major_name = normalize_major_name(row.get("专业名称"))
            vacancy_count = _safe_int(row.get("名额"), default=0)
            region_name, city_name = _resolve_region_and_city(row, "省份", "地区")
            profile_key = build_profile_key(
                year=2026,
                source_type="future_program",
                school_name_normalized=school_name_normalized,
                department_name_normalized=department_name_normalized,
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
                    "region_name": region_name,
                    "city_name": city_name,
                    "school_tier": None,
                    "department_name": department_name,
                    "department_name_normalized": department_name_normalized,
                    "major_code": major_code,
                    "major_name": major_name,
                    "major_name_normalized": major_name,
                    "study_mode": None,
                    "sample_count": vacancy_count,
                    "vacancy_count": vacancy_count,
                    "initial_score_min": None,
                    "initial_score_max": None,
                    "adjustment_score_min": None,
                    "adjustment_score_max": None,
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
                    "region_name": _resolve_region_and_city(row, "地区", "省份")[0],
                    "city_name": _resolve_region_and_city(row, "地区", "省份")[1],
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
                department_name_normalized=None,
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
                    "city_name": payload["city_name"],
                    "school_tier": None,
                    "department_name": None,
                    "department_name_normalized": None,
                    "major_code": None,
                    "major_name": None,
                    "major_name_normalized": None,
                    "study_mode": None,
                    "sample_count": int(payload["count"]),
                    "vacancy_count": None,
                    "initial_score_min": None,
                    "initial_score_max": None,
                    "adjustment_score_min": None,
                    "adjustment_score_max": None,
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
    archives = _load_archives_by_keys(
        db,
        [
            "admission_program_catalog_2026_raw",
            "adjustment_snapshot_2025_0409_raw",
            "adjustment_opportunity_2024_raw",
            "adjustment_snapshot_2024_0414_raw",
            "adjustment_announcement_2025_raw",
            "adjustment_stats_2025_full_raw",
            "adjustment_landing_2024_raw",
            "adjustment_landing_2025_raw",
            "adjustment_stats_2023_2025_raw",
        ],
    )
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
        city_name: str | None,
        school_tier: str | None,
        department_name: str | None,
        major_code: str | None,
        major_name: str | None,
        study_mode: str | None,
        vacancy_count: int | None,
        initial_score_min: int | None,
        initial_score_max: int | None,
        adjustment_score_min: int | None,
        adjustment_score_max: int | None,
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
        department_name_normalized = normalize_mentor_department_name(
            department_name,
            school_name=school_name,
        )
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
                "city_name": city_name,
                "school_tier": school_tier,
                "department_name": department_name,
                "department_name_normalized": department_name_normalized,
                "major_code": major_code,
                "major_name": major_name,
                "major_name_normalized": major_name_normalized,
                "study_mode": study_mode,
                "vacancy_count": vacancy_count,
                "initial_score_min": initial_score_min,
                "initial_score_max": initial_score_max,
                "adjustment_score_min": adjustment_score_min,
                "adjustment_score_max": adjustment_score_max,
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
            region_name, city_name = _resolve_region_and_city(row, "省份", "地区")
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
                city_name=city_name,
                school_tier=None,
                department_name=_strip_text(row.get("学院")) or None,
                major_code=major_code,
                major_name=major_name,
                study_mode=normalize_study_mode(row.get("学习形式")),
                vacancy_count=vacancy_count,
                initial_score_min=None,
                initial_score_max=None,
                adjustment_score_min=None,
                adjustment_score_max=None,
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
            region_name, city_name = _resolve_region_and_city(row, "地区", "省份")
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
                region_name=region_name,
                city_name=city_name,
                school_tier=None,
                department_name=_strip_text(row.get("学院")) or None,
                major_code=major_code,
                major_name=major_name,
                study_mode=normalize_study_mode(row.get("学习形式")),
                vacancy_count=vacancy_count,
                initial_score_min=None,
                initial_score_max=None,
                adjustment_score_min=None,
                adjustment_score_max=None,
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
                city_name=None,
                school_tier=None,
                department_name=department_name,
                major_code=major_code,
                major_name=major_name,
                study_mode=study_mode,
                vacancy_count=vacancy_count,
                initial_score_min=None,
                initial_score_max=None,
                adjustment_score_min=None,
                adjustment_score_max=None,
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
            region_name, city_name = _resolve_region_and_city(row, "地区", "省份")
            add_row(
                source_dataset_key=snapshot_2024.dataset_key,
                source_type="snapshot",
                year=2024,
                school_name=school_name,
                school_code=_strip_text(row.get("学校代码")) or None,
                region_name=region_name,
                city_name=city_name,
                school_tier=None,
                department_name=department_name,
                major_code=major_code,
                major_name=major_name,
                study_mode=study_mode,
                vacancy_count=vacancy_count,
                initial_score_min=None,
                initial_score_max=None,
                adjustment_score_min=None,
                adjustment_score_max=None,
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
            region_name, city_name = _resolve_region_and_city(row, "地区", "省份")
            add_row(
                source_dataset_key=announcement_2025.dataset_key,
                source_type="adjustment_notice",
                year=score_to_int(row.get("年份")) or 2025,
                school_name=school_name,
                school_code=None,
                region_name=region_name,
                city_name=city_name,
                school_tier=None,
                department_name=_strip_text(row.get("学院")) or None,
                major_code=major_code,
                major_name=major_name,
                study_mode=normalize_study_mode(row.get("学习形式")),
                vacancy_count=_safe_int(row.get("计划人数"), default=0) or None,
                initial_score_min=None,
                initial_score_max=None,
                adjustment_score_min=None,
                adjustment_score_max=None,
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
            adjustment_min_score = score_to_int(row.get("25调剂录取最低分"))
            adjustment_max_score = score_to_int(row.get("25调剂录取最高分")) or adjustment_min_score
            avg_score = _safe_float(row.get("25调剂平均分"))
            title = f"{school_name} {major_name or major_code or '调剂'} 历史统计"
            summary_parts = ["2025 年历史调剂统计"]
            if vacancy_count:
                summary_parts.append(f"调剂人数 {vacancy_count}")
            if adjustment_min_score is not None:
                summary_parts.append(f"最低 {adjustment_min_score}")
            if adjustment_max_score is not None and adjustment_max_score != adjustment_min_score:
                summary_parts.append(f"最高 {adjustment_max_score}")
            if avg_score is not None:
                summary_parts.append(f"均分 {round(avg_score, 1)}")
            add_row(
                source_dataset_key=stats25.dataset_key,
                source_type="stats",
                year=2025,
                school_name=school_name,
                school_code=school_code,
                region_name=None,
                city_name=None,
                school_tier=None,
                department_name=None,
                major_code=major_code,
                major_name=major_name,
                study_mode=study_mode,
                vacancy_count=vacancy_count,
                initial_score_min=None,
                initial_score_max=None,
                adjustment_score_min=adjustment_min_score,
                adjustment_score_max=adjustment_max_score,
                min_score=adjustment_min_score,
                avg_score=avg_score,
                max_score=adjustment_max_score,
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
            region_name, city_name = _resolve_region_and_city(row, "地区", "省份")
            school_tier = _strip_text(row.get("院校类别")) or None
            major_code = normalize_major_code(row.get("专业代码") or row.get("专业"))
            major_name = normalize_major_name(row.get("专业名称") or row.get("专业"))
            study_mode = normalize_study_mode(row.get("学习形式"))
            initial_score = _extract_initial_score(row)
            adjustment_score = _extract_adjustment_score(row)
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
                    "city_name": city_name,
                    "school_tier": school_tier,
                    "department_name": department_name,
                    "major_code": major_code,
                    "major_name": major_name,
                    "study_mode": study_mode,
                    "initial_scores": [],
                    "adjustment_scores": [],
                },
            )
            if initial_score is not None:
                payload["initial_scores"].append(initial_score)
            if adjustment_score is not None:
                payload["adjustment_scores"].append(adjustment_score)

        for payload in grouped.values():
            initial_scores = payload.pop("initial_scores")
            adjustment_scores = payload.pop("adjustment_scores")
            sample_count = len(initial_scores) or len(adjustment_scores) or None
            initial_min, initial_max = _score_bounds(initial_scores)
            adjustment_min, adjustment_max = _score_bounds(adjustment_scores)
            summary_parts = [f"{landing_year} 年调剂上岸样本"]
            if payload["department_name"]:
                summary_parts.append(payload["department_name"])
            if sample_count:
                summary_parts.append(f"样本 {sample_count}")
            if initial_min is not None:
                summary_parts.append(f"初试 {initial_min}-{initial_max}")
            if adjustment_min is not None:
                summary_parts.append(f"调剂 {adjustment_min}-{adjustment_max}")
            avg_score = round(sum(initial_scores) / len(initial_scores), 2) if initial_scores else None
            title = f"{payload['school_name']} {payload['major_name'] or payload['major_code'] or '调剂'} 上岸样本"
            add_row(
                source_dataset_key=landing_archive.dataset_key,
                source_type="landing",
                year=landing_year,
                school_name=payload["school_name"],
                school_code=payload["school_code"],
                region_name=payload["region_name"],
                city_name=payload["city_name"],
                school_tier=payload["school_tier"],
                department_name=payload["department_name"],
                major_code=payload["major_code"],
                major_name=payload["major_name"],
                study_mode=payload["study_mode"],
                vacancy_count=sample_count,
                initial_score_min=initial_min,
                initial_score_max=initial_max,
                adjustment_score_min=adjustment_min,
                adjustment_score_max=adjustment_max,
                min_score=initial_min,
                avg_score=avg_score,
                max_score=initial_max,
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
            region_name, city_name = _resolve_region_and_city(row, "地区", "省份")
            school_tier = _strip_text(row.get("院校类别")) or None
            initial_score = _extract_initial_score(row)
            adjustment_score = _extract_adjustment_score(row)
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
                    "city_name": city_name,
                    "school_tier": school_tier,
                    "department_name": department_name,
                    "major_code": major_code,
                    "major_name": major_name,
                    "study_mode": study_mode,
                    "initial_scores": [],
                    "adjustment_scores": [],
                },
            )
            if initial_score is not None:
                payload["initial_scores"].append(initial_score)
            if adjustment_score is not None:
                payload["adjustment_scores"].append(adjustment_score)
        for year, _school_name_normalized, _dept_norm, _major_code, _major_name_norm, _study_mode in grouped.keys():
            payload = grouped[(year, _school_name_normalized, _dept_norm, _major_code, _major_name_norm, _study_mode)]
            initial_scores = payload.pop("initial_scores")
            adjustment_scores = payload.pop("adjustment_scores")
            sample_count = len(initial_scores) or len(adjustment_scores) or None
            initial_min, initial_max = _score_bounds(initial_scores)
            adjustment_min, adjustment_max = _score_bounds(adjustment_scores)
            summary_parts = [f"{year or '未知'} 年历史调剂统计"]
            if payload["department_name"]:
                summary_parts.append(payload["department_name"])
            if sample_count:
                summary_parts.append(f"样本 {sample_count}")
            if initial_min is not None:
                summary_parts.append(f"初试 {initial_min}-{initial_max}")
            if adjustment_min is not None:
                summary_parts.append(f"调剂 {adjustment_min}-{adjustment_max}")
            avg_score = round(sum(initial_scores) / len(initial_scores), 2) if initial_scores else None
            title = f"{payload['school_name']} {payload['major_name'] or payload['major_code'] or '调剂'} 历史统计"
            add_row(
                source_dataset_key=stats_2023_2025.dataset_key,
                source_type="stats",
                year=year,
                school_name=payload["school_name"],
                school_code=payload["school_code"],
                region_name=payload["region_name"],
                city_name=payload["city_name"],
                school_tier=payload["school_tier"],
                department_name=payload["department_name"],
                major_code=payload["major_code"],
                major_name=payload["major_name"],
                study_mode=payload["study_mode"],
                vacancy_count=sample_count,
                initial_score_min=initial_min,
                initial_score_max=initial_max,
                adjustment_score_min=adjustment_min,
                adjustment_score_max=adjustment_max,
                min_score=initial_min,
                avg_score=avg_score,
                max_score=initial_max,
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

    school_dimension_map: dict[str, dict[str, str]] = defaultdict(dict)
    school_tier_counts: dict[str, Counter] = defaultdict(Counter)
    region_counts: dict[str, Counter] = defaultdict(Counter)
    city_counts: dict[str, Counter] = defaultdict(Counter)
    for row in deduped.values():
        school_key = str(row.get("school_name_normalized") or "").strip()
        if not school_key:
            continue
        if row.get("school_tier"):
            school_tier_counts[school_key][str(row["school_tier"]).strip()] += 1
        if row.get("region_name"):
            region_counts[school_key][str(row["region_name"]).strip()] += 1
        if row.get("city_name"):
            city_counts[school_key][str(row["city_name"]).strip()] += 1
    for school_key, counter in school_tier_counts.items():
        school_dimension_map[school_key]["school_tier"] = counter.most_common(1)[0][0]
    for school_key, counter in region_counts.items():
        school_dimension_map[school_key]["region_name"] = counter.most_common(1)[0][0]
    for school_key, counter in city_counts.items():
        school_dimension_map[school_key]["city_name"] = counter.most_common(1)[0][0]

    normalized_rows: list[dict[str, Any]] = []
    for row in deduped.values():
        school_key = str(row.get("school_name_normalized") or "").strip()
        if school_key:
            if not row.get("school_tier") and school_dimension_map[school_key].get("school_tier"):
                row["school_tier"] = school_dimension_map[school_key]["school_tier"]
            if not row.get("region_name") and school_dimension_map[school_key].get("region_name"):
                row["region_name"] = school_dimension_map[school_key]["region_name"]
            if not row.get("city_name") and school_dimension_map[school_key].get("city_name"):
                row["city_name"] = school_dimension_map[school_key]["city_name"]
        normalized_rows.append(row)
    return _annotate_adjustment_search_facets(normalized_rows)


def build_mentor_evaluations_from_archives(db: Session) -> list[dict[str, Any]]:
    archive = _load_archives_by_keys(db, ["mentor_reviews_raw"]).get("mentor_reviews_raw")
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
        department_name_normalized = normalize_mentor_department_name(
            department_name,
            school_name=school_name,
        )
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
    initial_score_min: int | None
    initial_score_max: int | None
    adjustment_score_min: int | None
    adjustment_score_max: int | None
    min_score: int | None
    avg_score: float | None
    max_score: int | None
    candidate_score: int | None
    delta_to_min: int | None
    delta_to_avg: int | None
    delta_to_max: int | None
    national_line_year: int | None = None
    national_line_major_category: str | None = None
    national_line_zone_a: int | None = None
    national_line_zone_b: int | None = None
    delta_to_zone_a: int | None = None
    delta_to_zone_b: int | None = None
    outlook: str | None = None
    outlook_label: str | None = None
    future_program_count: int | None = None


@dataclass
class NationalAdjustmentLineResult:
    year: int
    category_label: str
    area_a_total: int
    area_b_total: int
    comparison_area: str | None = None
    comparison_total: int | None = None
    delta_to_a: int | None = None
    delta_to_b: int | None = None


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


ENGINEERING_CARE_MAJOR_CODES = {
    "0801",
    "0806",
    "0807",
    "0815",
    "0818",
    "0819",
    "0824",
    "0825",
    "0826",
    "0827",
    "0828",
}

AREA_B_REGION_TOKENS = ("内蒙古", "广西", "海南", "贵州", "云南", "西藏", "甘肃", "青海", "宁夏", "新疆")

NATIONAL_ADJUSTMENT_LINES: dict[int, dict[str, tuple[str, int, int]]] = {
    2023: {
        "01": ("哲学", 323, 313),
        "02": ("经济学/经济类专硕", 346, 336),
        "03": ("法学/法律社工警务", 326, 316),
        "0403": ("体育学/体育", 305, 295),
        "0452": ("体育学/体育", 305, 295),
        "0451": ("教育/国际中文教育", 350, 340),
        "0453": ("教育/国际中文教育", 350, 340),
        "04": ("教育学", 350, 340),
        "05": ("文学/翻译新传出版", 363, 353),
        "06": ("历史学/文博", 336, 326),
        "07": ("理学", 279, 269),
        "08_care": ("工学照顾专业", 260, 250),
        "08": ("工学/电子信息机械等专硕", 273, 263),
        "09": ("农学/农业兽医园林林业", 251, 241),
        "1005": ("中医类照顾专业", 295, 285),
        "1006": ("中医类照顾专业", 295, 285),
        "1057": ("中医类照顾专业", 295, 285),
        "10": ("医学", 296, 286),
        "11": ("军事", 260, 250),
        "1251": ("工商管理", 167, 157),
        "1254": ("旅游管理", 167, 157),
        "1252": ("公共管理", 175, 165),
        "1253": ("会计/审计", 197, 187),
        "1257": ("会计/审计", 197, 187),
        "1255": ("图书情报", 198, 188),
        "1256": ("工程管理", 178, 168),
        "12": ("管理学", 340, 330),
        "13": ("艺术", 362, 352),
        "14": ("交叉学科", 265, 255),
    },
    2024: {
        "01": ("哲学", 333, 323),
        "02": ("经济学", 338, 328),
        "03": ("法学", 331, 321),
        "0403": ("体育学/体育", 313, 303),
        "0452": ("体育学/体育", 313, 303),
        "0451": ("教育/国际中文教育", 350, 340),
        "0453": ("教育/国际中文教育", 350, 340),
        "04": ("教育学", 350, 340),
        "05": ("文学", 365, 355),
        "06": ("历史学", 345, 335),
        "07": ("理学", 288, 278),
        "08_care": ("工学照顾专业", 260, 250),
        "08": ("工学", 273, 263),
        "09": ("农学", 251, 241),
        "1005": ("中医学/中西医结合/中医", 303, 293),
        "1006": ("中医学/中西医结合/中医", 303, 293),
        "1057": ("中医学/中西医结合/中医", 303, 293),
        "10": ("医学", 304, 294),
        "11": ("军事", 260, 250),
        "1251": ("工商管理/旅游管理", 162, 152),
        "1254": ("工商管理/旅游管理", 162, 152),
        "1252": ("公共管理", 173, 163),
        "1253": ("会计/审计", 201, 191),
        "1257": ("会计/审计", 201, 191),
        "1255": ("图书情报", 198, 188),
        "1256": ("工程管理", 176, 166),
        "12": ("管理学", 347, 337),
        "13": ("艺术", 362, 352),
        "14": ("交叉学科", 275, 265),
    },
    2025: {
        "01": ("哲学", 321, 311),
        "02": ("经济学", 323, 313),
        "03": ("法学", 323, 313),
        "0403": ("体育学/体育", 304, 294),
        "0452": ("体育学/体育", 304, 294),
        "0451": ("教育/国际中文教育", 341, 331),
        "0453": ("教育/国际中文教育", 341, 331),
        "04": ("教育学", 341, 331),
        "05": ("文学", 351, 341),
        "06": ("历史学", 336, 326),
        "07": ("理学", 274, 264),
        "08_care": ("工学照顾专业", 251, 241),
        "08": ("工学", 260, 250),
        "09": ("农学", 245, 235),
        "10": ("医学", 293, 283),
        "11": ("军事", 260, 250),
        "1251": ("工商管理/旅游管理", 151, 141),
        "1254": ("工商管理/旅游管理", 151, 141),
        "1252": ("公共管理", 164, 154),
        "1253": ("会计/审计", 194, 184),
        "1257": ("会计/审计", 194, 184),
        "1255": ("图书情报", 191, 181),
        "1256": ("工程管理", 162, 152),
        "12": ("管理学", 333, 323),
        "13": ("艺术", 351, 341),
        "14": ("交叉学科", 266, 256),
    },
    2026: {
        "01": ("哲学", 326, 316),
        "02": ("经济学", 324, 314),
        "03": ("法学", 321, 311),
        "0403": ("体育学/体育", 310, 300),
        "0452": ("体育学/体育", 310, 300),
        "0451": ("教育/国际中文教育", 347, 337),
        "0453": ("教育/国际中文教育", 347, 337),
        "04": ("教育学", 347, 337),
        "05": ("文学", 354, 344),
        "06": ("历史学", 341, 331),
        "07": ("理学", 275, 265),
        "08_care": ("工学照顾专业", 251, 241),
        "08": ("工学", 264, 254),
        "09": ("农学", 240, 230),
        "10": ("医学", 294, 284),
        "11": ("军事", 260, 250),
        "1251": ("工商管理", 146, 136),
        "1254": ("旅游管理", 151, 141),
        "1252": ("公共管理", 168, 158),
        "1253": ("会计/图情/审计", 199, 189),
        "1255": ("会计/图情/审计", 199, 189),
        "1257": ("会计/图情/审计", 199, 189),
        "1256": ("工程管理", 166, 156),
        "12": ("管理学", 332, 322),
        "13": ("艺术", 354, 344),
        "14": ("交叉学科", 266, 256),
    },
}


def resolve_national_line_key(major_code: str | None) -> str | None:
    normalized = normalize_major_code(major_code)
    if not normalized:
        return None
    prefix4 = normalized[:4]
    prefix2 = normalized[:2]
    if prefix4 in ENGINEERING_CARE_MAJOR_CODES:
        return "08_care"
    if prefix4 in {"0403", "0452", "0451", "0453", "1005", "1006", "1057", "1251", "1252", "1253", "1254", "1255", "1256", "1257"}:
        return prefix4
    return prefix2


def resolve_score_area(region_name: str | None) -> str:
    text = _strip_text(region_name)
    if any(token in text for token in AREA_B_REGION_TOKENS):
        return "B"
    return "A"


def _get_line_totals(year: int | None, major_code: str | None) -> tuple[str, int, int] | None:
    if year is None:
        return None
    year_lines = NATIONAL_ADJUSTMENT_LINES.get(int(year))
    if not year_lines:
        return None
    line_key = resolve_national_line_key(major_code)
    if not line_key:
        return None
    return year_lines.get(line_key) or year_lines.get(line_key[:2])


def build_national_adjustment_line(
    *,
    year: int | None,
    major_code: str | None,
    comparison_area: str | None,
    candidate_score: int | None,
) -> NationalAdjustmentLineResult | None:
    payload = _get_line_totals(year, major_code)
    if payload is None:
        return None
    category_label, area_a_total, area_b_total = payload
    comparison_total = None
    if comparison_area == "A":
        comparison_total = area_a_total
    elif comparison_area == "B":
        comparison_total = area_b_total
    return NationalAdjustmentLineResult(
        year=int(year),
        category_label=category_label,
        area_a_total=area_a_total,
        area_b_total=area_b_total,
        comparison_area=comparison_area,
        comparison_total=comparison_total,
        delta_to_a=(candidate_score - area_a_total) if candidate_score is not None else None,
        delta_to_b=(candidate_score - area_b_total) if candidate_score is not None else None,
    )


def convert_score_between_years(
    *,
    score: int | float | None,
    from_year: int | None,
    to_year: int | None,
    major_code: str | None,
    area: str,
) -> float | None:
    if score is None:
        return None
    from_payload = _get_line_totals(from_year, major_code)
    to_payload = _get_line_totals(to_year, major_code)
    if from_payload is None or to_payload is None:
        return None
    _from_label, from_a_total, from_b_total = from_payload
    _to_label, to_a_total, to_b_total = to_payload
    from_total = from_b_total if area == "B" else from_a_total
    to_total = to_b_total if area == "B" else to_a_total
    return round(float(score) - float(from_total) + float(to_total), 1)


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
    department_name: str | None,
    study_modes: list[str],
    candidate_score: int | None,
    reference_year: int | None = None,
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
    matched = _apply_department_scope(
        matched,
        department_name=department_name,
        department_getter=lambda row: row.department_name_normalized,
    )
    if not matched:
        return None
    score_profiles = [row for row in matched if row.source_type in {"adjustment_stats", "landing"}]
    future_profiles = [row for row in matched if row.source_type == "future_program"]
    if reference_year is not None:
        same_year_profiles = [row for row in score_profiles if row.year == reference_year]
        if same_year_profiles:
            score_profiles = same_year_profiles

    years = sorted({row.year for row in score_profiles if row.year})
    source_types = sorted({row.source_type for row in score_profiles})
    sample_count = sum(max(1, row.sample_count) for row in score_profiles)
    initial_min_candidates = [
        row.initial_score_min if row.initial_score_min is not None else row.min_score
        for row in score_profiles
        if row.initial_score_min is not None or (row.adjustment_score_min is None and row.min_score is not None)
    ]
    initial_max_candidates = [
        row.initial_score_max if row.initial_score_max is not None else row.max_score
        for row in score_profiles
        if row.initial_score_max is not None or (row.adjustment_score_max is None and row.max_score is not None)
    ]
    adjustment_min_candidates = [
        row.adjustment_score_min for row in score_profiles if row.adjustment_score_min is not None
    ]
    adjustment_max_candidates = [
        row.adjustment_score_max for row in score_profiles if row.adjustment_score_max is not None
    ]

    weighted_avg_num = 0.0
    weighted_avg_den = 0
    target_year = max(NATIONAL_ADJUSTMENT_LINES)
    line_major_code = normalized_codes[0] if normalized_codes else next(
        (row.major_code for row in matched if row.major_code),
        None,
    )
    comparison_area = next(
        (resolve_score_area(row.region_name) for row in score_profiles if _strip_text(row.region_name)),
        None,
    ) or next(
        (resolve_score_area(row.region_name) for row in future_profiles if _strip_text(row.region_name)),
        None,
    ) or "A"

    for row in score_profiles:
        row_major_code = row.major_code or line_major_code
        row_area = resolve_score_area(row.region_name) if _strip_text(row.region_name) else comparison_area
        baseline = row.avg_score if (row.initial_score_min is not None or row.initial_score_max is not None or row.adjustment_score_min is None) else None
        if baseline is None and row.initial_score_min is not None and row.initial_score_max is not None:
            baseline = (row.initial_score_min + row.initial_score_max) / 2
        converted_baseline = convert_score_between_years(
            score=baseline,
            from_year=row.year,
            to_year=target_year,
            major_code=row_major_code,
            area=row_area,
        )
        if converted_baseline is None:
            continue
        weight = max(1, row.sample_count)
        weighted_avg_num += converted_baseline * weight
        weighted_avg_den += weight
    avg_score = round(weighted_avg_num / weighted_avg_den, 1) if weighted_avg_den else None
    initial_score_min = min(initial_min_candidates) if initial_min_candidates else None
    initial_score_max = max(initial_max_candidates) if initial_max_candidates else None
    adjustment_score_min = min(adjustment_min_candidates) if adjustment_min_candidates else None
    adjustment_score_max = max(adjustment_max_candidates) if adjustment_max_candidates else None
    converted_min_candidates: list[float] = []
    converted_max_candidates: list[float] = []
    for row in score_profiles:
        row_major_code = row.major_code or line_major_code
        row_area = resolve_score_area(row.region_name) if _strip_text(row.region_name) else comparison_area
        raw_min = row.initial_score_min
        if raw_min is None and row.adjustment_score_min is None:
            raw_min = row.min_score
        raw_max = row.initial_score_max
        if raw_max is None and row.adjustment_score_max is None:
            raw_max = row.max_score
        converted_min = convert_score_between_years(
            score=raw_min,
            from_year=row.year,
            to_year=target_year,
            major_code=row_major_code,
            area=row_area,
        )
        converted_max = convert_score_between_years(
            score=raw_max,
            from_year=row.year,
            to_year=target_year,
            major_code=row_major_code,
            area=row_area,
        )
        if converted_min is not None:
            converted_min_candidates.append(converted_min)
        if converted_max is not None:
            converted_max_candidates.append(converted_max)
    min_score = int(round(min(converted_min_candidates))) if converted_min_candidates else initial_score_min
    max_score = int(round(max(converted_max_candidates))) if converted_max_candidates else initial_score_max

    outlook = None
    outlook_label = None
    delta_to_min = (candidate_score - min_score) if candidate_score is not None and min_score is not None else None
    delta_to_avg = (
        int(round(candidate_score - avg_score))
        if candidate_score is not None and avg_score is not None
        else None
    )
    delta_to_max = (candidate_score - max_score) if candidate_score is not None and max_score is not None else None
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
    line_year = target_year
    national_line = build_national_adjustment_line(
        year=line_year,
        major_code=line_major_code,
        comparison_area=comparison_area,
        candidate_score=candidate_score,
    )
    if not years and avg_score is None and min_score is None and future_program_count is None and national_line is None:
        return None
    return HistoricalAdjustmentInsightResult(
        sample_years=years,
        source_types=source_types,
        sample_count=sample_count,
        initial_score_min=initial_score_min,
        initial_score_max=initial_score_max,
        adjustment_score_min=adjustment_score_min,
        adjustment_score_max=adjustment_score_max,
        min_score=min_score,
        avg_score=avg_score,
        max_score=max_score,
        candidate_score=candidate_score,
        delta_to_min=delta_to_min,
        delta_to_avg=delta_to_avg,
        delta_to_max=delta_to_max,
        national_line_year=national_line.year if national_line is not None else None,
        national_line_major_category=national_line.category_label if national_line is not None else None,
        national_line_zone_a=national_line.area_a_total if national_line is not None else None,
        national_line_zone_b=national_line.area_b_total if national_line is not None else None,
        delta_to_zone_a=national_line.delta_to_a if national_line is not None else None,
        delta_to_zone_b=national_line.delta_to_b if national_line is not None else None,
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


def build_school_intelligence_insight(
    profiles: list[HistoricalAdjustmentProfile],
) -> SchoolIntelligenceInsightResult | None:
    if not profiles:
        return None

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
            canonical = canonicalize_reference_url(url)
            if canonical and canonical not in reference_urls:
                reference_urls.append(canonical)
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

    return SchoolIntelligenceInsightResult(
        profile_count=profile_count,
        active_years=active_years,
        source_types=source_types,
        future_program_count=future_program_count,
        reference_urls=reference_urls[:3],
        confidence_label=confidence_label,
        signal_detail=signal_detail,
    )


def load_mentor_evaluations_for_search(db: Session, school_names: list[str]) -> dict[str, list[MentorEvaluation]]:
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
    return grouped


def load_school_intelligence_for_search(
    db: Session, school_names: list[str]
) -> dict[str, SchoolIntelligenceInsightResult]:
    grouped = load_profiles_for_search(db, school_names)
    result: dict[str, SchoolIntelligenceInsightResult] = {}
    for school_name_normalized, profiles in grouped.items():
        insight = build_school_intelligence_insight(profiles)
        if insight is not None:
            result[school_name_normalized] = insight
    return result


def build_mentor_radar_insight(
    evaluations: list[MentorEvaluation],
    *,
    department_name: str | None = None,
    scope: Literal["resolved", "department", "school"] = "resolved",
) -> MentorRadarInsightResult | None:
    if scope == "school":
        scoped_evaluations = _apply_school_level_mentor_scope(evaluations)
    elif scope == "department":
        scoped_evaluations = _apply_exact_department_mentor_scope(
            evaluations,
            department_name=department_name,
        )
    else:
        scoped_evaluations = _apply_mentor_department_scope(
            evaluations,
            department_name=department_name,
        )
    if not scoped_evaluations:
        return None
    mentor_names = {
        row.mentor_name_normalized
        for row in scoped_evaluations
        if row.mentor_name_normalized
    }
    warning_count = sum(1 for row in scoped_evaluations if row.risk_level == "warning")
    positive_count = sum(1 for row in scoped_evaluations if row.risk_level == "positive")
    tag_counter: Counter[str] = Counter()
    for row in scoped_evaluations:
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
    return MentorRadarInsightResult(
        review_count=len(scoped_evaluations),
        mentor_count=len(mentor_names),
        warning_count=warning_count,
        positive_count=positive_count,
        top_tags=[label for label, _count in tag_counter.most_common(4)],
        risk_label=risk_label,
    )


def load_mentor_radar_for_search(db: Session, school_names: list[str]) -> dict[str, MentorRadarInsightResult]:
    grouped = load_mentor_evaluations_for_search(db, school_names)
    result: dict[str, MentorRadarInsightResult] = {}
    for school_name_normalized, evaluations in grouped.items():
        insight = build_mentor_radar_insight(evaluations)
        if insight is not None:
            result[school_name_normalized] = insight
    return result


def load_mentor_review_excerpts(
    db: Session,
    *,
    school_name: str | None,
    department_name: str | None = None,
    limit: int = 5,
    scope: Literal["resolved", "department", "school"] = "resolved",
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
    if scope == "school":
        scoped_rows = _apply_school_level_mentor_scope(rows)
    elif scope == "department":
        scoped_rows = _apply_exact_department_mentor_scope(
            rows,
            department_name=department_name,
        )
    else:
        scoped_rows = _apply_mentor_department_scope(
            rows,
            department_name=department_name,
        )
    if not scoped_rows:
        return []

    def sort_key(row: MentorEvaluation) -> tuple[int, int, int]:
        department_exact = int(
            bool(
                normalized_department_name
                and row.department_name_normalized
                and normalize_mentor_department_name(
                    row.department_name_normalized,
                    school_name=row.school_name_normalized or row.school_name,
                ) == normalized_department_name
            )
        )
        risk_rank = 2 if row.risk_level == "warning" else 1 if row.risk_level == "positive" else 0
        tag_rank = len(row.review_tags or [])
        return (department_exact, risk_rank, tag_rank)

    excerpts: list[MentorReviewExcerptResult] = []
    for row in sorted(scoped_rows, key=sort_key, reverse=True)[:limit]:
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
    archives = list(
        _load_archives_by_keys(
            db,
            [
                "adjustment_snapshot_2024_0414_raw",
                "adjustment_snapshot_2025_0409_raw",
                "adjustment_announcement_2025_raw",
            ],
        ).values()
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
