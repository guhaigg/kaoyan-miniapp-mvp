import hashlib

import httpx

from ..config import get_settings


class WechatService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def exchange_code_for_openid(self, code: str) -> str:
        if self.settings.use_mock_wechat:
            digest = hashlib.sha256(code.encode("utf-8")).hexdigest()[:24]
            return f"mock_{digest}"

        if not self.settings.wechat_appid or not self.settings.wechat_secret:
            raise ValueError("wechat credentials are required when USE_MOCK_WECHAT=false")

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
        errcode = int(data.get("errcode", 0) or 0)
        if errcode != 0:
            errmsg = str(data.get("errmsg", "unknown error"))
            raise ValueError(f"wechat api error errcode={errcode} errmsg={errmsg}")

        openid = str(data.get("openid", "")).strip()
        if not openid:
            raise ValueError(f"wechat exchange failed: {data}")
        return openid
