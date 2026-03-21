from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import HistoricalAdjustmentProfile
from .historical_intelligence import (
    ENGINEERING_CARE_MAJOR_CODES,
    NATIONAL_ADJUSTMENT_LINES,
    resolve_national_line_key,
    resolve_score_area,
)

RadarLevel = Literal["danger", "warning", "info", "success"]
RadarArea = Literal["A", "B"]


@dataclass(frozen=True)
class RadarCategory:
    key: str
    label: str


@dataclass(frozen=True)
class RadarPrediction:
    category_key: str
    category_label: str
    area: RadarArea
    win_rate: int
    level: RadarLevel
    national_line_year: int
    national_line_a: int
    national_line_b: int
    comparison_line: int
    national_line_reference_avg: float
    national_line_reference_years: list[int]
    historical_sample_count: int
    historical_group_count: int
    historical_benchmark_score: float | None
    historical_p25_score: float | None
    historical_p75_score: float | None
    delta_to_comparison_line: int
    advice: str


@dataclass(frozen=True)
class RadarProfileRow:
    year: int
    region_name: str | None
    major_code: str | None
    sample_count: int
    initial_score_min: int | None
    initial_score_max: int | None
    avg_score: float | None
    min_score: int | None
    max_score: int | None


def _normalize_category_token(value: str) -> str:
    return re.sub(r"[\s（）()【】\[\]·、/\\,，:：\-]+", "", value).lower()


def _build_category_aliases() -> dict[str, str]:
    latest_year = max(NATIONAL_ADJUSTMENT_LINES)
    aliases: dict[str, str] = {}
    for key, (label, _a, _b) in NATIONAL_ADJUSTMENT_LINES[latest_year].items():
        aliases[_normalize_category_token(key)] = key
        if key.startswith("0") and len(key) == 2:
            aliases[_normalize_category_token(key[1:])] = key
        aliases[_normalize_category_token(label)] = key

    aliases.update(
        {
            "工学": "08",
            "工科": "08",
            "工学不含照顾专业": "08",
            "工学不含照顾": "08",
            "电子信息": "08",
            "机械": "08",
            "工学照顾专业": "08_care",
            "照顾工学": "08_care",
            "理学": "07",
            "管理学": "12",
            "公共管理": "1252",
            "工商管理": "1251",
            "旅游管理": "1254",
            "会计": "1253",
            "审计": "1257",
            "图书情报": "1255",
            "工程管理": "1256",
            "教育学": "04",
            "教育专硕": "0451",
            "体育": "0403",
            "文学": "05",
            "历史学": "06",
            "医学": "10",
            "农学": "09",
            "艺术": "13",
            "交叉学科": "14",
        }
    )
    return aliases


CATEGORY_ALIASES = _build_category_aliases()


def resolve_radar_category(category: str) -> RadarCategory | None:
    raw = str(category or "").strip()
    if not raw:
        return None

    digits = re.sub(r"\D+", "", raw)
    latest_year = max(NATIONAL_ADJUSTMENT_LINES)
    latest_lines = NATIONAL_ADJUSTMENT_LINES[latest_year]
    if digits:
        if digits in latest_lines:
            label = latest_lines[digits][0]
            return RadarCategory(key=digits, label=label)
        if len(digits) >= 4 and digits[:4] in latest_lines:
            key = digits[:4]
            return RadarCategory(key=key, label=latest_lines[key][0])
        if len(digits) >= 2 and digits[:2] in latest_lines:
            key = digits[:2]
            return RadarCategory(key=key, label=latest_lines[key][0])

    alias_key = CATEGORY_ALIASES.get(_normalize_category_token(raw))
    if alias_key is None:
        return None
    label = latest_lines[alias_key][0]
    return RadarCategory(key=alias_key, label=label)


def _reference_years() -> list[int]:
    years = sorted(NATIONAL_ADJUSTMENT_LINES)
    return years[-3:] if len(years) >= 3 else years


def _line_payload(category_key: str, year: int) -> tuple[str, int, int]:
    payload = NATIONAL_ADJUSTMENT_LINES[year].get(category_key)
    if payload is None:
        raise KeyError(f"missing line payload for {category_key=} {year=}")
    return payload


def _baseline_from_profile(profile: HistoricalAdjustmentProfile | RadarProfileRow) -> float | None:
    if profile.initial_score_min is not None and profile.initial_score_max is not None:
        return round((float(profile.initial_score_min) + float(profile.initial_score_max)) / 2, 1)
    if profile.initial_score_min is not None:
        return float(profile.initial_score_min)
    if profile.initial_score_max is not None:
        return float(profile.initial_score_max)
    if profile.avg_score is not None:
        return float(profile.avg_score)
    if profile.min_score is not None and profile.max_score is not None:
        return round((float(profile.min_score) + float(profile.max_score)) / 2, 1)
    if profile.min_score is not None:
        return float(profile.min_score)
    if profile.max_score is not None:
        return float(profile.max_score)
    return None


