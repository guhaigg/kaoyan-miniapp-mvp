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
from app.services.announcement_asset_rebuild import rebuild_announcement_assets


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild crawler-backed announcement assets and requeue section discovery.")
    parser.add_argument("--school-name", type=str, default="", help="Optionally rebuild only a specific school.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the rebuild snapshot without mutating data.")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = rebuild_announcement_assets(
            db,
            school_name=args.school_name.strip() or None,
            dry_run=args.dry_run,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
