import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from binascii import Error as BinasciiError
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
    try:
        actual_sig = _b64_decode(encoded_sig)
    except (BinasciiError, ValueError):
        return None
    if not hmac.compare_digest(expected_sig, actual_sig):
        return None

    try:
        payload_raw = _b64_decode(encoded_body).decode("utf-8")
        payload = json.loads(payload_raw)
    except (BinasciiError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        iat = int(payload.get("iat", 0))
    except (TypeError, ValueError):
        return None
    if iat <= 0 or int(time.time()) - iat > ttl_seconds:
        return None
    return payload


def hash_password(password: str, iterations: int = 120_000) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64_encode(salt)}${_b64_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, iter_text, salt_encoded, digest_encoded = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_text)
        salt = _b64_decode(salt_encoded)
        expected_digest = _b64_decode(digest_encoded)
    except (ValueError, BinasciiError):
        return False

    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual_digest, expected_digest)


def create_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
