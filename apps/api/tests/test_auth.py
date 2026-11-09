import os
import pytest

from app.auth import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_round_trip_and_wrong_password():
    encoded = hash_password("correct horse battery")
    assert encoded.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery", encoded)
    assert not verify_password("wrong password", encoded)


def test_password_minimum_length():
    with pytest.raises(ValueError, match="at least 10"):
        hash_password("short")


def test_access_token_round_trip_and_tamper_detection(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-secret-value-with-more-than-thirty-two-characters")
    token = create_access_token("user-123", "tenant-456")
    claims = decode_access_token(token)
    assert claims["sub"] == "user-123"
    assert claims["tid"] == "tenant-456"
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(ValueError, match="Invalid or expired"):
        decode_access_token(tampered)


def test_token_requires_deployment_secret(monkeypatch):
    monkeypatch.delenv("AUTH_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="AUTH_SECRET"):
        create_access_token("u", "t")
