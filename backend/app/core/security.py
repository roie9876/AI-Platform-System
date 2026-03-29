from __future__ import annotations

import time
import logging
import traceback
from typing import Any

import httpx
from jose import jwt, JWTError

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
            logger.error("Token has no kid header")
            return None

        # Decode without verification to inspect claims for debugging
        unverified = jwt.get_unverified_claims(token)
        logger.info("Token aud=%s, iss=%s, kid=%s", unverified.get("aud"), unverified.get("iss"), kid)

        keys = await _get_jwks_keys()
        signing_key = _find_signing_key(keys, kid)
        if not signing_key:
            logger.error("No signing key found for kid=%s (have %d keys)", kid, len(keys))
            return None

        # Accept both raw client ID and api:// prefixed URI as valid audiences.
        # Use ENTRA_APP_CLIENT_ID (not overridden by workload identity webhook),
        # falling back to AZURE_CLIENT_ID for backward compatibility.
        app_client_id = settings.ENTRA_APP_CLIENT_ID or settings.AZURE_CLIENT_ID
        valid_audiences = {app_client_id}
        if not app_client_id.startswith("api://"):
            valid_audiences.add(f"api://{app_client_id}")

        # python-jose audience can be a string or set — check token's actual aud
        token_aud = unverified.get("aud")
        matched_aud = None
        if isinstance(token_aud, str) and token_aud in valid_audiences:
            matched_aud = token_aud
        elif isinstance(token_aud, list):
            for a in token_aud:
                if a in valid_audiences:
                    matched_aud = a
                    break

        if not matched_aud:
            logger.error("Token audience %s not in valid audiences %s", token_aud, valid_audiences)
            return None

        logger.info("Validating with audience=%s, issuer=%s", matched_aud, settings.AZURE_ISSUER)

        # Accept both v1 (sts.windows.net) and v2 (login.microsoftonline.com) issuers
        token_iss = unverified.get("iss", "")
        valid_issuers = [
            settings.AZURE_ISSUER,  # v2.0: https://login.microsoftonline.com/{tid}/v2.0
            f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/",  # v1
        ]
        matched_issuer = token_iss if token_iss in valid_issuers else None
        if not matched_issuer:
            logger.error("Token issuer %s not in valid issuers %s", token_iss, valid_issuers)
            return None

        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=matched_aud,
            issuer=matched_issuer,
        )
        logger.info("Token validated successfully for user=%s", claims.get("preferred_username") or claims.get("upn"))
        return claims
    except JWTError as e:
        logger.error("Entra ID token validation FAILED: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error validating Entra ID token: %s (type=%s)\n%s", repr(e), type(e).__name__, traceback.format_exc())
        return None


# Map Entra ID app role values to internal role names
_ROLE_MAP = {
    "Platform.Admin": "platform_admin",
    "Tenant.Admin": "tenant_admin",
    "Tenant.User": "tenant_user",
}


def extract_user_context(claims: dict) -> dict:
    from app.core.config import settings

    # v1 tokens use 'upn', v2 tokens use 'preferred_username'
    email = claims.get("preferred_username") or claims.get("upn", "")
    # Normalize Entra app role values to internal role names
    raw_roles = claims.get("roles", [])
    roles = [_ROLE_MAP.get(r, r) for r in raw_roles]
    groups = claims.get("groups", [])

    # Resolve platform_admin from Entra admin group membership
    admin_group_id = settings.ENTRA_ADMIN_GROUP_ID
    if admin_group_id and admin_group_id in groups and "platform_admin" not in roles:
        roles.append("platform_admin")

    # Fallback: configured admin emails
    if "platform_admin" not in roles and settings.PLATFORM_ADMIN_EMAILS:
        admin_emails = [
            e.strip().lower()
            for e in settings.PLATFORM_ADMIN_EMAILS.split(",")
            if e.strip()
        ]
        if email.lower() in admin_emails:
            roles.append("platform_admin")

    return {
        "user_id": claims.get("oid", ""),
        "tenant_id": claims.get("tid", ""),
        "email": email,
        "name": claims.get("name", ""),
        "roles": roles,
        "groups": groups,
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
