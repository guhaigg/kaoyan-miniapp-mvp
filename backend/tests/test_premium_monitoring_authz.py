from __future__ import annotations

import pytest
from fastapi.routing import APIRoute

from app.db import SessionLocal
from app.main import app
from app.models import PortalUser, School
from app.services.account_access import ENTITLEMENT_SOURCE_ADMIN_GRANT, upsert_premium_entitlement


def _extract_payload(response):
    body = response.json()
    if isinstance(body, dict) and {"code", "msg", "data"}.issubset(body.keys()):
        return body["data"]
    return body


def _route_exists(path_template: str, method: str) -> bool:
    method = method.upper()
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path_template and method in route.methods:
            return True
    return False


def _require_monitoring_api() -> None:
    enabled = any(
        isinstance(route, APIRoute) and route.path.startswith("/api/v1/monitoring")
        for route in app.routes
    )
    if not enabled:
        pytest.skip("premium monitoring API routes are not wired in app.main yet")


def _register_and_login(client, username: str) -> tuple[str, dict[str, str]]:
    register = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "StrongPass123", "nickname": f"{username}-nick"},
    )
    assert register.status_code == 200, register.text
    user_id = register.json()["user_id"]

    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "StrongPass123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return user_id, {"X-User-Token": token}


def _enable_premium_for_user(user_id: str) -> None:
    with SessionLocal() as db:
        upsert_premium_entitlement(
            db,
            user_id=user_id,
            operator_account_id=None,
            expires_at=None,
            source=ENTITLEMENT_SOURCE_ADMIN_GRANT,
        )
        db.commit()


def _ensure_school_id(name: str = "电子科技大学") -> str:
    with SessionLocal() as db:
        school = db.query(School).filter(School.name == name).order_by(School.created_at.asc()).first()
        if school is None:
            school = School(name=name, aliases=[], province="四川", enabled=1)
            db.add(school)
            db.commit()
            db.refresh(school)
        return school.id


def _base_target_payload() -> dict:
    return {
        "scope_type": "school",
        "school_id": _ensure_school_id(),
        "check_interval_minutes": 60,
    }


def test_regular_user_cannot_create_monitor_target(client):
    _require_monitoring_api()
    assert _route_exists("/api/v1/monitoring/targets", "POST")

    _user_id, user_headers = _register_and_login(client, "monitor_regular_user")
    response = client.post("/api/v1/monitoring/targets", json=_base_target_payload(), headers=user_headers)
    assert response.status_code == 403, response.text


def test_premium_user_can_create_list_and_update_target(client):
    _require_monitoring_api()
    assert _route_exists("/api/v1/monitoring/targets", "POST")
    assert _route_exists("/api/v1/monitoring/targets", "GET")
    assert _route_exists("/api/v1/monitoring/targets/{target_id}", "PATCH")

    user_id, user_headers = _register_and_login(client, "monitor_premium_user")
    _enable_premium_for_user(user_id)

    create_response = client.post("/api/v1/monitoring/targets", json=_base_target_payload(), headers=user_headers)
    assert create_response.status_code == 200, create_response.text
    created = _extract_payload(create_response)
    target_id = created["id"]

    list_response = client.get("/api/v1/monitoring/targets", headers=user_headers)
    assert list_response.status_code == 200, list_response.text
    listed = _extract_payload(list_response)
    items = listed["items"] if isinstance(listed, dict) else listed
    assert any(item["id"] == target_id for item in items)

    update_response = client.patch(
        f"/api/v1/monitoring/targets/{target_id}",
        json={"status": "paused"},
        headers=user_headers,
    )
    assert update_response.status_code == 200, update_response.text
    updated = _extract_payload(update_response)
    assert updated["status"] == "paused"


def test_admin_can_access_monitoring_admin_hits(client):
    _require_monitoring_api()
    assert _route_exists("/api/v1/monitoring/admin/hits", "GET")

    response = client.get("/api/v1/monitoring/admin/hits", headers={"X-Admin-Token": "test-admin-token"})
    assert response.status_code == 200, response.text


def test_non_admin_cannot_access_monitoring_admin_hits(client):
    _require_monitoring_api()
    assert _route_exists("/api/v1/monitoring/admin/hits", "GET")

    _user_id, user_headers = _register_and_login(client, "monitor_non_admin_user")
    response = client.get("/api/v1/monitoring/admin/hits", headers=user_headers)
    assert response.status_code in (401, 403), response.text
