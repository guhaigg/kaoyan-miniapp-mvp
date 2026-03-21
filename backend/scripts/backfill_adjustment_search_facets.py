from __future__ import annotations

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


def main() -> None:
    init_db()
    with SessionLocal() as db:
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
            .all()
        )
        payload_rows = [
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
            for row in rows
        ]
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

    print(json.dumps({"updated_rows": len(updates)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
