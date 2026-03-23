from __future__ import annotations

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
