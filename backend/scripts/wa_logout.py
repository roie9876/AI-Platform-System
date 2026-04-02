import asyncio, json, uuid, sys
sys.path.insert(0, "/app")
import websockets
from app.services.openclaw_service import OpenClawService

async def main():
    svc = OpenClawService()
    pod_url = await svc.get_pod_url("oc-openclaw-agent-f1a5787c", "eng")
    ws_url = pod_url.replace("http://", "ws://") + "/ws"
    print(f"Connecting to {ws_url}")
    async with websockets.connect(ws_url, additional_headers={"Origin": pod_url}) as ws:
        await ws.recv()  # challenge
        await ws.send(json.dumps({
            "type": "req", "id": str(uuid.uuid4()), "method": "connect",
            "params": {
                "minProtocol": 3, "maxProtocol": 3,
                "client": {"id": "openclaw-control-ui", "version": "control-ui", "platform": "linux", "mode": "webchat", "instanceId": "logout-" + str(uuid.uuid4())},
                "role": "operator", "scopes": ["operator.admin","operator.read","operator.write","operator.approvals","operator.pairing"], "caps": ["tool-events"]
            }
        }))
        await ws.recv()  # connect response
        print("Connected. Sending channels.logout for whatsapp...")
        await ws.send(json.dumps({
            "type": "req", "id": str(uuid.uuid4()), "method": "channels.logout",
            "params": {"channel": "whatsapp"}
        }))
        for _ in range(10):
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            print(f"  [{resp.get('type')}] {resp.get('event', resp.get('method', ''))}: ok={resp.get('ok')}")
            if resp.get("type") == "res":
                print("Logout result:", json.dumps(resp.get("payload", {}), indent=2))
                break

asyncio.run(main())
