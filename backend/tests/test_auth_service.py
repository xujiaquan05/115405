# backend/tests/test_auth_service.py

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app.services import auth_service
from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def make_user(user_id=1, username="admin", role="admin"):
    return SimpleNamespace(id=user_id, username=username, role=role)


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self):
        password_hash = hash_password("secret123")

        assert verify_password("secret123", password_hash)

    def test_wrong_password_rejected(self):
        password_hash = hash_password("secret123")

        assert not verify_password("wrong-password", password_hash)

    def test_same_password_different_salt(self):
        # 每次雜湊都用隨機 salt，同一組密碼的雜湊值必須不同。
        first = hash_password("secret123")
        second = hash_password("secret123")

        assert first != second
        assert verify_password("secret123", first)
        assert verify_password("secret123", second)

    def test_malformed_hash_rejected(self):
        assert not verify_password("secret123", "not-a-valid-hash")
        assert not verify_password("secret123", "")
        assert not verify_password("secret123", None)

    def test_hash_format(self):
        password_hash = hash_password("secret123")
        algorithm, iterations, salt, digest = password_hash.split("$")

        assert algorithm == "pbkdf2_sha256"
        assert int(iterations) >= 100_000
        assert len(salt) == 32
        assert len(digest) == 64


class TestJwtTokens:
    def test_create_and_decode_roundtrip(self):
        token = create_access_token(make_user(user_id=7, username="tester", role="user"))
        payload = decode_access_token(token)

        assert payload["uid"] == 7
        assert payload["sub"] == "tester"
        assert payload["role"] == "user"

    def test_expired_token_rejected(self):
        now = datetime.now(timezone.utc)
        expired_token = jwt.encode(
            {
                "sub": "tester",
                "uid": 1,
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
            },
            auth_service.JWT_SECRET,
            algorithm=auth_service.JWT_ALGORITHM,
        )

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(expired_token)

        assert exc_info.value.status_code == 401

    def test_tampered_token_rejected(self):
        token = create_access_token(make_user())
        tampered = token[:-2] + "xx"

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(tampered)

        assert exc_info.value.status_code == 401

    def test_wrong_secret_rejected(self):
        forged = jwt.encode(
            {"sub": "hacker", "uid": 1},
            "another-secret",
            algorithm=auth_service.JWT_ALGORITHM,
        )

        with pytest.raises(HTTPException):
            decode_access_token(forged)
