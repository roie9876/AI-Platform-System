"""Shared Azure Key Vault client for platform and tenant vaults."""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Platform Key Vault name (injected via env / configmap)
PLATFORM_KV_NAME = os.getenv("KEY_VAULT_NAME", "")
# Tenant Key Vault name (shared across tenants, secrets namespaced by slug)
TENANT_KV_NAME = os.getenv("TENANT_KEY_VAULT_NAME", "")

_AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
_WORKLOAD_CLIENT_ID = os.getenv(
    "AZURE_WORKLOAD_CLIENT_ID",
    os.getenv("AZURE_CLIENT_ID", ""),
)


def _get_credential():
    """Get a credential for Key Vault using workload identity."""
    from azure.identity import WorkloadIdentityCredential, DefaultAzureCredential

    token_file = os.getenv("AZURE_FEDERATED_TOKEN_FILE")
    if token_file and _WORKLOAD_CLIENT_ID:
        return WorkloadIdentityCredential(
            client_id=_WORKLOAD_CLIENT_ID,
            tenant_id=_AZURE_TENANT_ID,
            token_file_path=token_file,
        )
    return DefaultAzureCredential()


def _vault_url(vault_name: str) -> str:
    return f"https://{vault_name}.vault.azure.net"


# ── Platform Key Vault ──────────────────────────────────────────────────

def get_platform_secret(secret_name: str) -> str:
    """Read a secret from the platform Key Vault."""
    try:
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(vault_url=_vault_url(PLATFORM_KV_NAME), credential=_get_credential())
        return client.get_secret(secret_name).value or ""
    except Exception as e:
        logger.warning("Could not fetch platform KV secret %s: %s", secret_name, e)
        return ""


def set_platform_secret(secret_name: str, value: str) -> bool:
    """Write a secret to the platform Key Vault."""
    try:
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(vault_url=_vault_url(PLATFORM_KV_NAME), credential=_get_credential())
        client.set_secret(secret_name, value)
        logger.info("Stored secret %s in platform KV", secret_name)
        return True
    except Exception as e:
        logger.error("Could not store platform KV secret %s: %s", secret_name, e)
        return False


# ── Tenant Key Vault ────────────────────────────────────────────────────

def _tenant_secret_name(tenant_slug: str, key: str) -> str:
    """Build a namespaced secret name: {slug}-{key}."""
    return f"{tenant_slug}-{key}"


def get_tenant_secret(tenant_slug: str, key: str) -> str:
    """Read a secret from the tenant Key Vault."""
    name = _tenant_secret_name(tenant_slug, key)
    try:
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(vault_url=_vault_url(TENANT_KV_NAME), credential=_get_credential())
        return client.get_secret(name).value or ""
    except Exception as e:
        logger.warning("Could not fetch tenant KV secret %s: %s", name, e)
        return ""


def set_tenant_secret(tenant_slug: str, key: str, value: str) -> bool:
    """Write a secret to the tenant Key Vault."""
    name = _tenant_secret_name(tenant_slug, key)
    try:
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(vault_url=_vault_url(TENANT_KV_NAME), credential=_get_credential())
        client.set_secret(name, value)
        logger.info("Stored tenant secret %s in tenant KV", name)
        return True
    except Exception as e:
        logger.error("Could not store tenant KV secret %s: %s", name, e)
        return False


def delete_tenant_secret(tenant_slug: str, key: str) -> bool:
    """Delete a secret from the tenant Key Vault."""
    name = _tenant_secret_name(tenant_slug, key)
    try:
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(vault_url=_vault_url(TENANT_KV_NAME), credential=_get_credential())
        client.begin_delete_secret(name)
        logger.info("Deleted tenant secret %s from tenant KV", name)
        return True
    except Exception as e:
        logger.warning("Could not delete tenant KV secret %s: %s", name, e)
        return False
