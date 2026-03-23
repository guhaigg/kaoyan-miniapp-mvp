from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy.orm import load_only

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import AdjustmentOpportunity  # noqa: E402
from app.services.historical_intelligence import _annotate_adjustment_search_facets  # noqa: E402


LOAD_BATCH_SIZE = 5000


def _load_adjustment_payload_rows(db) -> list[dict[str, object]]:
    rows = (
        db.query(AdjustmentOpportunity)
        .options(
            load_only(
                AdjustmentOpportunity.id,
                AdjustmentOpportunity.school_name_normalized,
                AdjustmentOpportunity.source_type,
                AdjustmentOpportunity.year,
                AdjustmentOpportunity.school_tier,
                AdjustmentOpportunity.department_name,
                AdjustmentOpportunity.department_name_normalized,
                AdjustmentOpportunity.major_code,
                AdjustmentOpportunity.major_name,
                AdjustmentOpportunity.major_name_normalized,
                AdjustmentOpportunity.study_mode,
                AdjustmentOpportunity.source_url,
                AdjustmentOpportunity.meta_json,
                AdjustmentOpportunity.region_name,
                AdjustmentOpportunity.initial_score_min,
                AdjustmentOpportunity.adjustment_score_min,
                AdjustmentOpportunity.min_score,
            )
        )
        .execution_options(stream_results=True)
        .yield_per(LOAD_BATCH_SIZE)
    )
    payload_rows: list[dict[str, object]] = []
    for row in rows:
        payload_rows.append(
            {
                "id": row.id,
                "school_name_normalized": row.school_name_normalized,
                "source_type": row.source_type,
                "year": row.year,
                "school_tier": row.school_tier,
                "department_name": row.department_name,
                "department_name_normalized": row.department_name_normalized,
                "major_code": row.major_code,
                "major_name": row.major_name,
                "major_name_normalized": row.major_name_normalized,
                "study_mode": row.study_mode,
                "source_url": row.source_url,
                "meta_json": dict(row.meta_json or {}),
                "region_name": row.region_name,
                "initial_score_min": row.initial_score_min,
                "adjustment_score_min": row.adjustment_score_min,
                "min_score": row.min_score,
            }
        )
    return payload_rows


def _run_exact_backfill() -> int:
    with SessionLocal() as db:
        payload_rows = _load_adjustment_payload_rows(db)
        annotated = _annotate_adjustment_search_facets(payload_rows)
        updates = [
            {
                "id": row["id"],
                "has_history": int(row.get("has_history") or 0),
                "is_long_track": int(row.get("is_long_track") or 0),
                "reference_link_count": int(row.get("reference_link_count") or 0),
                "min_score_required": row.get("min_score_required"),
            }
            for row in annotated
        ]
        for start in range(0, len(updates), 5000):
            db.bulk_update_mappings(AdjustmentOpportunity, updates[start : start + 5000])
            db.commit()
        return len(updates)


def _run_fast_backfill() -> int:
    # Broad-query score gating must use the strict cross-year national-line conversion.
    # Keep the legacy "fast" entrypoint for operational compatibility, but make it exact.
    return _run_exact_backfill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill denormalized adjustment search facets.")
    parser.add_argument(
        "--strategy",
        choices=("fast", "exact"),
        default="fast",
        help="Backfill strategy. Both modes now use strict Python recomputation; fast is a legacy alias for exact.",
    )
    args = parser.parse_args()

    init_db()
    updated_rows = _run_fast_backfill() if args.strategy == "fast" else _run_exact_backfill()
    print(json.dumps({"updated_rows": updated_rows, "strategy": args.strategy}, ensure_ascii=False))


if __name__ == "__main__":
    main()
