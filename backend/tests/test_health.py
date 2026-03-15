def test_health_returns_expected_shape(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in ("ok", "degraded")
    assert payload["db"] in ("up", "down")
    assert payload["redis"] in ("up", "down")
