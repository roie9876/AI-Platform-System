"""Quick script to check MCP servers and tools in Cosmos DB."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential


async def main():
    credential = DefaultAzureCredential()
    client = CosmosClient(settings.COSMOS_ENDPOINT, credential)
    db = client.get_database_client(settings.COSMOS_DATABASE)

    # Check mcp_servers
    container = db.get_container_client("mcp_servers")
    servers = []
    async for item in container.query_items(
        "SELECT c.id, c.name, c.url, c.is_active, c.tenant_id FROM c",
        enable_cross_partition_query=True,
    ):
        servers.append(item)
    print("=== MCP SERVERS ===")
    for s in servers:
        print(f"  id={s['id']}, name={s.get('name')}, url={s.get('url')}, is_active={s.get('is_active')}, tenant={s.get('tenant_id')}")
    print(f"Total: {len(servers)}")

    # Check mcp_discovered_tools
    container2 = db.get_container_client("mcp_discovered_tools")
    tools = []
    async for item in container2.query_items(
        "SELECT c.id, c.tool_name, c.server_id, c.is_available, c.tenant_id FROM c",
        enable_cross_partition_query=True,
    ):
        tools.append(item)
    print()
    print("=== MCP DISCOVERED TOOLS ===")
    for t in tools:
        print(f"  id={t['id']}, tool={t.get('tool_name')}, server_id={t.get('server_id')}, available={t.get('is_available')}, tenant={t.get('tenant_id')}")
    print(f"Total: {len(tools)}")

    # Check agent_mcp_tools (links between agents and MCP tools)
    try:
        container3 = db.get_container_client("agent_mcp_tools")
        links = []
        async for item in container3.query_items(
            "SELECT c.id, c.agent_id, c.mcp_tool_id, c.tenant_id FROM c",
            enable_cross_partition_query=True,
        ):
            links.append(item)
        print()
        print("=== AGENT-MCP-TOOL LINKS ===")
        for l in links:
            print(f"  id={l['id']}, agent_id={l.get('agent_id')}, mcp_tool_id={l.get('mcp_tool_id')}, tenant={l.get('tenant_id')}")
        print(f"Total: {len(links)}")
    except Exception as e:
        print(f"\nCould not query agent_mcp_tools: {e}")

    await client.close()


asyncio.run(main())
