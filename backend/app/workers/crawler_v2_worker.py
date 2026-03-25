from __future__ import annotations

import argparse
import time

from ..config import get_settings
from ..db import init_db
from ..services.workflow_v2 import workflow_engine


def run_worker(*, once: bool) -> None:
    settings = get_settings()
    init_db()
    sleep_seconds = max(0.2, float(settings.workflow_poll_interval_seconds))
    batch_size = max(1, int(settings.workflow_batch_size))

    while True:
        processed = workflow_engine.process_step_batch(
            batch_size=batch_size,
            worker_name="crawler-v2-worker",
        )
        if once:
            return
        time.sleep(0.05 if processed > 0 else sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the standalone crawler v2 workflow worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one batch and exit.")
    args = parser.parse_args()
    run_worker(once=bool(args.once))


if __name__ == "__main__":
    main()
