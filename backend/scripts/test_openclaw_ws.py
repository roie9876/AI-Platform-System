#!/usr/bin/env python3
"""Test OpenClaw WS chat.send from within the cluster."""
import asyncio
import json
import uuid
import os

async def test():
    import websockets
    
    url = "ws://oc-openclaw-agent-c227ef5f.tenant-familiy.svc.cluster.local:18789/"
    
    gw_token = os.environ.get("GW_TOKEN")
    if not gw_token:
        print("ERROR: Set GW_TOKEN env var (from OpenClaw CR spec.config.raw.gateway.token)")
        return
    print(f"Token: {gw_token[:20]}...")
    
    headers = {
        "Origin": "http://oc-openclaw-agent-c227ef5f.tenant-familiy.svc.cluster.local:18789",
        "Authorization": f"Bearer {gw_token}",
    }
    
    ws = await websockets.connect(url, additional_headers=headers, open_timeout=5)
    print("WS connected")
    
    # Read challenge
    raw = await asyncio.wait_for(ws.recv(), timeout=3)
    print("Challenge OK")
    
    # Connect handshake
    req_id = str(uuid.uuid4())
    await ws.send(json.dumps({
        "type": "req",
        "id": req_id,
        "method": "connect",
        "params": {
            "minProtocol": 3,
            "maxProtocol": 3,
            "client": {
                "id": "test",
                "version": "1.0",
                "platform": "linux",
                "mode": "webchat",
                "instanceId": f"test-{uuid.uuid4().hex[:8]}",
            },
            "role": "operator",
            "scopes": ["operator.admin", "operator.read"],
            "caps": [],
            "userAgent": "test/1.0",
            "locale": "en-US",
        },
    }))
    
    # Wait for connect response
    connected = False
    for _ in range(10):
        raw = await asyncio.wait_for(ws.recv(), timeout=5)
        msg = json.loads(raw)
        if msg.get("id") == req_id or msg.get("type") == "res":
            print(f"Connect: ok={msg.get('ok')}")
            if msg.get("ok"):
                connected = True
            else:
                print(f"Connect FAILED: {json.dumps(msg)[:300]}")
            break
        print(f"Skipping: {msg.get('type')}/{msg.get('event', '')}")
    
    if not connected:
        print("ABORT: not connected")
        await ws.close()
        return
    
    # Send chat.send
    run_id = f"platform-{uuid.uuid4().hex[:12]}"
    chat_req_id = str(uuid.uuid4())
    await ws.send(json.dumps({
        "type": "req",
        "id": chat_req_id,
        "method": "chat.send",
        "params": {
            "message": "hello from test",
            "sessionKey": "agent:main:main",
            "idempotencyKey": run_id,
        },
    }))
    print("chat.send sent, waiting for response...")
    
    # Wait for events
    for i in range(50):
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            msg = json.loads(raw)
            t = msg.get("type", "")
            
            if msg.get("id") == chat_req_id:
                ok = msg.get("ok")
                run_id_returned = msg.get("payload", {}).get("runId", "")
                print(f"RESPONSE [{i}]: ok={ok} runId={run_id_returned[:30]}")
                if not ok:
                    print(f"  ERROR: {json.dumps(msg.get('error', {}))}")
                    break
                run_id = run_id_returned or run_id
                continue
            
            if t == "event":
                evt = msg.get("event", "")
                payload = msg.get("payload", {})
                rid = payload.get("runId", "")
                stream = payload.get("stream", "")
                data = payload.get("data", {})
                delta = data.get("delta", "") if isinstance(data, dict) else ""
                phase = data.get("phase", "") if isinstance(data, dict) else ""
                state = payload.get("state", "")
                
                if rid and rid != run_id:
                    continue  # skip events from other runs
                
                if delta:
                    print(f"DELTA [{i}]: {delta[:200]}", end="", flush=True)
                elif phase:
                    print(f"\nPHASE [{i}]: {phase}")
                elif state:
                    print(f"\nSTATE [{i}]: {evt} state={state}")
                else:
                    print(f"\nEVENT [{i}]: {evt} stream={stream} {json.dumps(payload)[:200]}")
                
                if phase == "end" or state == "final":
                    print("\n--- DONE ---")
                    break
            else:
                print(f"OTHER [{i}]: {t} {json.dumps(msg)[:200]}")
        except asyncio.TimeoutError:
            print(f"\nTIMEOUT at iteration {i}")
            break
    
    await ws.close()
    print("Closed")

asyncio.run(test())
