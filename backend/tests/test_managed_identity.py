from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_azure_credential_returns_default_credential():
    from app.core import security
    security._credential = None  # reset singleton

    with patch("app.core.security.DefaultAzureCredential") as MockCred:
        mock_instance = MagicMock()
        MockCred.return_value = mock_instance

        result = security.get_azure_credential()
        assert result is mock_instance
        MockCred.assert_called_once()

    security._credential = None  # cleanup


@pytest.mark.asyncio
async def test_get_azure_credential_returns_same_instance():
    from app.core import security
    security._credential = None

    with patch("app.core.security.DefaultAzureCredential") as MockCred:
        mock_instance = MagicMock()
        MockCred.return_value = mock_instance

        result1 = security.get_azure_credential()
        result2 = security.get_azure_credential()
        assert result1 is result2
        MockCred.assert_called_once()

    security._credential = None


@pytest.mark.asyncio
async def test_get_service_token_calls_credential_with_scope():
    from app.core import security
    security._credential = None

    mock_token = MagicMock()
    mock_token.token = "test-access-token-123"

    mock_cred = AsyncMock()
    mock_cred.get_token = AsyncMock(return_value=mock_token)

    with patch("app.core.security.DefaultAzureCredential", return_value=mock_cred):
        security._credential = None
        token = await security.get_service_token("https://cosmos.azure.com/.default")

    assert token == "test-access-token-123"
    mock_cred.get_token.assert_called_once_with("https://cosmos.azure.com/.default")

    security._credential = None
