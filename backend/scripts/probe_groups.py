"""Probe unknown group JIDs via sessions.create to trigger metadata fetch,
then re-list sessions to see if subjects appeared."""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, "/app")


async def main():
    from app.services.openclaw_service import OpenClawService

    svc = OpenClawService()
    pod_url = await svc.get_pod_url("oc-openclaw-agent-ecf1ef1d", "eng")
    ws_url = pod_url.replace("http://", "ws://", 1) + "/"

    import websockets

    async with websockets.connect(
        ws_url, additional_headers={"Origin": pod_url}, open_timeout=5, close_timeout=3
    ) as ws:
        # Auth handshake
        await asyncio.wait_for(ws.recv(), timeout=3)
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": str(uuid.uuid4()),
                    "method": "connect",
                    "params": {
                        "minProtocol": 3,
                        "maxProtocol": 3,
                        "client": {
                            "id": "openclaw-control-ui",
                            "version": "control-ui",
                            "platform": "linux",
                            "mode": "webchat",
                            "instanceId": "probe-groups",
                        },
                        "role": "operator",
                        "scopes": ["operator.admin"],
                        "caps": [],
                    },
                }
            )
        )
        for _ in range(10):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg.get("type") == "res":
                break

        # Create sessions for unknown groups
        unknown_jids = [
            "120363404292911474@g.us",
            "120363404850682826@g.us",
            "120363428242167177@g.us",
            "972507990873-1353259357@g.us",
            "972508337611-1532315018@g.us",
            "972543123423-1585215652@g.us",
        ]
        for jid in unknown_jids:
            req_id = str(uuid.uuid4())
            await ws.send(
                json.dumps(
                    {
                        "type": "req",
                        "id": req_id,
                        "method": "sessions.create",
                        "params": {"key": f"agent:main:whatsapp:group:{jid}"},
                    }
                )
            )
            for _ in range(10):
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                msg = json.loads(raw)
                if msg.get("type") == "event":
                    continue
                if msg.get("type") == "res":
                    print(f"CREATE {jid}: ok={msg.get('ok')}")
                    break

        # Now re-list sessions to see if subjects appeared
        await ws.send(
            json.dumps(
                {
                    "type": "req",
                    "id": str(uuid.uuid4()),
                    "method": "sessions.list",
                    "params": {},
                }
            )
        )
        for _ in range(10):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg.get("type") == "event":
                continue
            if msg.get("type") == "res" and msg.get("ok"):
                for s in msg.get("payload", {}).get("sessions", []):
                    if s.get("kind") != "group":
                        continue
                    subject = s.get("subject") or s.get("displayName") or s.get("name") or ""
                    key = s.get("key", "")
                    print(f"SESSION: {key}  subject={subject}")
            break


asyncio.run(main())
