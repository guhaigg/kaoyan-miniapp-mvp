def _portal_login(client, username: str, password: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _bootstrap_admin_headers(client, username: str = "portal_admin", password: str = "StrongPass123") -> dict[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password, "nickname": f"{username}-nick"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    promote_response = client.post(
        f"/api/v1/admin/users/{user_id}/promote",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert promote_response.status_code == 200

    access_token = _portal_login(client, username, password)
    return {"X-User-Token": access_token}


def test_admin_me_requires_portal_admin_login(client):
    response = client.get("/api/v1/admin/auth/me")
    assert response.status_code == 401


def test_portal_admin_token_can_access_admin_me(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_me")
    me_response = client.get("/api/v1/admin/auth/me", headers=admin_headers)
    assert me_response.status_code == 200
    assert me_response.json()["authenticated"] is True
    assert me_response.json()["username"] == "portal_admin_me"


def test_admin_users_requires_login(client):
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_admin_users_list_and_update(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_users")

    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "user_for_admin", "password": "StrongPass123", "nickname": "普通用户"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    list_response = client.get("/api/v1/admin/users", headers=admin_headers)
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] >= 1
    matched_user = next(x for x in payload["items"] if x["id"] == user_id)
    assert matched_user["identities"]
    assert matched_user["identities"][0]["identity_type"] == "password"
    assert matched_user["roles"] == []
    assert matched_user["entitlements"] == []

    patch_response = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"status": "blocked", "nickname": "封禁测试"},
        headers=admin_headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "blocked"
    assert patch_response.json()["nickname"] == "封禁测试"
    assert patch_response.json()["identities"][0]["status"] == "inactive"

    filtered_response = client.get("/api/v1/admin/users?state=blocked", headers=admin_headers)
    assert filtered_response.status_code == 200
    assert any(x["id"] == user_id for x in filtered_response.json()["items"])


def test_admin_can_promote_user_and_login_as_promoted_admin(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_promoter")
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "new_admin_user", "password": "StrongPass123", "nickname": "可提升用户"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    promote_response = client.post(f"/api/v1/admin/users/{user_id}/promote", headers=admin_headers)
    assert promote_response.status_code == 200
    assert promote_response.json()["is_admin"] is True
    assert promote_response.json()["is_premium"] is True
    assert any(role["role_code"] == "admin" and role["status"] == "active" for role in promote_response.json()["roles"])

    promoted_headers = {"X-User-Token": _portal_login(client, "new_admin_user", "StrongPass123")}
    me_response = client.get("/api/v1/admin/auth/me", headers=promoted_headers)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "new_admin_user"


def test_admin_change_password_for_promoted_admin(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_pw")
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "pw_admin_user", "password": "StrongPass123", "nickname": "密码测试"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    promote_response = client.post(f"/api/v1/admin/users/{user_id}/promote", headers=admin_headers)
    assert promote_response.status_code == 200

    promoted_headers = {"X-User-Token": _portal_login(client, "pw_admin_user", "StrongPass123")}
    change_response = client.post(
        "/api/v1/admin/auth/change-password",
        json={"old_password": "StrongPass123", "new_password": "NewStrongPass456"},
        headers=promoted_headers,
    )
    assert change_response.status_code == 200
    assert change_response.json()["status"] == "ok"

    old_login = client.post(
        "/api/v1/auth/login",
        json={"username": "pw_admin_user", "password": "StrongPass123"},
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": "pw_admin_user", "password": "NewStrongPass456"},
    )
    assert new_login.status_code == 200


def test_admin_can_promote_user_to_premium_only(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_premium")
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "premium_user", "password": "StrongPass123", "nickname": "高级用户"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    promote_response = client.post(
        f"/api/v1/admin/users/{user_id}/promote",
        json={"target_role": "premium"},
        headers=admin_headers,
    )
    assert promote_response.status_code == 200
    payload = promote_response.json()
    assert payload["is_admin"] is False
    assert payload["is_premium"] is True
    assert payload["premium_expires_at"] is not None
    assert any(
        entitlement["entitlement_code"] == "premium_monitoring" and entitlement["status"] == "active"
        for entitlement in payload["entitlements"]
    )


def test_admin_can_reset_user_password_via_identity(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_reset")
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "reset_identity_user", "password": "StrongPass123", "nickname": "重置密码"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    reset_response = client.post(
        f"/api/v1/admin/users/{user_id}/reset-password",
        json={"new_password": "ResetPass456"},
        headers=admin_headers,
    )
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "ok"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "reset_identity_user", "password": "ResetPass456"},
    )
    assert login_response.status_code == 200


def test_admin_can_demote_admin_user_to_normal_user(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_demoter")
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "demote_user", "password": "StrongPass123", "nickname": "待降级"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    promote_response = client.post(f"/api/v1/admin/users/{user_id}/promote", headers=admin_headers)
    assert promote_response.status_code == 200
    assert promote_response.json()["is_admin"] is True

    demote_response = client.post(
        f"/api/v1/admin/users/{user_id}/demote",
        json={"target_role": "user"},
        headers=admin_headers,
    )
    assert demote_response.status_code == 200
    payload = demote_response.json()
    assert payload["is_admin"] is False
    assert payload["is_premium"] is False
    assert payload["premium_expires_at"] is None

    demoted_headers = {"X-User-Token": _portal_login(client, "demote_user", "StrongPass123")}
    me_response = client.get("/api/v1/admin/auth/me", headers=demoted_headers)
    assert me_response.status_code == 401


def test_admin_can_demote_admin_user_to_premium(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_demote_premium")
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "demote_to_premium", "password": "StrongPass123", "nickname": "降级高级"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]

    promote_response = client.post(f"/api/v1/admin/users/{user_id}/promote", headers=admin_headers)
    assert promote_response.status_code == 200
    assert promote_response.json()["is_admin"] is True

    demote_response = client.post(
        f"/api/v1/admin/users/{user_id}/demote",
        json={"target_role": "premium", "premium_days": 7},
        headers=admin_headers,
    )
    assert demote_response.status_code == 200
    payload = demote_response.json()
    assert payload["is_admin"] is False
    assert payload["is_premium"] is True
    assert payload["premium_expires_at"] is not None

    demoted_headers = {"X-User-Token": _portal_login(client, "demote_to_premium", "StrongPass123")}
    me_response = client.get("/api/v1/admin/auth/me", headers=demoted_headers)
    assert me_response.status_code == 401


def test_admin_audits_endpoint(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_audits")
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "audit_user", "password": "StrongPass123", "nickname": "审计用户"},
    )
    user_id = register_response.json()["user_id"]
    client.post(f"/api/v1/admin/users/{user_id}/promote", headers=admin_headers)

    audit_response = client.get("/api/v1/admin/audits?page=1&page_size=5", headers=admin_headers)
    assert audit_response.status_code == 200
    payload = audit_response.json()
    assert payload["total"] >= 1
    assert isinstance(payload["items"], list)
    assert any(item["event_type"].startswith("admin.") for item in payload["items"])


def test_console_requires_admin_login(client):
    response = client.get("/console/", follow_redirects=False)
    assert response.status_code == 401

    admin_headers = _bootstrap_admin_headers(client, "portal_admin_console")
    response_after_login = client.get("/console/", follow_redirects=False, headers=admin_headers)
    assert response_after_login.status_code == 307
    assert response_after_login.headers["location"] == "https://gewujl.cloud/admin/"


def test_admin_page_redirects_to_web_console(client):
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code == 401


def test_admin_can_register_new_admin_account(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_register")

    register_response = client.post(
        "/api/v1/admin/auth/register",
        json={"username": "ops_admin", "password": "StrongPass123"},
        headers=admin_headers,
    )
    assert register_response.status_code == 200
    payload = register_response.json()
    assert payload["username"] == "ops_admin"
    assert payload["promoted"] is True

    ops_admin_headers = {"X-User-Token": _portal_login(client, "ops_admin", "StrongPass123")}
    login_response = client.get("/api/v1/admin/auth/me", headers=ops_admin_headers)
    assert login_response.status_code == 200
    assert login_response.json()["username"] == "ops_admin"


def test_admin_can_import_priority_school_targets(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_import")

    import_response = client.post("/api/v1/schools/import/priority-targets", headers=admin_headers)
    assert import_response.status_code == 200
    payload = import_response.json()
    assert payload["total_rows"] >= 10
    assert payload["created_schools"] >= 10

    suggest_response = client.get("/api/v1/schools/suggest?q=湖北")
    assert suggest_response.status_code == 200
    names = [item["name"] for item in suggest_response.json()["items"]]
    assert "湖北大学" in names
    assert "湖北师范大学" in names


def test_admin_can_import_adjustment_priority_targets(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_import_adjustment")

    import_response = client.post("/api/v1/schools/import/adjustment-priority-targets", headers=admin_headers)
    assert import_response.status_code == 200
    payload = import_response.json()
    assert payload["total_rows"] >= 20
    assert payload["created_schools"] >= 10

    suggest_response = client.get("/api/v1/schools/suggest?q=河北")
    assert suggest_response.status_code == 200
    names = [item["name"] for item in suggest_response.json()["items"]]
    assert "河北大学" in names


def test_admin_can_view_school_import_seed_summaries(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_seed_summaries")

    response = client.get("/api/v1/schools/import/seed-summaries", headers=admin_headers)
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) >= 4

    source_keys = {item["source_key"] for item in payload["items"]}
    assert "adjustment_stats_2023_2025" in source_keys
    assert "adjustment_supplemental_2024_2025" in source_keys
    assert "adjustment_landing_2025" in source_keys
    assert "mentor_reviews" in source_keys


def test_admin_can_import_adjustment_supplemental_targets(client):
    admin_headers = _bootstrap_admin_headers(client, "portal_admin_import_adjustment_extra")

    import_response = client.post("/api/v1/schools/import/adjustment-supplemental-targets", headers=admin_headers)
    assert import_response.status_code == 200
    payload = import_response.json()
    assert payload["total_rows"] >= 20
    assert payload["created_schools"] >= 10

    suggest_response = client.get("/api/v1/schools/suggest?q=青岛")
    assert suggest_response.status_code == 200
    names = [item["name"] for item in suggest_response.json()["items"]]
    assert "青岛大学" in names
