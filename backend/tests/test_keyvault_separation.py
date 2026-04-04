"""Tests for Key Vault separation (AUDIT-05).

Validates that TENANT_KEY_VAULT_NAME env var has fallback behavior
and that tenant SecretProviderClasses reference the tenant vault.
"""
import os
from unittest.mock import patch

import pytest


class TestTenantKeyVaultFallback:
    """Test TENANT_KEY_VAULT_NAME env var fallback logic."""

    def test_tenant_keyvault_uses_env_when_set(self):
        """When TENANT_KEY_VAULT_NAME is explicitly set, use that value."""
        with patch.dict(os.environ, {
            "KEY_VAULT_NAME": "platform-kv",
            "TENANT_KEY_VAULT_NAME": "tenant-kv",
        }):
            import importlib
            from app.services import openclaw_service
            importlib.reload(openclaw_service)
            assert openclaw_service.TENANT_KEY_VAULT_NAME == "tenant-kv"

    def test_tenant_keyvault_falls_back_to_platform(self):
        """When TENANT_KEY_VAULT_NAME is NOT set, fall back to KEY_VAULT_NAME."""
        env = {"KEY_VAULT_NAME": "platform-kv"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("TENANT_KEY_VAULT_NAME", None)
            import importlib
            from app.services import openclaw_service
            importlib.reload(openclaw_service)
            assert openclaw_service.TENANT_KEY_VAULT_NAME == "platform-kv"

    def test_tenant_keyvault_empty_when_neither_set(self):
        """When neither env var is set, both are empty."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("KEY_VAULT_NAME", None)
            os.environ.pop("TENANT_KEY_VAULT_NAME", None)
            import importlib
            from app.services import openclaw_service
            importlib.reload(openclaw_service)
            assert openclaw_service.TENANT_KEY_VAULT_NAME == ""


class TestSecretProviderClassUsesTenantVault:
    """Test that _build_secret_provider_class references tenant vault."""

    def test_spc_uses_tenant_keyvault_name(self):
        """SecretProviderClass should use TENANT_KEY_VAULT_NAME, not KEY_VAULT_NAME."""
        with patch.dict(os.environ, {
            "KEY_VAULT_NAME": "platform-kv",
            "TENANT_KEY_VAULT_NAME": "tenant-kv",
            "AZURE_TENANT_ID": "test-tenant-id",
            "AZURE_WORKLOAD_CLIENT_ID": "test-client-id",
        }):
            import importlib
            from app.services import openclaw_service
            importlib.reload(openclaw_service)

            service = openclaw_service.OpenClawService.__new__(
                openclaw_service.OpenClawService
            )
            spc = service._build_secret_provider_class(
                instance_name="test-agent",
                namespace="tenant-eng",
                openclaw_config={},
            )
            assert spc["spec"]["parameters"]["keyvaultName"] == "tenant-kv"
