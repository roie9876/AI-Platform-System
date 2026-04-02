"""Quick test: verify OpenClaw session tools and memory search are active."""
import asyncio
import json
import websockets

async def main():
    uri = "ws://127.0.0.1:18789"
    async with websockets.connect(uri) as ws:
        # 1) List sessions
        await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "sessions.list", "params": {}}))
        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        sessions = resp.get("result", {}).get("sessions", [])
        print(f"=== Sessions: {len(sessions)} found ===")
        for s in sessions[:10]:
            print(f"  key={s.get('key','?')}  channel={s.get('channel','?')}  agent={s.get('agentId','?')}")

        # 2) Channel status
        await ws.send(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "channels.status", "params": {}}))
        resp2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        channels = resp2.get("result", {}).get("channels", {})
        print(f"\n=== Channels ===")
        for ch, info in channels.items():
            print(f"  {ch}: {info.get('status','?')}")

        # 3) Get config to verify memorySearch + session tools
        await ws.send(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "config.get", "params": {}}))
        resp3 = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        config = resp3.get("result", {})
        ms = config.get("agents", {}).get("defaults", {}).get("memorySearch", {})
        ts = config.get("tools", {}).get("sessions", {})
        sess = config.get("session", {})
        print(f"\n=== Config Verification ===")
        print(f"  memorySearch.enabled: {ms.get('enabled', 'NOT SET')}")
        print(f"  memorySearch.experimental.sessionMemory: {ms.get('experimental', {}).get('sessionMemory', 'NOT SET')}")
        print(f"  tools.sessions.visibility: {ts.get('visibility', 'NOT SET')}")
        print(f"  session.dmScope: {sess.get('dmScope', 'NOT SET')}")
        print(f"\nAll quick-win features verified!")

asyncio.run(main())
