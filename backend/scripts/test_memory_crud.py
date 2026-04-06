"""Test memory CRUD operations via MCP functions."""
import asyncio
import json
import sys


async def main():
    from app.repositories.cosmos_client import get_cosmos_container
    from mcp_platform_tools.memory import memory_delete, memory_delete_by_agent

    tid = "ff4e242e-5131-4f61-a1c3-dc7321628f47"
    aid = "6e6c6749-47b3-402f-bb9c-bdc4a28c08a8"

    c = await get_cosmos_container("agent_memories")

    # Count before
    sql_count = "SELECT VALUE COUNT(1) FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid"
    params = [{"name": "@tid", "value": tid}, {"name": "@aid", "value": aid}]
    count_before = 0
    async for count in c.query_items(query=sql_count, parameters=params, partition_key=tid):
        count_before = count

    print(f"Memories before: {count_before}")

    if count_before == 0:
        print("No memories to test with. Send a message to the bot first.")
        return

    # Get first memory
    sql = "SELECT TOP 1 c.id, c.memory_type FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid ORDER BY c.created_at DESC"
    full_id = None
    async for item in c.query_items(query=sql, parameters=params, partition_key=tid):
        full_id = item["id"]
        print(f"Target for single delete: {full_id} ({item['memory_type']})")

    # Test 1: Single delete
    result = await memory_delete(tenant_id=tid, agent_id=aid, memory_id=full_id)
    print(f"Single delete result: {json.dumps(result)}")

    try:
        await c.read_item(item=full_id, partition_key=tid)
        print("FAIL: memory still exists after delete!")
        sys.exit(1)
    except Exception:
        print("PASS: single memory confirmed deleted")

    # Count after single delete
    async for count in c.query_items(query=sql_count, parameters=params, partition_key=tid):
        print(f"Memories after single delete: {count}")

    # Test 2: Delete all
    result2 = await memory_delete_by_agent(tenant_id=tid, agent_id=aid)
    print(f"Delete-all result: {json.dumps(result2)}")

    # Count after delete all
    async for count in c.query_items(query=sql_count, parameters=params, partition_key=tid):
        if count == 0:
            print("PASS: all memories deleted")
        else:
            print(f"FAIL: {count} memories remain after delete-all")
            sys.exit(1)

    print("\nAll tests passed!")


asyncio.run(main())
