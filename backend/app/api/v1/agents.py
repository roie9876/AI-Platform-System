from fastapi import APIRouter, Depends, HTTPException, Request

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository, AgentConfigVersionRepository
from app.repositories.config_repo import ModelEndpointRepository
from app.repositories.tenant_repo import TenantRepository
from app.services.openclaw_service import OpenClawService
from app.api.v1.schemas import (
    AgentCreateRequest,
    AgentUpdateRequest,
    AgentResponse,
    AgentListResponse,
    AgentConfigVersionResponse,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

agent_repo = AgentRepository()
config_version_repo = AgentConfigVersionRepository()
endpoint_repo = ModelEndpointRepository()
tenant_repo = TenantRepository()
openclaw_service = OpenClawService()


def _build_config_snapshot(agent: dict) -> dict:
    return {
        "system_prompt": agent.get("system_prompt"),
        "temperature": agent.get("temperature"),
        "max_tokens": agent.get("max_tokens"),
        "timeout_seconds": agent.get("timeout_seconds"),
        "model_endpoint_id": agent.get("model_endpoint_id"),
    }


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent_data = {
        "name": body.name,
        "description": body.description,
        "system_prompt": body.system_prompt,
        "agent_type": body.agent_type,
        "model_endpoint_id": str(body.model_endpoint_id) if body.model_endpoint_id else None,
        "temperature": body.temperature,
        "max_tokens": body.max_tokens,
        "timeout_seconds": body.timeout_seconds,
        "current_config_version": 1,
        "status": "active" if body.model_endpoint_id else "inactive",
    }

    # Store OpenClaw config if provided
    if body.agent_type == "openclaw" and body.openclaw_config:
        oc_config = body.openclaw_config.model_dump()

        # Gmail secrets are stored after tenant lookup (below) to include tenant prefix
        agent_data["openclaw_config"] = oc_config

    agent = await agent_repo.create(tenant_id, agent_data)

    config_data = {
        "agent_id": agent["id"],
        "version_number": 1,
        "config_snapshot": _build_config_snapshot(agent),
        "change_description": "Initial configuration",
    }
    await config_version_repo.create(tenant_id, config_data)

    # Deploy OpenClaw instance if agent_type is "openclaw"
    if body.agent_type == "openclaw":
        try:
            tenant = await tenant_repo.get(tenant_id, tenant_id)
            if not tenant:
                raise HTTPException(status_code=400, detail="Tenant not found")
            slug = tenant["slug"]

            # Handle Gmail: store app password in Key Vault with tenant prefix
            oc_config = agent.get("openclaw_config") or {}
            agent_slug = body.name.lower().replace(" ", "-")

            # Handle Telegram: store bot token in Key Vault with tenant prefix
            channels = oc_config.get("channels") or {}
            if channels.get("telegram_enabled"):
                raw_token = channels.pop("telegram_bot_token", None)
                if raw_token:
                    raw_token = raw_token.strip()
                    secret_name = channels.get("telegram_bot_token_secret") or f"{slug}-telegram-bot-token-{agent_slug}"
                    stored = await openclaw_service._set_kv_secret(secret_name, raw_token)
                    if not stored:
                        raise HTTPException(status_code=500, detail="Failed to store Telegram bot token in Key Vault")
                    channels["telegram_bot_token_secret"] = secret_name
                elif not channels.get("telegram_bot_token_secret"):
                    channels["telegram_bot_token_secret"] = f"{slug}-telegram-bot-token"
                oc_config["channels"] = channels

            gmail = oc_config.get("gmail") or {}
            if gmail.get("gmail_enabled") and gmail.get("gmail_email"):
                raw_password = gmail.pop("gmail_app_password", None)
                if raw_password:
                    # Strip non-breaking spaces (U+00A0) and regular spaces
                    # that Google's UI injects into app password display.
                    import re as _re
                    raw_password = _re.sub(r'[\s\u00a0]+', '', raw_password)
                    secret_name = gmail.get("gmail_app_password_secret") or f"{slug}-gmail-app-password-{agent_slug}"
                    stored = await openclaw_service._set_kv_secret(secret_name, raw_password)
                    if not stored:
                        raise HTTPException(status_code=500, detail="Failed to store Gmail app password in Key Vault")
                    gmail["gmail_app_password_secret"] = secret_name
                elif not gmail.get("gmail_app_password_secret"):
                    gmail["gmail_app_password_secret"] = f"{slug}-gmail-app-password"
                oc_config["gmail"] = gmail

            # Persist updated config (with secret names, without raw values)
            if channels.get("telegram_enabled") or (gmail.get("gmail_enabled") and gmail.get("gmail_email")):
                agent["openclaw_config"] = oc_config
                etag = agent.get("_etag")
                agent = await agent_repo.update(tenant_id, agent["id"], agent, etag=etag)

            # Resolve model endpoint details
            model_ep = None
            if body.model_endpoint_id:
                model_ep = await endpoint_repo.get(tenant_id, str(body.model_endpoint_id))

            instance_name = await openclaw_service.deploy_agent(
                agent_id=agent["id"],
                agent_name=body.name,
                tenant_slug=slug,
                system_prompt=body.system_prompt or "",
                model_endpoint=model_ep,
                openclaw_config=oc_config,
            )
            agent["openclaw_instance_name"] = instance_name["instance_name"]
            agent["openclaw_gateway_url"] = instance_name["gateway_url"]
            agent["status"] = "provisioning"
            etag = agent.get("_etag")
            agent = await agent_repo.update(tenant_id, agent["id"], agent, etag=etag)
            logger.info("OpenClaw agent %s deployed as %s", agent["id"], agent.get("openclaw_instance_name"))
        except Exception as e:
            logger.error("Failed to deploy OpenClaw instance for agent %s: %s", agent["id"], e)
            agent["status"] = "error"
            agent["status_message"] = str(e)
            etag = agent.get("_etag")
            await agent_repo.update(tenant_id, agent["id"], agent, etag=etag)

    return agent


@router.get("", response_model=AgentListResponse)
async def list_agents(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agents = await agent_repo.list_by_tenant(tenant_id)

    # Check live pod status for provisioning OpenClaw agents
    provisioning = [
        a for a in agents
        if a.get("agent_type") == "openclaw"
        and a.get("status") == "provisioning"
        and a.get("openclaw_instance_name")
    ]
    if provisioning:
        tenant = await tenant_repo.get(tenant_id, tenant_id)
        slug = tenant["slug"] if tenant else None
        if slug:
            for agent in provisioning:
                try:
                    pod_status = await openclaw_service.get_agent_status(
                        agent["openclaw_instance_name"], slug
                    )
                    if pod_status["ready"]:
                        agent["status"] = "active"
                        agent["status_message"] = None
                        etag = agent.get("_etag")
                        await agent_repo.update(tenant_id, agent["id"], agent, etag=etag)
                    else:
                        agent["status_message"] = pod_status["message"]
                except Exception:
                    pass  # non-critical — keep provisioning status

    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check live pod status for provisioning OpenClaw agents
    if (
        agent.get("agent_type") == "openclaw"
        and agent.get("status") == "provisioning"
        and agent.get("openclaw_instance_name")
    ):
        tenant = await tenant_repo.get(tenant_id, tenant_id)
        slug = tenant["slug"] if tenant else None
        if slug:
            try:
                pod_status = await openclaw_service.get_agent_status(
                    agent["openclaw_instance_name"], slug
                )
                if pod_status["ready"]:
                    agent["status"] = "active"
                    agent["status_message"] = None
                    etag = agent.get("_etag")
                    await agent_repo.update(tenant_id, agent["id"], agent, etag=etag)
                else:
                    agent["status_message"] = pod_status["message"]
            except Exception:
                pass

    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    body: AgentUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    for field, value in update_data.items():
        if field == "model_endpoint_id" and value is not None:
            agent[field] = str(value)
        else:
            agent[field] = value

    if "model_endpoint_id" in update_data:
        agent["status"] = "active" if update_data["model_endpoint_id"] else "inactive"

    agent["current_config_version"] = agent.get("current_config_version", 1) + 1
    etag = agent.get("_etag")
    agent = await agent_repo.update(tenant_id, agent_id, agent, etag=etag)

    config_data = {
        "agent_id": agent["id"],
        "version_number": agent["current_config_version"],
        "config_snapshot": _build_config_snapshot(agent),
        "change_description": f"Updated: {', '.join(update_data.keys())}",
    }
    await config_version_repo.create(tenant_id, config_data)
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Delete OpenClaw instance if this is an OpenClaw agent
    if agent.get("agent_type") == "openclaw" and agent.get("openclaw_instance_name"):
        try:
            tenant = await tenant_repo.get(tenant_id, tenant_id)
            if tenant:
                await openclaw_service.delete_agent(
                    instance_name=agent["openclaw_instance_name"],
                    tenant_slug=tenant["slug"],
                )
        except Exception as e:
            logger.warning("Failed to delete OpenClaw instance %s: %s", agent.get("openclaw_instance_name"), e)

    versions = await config_version_repo.list_by_agent(tenant_id, agent_id)
    for v in versions:
        await config_version_repo.delete(tenant_id, v["id"])

    await agent_repo.delete(tenant_id, agent_id)


@router.get("/{agent_id}/versions", response_model=list[AgentConfigVersionResponse])
async def list_agent_versions(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return await config_version_repo.list_by_agent(tenant_id, agent_id)


@router.post("/{agent_id}/rollback/{version_number}", response_model=AgentResponse)
async def rollback_agent(
    agent_id: str,
    version_number: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    versions = await config_version_repo.list_by_agent(tenant_id, agent_id)
    version = next((v for v in versions if v.get("version_number") == version_number), None)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    snapshot = version["config_snapshot"]
    agent["system_prompt"] = snapshot.get("system_prompt")
    agent["temperature"] = snapshot.get("temperature", 0.7)
    agent["max_tokens"] = snapshot.get("max_tokens", 1024)
    agent["timeout_seconds"] = snapshot.get("timeout_seconds", 30)
    agent["model_endpoint_id"] = snapshot.get("model_endpoint_id")
    agent["current_config_version"] = agent.get("current_config_version", 1) + 1

    etag = agent.get("_etag")
    agent = await agent_repo.update(tenant_id, agent_id, agent, etag=etag)

    rollback_config = {
        "agent_id": agent["id"],
        "version_number": agent["current_config_version"],
        "config_snapshot": _build_config_snapshot(agent),
        "change_description": f"Rollback to version {version_number}",
    }
    await config_version_repo.create(tenant_id, rollback_config)
    return agent
