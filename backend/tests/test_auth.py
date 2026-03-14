def test_silent_login_returns_shadow_account(client):
    response = client.post("/api/v1/auth/silent-login", json={"code": "abc123"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_state"] == "shadow"
    assert payload["visitor_token"]
    assert payload["user_id"]

