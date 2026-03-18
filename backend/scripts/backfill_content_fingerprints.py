import argparse

from app.db import SessionLocal
from app.models import Content, School
from app.services.content import _build_content_fingerprint
from app.schemas import ContentIn


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill content_fingerprint for existing contents.")
    parser.add_argument("--dry-run", action="store_true", help="Only report updates without committing.")
    parser.add_argument("--limit", type=int, default=0, help="Optional row limit for trial runs.")
    args = parser.parse_args()

    scanned = 0
    updated = 0
    skipped = 0
    collided = 0

    with SessionLocal() as db:
        seen_fingerprints = {
            row[0]
            for row in db.query(Content.content_fingerprint)
            .filter(Content.content_fingerprint.is_not(None), Content.content_fingerprint != "")
            .all()
            if row[0]
        }
        query = (
            db.query(Content)
            .outerjoin(School, School.id == Content.school_id)
            .filter((Content.content_fingerprint.is_(None)) | (Content.content_fingerprint == ""))
            .order_by(Content.created_at.asc())
        )
        if args.limit > 0:
            query = query.limit(args.limit)

        rows = query.all()
        for row in rows:
            scanned += 1
            school_name = row.school.name if row.school else None
            payload = ContentIn(
                category=row.category,
                title=row.title,
                body=row.body,
                summary=row.summary,
                school_name=school_name,
                source_url=row.source_url,
                source_type=row.source_type,
                published_at=row.published_at,
                region=row.region,
                major=row.major,
                extra=dict(row.extra or {}),
                raw_html=None,
            )
            fingerprint = _build_content_fingerprint(payload, school_name)
            duplicate = (
                db.query(Content.id)
                .filter(Content.content_fingerprint == fingerprint, Content.id != row.id)
                .first()
            )
            if duplicate is not None or fingerprint in seen_fingerprints:
                collided += 1
                continue
            if row.content_fingerprint == fingerprint:
                skipped += 1
                continue
            row.content_fingerprint = fingerprint
            seen_fingerprints.add(fingerprint)
            updated += 1

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    print(
        f"scanned={scanned} updated={updated} skipped={skipped} collided={collided} dry_run={args.dry_run}"
    )


if __name__ == "__main__":
    main()
