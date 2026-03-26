from __future__ import annotations

import time
import logging
from typing import Any

import httpx
from jose import jwt, jwk, JWTError

from app.core.config import settings

logger = logging.getLogger(__name__)

# JWKS cache
_jwks_cache: dict[str, Any] = {"keys": [], "fetched_at": 0}
_JWKS_CACHE_TTL = 86400  # 24 hours


async def _get_jwks_keys() -> list[dict]:
    now = time.time()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < _JWKS_CACHE_TTL:
        return _jwks_cache["keys"]

    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.AZURE_JWKS_URI)
        resp.raise_for_status()
        data = resp.json()

    _jwks_cache["keys"] = data.get("keys", [])
    _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


def _find_signing_key(keys: list[dict], kid: str) -> dict | None:
    for key in keys:
        if key.get("kid") == kid:
            return key
    return None


async def validate_entra_token(token: str) -> dict | None:
    try:
        headers = jwt.get_unverified_headers(token)
        kid = headers.get("kid")
        if not kid:
            return None

        keys = await _get_jwks_keys()
        signing_key = _find_signing_key(keys, kid)
        if not signing_key:
            return None

        rsa_key = jwk.construct(signing_key)

        claims = jwt.decode(
            token,
            rsa_key.to_dict(),
            algorithms=["RS256"],
            audience=settings.AZURE_CLIENT_ID,
            issuer=settings.AZURE_ISSUER,
        )
        return claims
    except JWTError as e:
        logger.debug("Entra ID token validation failed: %s", e)
        return None
    except Exception as e:
        logger.warning("Unexpected error validating Entra ID token: %s", e)
        return None


def extract_user_context(claims: dict) -> dict:
    return {
        "user_id": claims.get("oid", ""),
        "tenant_id": claims.get("tid", ""),
        "email": claims.get("preferred_username", ""),
        "name": claims.get("name", ""),
        "roles": claims.get("roles", []),
    }


# DEPRECATED: Remove after Phase 18 complete
def hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# DEPRECATED: Remove after Phase 18 complete
def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# Managed Identity support
from azure.identity.aio import DefaultAzureCredential

_credential: DefaultAzureCredential | None = None


def get_azure_credential() -> DefaultAzureCredential:
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


async def get_service_token(scope: str) -> str:
    credential = get_azure_credential()
    token = await credential.get_token(scope)
    return token.token
