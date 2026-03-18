#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import Content
from app.services.nlp import extract_domain_tags


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill missing content tags into contents.extra.tags")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of rows to process")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without committing")
    parser.add_argument("--overwrite", action="store_true", help="Recompute tags even when contents.extra.tags already exists")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Content).order_by(Content.created_at.asc(), Content.id.asc())
        if args.limit and args.limit > 0:
            query = query.limit(args.limit)

        scanned = 0
        updated = 0
        skipped = 0

        for row in query.all():
            scanned += 1
            extra = dict(row.extra or {})
            existing_tags = [str(tag).strip() for tag in (extra.get("tags") or []) if str(tag).strip()]
            if existing_tags and not args.overwrite:
                skipped += 1
                continue

            text = "\n".join(part.strip() for part in [row.title or "", row.summary or "", row.body or ""] if part and part.strip())
            tags = extract_domain_tags(text)
            if not tags:
                skipped += 1
                continue

            extra["tags"] = tags
            updated += 1
            if not args.dry_run:
                row.extra = extra

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print(f"scanned={scanned} updated={updated} skipped={skipped} dry_run={args.dry_run}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
