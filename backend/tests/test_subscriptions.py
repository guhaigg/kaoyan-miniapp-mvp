def _access_token(client, username: str = "watch_user") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "StrongPass123", "nickname": "关注用户"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_subscriptions_requires_user_login(client):
    response = client.get("/api/v1/subscriptions")
    assert response.status_code == 401


def test_subscriptions_crud_flow(client):
    token = _access_token(client)
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

    second_response = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "major", "value": "0854", "category": "adjustment"},
        headers=headers,
    )
    assert second_response.status_code == 200

    list_response = client.get("/api/v1/subscriptions", headers=headers)
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 2
    values = {item["value"] for item in payload["items"]}
    assert values == {"电子科技大学", "0854"}

    delete_response = client.delete(f"/api/v1/subscriptions/{created['id']}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["status"] == "ok"

    list_after_delete = client.get("/api/v1/subscriptions", headers=headers)
    assert list_after_delete.status_code == 200
    payload_after_delete = list_after_delete.json()
    assert payload_after_delete["total"] == 1
    assert payload_after_delete["items"][0]["value"] == "0854"
