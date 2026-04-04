"""Fix agent group rules: strip JID prefixes and add missing family group."""
import asyncio
import json
import re
import sys
sys.path.insert(0, "/app")

from app.repositories.agent_repo import AgentRepository


async def fix():
    repo = AgentRepository()
    tid = "f71b6b86-2939-4754-a905-75a547bb7150"
    aid = "ecf1ef1d-80d5-4434-a871-9134ddeeb26f"
    agent = await repo.get(tid, aid)
    etag = agent.get("_etag")
    wa = agent["openclaw_config"]["whatsapp"]
    rules = wa.get("whatsapp_group_rules", [])

    # Fix existing JIDs - strip prefix
    for r in rules:
        jid = r.get("group_jid", "")
        m = re.search(r"(\d[\d@.\-]+@g\.us)", jid)
        if m:
            r["group_jid"] = m.group(1)

    # Check if family group already exists
    family_jid = "972508337611-1532315018@g.us"
    has_family = any(r.get("group_jid") == family_jid for r in rules)

    if not has_family:
        rules.append({
            "group_name": "\u05de\u05e9\u05e4\u05d7\u05d4 \u05d4\u05db\u05d9 \u05d4\u05db\u05d9 \u05d8\u05d5\u05d1\u05d4",
            "group_jid": family_jid,
            "policy": "open",
            "require_mention": False,
            "allowed_phones": [],
            "instructions": "",
        })

    wa["whatsapp_group_rules"] = rules
    agent["openclaw_config"]["whatsapp"] = wa
    await repo.update(tid, aid, agent, etag=etag)

    print(f"Updated rules: {len(rules)}")
    for r in rules:
        print(json.dumps(r, ensure_ascii=False))


asyncio.run(fix())
