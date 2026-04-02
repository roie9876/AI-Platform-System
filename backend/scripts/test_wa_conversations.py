"""Test WhatsApp conversation retrieval via OpenClaw WebSocket."""
import asyncio
import json
import uuid
import sys
sys.path.insert(0, "/app")

import websockets

WS_URL = "ws://192.168.3.236:18790/"
ORIGIN = "http://192.168.3.236:18790"


async def main():
    async with websockets.connect(WS_URL, additional_headers={"Origin": ORIGIN}, open_timeout=5) as ws:
        await asyncio.wait_for(ws.recv(), timeout=3)  # challenge
        await ws.send(json.dumps({
            "type": "req", "id": str(uuid.uuid4()), "method": "connect",
            "params": {
                "minProtocol": 3, "maxProtocol": 3,
                "client": {"id": "openclaw-control-ui", "version": "control-ui",
                           "platform": "linux", "mode": "webchat",
                           "instanceId": "debug-tools"},
                "role": "operator",
                "scopes": ["operator.admin", "operator.read", "operator.write"],
                "caps": [],
            },
        }))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        if not resp.get("ok"):
            print("connect failed:", json.dumps(resp))
            return

        # Try methods.list or help to discover available API
        methods = [
            "methods.list",
            "help",
            "api.list",
            "system.methods",
            "rpc.discover",
            "ws.methods",
        ]

        for method in methods:
            req_id = str(uuid.uuid4())
            await ws.send(json.dumps({
                "type": "req", "id": req_id,
                "method": method, "params": {},
            }))
            try:
                for _ in range(5):
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                    if msg.get("type") == "event":
                        continue
                    ok = msg.get("ok")
                    print(f"\n--- {method} (ok={ok}) ---")
                    print(json.dumps(msg, indent=2, ensure_ascii=False)[:2000])
                    break
            except asyncio.TimeoutError:
                print(f"\n--- {method} --- TIMEOUT")


asyncio.run(main())
