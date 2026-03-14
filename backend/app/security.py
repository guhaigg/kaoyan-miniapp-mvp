import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def create_visitor_token(payload: dict[str, Any], secret_key: str) -> str:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    encoded_body = _b64_encode(body)
    sig = hmac.new(secret_key.encode("utf-8"), encoded_body.encode("utf-8"), hashlib.sha256).digest()
    encoded_sig = _b64_encode(sig)
    return f"{encoded_body}.{encoded_sig}"


def parse_visitor_token(token: str, secret_key: str, ttl_seconds: int) -> dict[str, Any] | None:
    if "." not in token:
        return None
    encoded_body, encoded_sig = token.split(".", 1)
    expected_sig = hmac.new(secret_key.encode("utf-8"), encoded_body.encode("utf-8"), hashlib.sha256).digest()
    actual_sig = _b64_decode(encoded_sig)
    if not hmac.compare_digest(expected_sig, actual_sig):
        return None

    payload = json.loads(_b64_decode(encoded_body).decode("utf-8"))
    iat = int(payload.get("iat", 0))
    if iat <= 0 or int(time.time()) - iat > ttl_seconds:
        return None
    return payload

