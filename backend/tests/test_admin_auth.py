from app.config import get_settings


def _admin_login(client):
    return client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )


def test_admin_login_and_me(client):
    login_response = _admin_login(client)
    assert login_response.status_code == 200
    assert login_response.json()["username"] == "admin"
    assert "gw_admin_session=" in login_response.headers.get("set-cookie", "")

    me_response = client.get("/api/v1/admin/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["authenticated"] is True


def test_admin_users_requires_login(client):
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_admin_users_list_and_update(client):
    login_response = _admin_login(client)
    assert login_response.status_code == 200

    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "user_for_admin", "password": "StrongPass123", "nickname": "普通用户"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    list_response = client.get("/api/v1/admin/users")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] >= 1
    assert any(x["id"] == user_id for x in payload["items"])

    patch_response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"status": "blocked", "nickname": "封禁测试"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "blocked"
    assert patch_response.json()["nickname"] == "封禁测试"

    filtered_response = client.get("/api/v1/admin/users?state=blocked")
    assert filtered_response.status_code == 200
    assert any(x["id"] == user_id for x in filtered_response.json()["items"])


def test_admin_can_promote_user_and_login_as_promoted_admin(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "new_admin_user", "password": "StrongPass123", "nickname": "可提升用户"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    assert _admin_login(client).status_code == 200
    promote_response = client.post(f"/api/v1/admin/users/{user_id}/promote")
    assert promote_response.status_code == 200
    assert promote_response.json()["is_admin"] is True

    client.post("/api/v1/admin/auth/logout")
    login_promoted_response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "new_admin_user", "password": "StrongPass123"},
    )
    assert login_promoted_response.status_code == 200
    assert login_promoted_response.json()["username"] == "new_admin_user"


def test_admin_change_password_for_promoted_admin(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "pw_admin_user", "password": "StrongPass123", "nickname": "密码测试"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    assert _admin_login(client).status_code == 200
    promote_response = client.post(f"/api/v1/admin/users/{user_id}/promote")
    assert promote_response.status_code == 200

    client.post("/api/v1/admin/auth/logout")
    login_response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "pw_admin_user", "password": "StrongPass123"},
    )
    assert login_response.status_code == 200

    change_response = client.post(
        "/api/v1/admin/auth/change-password",
        json={"old_password": "StrongPass123", "new_password": "NewStrongPass456"},
    )
    assert change_response.status_code == 200
    assert change_response.json()["status"] == "ok"

    client.post("/api/v1/admin/auth/logout")
    old_login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "pw_admin_user", "password": "StrongPass123"},
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "pw_admin_user", "password": "NewStrongPass456"},
    )
    assert new_login.status_code == 200


def test_admin_login_lock_after_failures(client, monkeypatch):
    monkeypatch.setenv("ADMIN_LOGIN_FAIL_LIMIT", "2")
    monkeypatch.setenv("ADMIN_LOGIN_LOCK_SECONDS", "60")
    get_settings.cache_clear()

    first = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "wrong-1"})
    assert first.status_code == 401
    second = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "wrong-2"})
    assert second.status_code == 401

    locked = client.post("/api/v1/admin/auth/login", json={"username": "admin", "password": "test-admin-password"})
    assert locked.status_code == 429
    assert "locked" in locked.json()["detail"]

    get_settings.cache_clear()


def test_admin_audits_endpoint(client):
    assert _admin_login(client).status_code == 200
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "audit_user", "password": "StrongPass123", "nickname": "审计用户"},
    )
    user_id = register_response.json()["user_id"]
    client.post(f"/api/v1/admin/users/{user_id}/promote")

    audit_response = client.get("/api/v1/admin/audits?page=1&page_size=5")
    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["total"] >= 1
    assert isinstance(payload["items"], list)
    assert any(item["event_type"].startswith("admin.") for item in payload["items"])


def test_console_requires_admin_login(client):
    response = client.get("/console/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/admin/"

    _admin_login(client)
    response_after_login = client.get("/console/", follow_redirects=False)
    assert response_after_login.status_code == 307
    assert response_after_login.headers["location"] == "/admin/"
