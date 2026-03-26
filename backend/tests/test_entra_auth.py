from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from app.core.config import settings


# Generate test RSA key pair
_test_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend(),
)
_test_public_key = _test_private_key.public_key()

# Export public key numbers for JWKS format
_pub_numbers = _test_public_key.public_numbers()


def _int_to_base64url(n: int, length: int | None = None) -> str:
    import base64
    byte_length = length or (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(byte_length, "big")).rstrip(b"=").decode()


TEST_KID = "test-key-id-1"
TEST_JWKS_KEY = {
    "kty": "RSA",
    "kid": TEST_KID,
    "use": "sig",
    "alg": "RS256",
    "n": _int_to_base64url(_pub_numbers.n, 256),
    "e": _int_to_base64url(_pub_numbers.e, 3),
}

# PEM for signing test tokens
_private_pem = _test_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)


def _make_token(claims: dict, kid: str = TEST_KID, expired: bool = False) -> str:
    now = datetime.now(timezone.utc)
    defaults = {
        "iss": settings.AZURE_ISSUER or "https://login.microsoftonline.com/test-tenant/v2.0",
        "aud": settings.AZURE_CLIENT_ID or "test-client-id",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(hours=-1 if expired else 1)).timestamp()),
        "oid": "user-oid-123",
        "tid": "tenant-id-456",
        "preferred_username": "user@example.com",
        "name": "Test User",
        "roles": ["Member"],
    }
    defaults.update(claims)
    return jwt.encode(defaults, _private_pem, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", "test-tenant")
    monkeypatch.setattr(settings, "AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "AZURE_ISSUER", "https://login.microsoftonline.com/test-tenant/v2.0")
    monkeypatch.setattr(settings, "AZURE_JWKS_URI", "https://login.microsoftonline.com/test-tenant/discovery/v2.0/keys")


@pytest.fixture(autouse=True)
def _clear_jwks_cache():
    from app.core import security
    security._jwks_cache["keys"] = []
    security._jwks_cache["fetched_at"] = 0
    yield
    security._jwks_cache["keys"] = []
    security._jwks_cache["fetched_at"] = 0


@pytest.mark.asyncio
async def test_validate_entra_token_rejects_wrong_issuer():
    from app.core.security import validate_entra_token

    token = _make_token({"iss": "https://evil.example.com/v2.0"})

    with patch("app.core.security._get_jwks_keys", new_callable=AsyncMock, return_value=[TEST_JWKS_KEY]):
        result = await validate_entra_token(token)
    assert result is None


@pytest.mark.asyncio
async def test_validate_entra_token_rejects_expired():
    from app.core.security import validate_entra_token

    token = _make_token({}, expired=True)

    with patch("app.core.security._get_jwks_keys", new_callable=AsyncMock, return_value=[TEST_JWKS_KEY]):
        result = await validate_entra_token(token)
    assert result is None


@pytest.mark.asyncio
async def test_validate_entra_token_extracts_tenant_id():
    from app.core.security import validate_entra_token

    token = _make_token({"tid": "my-tenant-xyz"})

    with patch("app.core.security._get_jwks_keys", new_callable=AsyncMock, return_value=[TEST_JWKS_KEY]):
        result = await validate_entra_token(token)
    assert result is not None
    assert result["tid"] == "my-tenant-xyz"


@pytest.mark.asyncio
async def test_validate_entra_token_extracts_roles():
    from app.core.security import validate_entra_token

    token = _make_token({"roles": ["Platform Admin", "Member"]})

    with patch("app.core.security._get_jwks_keys", new_callable=AsyncMock, return_value=[TEST_JWKS_KEY]):
        result = await validate_entra_token(token)
    assert result is not None
    assert result["roles"] == ["Platform Admin", "Member"]


@pytest.mark.asyncio
async def test_require_role_allows_matching_role():
    from app.api.v1.dependencies import require_role

    dep = require_role("Platform Admin")
    user = {"user_id": "u1", "tenant_id": "t1", "roles": ["Platform Admin"]}
    result = await dep(current_user=user)
    assert result == user


@pytest.mark.asyncio
async def test_require_role_rejects_missing_role():
    from fastapi import HTTPException
    from app.api.v1.dependencies import require_role

    dep = require_role("Platform Admin")
    user = {"user_id": "u1", "tenant_id": "t1", "roles": ["Member"]}
    with pytest.raises(HTTPException) as exc_info:
        await dep(current_user=user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_current_user_returns_user_from_request():
    from fastapi import HTTPException
    from app.api.v1.dependencies import get_current_user

    request = MagicMock()
    request.state.user_context = {
        "user_id": "oid-1",
        "tenant_id": "tid-1",
        "email": "test@example.com",
        "name": "Test",
        "roles": ["Member"],
    }
    result = await get_current_user(request)
    assert result["user_id"] == "oid-1"
    assert result["tenant_id"] == "tid-1"


@pytest.mark.asyncio
async def test_get_current_user_returns_401_when_no_token():
    from fastapi import HTTPException
    from app.api.v1.dependencies import get_current_user

    request = MagicMock()
    request.state = MagicMock(spec=[])  # no user_context attribute
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request)
    assert exc_info.value.status_code == 401