def _build_profile_query(db: Session, category_key: str, years: list[int]):
    query = db.query(
        HistoricalAdjustmentProfile.year.label("year"),
        HistoricalAdjustmentProfile.region_name.label("region_name"),
        HistoricalAdjustmentProfile.major_code.label("major_code"),
        HistoricalAdjustmentProfile.sample_count.label("sample_count"),
        HistoricalAdjustmentProfile.initial_score_min.label("initial_score_min"),
        HistoricalAdjustmentProfile.initial_score_max.label("initial_score_max"),
        HistoricalAdjustmentProfile.avg_score.label("avg_score"),
        HistoricalAdjustmentProfile.min_score.label("min_score"),
        HistoricalAdjustmentProfile.max_score.label("max_score"),
    ).execution_options(stream_results=True).filter(
        HistoricalAdjustmentProfile.year.in_(years),
        HistoricalAdjustmentProfile.sample_count > 0,
        HistoricalAdjustmentProfile.major_code.is_not(None),
    )

    if category_key == "08_care":
        return query.filter(
            or_(*[HistoricalAdjustmentProfile.major_code.like(f"{prefix}%") for prefix in ENGINEERING_CARE_MAJOR_CODES])
        )

    prefix = category_key[:4] if len(category_key) >= 4 else category_key[:2]
    return query.filter(HistoricalAdjustmentProfile.major_code.like(f"{prefix}%"))


def _match_profile_category(profile: HistoricalAdjustmentProfile | RadarProfileRow, category_key: str) -> bool:
    if not profile.major_code:
        return False
    return resolve_national_line_key(profile.major_code) == category_key


def _conversion_offset(category_key: str, from_year: int | None, to_year: int | None, area: RadarArea) -> float | None:
    if from_year is None or to_year is None:
        return None
    try:
        _from_label, from_a, from_b = _line_payload(category_key, from_year)
        _to_label, to_a, to_b = _line_payload(category_key, to_year)
    except KeyError:
        return None
    from_total = from_b if area == "B" else from_a
    to_total = to_b if area == "B" else to_a
    return round(float(to_total) - float(from_total), 1)


def _weighted_quantile(samples: list[tuple[float, int]], quantile: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples, key=lambda item: item[0])
    total_weight = sum(weight for _value, weight in ordered)
    if total_weight <= 0:
        return None
    threshold = total_weight * quantile
    cumulative = 0
    for value, weight in ordered:
        cumulative += weight
        if cumulative >= threshold:
            return round(value, 1)
    return round(ordered[-1][0], 1)


def _candidate_percentile(samples: list[tuple[float, int]], score: int) -> float | None:
    if not samples:
        return None
    total_weight = sum(weight for _value, weight in samples)
    if total_weight <= 0:
        return None
    below_or_equal = sum(weight for value, weight in samples if score >= value)
    return (below_or_equal / total_weight) * 100


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _resolve_level(win_rate: int) -> RadarLevel:
    if win_rate < 25:
        return "danger"
    if win_rate < 50:
        return "warning"
    if win_rate < 78:
        return "info"
    return "success"


def _build_advice(
    *,
    score: int,
    category_label: str,
    area: RadarArea,
    national_line_year: int,
    comparison_line: int,
    delta: int,
    historical_benchmark_score: float | None,
    historical_p75_score: float | None,
    historical_sample_count: int,
    win_rate: int,
) -> str:
    area_label = f"{area}区"
    benchmark_clause = (
        f"，近三年同门类历史样本折算后的中位初试门槛约 {historical_benchmark_score:.1f} 分"
        if historical_benchmark_score is not None and historical_sample_count > 0
        else ""
    )
    upper_clause = (
        f"，上四分位约 {historical_p75_score:.1f} 分"
        if historical_p75_score is not None and historical_sample_count > 0
        else ""
    )

    if delta < -10:
        return (
            f"你当前 {score} 分，较 {national_line_year} 年 {area_label}{category_label}国家线 {comparison_line} 分仍低 {abs(delta)} 分"
            f"{benchmark_clause}{upper_clause}。建议先把目标放在 B 区、冷门方向或校内扩招机会，同时准备补充方案。"
        )
    if delta < 0:
        return (
            f"你当前 {score} 分处于 {area_label}线边缘，距 {national_line_year} 年国家线仅差 {abs(delta)} 分"
            f"{benchmark_clause}{upper_clause}。建议避开热门强校，优先关注信息更新快、连续活跃的双非院校。"
        )
    if win_rate < 78:
        return (
            f"你当前 {score} 分已高于 {national_line_year} 年 {area_label}国家线 {comparison_line} 分 {delta} 分"
            f"{benchmark_clause}{upper_clause}。初筛通过率处在可主动出击区间，建议广撒网并优先筛选历史样本稳定的院校。"
        )
    return (
        f"你当前 {score} 分显著高于 {national_line_year} 年 {area_label}国家线 {comparison_line} 分"
        f"{benchmark_clause}{upper_clause}。当前属于强势调剂区间，可以直接关注优质院校缺额并尽早联系导师。"
    )


