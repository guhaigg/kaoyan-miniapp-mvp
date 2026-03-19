from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal, init_db
from app.services.historical_intelligence import (  # noqa: E402
    build_historical_profiles_from_archives,
    build_release_timing_profiles_from_archives,
    build_mentor_evaluations_from_archives,
    replace_historical_adjustment_profiles,
    replace_release_timing_profiles,
    replace_mentor_evaluations,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import historical adjustment intelligence from archived raw datasets.")
    parser.add_argument("--skip-mentor", action="store_true", help="Skip mentor evaluation import.")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        profiles = build_historical_profiles_from_archives(db)
        profile_result = replace_historical_adjustment_profiles(db, profiles)
        timing_profiles = build_release_timing_profiles_from_archives(db)
        timing_result = replace_release_timing_profiles(db, timing_profiles)

        mentor_result = {"evaluations": 0}
        if not args.skip_mentor:
            evaluations = build_mentor_evaluations_from_archives(db)
            mentor_result = replace_mentor_evaluations(db, evaluations)

    print(
        json.dumps(
            {
                "historical_profiles": profile_result["profiles"],
                "release_timing_profiles": timing_result["profiles"],
                "mentor_evaluations": mentor_result["evaluations"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
