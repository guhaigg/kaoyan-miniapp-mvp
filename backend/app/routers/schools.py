import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import audit_event, require_admin_request
from ..models import Department, School
from ..schemas import SchoolBulkImportResponse, SchoolSuggestItem, SchoolSuggestResponse

router = APIRouter(prefix="/schools", tags=["schools"])


def _priority_targets_path() -> Path:
    return Path(__file__).resolve().parents[3] / "docs" / "priority_school_targets_2026-03-18.json"


def _department_type_for_name(name: str) -> str:
    return "graduate_school" if "研究生院" in name else "college"


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
    payload = json.loads(_priority_targets_path().read_text(encoding="utf-8"))

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
        "schools.import_priority_targets",
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
