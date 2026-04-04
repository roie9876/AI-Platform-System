import asyncio, json
from app.repositories.agent_repo import AgentRepository
from app.repositories.config_repo import ModelEndpointRepository
from app.services.openclaw_service import OpenClawService

repo = AgentRepository()
ep_repo = ModelEndpointRepository()
svc = OpenClawService()

async def redeploy():
    tid = "f71b6b86-2939-4754-a905-75a547bb7150"
    aid = "ecf1ef1d-80d5-4434-a871-9134ddeeb26f"
    agent = await repo.get(tid, aid)

    rules = (agent.get("openclaw_config") or {}).get("whatsapp", {}).get("whatsapp_group_rules", [])
    print(f"Agent has {len(rules)} group rules:")
    for r in rules:
        n = r.get("group_name", "?")
        j = r.get("group_jid", "None")
        p = r.get("policy", "?")
        print(f"  name={n}  jid={j}  policy={p}")

    model_ep = None
    if agent.get("model_endpoint_id"):
        model_ep = await ep_repo.get(tid, agent["model_endpoint_id"])

    instance = agent.get("openclaw_instance_name")
    slug = "eng"

    print(f"Re-deploying CR {instance}...")
    await svc.update_agent(
        instance_name=instance,
        tenant_slug=slug,
        system_prompt=agent.get("system_prompt") or "",
        model_endpoint=model_ep,
        openclaw_config=agent.get("openclaw_config"),
    )
    print("Done")

asyncio.run(redeploy())
