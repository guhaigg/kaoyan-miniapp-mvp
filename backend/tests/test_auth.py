import pytest

from app.config import get_settings
from app.services.wechat import WechatService


def test_silent_login_returns_shadow_account(client):
    response = client.post("/api/v1/auth/silent-login", json={"code": "abc123"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_state"] == "shadow"
    assert payload["visitor_token"]
    assert payload["user_id"]


def test_wechat_service_requires_credentials_when_mock_disabled(monkeypatch):
    monkeypatch.setenv("USE_MOCK_WECHAT", "false")
    monkeypatch.setenv("WECHAT_APPID", "")
    monkeypatch.setenv("WECHAT_SECRET", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="WECHAT_APPID and WECHAT_SECRET are required"):
        WechatService().exchange_code_for_openid("abc123")

    get_settings.cache_clear()
