import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import School, Source


def load_seed_file(path: Path) -> list[dict]:
    content = path.read_text(encoding="utf-8")
    return json.loads(content)


def upsert_source(db: Session, school_name: str, source_name: str, source_url: str) -> str:
    school = db.query(School).filter(School.name == school_name).one_or_none()
    if school is None:
        school = School(name=school_name, aliases=[])
        db.add(school)
        db.flush()

    source = db.query(Source).filter(Source.school_id == school.id, Source.base_url == source_url).one_or_none()
    status = "updated" if source else "created"
    source = source or Source()
    source.school_id = school.id
    source.name = source_name
    source.base_url = source_url
    source.source_type = "official"
    source.enabled = 1
    source.config = {"categories": ["announcement", "adjustment"]}
    if status == "created":
        db.add(source)
    return status


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    seed_path = root / "data" / "seed_sources_week4.json"
    rows = load_seed_file(seed_path)

    created = 0
    updated = 0
    with SessionLocal() as db:
        for row in rows:
            status = upsert_source(
                db,
                school_name=str(row.get("name", "")).strip(),
                source_name=str(row.get("type", "")).strip() or "研招公告",
                source_url=str(row.get("url", "")).strip(),
            )
            if status == "created":
                created += 1
            else:
                updated += 1
        db.commit()

    print(f"seed_sources_done created={created} updated={updated} total={len(rows)}")


if __name__ == "__main__":
    main()

