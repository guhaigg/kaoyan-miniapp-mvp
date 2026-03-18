import hashlib
from dataclasses import dataclass

import httpx

from ..config import get_settings


@dataclass
class WechatIdentityPayload:
    openid: str
    unionid: str | None
    provider_app_id: str


class WechatService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def provider_app_id(self) -> str:
        value = self.settings.wechat_appid.strip()
        if value:
            return value
        return "mock_miniapp" if self.settings.use_mock_wechat else "unknown_miniapp"

    def exchange_code(self, code: str) -> WechatIdentityPayload:
        provider_app_id = self.provider_app_id()
        if self.settings.use_mock_wechat:
            digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:24]
            return WechatIdentityPayload(openid=f"mock_{digest}", unionid=None, provider_app_id=provider_app_id)

        if not self.settings.wechat_appid or not self.settings.wechat_secret:
            raise ValueError("WECHAT_APPID and WECHAT_SECRET are required when USE_MOCK_WECHAT=false")

        params = {
            "appid": self.settings.wechat_appid,
            "secret": self.settings.wechat_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        with httpx.Client(timeout=8.0) as client:
            response = client.get("https://api.weixin.qq.com/sns/jscode2session", params=params)
            response.raise_for_status()
            data = response.json()
        openid = str(data.get("openid", "")).strip()
        if not openid:
            raise ValueError(f"wechat exchange failed: {data}")
        unionid = str(data.get("unionid", "")).strip() or None
        return WechatIdentityPayload(openid=openid, unionid=unionid, provider_app_id=provider_app_id)

    def exchange_code_for_openid(self, code: str) -> str:
        return self.exchange_code(code).openid
