#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.announcement_foundation import refresh_announcement_foundation


def main() -> int:
    parser = argparse.ArgumentParser(description="Build offline announcement foundation snapshots and seed registry.")
    parser.add_argument("--school-name", action="append", default=[], help="Restrict refresh to one or more school names.")
    parser.add_argument("--dry-run", action="store_true", help="Write candidates and diff only, do not update the final registry.")
    parser.add_argument("--source", action="append", default=[], help="Optional source selector, e.g. chsi / official_rosters / school_homepages.")
    parser.add_argument("--base-dir", default="", help="Optional output directory override.")
    args = parser.parse_args()

    result = refresh_announcement_foundation(
        base_dir=args.base_dir or None,
        school_names=args.school_name or None,
        dry_run=args.dry_run,
        sources=args.source or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
