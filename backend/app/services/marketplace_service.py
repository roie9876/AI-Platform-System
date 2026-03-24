from uuid import UUID
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketplace import AgentTemplate, ToolTemplate
from app.models.agent import Agent
from app.models.tool import Tool


class MarketplaceService:

    # ── Agent Templates ──

    @staticmethod
    async def list_agent_templates(
        db: AsyncSession,
        category: Optional[str] = None,
        search: Optional[str] = None,
        featured_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ):
        query = select(AgentTemplate).where(AgentTemplate.is_public.is_(True))
        if category:
            query = query.where(AgentTemplate.category == category)
        if featured_only:
            query = query.where(AgentTemplate.is_featured.is_(True))
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    AgentTemplate.name.ilike(pattern),
                    AgentTemplate.description.ilike(pattern),
                )
            )
        query = query.order_by(AgentTemplate.install_count.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_agent_template(db: AsyncSession, template_id: UUID):
        result = await db.execute(
            select(AgentTemplate).where(AgentTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def publish_agent_template(
        db: AsyncSession,
        agent_id: UUID,
        tenant_id: UUID,
        name: str,
        description: Optional[str],
        category: Optional[str],
        tags: Optional[list],
    ):
        result = await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.tenant_id == tenant_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return None

        template = AgentTemplate(
            name=name,
            description=description or agent.description,
            category=category,
            tags=tags,
            system_prompt=agent.system_prompt,
            config={
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "timeout_seconds": agent.timeout_seconds,
            },
            author_tenant_id=tenant_id,
            is_public=True,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def import_agent_template(
        db: AsyncSession, template_id: UUID, tenant_id: UUID
    ):
        result = await db.execute(
            select(AgentTemplate).where(AgentTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            return None

        config = template.config or {}
        agent = Agent(
            name=template.name,
            description=template.description,
            system_prompt=template.system_prompt,
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 1024),
            timeout_seconds=config.get("timeout_seconds", 30),
            status="inactive",
            tenant_id=tenant_id,
        )
        db.add(agent)
        template.install_count = (template.install_count or 0) + 1
        await db.commit()
        await db.refresh(agent)
        return agent

    # ── Tool Templates ──

    @staticmethod
    async def list_tool_templates(
        db: AsyncSession,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        query = select(ToolTemplate).where(ToolTemplate.is_public.is_(True))
        if category:
            query = query.where(ToolTemplate.category == category)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    ToolTemplate.name.ilike(pattern),
                    ToolTemplate.description.ilike(pattern),
                )
            )
        query = query.order_by(ToolTemplate.install_count.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_tool_template(db: AsyncSession, template_id: UUID):
        result = await db.execute(
            select(ToolTemplate).where(ToolTemplate.id == template_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def publish_tool_template(
        db: AsyncSession,
        tool_id: UUID,
        tenant_id: UUID,
        name: Optional[str],
        description: Optional[str],
        category: Optional[str],
        tags: Optional[list],
    ):
        result = await db.execute(
            select(Tool).where(Tool.id == tool_id, Tool.tenant_id == tenant_id)
        )
        tool = result.scalar_one_or_none()
        if not tool:
            return None

        template = ToolTemplate(
            name=name or tool.name,
            description=description or tool.description,
            category=category,
            tags=tags,
            input_schema=tool.input_schema,
            tool_type="function",
            config={"timeout_seconds": tool.timeout_seconds},
            author_tenant_id=tenant_id,
            is_public=True,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
        return template

    @staticmethod
    async def import_tool_template(
        db: AsyncSession, template_id: UUID, tenant_id: UUID
    ):
        result = await db.execute(
            select(ToolTemplate).where(ToolTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            return None

        config = template.config or {}
        tool = Tool(
            name=template.name,
            description=template.description,
            input_schema=template.input_schema or {},
            timeout_seconds=config.get("timeout_seconds", 30),
            tenant_id=tenant_id,
        )
        db.add(tool)
        template.install_count = (template.install_count or 0) + 1
        await db.commit()
        await db.refresh(tool)
        return tool
