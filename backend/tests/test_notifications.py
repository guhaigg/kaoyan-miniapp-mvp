from app.services.notifications import notification_engine


def _access_token(client, username: str = "notify_user") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "StrongPass123", "nickname": "通知用户"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_outbox_to_delivery_flow(client):
    token = _access_token(client)
    user_headers = {"X-User-Token": token}
    admin_headers = {"X-Admin-Token": "test-admin-token"}

    create_sub = client.post(
        "/api/v1/subscriptions",
        json={"subscription_type": "school", "value": "电子科技大学", "category": "all"},
        headers=user_headers,
    )
    assert create_sub.status_code == 200

    ingest_resp = client.post(
        "/api/v1/content",
        json={
            "category": "announcement",
            "title": "电子科技大学调剂通知",
            "body": "2026 年硕士调剂公告发布",
            "summary": "请关注系统开放时间",
            "school_name": "电子科技大学",
            "source_url": "https://example.com/notice-1",
        },
        headers=admin_headers,
    )
    assert ingest_resp.status_code == 200

    processed = notification_engine.process_outbox_batch()
    assert processed == 1

    pending_resp = client.get("/api/v1/notifications/pending", headers=user_headers)
    assert pending_resp.status_code == 200
    payload = pending_resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["payload"]["title"] == "电子科技大学调剂通知"

    pending_again = client.get("/api/v1/notifications/pending", headers=user_headers)
    assert pending_again.status_code == 200
    assert pending_again.json()["total"] == 0
