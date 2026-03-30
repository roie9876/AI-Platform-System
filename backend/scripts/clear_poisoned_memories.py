"""Clear all 'knowledge' type memories from agent_memories collection.

These are stored assistant responses that may contain non-tool-calling
responses, which poison future interactions by biasing the model to
repeat the same pattern.

Run inside the api-gateway pod:
  python -m scripts.clear_poisoned_memories
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


async def main():
    from app.repositories.cosmos_client import get_cosmos_container

    container = await get_cosmos_container("agent_memories")
    if container is None:
        print("ERROR: Could not connect to Cosmos DB")
        sys.exit(1)

    # Get all tenant IDs
    tc = await get_cosmos_container("tenants")
    tenants = []
    async for t in tc.query_items("SELECT c.id FROM c", partition_key=None):
        tenants.append(t["id"])
    print(f"Found {len(tenants)} tenants")

    total = 0
    for tid in tenants:
        items = []
        try:
            async for m in container.query_items(
                'SELECT c.id, c.memory_type, c.content FROM c WHERE c.memory_type = "knowledge"',
                partition_key=tid,
            ):
                items.append(m)
        except Exception:
            continue

        for m in items:
            try:
                await container.delete_item(item=m["id"], partition_key=tid)
                preview = (m.get("content", "") or "")[:60]
                print(f"DEL [{tid[:8]}] {m['id'][:8]}: {preview}")
                total += 1
            except Exception as e:
                print(f"FAIL: {e}")

    print(f"Total deleted: {total}")


if __name__ == "__main__":
    asyncio.run(main())
