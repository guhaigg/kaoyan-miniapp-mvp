import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, require_admin_request
from ..models import Department, School
from ..schemas import (
    SchoolBulkImportResponse,
    SchoolImportSeedSchoolItem,
    SchoolImportSeedSummaryItem,
    SchoolImportSeedSummaryListResponse,
    SchoolSuggestItem,
    SchoolSuggestResponse,
)

router = APIRouter(prefix="/schools", tags=["schools"])


def _priority_targets_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "priority_school_targets_2026-03-18.json"


def _adjustment_priority_targets_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_priority_school_targets_2023_2025.json"


def _adjustment_supplemental_targets_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_supplemental_priority_targets_2024_2025.json"


def _adjustment_2024_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_opportunity_2024_summary.json"


def _adjustment_2025_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_opportunity_2025_snapshot_summary.json"


def _mentor_review_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "mentor_review_summary.json"


def _adjustment_landing_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_landing_2025_summary.json"


def _adjustment_snapshot_2024_0414_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_snapshot_2024_0414_summary.json"


def _program_catalog_2026_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "admission_program_catalog_2026_summary.json"


def _adjustment_stats_2025_full_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_stats_2025_full_summary.json"


def _adjustment_announcement_2025_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_announcement_2025_summary.json"


def _adjustment_landing_2024_summary_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_landing_2024_summary.json"


def _adjustment_expanded_targets_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "data" / "adjustment_expanded_priority_targets_2024_2026.json"


def _department_type_for_name(name: str) -> str:
    return "graduate_school" if "研究生院" in name else "college"


def _import_school_targets_from_path(path: Path, *, request: Request, db: Session, event_type: str) -> SchoolBulkImportResponse:
    payload = json.loads(path.read_text(encoding="utf-8"))

    created_schools = 0
    existing_schools = 0
    created_departments = 0
    existing_departments = 0

    for row in payload:
        school_name = str(row.get("school_name") or "").strip()
        department_name = str(row.get("department_name") or "").strip()
        if not school_name:
            continue

        school = db.query(School).filter(School.name == school_name).one_or_none()
        if school is None:
            school = School(name=school_name, aliases=[])
            db.add(school)
            db.flush()
            created_schools += 1
        else:
            existing_schools += 1

        if not department_name or department_name == "未区分院系":
            continue

        department = (
            db.query(Department)
            .filter(Department.school_id == school.id, Department.name == department_name)
            .one_or_none()
        )
        if department is None:
            db.add(
                Department(
                    school_id=school.id,
                    name=department_name,
                    aliases=[],
                    department_type=_department_type_for_name(department_name),
                )
            )
            created_departments += 1
        else:
            existing_departments += 1

    db.commit()
    audit_event(
        db,
        request,
        event_type,
        None,
        {
            "total_rows": len(payload),
            "created_schools": created_schools,
            "created_departments": created_departments,
        },
    )
    return SchoolBulkImportResponse(
        total_rows=len(payload),
        created_schools=created_schools,
        existing_schools=existing_schools,
        created_departments=created_departments,
        existing_departments=existing_departments,
    )


def _summary_top_school_items(raw_rows: list[dict], limit: int = 5) -> list[SchoolImportSeedSchoolItem]:
    items: list[SchoolImportSeedSchoolItem] = []
    for raw in raw_rows[:limit]:
        top_departments = []
        if isinstance(raw.get("top_departments"), list):
            top_departments = [
                str(row.get("department_name") or "").strip()
                for row in raw["top_departments"]
                if str(row.get("department_name") or "").strip()
            ]
        items.append(
            SchoolImportSeedSchoolItem(
                rank=int(raw["rank"]) if raw.get("rank") is not None else None,
                school_code=str(raw.get("school_code") or "").strip() or None,
                school_name=str(raw.get("school_name") or "").strip(),
                region_name=str(raw.get("region_name") or "").strip() or None,
                school_category=str(raw.get("school_category") or "").strip() or None,
                adjustment_count=int(raw["adjustment_count"]) if raw.get("adjustment_count") is not None else None,
                top_departments=top_departments,
            )
        )
    return items


