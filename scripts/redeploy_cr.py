"""Re-deploy the OpenClaw CR to apply updated agent config."""
import asyncio
import sys
sys.path.insert(0, "/app")

from app.repositories.agent_repo import AgentRepository
from app.repositories.tenant_repo import TenantRepository
from app.services.openclaw_service import OpenClawService


async def redeploy():
    agent_repo = AgentRepository()
    tenant_repo = TenantRepository()
    svc = OpenClawService()

    tid = "f71b6b86-2939-4754-a905-75a547bb7150"
    aid = "ecf1ef1d-80d5-4434-a871-9134ddeeb26f"

    agent = await agent_repo.get(tid, aid)
    tenant = await tenant_repo.get(tid, tid)
    slug = tenant["slug"]
    instance_name = agent["openclaw_instance_name"]

    # Get model endpoint if configured
    model_ep = None
    if agent.get("model_endpoint_id"):
        from app.repositories.config_repo import ModelEndpointRepository
        ep_repo = ModelEndpointRepository()
        model_ep = await ep_repo.get(tid, agent["model_endpoint_id"])

    await svc.update_agent(
        instance_name=instance_name,
        tenant_slug=slug,
        system_prompt=agent.get("system_prompt", "You are a helpful assistant."),
        model_endpoint=model_ep,
        openclaw_config=agent.get("openclaw_config"),
    )
    print(f"Re-deployed CR {instance_name} in tenant-{slug}")


asyncio.run(redeploy())
