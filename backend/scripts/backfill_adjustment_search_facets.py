from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy import text
from sqlalchemy.orm import load_only

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import AdjustmentOpportunity  # noqa: E402
from app.services.historical_intelligence import _annotate_adjustment_search_facets  # noqa: E402


def _run_exact_backfill() -> int:
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
        return len(updates)


def _run_fast_backfill() -> int:
    with SessionLocal() as db:
        dialect = (db.bind.dialect.name if db.bind is not None else "").lower()
        if dialect != "mysql":
            return _run_exact_backfill()

        statements = [
            """
            UPDATE adjustment_opportunities
            SET has_history = 0,
                is_long_track = 0,
                reference_link_count = 0,
                min_score_required = NULL
            """,
            """
            UPDATE adjustment_opportunities a
            JOIN (
                SELECT DISTINCT
                    school_name_normalized,
                    COALESCE(major_code, '') AS major_code_key,
                    COALESCE(major_name_normalized, '') AS major_name_key,
                    COALESCE(study_mode, '') AS study_mode_key
                FROM adjustment_opportunities
                WHERE source_type IN ('stats', 'landing', 'adjustment_stats')
            ) h
              ON a.school_name_normalized = h.school_name_normalized
             AND COALESCE(a.major_code, '') = h.major_code_key
             AND COALESCE(a.major_name_normalized, '') = h.major_name_key
             AND COALESCE(a.study_mode, '') = h.study_mode_key
            SET a.has_history = 1
            """,
            """
            UPDATE adjustment_opportunities a
            JOIN (
                SELECT school_name_normalized
                FROM adjustment_opportunities
                GROUP BY school_name_normalized
                HAVING COUNT(DISTINCT year) >= 3 OR COUNT(*) >= 40
            ) s
              ON a.school_name_normalized = s.school_name_normalized
            SET a.is_long_track = 1
            """,
            """
            UPDATE adjustment_opportunities
            SET reference_link_count =
                (CASE WHEN source_url IS NOT NULL AND TRIM(source_url) <> '' THEN 1 ELSE 0 END)
                + (CASE
                    WHEN JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.source_url')) IS NOT NULL
                     AND JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.source_url')) <> ''
                    THEN 1 ELSE 0 END)
                + (CASE
                    WHEN JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.top_source_url')) IS NOT NULL
                     AND JSON_UNQUOTE(JSON_EXTRACT(meta_json, '$.top_source_url')) <> ''
                    THEN 1 ELSE 0 END)
                + COALESCE(JSON_LENGTH(JSON_EXTRACT(meta_json, '$.reference_urls')), 0)
            """,
            """
            UPDATE adjustment_opportunities a
            JOIN (
                SELECT
                    school_name_normalized,
                    COALESCE(major_code, '') AS major_code_key,
                    COALESCE(major_name_normalized, '') AS major_name_key,
                    COALESCE(study_mode, '') AS study_mode_key,
                    MIN(
                        CASE
                            WHEN initial_score_min IS NOT NULL THEN initial_score_min
                            WHEN adjustment_score_min IS NULL THEN min_score
                            ELSE NULL
                        END
                    ) AS score_floor
                FROM adjustment_opportunities
                GROUP BY
                    school_name_normalized,
                    COALESCE(major_code, ''),
                    COALESCE(major_name_normalized, ''),
                    COALESCE(study_mode, '')
            ) g
              ON a.school_name_normalized = g.school_name_normalized
             AND COALESCE(a.major_code, '') = g.major_code_key
             AND COALESCE(a.major_name_normalized, '') = g.major_name_key
             AND COALESCE(a.study_mode, '') = g.study_mode_key
            SET a.min_score_required = g.score_floor
            """,
        ]
        for statement in statements:
            db.execute(text(" ".join(statement.split())))
            db.commit()

        updated_rows = db.execute(text("SELECT COUNT(*) FROM adjustment_opportunities")).scalar() or 0
        return int(updated_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill denormalized adjustment search facets.")
    parser.add_argument(
        "--strategy",
        choices=("fast", "exact"),
        default="fast",
        help="Backfill strategy. fast uses SQL approximations on MySQL; exact uses Python recomputation.",
    )
    args = parser.parse_args()

    init_db()
    updated_rows = _run_fast_backfill() if args.strategy == "fast" else _run_exact_backfill()
    print(json.dumps({"updated_rows": updated_rows, "strategy": args.strategy}, ensure_ascii=False))


if __name__ == "__main__":
    main()
