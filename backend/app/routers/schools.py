from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import School
from ..schemas import SchoolSuggestItem, SchoolSuggestResponse

router = APIRouter(prefix="/schools", tags=["schools"])


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

