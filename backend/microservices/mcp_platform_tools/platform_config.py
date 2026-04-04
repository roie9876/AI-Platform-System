"""Platform config MCP tools — agent config and per-group instructions from Cosmos DB."""

from __future__ import annotations

import logging

from app.repositories.cosmos_client import get_cosmos_container

logger = logging.getLogger(__name__)


async def get_group_instructions(tenant_id: str, agent_id: str, group_jid: str) -> dict:
    """Return per-group instructions and settings for a specific WhatsApp group."""
    container = await get_cosmos_container("agents")
    if container is None:
        return {"error": "Database not configured"}

    try:
        doc = await container.read_item(item=agent_id, partition_key=tenant_id)
    except Exception:
        return {"error": "Agent not found"}

    openclaw_config = doc.get("openclaw_config", {})
    whatsapp = openclaw_config.get("whatsapp", {})
    groups = whatsapp.get("groups", {})

    group_config = groups.get(group_jid)
    if group_config is None:
        return {"group_jid": group_jid, "system_prompt": "", "found": False}

    return {
        "group_jid": group_jid,
        "system_prompt": group_config.get("systemPrompt", ""),
        "require_mention": group_config.get("requireMention", True),
        "contact_policy": group_config.get("contactPolicy", "open"),
        "found": True,
    }


async def get_agent_config(tenant_id: str, agent_id: str) -> dict:
    """Return agent configuration (safe fields only — no secrets or openclaw_config)."""
    container = await get_cosmos_container("agents")
    if container is None:
        return {"error": "Database not configured"}

    try:
        doc = await container.read_item(item=agent_id, partition_key=tenant_id)
    except Exception:
        return {"error": "Agent not found"}

    return {
        "id": doc.get("id"),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "system_prompt": doc.get("system_prompt"),
        "model_name": doc.get("model_name"),
        "created_at": doc.get("created_at"),
    }


async def list_configured_groups(tenant_id: str, agent_id: str) -> dict:
    """List all WhatsApp groups configured for an agent with their settings."""
    container = await get_cosmos_container("agents")
    if container is None:
        return {"error": "Database not configured"}

    try:
        doc = await container.read_item(item=agent_id, partition_key=tenant_id)
    except Exception:
        return {"error": "Agent not found"}

    openclaw_config = doc.get("openclaw_config", {})
    whatsapp = openclaw_config.get("whatsapp", {})
    groups_dict = whatsapp.get("groups", {})

    groups = []
    for jid, cfg in groups_dict.items():
        prompt = cfg.get("systemPrompt", "")
        groups.append({
            "group_jid": jid,
            "system_prompt": prompt[:100] if prompt else "",
            "require_mention": cfg.get("requireMention", True),
            "contact_policy": cfg.get("contactPolicy", "open"),
        })

    return {"groups": groups, "count": len(groups)}
