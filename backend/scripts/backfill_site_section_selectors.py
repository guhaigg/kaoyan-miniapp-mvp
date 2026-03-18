#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import SessionLocal  # noqa: E402
from app.models import Department, School, SiteSection  # noqa: E402
from app.services.crawler import build_site_section_detail_selector_config, build_site_section_list_selector_config  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill default selector config for site sections.")
    parser.add_argument("--school", dest="school_name", help="Only update sections under the matched school name.")
    parser.add_argument("--department", dest="department_name", help="Only update sections under the matched department name.")
    parser.add_argument("--section-type", dest="section_type", help="Only update sections with this section_type.")
    parser.add_argument("--overwrite-existing", action="store_true", help="Replace existing selector config with defaults.")
    parser.add_argument("--disabled-too", action="store_true", help="Include disabled site sections.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without committing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as db:
        query = db.query(SiteSection)
        if args.school_name:
            query = query.join(School, isouter=True).filter(School.name.ilike(f"%{args.school_name.strip()}%"))
        if args.department_name:
            query = query.join(Department, isouter=True).filter(Department.name.ilike(f"%{args.department_name.strip()}%"))
        if args.section_type:
            query = query.filter(SiteSection.section_type == args.section_type.strip())
        if not args.disabled_too:
            query = query.filter(SiteSection.enabled == 1)

        sections = query.order_by(SiteSection.created_at.asc()).all()
        updated = 0
        for section in sections:
            current_list = section.list_selector_config or {}
            current_detail = section.detail_selector_config or {}
            next_list = build_site_section_list_selector_config(
                section,
                {} if args.overwrite_existing else current_list,
            )
            next_detail = build_site_section_detail_selector_config(
                section,
                {} if args.overwrite_existing else current_detail,
            )
            if next_list == current_list and next_detail == current_detail:
                continue

            section.list_selector_config = next_list
            section.detail_selector_config = next_detail
            updated += 1
            school_name = section.school.name if section.school else "-"
            department_name = section.department.name if section.department else "-"
            print(f"[update] {section.id} {school_name} / {department_name} / {section.name}")

        if args.dry_run:
            db.rollback()
            print(f"[dry-run] matched={len(sections)} would_update={updated}")
            return 0

        db.commit()
        print(f"[done] matched={len(sections)} updated={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
