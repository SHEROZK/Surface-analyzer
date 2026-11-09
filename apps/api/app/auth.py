"""Minimal stateless access-token primitives for the API.

Passwords use PBKDF2-HMAC-SHA256 with per-user random salts. Access tokens are
HMAC-SHA256 signed and require a deployment-specific AUTH_SECRET.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return "pbkdf2_sha256$310000$" + _b64(salt) + "$" + _b64(digest)


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _unb64(salt), int(rounds))
        return hmac.compare_digest(actual, _unb64(expected))
    except (ValueError, TypeError):
        return False


def _secret() -> bytes:
    value = os.getenv("AUTH_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("AUTH_SECRET must be configured with at least 32 characters.")
    return value.encode("utf-8")


def create_access_token(user_id: str, tenant_id: str, expires_in: int = 3600) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": user_id, "tid": tenant_id, "iat": now, "exp": now + expires_in}, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode("ascii")
    signature = _b64(hmac.new(_secret(), message, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        message = f"{header}.{payload}".encode("ascii")
        expected = _b64(hmac.new(_secret(), message, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid access token.")
        claims = json.loads(_unb64(payload))
        if int(claims["exp"]) <= int(time.time()):
            raise ValueError("Access token has expired.")
        if not claims.get("sub") or not claims.get("tid"):
            raise ValueError("Invalid access token claims.")
        return claims
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired access token.") from exc
