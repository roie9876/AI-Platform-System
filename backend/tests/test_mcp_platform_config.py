"""Unit tests for MCP Platform Tools — platform config tools."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from microservices.mcp_platform_tools.platform_config import (
    get_agent_config,
    get_group_instructions,
    list_configured_groups,
)

TENANT = "test-tenant"
AGENT = "test-agent"

MOCK_AGENT_DOC = {
    "id": AGENT,
    "tenant_id": TENANT,
    "name": "Test Agent",
    "description": "A test agent",
    "system_prompt": "You are helpful",
    "model_name": "gpt-4.1",
    "created_at": "2024-01-01T00:00:00",
    "openclaw_config": {
        "mcp_server_urls": [],
        "whatsapp": {
            "groupPolicy": "allowlist",
            "dmPolicy": "pairing",
            "groups": {
                "test-group-1@g.us": {
                    "systemPrompt": "Help in Hebrew",
                    "requireMention": True,
                    "contactPolicy": "open",
                    "allowFrom": ["*"],
                },
                "test-group-2@g.us": {
                    "systemPrompt": "English only",
                    "requireMention": False,
                    "contactPolicy": "open",
                    "allowFrom": ["*"],
                },
            },
        },
    },
}


class FakeAgentContainer:
    """Mock container that returns the agent document on read_item."""

    async def read_item(self, item: str, partition_key: str, **kw) -> dict:
        if item == AGENT and partition_key == TENANT:
            return dict(MOCK_AGENT_DOC)
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        raise CosmosResourceNotFoundError(status_code=404, message="Not found")


@pytest.fixture
def _mock_container():
    with patch(
        "microservices.mcp_platform_tools.platform_config.get_cosmos_container",
        return_value=FakeAgentContainer(),
    ):
        yield


# ---------------------------------------------------------------------------
#  get_group_instructions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_group_instructions_found(_mock_container):
    result = await get_group_instructions(TENANT, AGENT, "test-group-1@g.us")
    assert result["found"] is True
    assert result["system_prompt"] == "Help in Hebrew"
    assert result["require_mention"] is True
    assert result["group_jid"] == "test-group-1@g.us"


@pytest.mark.asyncio
async def test_get_group_instructions_not_found(_mock_container):
    result = await get_group_instructions(TENANT, AGENT, "unknown-group@g.us")
    assert result["found"] is False
    assert result["system_prompt"] == ""


# ---------------------------------------------------------------------------
#  get_agent_config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_agent_config(_mock_container):
    result = await get_agent_config(TENANT, AGENT)
    assert result["name"] == "Test Agent"
    assert result["system_prompt"] == "You are helpful"
    assert result["model_name"] == "gpt-4.1"
    # Must NOT leak openclaw_config
    assert "openclaw_config" not in result


# ---------------------------------------------------------------------------
#  list_configured_groups
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_configured_groups(_mock_container):
    result = await list_configured_groups(TENANT, AGENT)
    assert result["count"] == 2
    jids = {g["group_jid"] for g in result["groups"]}
    assert "test-group-1@g.us" in jids
    assert "test-group-2@g.us" in jids
    # Verify system_prompt is truncated at 100 chars
    for g in result["groups"]:
        assert len(g["system_prompt"]) <= 100
