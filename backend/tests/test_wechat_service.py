import pytest

from app.services.wechat import WechatService


def test_wechat_service_mock_mode_returns_mock_openid():
    service = WechatService()
    service.settings.use_mock_wechat = True
    openid = service.exchange_code_for_openid("sample-code")
    assert openid.startswith("mock_")


def test_wechat_service_real_mode_requires_credentials():
    service = WechatService()
    service.settings.use_mock_wechat = False
    service.settings.wechat_appid = ""
    service.settings.wechat_secret = ""
    with pytest.raises(ValueError, match="credentials are required"):
        service.exchange_code_for_openid("sample-code")

