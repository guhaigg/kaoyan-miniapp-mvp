from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.services.monitor_target_repair import repair_broken_monitor_targets


def main() -> None:
    with SessionLocal() as db:
        stats = repair_broken_monitor_targets(db)
    print(
        "repair_broken_monitor_targets",
        " ".join(f"{key}={value}" for key, value in stats.items()),
    )


if __name__ == "__main__":
    main()
