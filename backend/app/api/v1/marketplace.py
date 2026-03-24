from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.middleware.tenant import get_tenant_id
from app.services.marketplace_service import MarketplaceService
from app.api.v1.schemas import (
    AgentTemplateResponse,
    AgentTemplateDetailResponse,
    PublishAgentTemplateRequest,
    ToolTemplateResponse,
    PublishToolTemplateRequest,
)

router = APIRouter()


# ── Agent Templates ──


@router.get("/agents", response_model=list[AgentTemplateResponse])
async def list_agent_templates(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    featured: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    templates = await MarketplaceService.list_agent_templates(
        db, category=category, search=search, featured_only=featured,
        limit=limit, offset=offset,
    )
    return templates


@router.get("/agents/{template_id}", response_model=AgentTemplateDetailResponse)
async def get_agent_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    template = await MarketplaceService.get_agent_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Agent template not found")
    return template


@router.post("/agents/publish", response_model=AgentTemplateDetailResponse)
async def publish_agent_template(
    body: PublishAgentTemplateRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
):
    template = await MarketplaceService.publish_agent_template(
        db,
        agent_id=body.agent_id,
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        category=body.category,
        tags=body.tags,
    )
    if not template:
        raise HTTPException(status_code=404, detail="Agent not found or not owned by tenant")
    return template


@router.post("/agents/{template_id}/import")
async def import_agent_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
):
    agent = await MarketplaceService.import_agent_template(db, template_id, tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent template not found")
    return {"agent_id": str(agent.id), "name": agent.name}


# ── Tool Templates ──


@router.get("/tools", response_model=list[ToolTemplateResponse])
async def list_tool_templates(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    templates = await MarketplaceService.list_tool_templates(
        db, category=category, search=search, limit=limit, offset=offset,
    )
    return templates


@router.get("/tools/{template_id}", response_model=ToolTemplateResponse)
async def get_tool_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    template = await MarketplaceService.get_tool_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Tool template not found")
    return template


@router.post("/tools/publish", response_model=ToolTemplateResponse)
async def publish_tool_template(
    body: PublishToolTemplateRequest,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
):
    template = await MarketplaceService.publish_tool_template(
        db,
        tool_id=body.tool_id,
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        category=body.category,
        tags=body.tags,
    )
    if not template:
        raise HTTPException(status_code=404, detail="Tool not found or not owned by tenant")
    return template


@router.post("/tools/{template_id}/import")
async def import_tool_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id),
):
    tool = await MarketplaceService.import_tool_template(db, template_id, tenant_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool template not found")
    return {"tool_id": str(tool.id), "name": tool.name}
