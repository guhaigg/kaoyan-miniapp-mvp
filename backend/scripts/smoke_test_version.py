"""Smoke test for MVP test-version readiness.

Run with environment variables already set, for example:

  DATABASE_URL=mysql+pymysql://...
  USE_MOCK_WECHAT=true
  SECRET_KEY=...
  AUTO_CREATE_TABLES=false

This script validates:
1) health endpoint
2) silent shadow login
3) refresh=true job enqueue
4) worker job consumption
5) contents growth after worker run
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

# Allow running as: python scripts/smoke_test_version.py
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db import SessionLocal
from app.main import app
from app.models import Content, CrawlJob, Source
from app.worker import process_single_pending_job


def fail(message: str) -> int:
    print(f"[FAIL] {message}")
    return 1


def ok(message: str) -> None:
    print(f"[OK] {message}")


def main() -> int:
    client = TestClient(app)

    health = client.get("/api/v1/health")
    if health.status_code != 200:
        return fail(f"health status_code={health.status_code}")
    ok("health endpoint is reachable")

    login = client.post("/api/v1/auth/silent-login", json={"code": "smoke-test-version-001"})
    if login.status_code != 200:
        return fail(f"silent-login status_code={login.status_code} body={login.text}")
    token = login.json().get("visitor_token")
    if not token:
        return fail("silent-login missing visitor_token")
    ok("silent-login returns visitor_token")

    headers = {"Authorization": f"Bearer {token}"}
    with SessionLocal() as db:
        source_count = db.query(Source).filter(Source.enabled == 1).count()
    if source_count == 0:
        return fail("no enabled sources found; run source seed first")
    ok(f"enabled sources found: {source_count}")

    before_job_count = 0
    before_content_count = 0
    with SessionLocal() as db:
        before_job_count = db.query(CrawlJob).count()
        before_content_count = db.query(Content).count()

    queued = client.post(
        "/api/v1/search/announcements",
        json={"page": 1, "page_size": 5, "refresh": True},
        headers=headers,
    )
    if queued.status_code != 200:
        return fail(f"search(refresh=true) status_code={queued.status_code} body={queued.text}")
    job_id = queued.json().get("refresh_job_id")
    if not job_id:
        return fail("refresh=true response missing refresh_job_id")
    ok(f"refresh job created: {job_id}")

    before = client.get(f"/api/v1/jobs/{job_id}")
    if before.status_code != 200:
        return fail(f"job status before worker status_code={before.status_code}")
    ok(f"job status before worker: {before.json().get('status')}")

    ran = process_single_pending_job()
    if not ran:
        return fail("worker did not pick up a pending job")
    ok("worker consumed one pending job")

    after = client.get(f"/api/v1/jobs/{job_id}")
    if after.status_code != 200:
        return fail(f"job status after worker status_code={after.status_code}")
    after_payload = after.json()
    if after_payload.get("status") not in {"completed", "failed"}:
        return fail(f"unexpected job status: {after_payload.get('status')}")
    ok(f"job status after worker: {after_payload.get('status')}")
    print(f"[INFO] job message: {after_payload.get('message')}")

    with SessionLocal() as db:
        after_job_count = db.query(CrawlJob).count()
        after_content_count = db.query(Content).count()

    if after_job_count <= before_job_count:
        return fail("crawl_jobs count did not increase")
    ok(f"crawl_jobs increased: {before_job_count} -> {after_job_count}")

    if after_content_count < before_content_count:
        return fail("contents count decreased unexpectedly")
    ok(f"contents count: {before_content_count} -> {after_content_count}")

    print("[DONE] smoke test finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
