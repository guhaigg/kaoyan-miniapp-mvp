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
from app.services.polluted_announcement_cleanup import cleanup_polluted_announcement_data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect and delete cross-school polluted announcement data caused by cold-start host drift."
    )
    parser.add_argument("--school-name", type=str, default="", help="Only clean rows under the matched school name.")
    parser.add_argument(
        "--host-suffix",
        dest="host_suffixes",
        action="append",
        default=[],
        help="Restrict cleanup to a host suffix such as hbut.edu.cn. Can be provided multiple times.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show matched rows without committing.")
    args = parser.parse_args()

    with SessionLocal() as db:
        stats = cleanup_polluted_announcement_data(
            db,
            school_name=args.school_name.strip() or None,
            host_suffixes=[str(item or "").strip() for item in args.host_suffixes if str(item or "").strip()],
            dry_run=args.dry_run,
        )
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