def _load_school_import_seed_summaries() -> list[SchoolImportSeedSummaryItem]:
    base_dir = Path(__file__).resolve().parents[3] / "docs" / "data"
    adjustment_stats = json.loads((base_dir / "adjustment_stats_2023_2025_summary.json").read_text(encoding="utf-8"))
    adjustment_stats_targets = json.loads(_adjustment_priority_targets_path().read_text(encoding="utf-8"))
    adjustment_2024 = json.loads(_adjustment_2024_summary_path().read_text(encoding="utf-8"))
    adjustment_2025 = json.loads(_adjustment_2025_summary_path().read_text(encoding="utf-8"))
    supplemental_targets = json.loads(_adjustment_supplemental_targets_path().read_text(encoding="utf-8"))
    landing_summary = json.loads(_adjustment_landing_summary_path().read_text(encoding="utf-8"))
    mentor_reviews = json.loads(_mentor_review_summary_path().read_text(encoding="utf-8"))
    snapshot_2024 = json.loads(_adjustment_snapshot_2024_0414_summary_path().read_text(encoding="utf-8"))
    program_catalog_2026 = json.loads(_program_catalog_2026_summary_path().read_text(encoding="utf-8"))
    stats_2025_full = json.loads(_adjustment_stats_2025_full_summary_path().read_text(encoding="utf-8"))
    announcement_2025 = json.loads(_adjustment_announcement_2025_summary_path().read_text(encoding="utf-8"))
    landing_2024 = json.loads(_adjustment_landing_2024_summary_path().read_text(encoding="utf-8"))
    expanded_targets = json.loads(_adjustment_expanded_targets_path().read_text(encoding="utf-8"))

    return [
        SchoolImportSeedSummaryItem(
            source_key="adjustment_stats_2023_2025",
            title="23-25 调剂统计重点学校",
            description="基于 23-25 调剂统计表聚合出的高频学校/学院，适合先补 schools / departments 和栏目资产。",
            total_rows=int(adjustment_stats["total_rows"]),
            target_rows=len(adjustment_stats_targets),
            unique_schools=len(adjustment_stats.get("top_schools", [])),
            import_endpoint="/schools/import/adjustment-priority-targets",
            highlights=[
                f"年份覆盖：{', '.join(adjustment_stats.get('year_counts', {}).keys())}",
                f"学习形式：{', '.join(f'{k} {v}' for k, v in adjustment_stats.get('study_mode_counts', {}).items())}",
            ],
            top_schools=_summary_top_school_items(adjustment_stats.get("top_schools", [])),
        ),
        SchoolImportSeedSummaryItem(
            source_key="adjustment_supplemental_2024_2025",
            title="24 / 25 调剂补充重点学校",
            description="把 2024 调剂余额表和 2025 调剂快照表合并成新的补充学校 seed，用来继续扩学校/学院资产。",
            total_rows=int(adjustment_2024["total_rows"]) + int(adjustment_2025["total_rows"]),
            target_rows=len(supplemental_targets),
            unique_schools=len({str(row.get("school_name") or "").strip() for row in supplemental_targets if str(row.get("school_name") or "").strip()}),
            import_endpoint="/schools/import/adjustment-supplemental-targets",
            highlights=[
                f"2024 样本：{adjustment_2024['total_rows']} 条，学校 {adjustment_2024['unique_schools']} 所",
                f"2025 快照：{adjustment_2025['total_rows']} 条，学校 {adjustment_2025['unique_schools']} 所",
            ],
            top_schools=_summary_top_school_items(adjustment_2025.get("top_schools", [])),
        ),
        SchoolImportSeedSummaryItem(
            source_key="adjustment_landing_2025",
            title="25 调剂上岸结果画像",
            description="用于辅助判断哪些学校/学院在调剂结果层面持续活跃，适合做学校优先级和调剂画像，不直接导入学校主库。",
            total_rows=int(landing_summary["total_rows"]),
            unique_schools=int(landing_summary["unique_schools"]),
            import_endpoint=None,
            highlights=[
                f"院校层级：{', '.join(f'{k} {v}' for k, v in list(landing_summary.get('category_counts', {}).items())[:4])}",
                f"学习形式：{', '.join(f'{k} {v}' for k, v in list(landing_summary.get('study_mode_counts', {}).items())[:3])}",
            ],
            top_schools=_summary_top_school_items(landing_summary.get("top_schools", [])),
        ),
        SchoolImportSeedSummaryItem(
            source_key="adjustment_expanded_bundle_2024_2026",
            title="24 / 25 / 26 扩展资产包",
            description="用 2024 调剂快照、2025 公告与完整统计、2024 上岸画像、2026 招生专业目录继续补学校/学院资产。",
            total_rows=
            int(snapshot_2024["total_rows"])
            + int(program_catalog_2026["total_rows"])
            + int(stats_2025_full["total_rows"])
            + int(announcement_2025["total_rows"])
            + int(landing_2024["total_rows"]),
            target_rows=len(expanded_targets),
            unique_schools=len({str(row.get("school_name") or "").strip() for row in expanded_targets if str(row.get("school_name") or "").strip()}),
            import_endpoint="/schools/import/adjustment-expanded-targets",
            highlights=[
                f"2024 调剂快照：{snapshot_2024['total_rows']} 条，学校 {snapshot_2024['unique_schools']} 所",
                f"2025 公告：{announcement_2025['total_rows']} 条，学校 {announcement_2025['unique_schools']} 所",
                f"2026 专业目录：{program_catalog_2026['total_rows']} 条，学校 {program_catalog_2026['unique_schools']} 所",
            ],
            top_schools=_summary_top_school_items(announcement_2025.get("top_schools", [])),
        ),
        SchoolImportSeedSummaryItem(
            source_key="mentor_reviews",
            title="导师公开评价补充",
            description="导师评价数据质量足够做情报源，但不适合直接混入公告/调剂主搜索，当前先保留为独立清洗资产。",
            total_rows=int(mentor_reviews["total_rows"]),
            unique_schools=int(mentor_reviews["unique_schools"]),
            import_endpoint=None,
            highlights=[
                f"HTML 残留：{mentor_reviews['htmlish_rows']} 条",
                f"含外链：{mentor_reviews['url_rows']} 条",
                f"重复导师键：{mentor_reviews['duplicate_name_keys']} 组",
            ],
            top_schools=_summary_top_school_items(mentor_reviews.get("top_schools", [])),
        ),
    ]