def predict_adjustment_rate(
    db: Session,
    *,
    score: int,
    category: str,
    area: RadarArea = "A",
) -> RadarPrediction:
    resolved = resolve_radar_category(category)
    if resolved is None:
        raise ValueError("unsupported category")

    reference_years = _reference_years()
    national_line_year = max(NATIONAL_ADJUSTMENT_LINES)
    _label, national_line_a, national_line_b = _line_payload(resolved.key, national_line_year)
    comparison_line = national_line_b if area == "B" else national_line_a
    delta = int(score - comparison_line)

    reference_lines = [
        _line_payload(resolved.key, year)[2 if area == "B" else 1]
        for year in reference_years
    ]
    national_line_reference_avg = round(sum(reference_lines) / len(reference_lines), 1)

    samples: list[tuple[float, int]] = []
    historical_sample_count = 0
    historical_group_count = 0
    conversion_offsets: dict[tuple[int, RadarArea], float | None] = {}
    for raw_profile in _build_profile_query(db, resolved.key, reference_years).yield_per(1000):
        profile = RadarProfileRow(
            year=raw_profile.year,
            region_name=raw_profile.region_name,
            major_code=raw_profile.major_code,
            sample_count=int(raw_profile.sample_count or 0),
            initial_score_min=raw_profile.initial_score_min,
            initial_score_max=raw_profile.initial_score_max,
            avg_score=raw_profile.avg_score,
            min_score=raw_profile.min_score,
            max_score=raw_profile.max_score,
        )
        if not _match_profile_category(profile, resolved.key):
            continue
        baseline = _baseline_from_profile(profile)
        if baseline is None:
            continue
        sample_area = resolve_score_area(profile.region_name)
        offset_key = (profile.year, sample_area)
        if offset_key not in conversion_offsets:
            conversion_offsets[offset_key] = _conversion_offset(
                resolved.key,
                profile.year,
                national_line_year,
                sample_area,
            )
        offset = conversion_offsets[offset_key]
        if offset is None:
            continue
        converted = round(float(baseline) + float(offset), 1)
        weight = max(1, min(int(profile.sample_count or 1), 20))
        samples.append((float(converted), weight))
        historical_sample_count += int(profile.sample_count or 0)
        historical_group_count += 1

    historical_benchmark_score = _weighted_quantile(samples, 0.5)
    historical_p25_score = _weighted_quantile(samples, 0.25)
    historical_p75_score = _weighted_quantile(samples, 0.75)

    line_rate = _clamp(50 + delta * 2.6, 5, 95)
    percentile = _candidate_percentile(samples, score)
    if percentile is None:
        win_rate = round(line_rate)
    else:
        sample_rate = _clamp(8 + percentile * 0.88, 5, 96)
        sample_confidence = _clamp(historical_sample_count / 180, 0.18, 0.62)
        win_rate = round(line_rate * (1 - sample_confidence) + sample_rate * sample_confidence)
    level = _resolve_level(win_rate)

    advice = _build_advice(
        score=score,
        category_label=resolved.label,
        area=area,
        national_line_year=national_line_year,
        comparison_line=comparison_line,
        delta=delta,
        historical_benchmark_score=historical_benchmark_score,
        historical_p75_score=historical_p75_score,
        historical_sample_count=historical_sample_count,
        win_rate=win_rate,
    )

    return RadarPrediction(
        category_key=resolved.key,
        category_label=resolved.label,
        area=area,
        win_rate=win_rate,
        level=level,
        national_line_year=national_line_year,
        national_line_a=national_line_a,
        national_line_b=national_line_b,
        comparison_line=comparison_line,
        national_line_reference_avg=national_line_reference_avg,
        national_line_reference_years=reference_years,
        historical_sample_count=historical_sample_count,
        historical_group_count=historical_group_count,
        historical_benchmark_score=historical_benchmark_score,
        historical_p25_score=historical_p25_score,
        historical_p75_score=historical_p75_score,
        delta_to_comparison_line=delta,
        advice=advice,
    )
