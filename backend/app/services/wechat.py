import hashlib

import httpx

from ..config import get_settings


class WechatService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def exchange_code_for_openid(self, code: str) -> str:
        if self.settings.use_mock_wechat or not self.settings.wechat_appid or not self.settings.wechat_secret:
            digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:24]
            return f"mock_{digest}"

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
        return openid

