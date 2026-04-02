#!/usr/bin/env python3
"""Quick test: fetch cross-session context from OpenClaw via WebSocket."""
import asyncio
import json
import sys
import uuid

async def main(ip: str):
    import websockets
    ws_url = f"ws://{ip}:18790/"
    async with websockets.connect(
        ws_url,
        additional_headers={"Origin": f"http://{ip}:18790"},
        open_timeout=5,
    ) as ws:
        # 1. Challenge
        challenge = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        print(f"1. Challenge: {challenge.get('event')}")

        # 2. Connect
        await ws.send(json.dumps({
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
                    "instanceId": "test-session-ctx",
                },
                "role": "operator",
                "scopes": ["operator.read"],
                "caps": [],
            },
        }))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
        print(f"2. Connected: {resp.get('ok')}")
        if not resp.get("ok"):
            print(f"   Error: {resp.get('error')}")
            return

        # 3. Sessions list
        await ws.send(json.dumps({
            "type": "req",
            "id": str(uuid.uuid4()),
            "method": "sessions.list",
            "params": {},
        }))
        sessions = []
        for _ in range(10):
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if msg.get("type") == "event":
                continue
            print(f"3. sessions.list ok: {msg.get('ok')}")
            if msg.get("ok"):
                sessions = msg.get("payload", {}).get("sessions", [])
                print(f"   Found {len(sessions)} sessions")
                for s in sessions:
                    print(f"   - key={s.get('key')} channel={s.get('channel')} kind={s.get('kind')}")
            else:
                print(f"   Error: {msg.get('error')}")
                payload = json.dumps(msg, indent=2)
                print(f"   Full response: {payload[:500]}")
            break

        # 4. Try sessions.history for first non-main session
        other = [s for s in sessions if s.get("key") not in ("main", "agent:main:main")]
        if other:
            skey = other[0].get("key")
            print(f"\n4. Fetching history for: {skey}")
            await ws.send(json.dumps({
                "type": "req",
                "id": str(uuid.uuid4()),
                "method": "sessions.history",
                "params": {"sessionKey": skey, "limit": 5},
            }))
            for _ in range(10):
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if msg.get("type") == "event":
                    continue
                print(f"   sessions.history ok: {msg.get('ok')}")
                if msg.get("ok"):
                    entries = msg.get("payload", {}).get("messages", [])
                    print(f"   Got {len(entries)} messages")
                    for e in entries[-3:]:
                        role = e.get("role", "?")
                        text = (e.get("content") or "")[:100]
                        print(f"   [{role}]: {text}")
                else:
                    print(f"   Error: {msg.get('error')}")
                break
        else:
            print("\n4. No non-main sessions found")

if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.3.243"
    asyncio.run(main(ip))
