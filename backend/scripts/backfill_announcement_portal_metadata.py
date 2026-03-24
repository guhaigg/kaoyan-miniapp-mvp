#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.services.announcement_portal_backfill import backfill_announcement_portal_metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill portal metadata and system tags for existing announcement contents."
    )
    parser.add_argument("--school-name", type=str, default="", help="Only process rows under the matched school name.")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of scanned announcement rows.")
    parser.add_argument("--overwrite", action="store_true", help="Recompute portal fields and system tags even when present.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing.")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = backfill_announcement_portal_metadata(
            db,
            school_name=args.school_name.strip() or None,
            limit=args.limit,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
