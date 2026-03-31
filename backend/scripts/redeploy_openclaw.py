"""Re-deploy OpenClaw instance with updated gateway config."""
import asyncio
from app.repositories.agent_repo import AgentRepository
from app.repositories.config_repo import ModelEndpointRepository
from app.services.openclaw_service import OpenClawService


async def main():
    agent_id = "4a9886de-5fa8-4503-9030-d6ffc7e54f8e"
    tenant_id = "f71b6b86-2939-4754-a905-75a547bb7150"

    arepo = AgentRepository()
    agent = await arepo.get(tenant_id, agent_id)
    print(f"Agent: {agent['name']}, type={agent.get('agent_type')}")
    print(f"Model EP: {agent.get('model_endpoint_id')}")

    # Get model endpoint
    eprepo = ModelEndpointRepository()
    model_ep = None
    if agent.get("model_endpoint_id"):
        model_ep = await eprepo.get(tenant_id, agent["model_endpoint_id"])
        if model_ep:
            print(f"Endpoint: {model_ep.get('model_name')} @ {model_ep.get('provider_type')}")

    # Deploy fresh OpenClaw instance
    svc = OpenClawService()
    result = await svc.deploy_agent(
        agent_id=agent_id,
        agent_name=agent["name"],
        tenant_slug="eng",
        system_prompt=agent.get("system_prompt", ""),
        model_endpoint=model_ep,
        openclaw_config=agent.get("openclaw_config") or {},
    )
    print(f"Deployed: {result}")

    # Store gateway details on agent record
    agent["openclaw_instance_name"] = result["instance_name"]
    agent["openclaw_gateway_url"] = result["gateway_url"]
    agent["openclaw_gateway_token"] = result["gateway_token"]
    etag = agent.get("_etag")
    await arepo.update(tenant_id, agent_id, agent, etag=etag)
    print("Agent record updated with gateway URL and token")


if __name__ == "__main__":
    asyncio.run(main())