@router.get("/suggest", response_model=SchoolSuggestResponse)
def suggest_schools(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> SchoolSuggestResponse:
    keyword = q.strip()
    query = db.query(School).filter(School.enabled == 1)
    if keyword:
        query = query.filter(or_(School.name.ilike(f"%{keyword}%"), School.province.ilike(f"%{keyword}%")))
    rows = query.order_by(School.updated_at.desc()).limit(limit).all()
    return SchoolSuggestResponse(items=[SchoolSuggestItem(id=x.id, name=x.name, province=x.province) for x in rows])


@router.post("/import/priority-targets", response_model=SchoolBulkImportResponse)
def import_priority_targets(request: Request, db: Session = Depends(get_db)) -> SchoolBulkImportResponse:
    require_admin_request(request)
    return _import_school_targets_from_path(
        _priority_targets_path(),
        request=request,
        db=db,
        event_type="schools.import_priority_targets",
    )


@router.post("/import/adjustment-priority-targets", response_model=SchoolBulkImportResponse)
def import_adjustment_priority_targets(request: Request, db: Session = Depends(get_db)) -> SchoolBulkImportResponse:
    require_admin_request(request)
    return _import_school_targets_from_path(
        _adjustment_priority_targets_path(),
        request=request,
        db=db,
        event_type="schools.import_adjustment_priority_targets",
    )


@router.post("/import/adjustment-supplemental-targets", response_model=SchoolBulkImportResponse)
def import_adjustment_supplemental_targets(request: Request, db: Session = Depends(get_db)) -> SchoolBulkImportResponse:
    require_admin_request(request)
    return _import_school_targets_from_path(
        _adjustment_supplemental_targets_path(),
        request=request,
        db=db,
        event_type="schools.import_adjustment_supplemental_targets",
    )


@router.post("/import/adjustment-expanded-targets", response_model=SchoolBulkImportResponse)
def import_adjustment_expanded_targets(request: Request, db: Session = Depends(get_db)) -> SchoolBulkImportResponse:
    require_admin_request(request)
    return _import_school_targets_from_path(
        _adjustment_expanded_targets_path(),
        request=request,
        db=db,
        event_type="schools.import_adjustment_expanded_targets",
    )


@router.get("/import/seed-summaries", response_model=SchoolImportSeedSummaryListResponse)
def school_import_seed_summaries(request: Request) -> SchoolImportSeedSummaryListResponse:
    require_admin_request(request)
    return SchoolImportSeedSummaryListResponse(items=_load_school_import_seed_summaries())
