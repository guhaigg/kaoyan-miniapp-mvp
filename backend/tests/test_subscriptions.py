from datetime import timedelta

from app.db import SessionLocal
from app.models import PortalUser
from app.models import utcnow
from app.services.account_access import ENTITLEMENT_SOURCE_ADMIN_GRANT, upsert_premium_entitlement


def _register_and_login(client, username: str = "watch_user") -> tuple[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "StrongPass123", "nickname": "关注用户"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    return user_id, login_response.json()["access_token"]


def _enable_premium(user_id: str) -> None:
    with SessionLocal() as db:
        upsert_premium_entitlement(
            db,
            user_id=user_id,
            operator_account_id=None,
            expires_at=None,
            source=ENTITLEMENT_SOURCE_ADMIN_GRANT,
        )
        db.commit()


def test_subscriptions_requires_user_login(client):
    response = client.get("/api/v1/subscriptions")
    assert response.status_code == 401


def test_regular_user_cannot_subscribe_school_but_can_subscribe_major(client):
    _user_id, token = _register_and_login(client, username="watch_regular")
    headers = {"X-User-Token": token}

    school_response = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "电子科技大学", "category": "all"},
        headers=headers,
    )
    assert school_response.status_code == 403

    major_response = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "major", "value": "0854", "category": "adjustment"},
        headers=headers,
    )
    assert major_response.status_code == 200


def test_premium_user_school_subscription_crud_flow(client):
    user_id, token = _register_and_login(client, username="watch_premium")
    _enable_premium(user_id)
    headers = {"X-User-Token": token}

    create_response = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "电子科技大学", "category": "all"},
        headers=headers,
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["subscription_type"] == "school"
    assert created["value"] == "电子科技大学"

    duplicate_response = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "电子科技大学", "category": "all"},
        headers=headers,
    )
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["id"] == created["id"]

    list_response = client.get("/api/v1/subscriptions", headers=headers)
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 1
    values = {item["value"] for item in payload["items"]}
    assert values == {"电子科技大学"}

    delete_response = client.delete(f"/api/v1/subscriptions/{created['id']}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"

    list_after_delete = client.get("/api/v1/subscriptions", headers=headers)
    assert list_after_delete.status_code == 200
    payload_after_delete = list_after_delete.json()
    assert payload_after_delete["total"] == 0


def test_expired_premium_user_is_auto_recycled_and_cannot_subscribe_school(client):
    user_id, token = _register_and_login(client, username="watch_expired")
    _enable_premium(user_id)
    with SessionLocal() as db:
        entitlement = next(x for x in db.query(PortalUser).filter(PortalUser.id == user_id).one().entitlements if x.status == "active")
        entitlement.expires_at = utcnow() - timedelta(days=1)
        db.commit()

    headers = {"X-User-Token": token}
    response = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "北京大学", "category": "all"},
        headers=headers,
    )
    assert response.status_code == 403

    with SessionLocal() as db:
        user = db.query(PortalUser).filter(PortalUser.id == user_id).one()
        assert not any(x.status == "active" for x in user.entitlements)
