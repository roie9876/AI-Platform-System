import logging
from typing import Optional
from uuid import uuid4

from app.repositories.marketplace_repo import AgentTemplateRepository, ToolTemplateRepository
from app.repositories.agent_repo import AgentRepository

logger = logging.getLogger(__name__)
from app.repositories.tool_repo import ToolRepository

_agent_template_repo = AgentTemplateRepository()
_tool_template_repo = ToolTemplateRepository()
_agent_repo = AgentRepository()
_tool_repo = ToolRepository()


class MarketplaceService:

    # ── Agent Templates ──

    @staticmethod
    async def list_agent_templates(
        tenant_id: str,
        category: Optional[str] = None,
        search: Optional[str] = None,
        featured_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ):
        # Build query dynamically
        conditions = ["c.is_public = true"]
        params = []
        if category:
            conditions.append("c.category = @cat")
            params.append({"name": "@cat", "value": category})
        if featured_only:
            conditions.append("c.is_featured = true")
        if search:
            conditions.append("(CONTAINS(LOWER(c.name), @search) OR CONTAINS(LOWER(c.description), @search))")
            params.append({"name": "@search", "value": search.lower()})

        where_clause = " AND ".join(conditions)
        query = f"SELECT * FROM c WHERE {where_clause} ORDER BY c.install_count DESC OFFSET @offset LIMIT @limit"
        params.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ])
        try:
            return await _agent_template_repo.query(tenant_id, query, params)
        except Exception:
            logger.exception("Failed to query agent templates from Cosmos DB")
            return []

    @staticmethod
    async def get_agent_template(tenant_id: str, template_id: str):
        return await _agent_template_repo.get(tenant_id, template_id)

    @staticmethod
    async def publish_agent_template(
        tenant_id: str,
        agent_id: str,
        name: str,
        description: Optional[str],
        category: Optional[str],
        tags: Optional[list],
    ):
        agent = await _agent_repo.get(tenant_id, agent_id)
        if not agent:
            return None

        template = {
            "id": str(uuid4()),
            "name": name,
            "description": description or agent.get("description"),
            "category": category,
            "tags": tags,
            "system_prompt": agent.get("system_prompt"),
            "config": {
                "temperature": agent.get("temperature"),
                "max_tokens": agent.get("max_tokens"),
                "timeout_seconds": agent.get("timeout_seconds"),
            },
            "author_tenant_id": tenant_id,
            "is_public": True,
            "install_count": 0,
            "tenant_id": tenant_id,
        }
        return await _agent_template_repo.create(tenant_id, template)

    @staticmethod
    async def import_agent_template(
        tenant_id: str, template_id: str,
    ):
        template = await _agent_template_repo.get(tenant_id, template_id)
        if not template:
            return None

        config = template.get("config") or {}
        agent = {
            "id": str(uuid4()),
            "name": template["name"],
            "description": template.get("description"),
            "system_prompt": template.get("system_prompt"),
            "temperature": config.get("temperature", 0),
            "max_tokens": config.get("max_tokens", None),
            "timeout_seconds": config.get("timeout_seconds", 30),
            "status": "inactive",
            "tenant_id": tenant_id,
        }
        created = await _agent_repo.create(tenant_id, agent)

        template["install_count"] = (template.get("install_count") or 0) + 1
        await _agent_template_repo.update(tenant_id, template_id, template)

        return created

    # ── Tool Templates ──

    @staticmethod
    async def list_tool_templates(
        tenant_id: str,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        conditions = ["c.is_public = true"]
        params = []
        if category:
            conditions.append("c.category = @cat")
            params.append({"name": "@cat", "value": category})
        if search:
            conditions.append("(CONTAINS(LOWER(c.name), @search) OR CONTAINS(LOWER(c.description), @search))")
            params.append({"name": "@search", "value": search.lower()})

        where_clause = " AND ".join(conditions)
        query = f"SELECT * FROM c WHERE {where_clause} ORDER BY c.install_count DESC OFFSET @offset LIMIT @limit"
        params.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ])
        try:
            return await _tool_template_repo.query(tenant_id, query, params)
        except Exception:
            logger.exception("Failed to query tool templates from Cosmos DB")
            return []

    @staticmethod
    async def get_tool_template(tenant_id: str, template_id: str):
        return await _tool_template_repo.get(tenant_id, template_id)

    @staticmethod
    async def publish_tool_template(
        tenant_id: str,
        tool_id: str,
        name: Optional[str],
        description: Optional[str],
        category: Optional[str],
        tags: Optional[list],
    ):
        tool = await _tool_repo.get(tenant_id, tool_id)
        if not tool:
            return None

        template = {
            "id": str(uuid4()),
            "name": name or tool["name"],
            "description": description or tool.get("description"),
            "category": category,
            "tags": tags,
            "input_schema": tool.get("input_schema"),
            "tool_type": "function",
            "config": {"timeout_seconds": tool.get("timeout_seconds")},
            "author_tenant_id": tenant_id,
            "is_public": True,
            "install_count": 0,
            "tenant_id": tenant_id,
        }
        return await _tool_template_repo.create(tenant_id, template)

    @staticmethod
    async def import_tool_template(
        tenant_id: str, template_id: str,
    ):
        template = await _tool_template_repo.get(tenant_id, template_id)
        if not template:
            return None

        config = template.get("config") or {}
        tool = {
            "id": str(uuid4()),
            "name": template["name"],
            "description": template.get("description"),
            "input_schema": template.get("input_schema") or {},
            "timeout_seconds": config.get("timeout_seconds", 30),
            "tenant_id": tenant_id,
        }
        created = await _tool_repo.create(tenant_id, tool)

        template["install_count"] = (template.get("install_count") or 0) + 1
        await _tool_template_repo.update(tenant_id, template_id, template)

        return created
