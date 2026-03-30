import asyncio
from app.repositories.cosmos_client import get_cosmos_container


async def main():
    container = await get_cosmos_container("mcp_servers")
    servers = []
    async for item in container.query_items(
        "SELECT c.id, c.name, c.url, c.is_active, c.tenant_id FROM c",
        enable_cross_partition_query=True,
    ):
        servers.append(item)
    print("=== MCP SERVERS ===")
    for s in servers:
        print(f"  id={s['id']}, name={s.get('name')}, url={s.get('url')}, active={s.get('is_active')}, tenant={s.get('tenant_id')}")
    print(f"Total: {len(servers)}")

    container2 = await get_cosmos_container("mcp_discovered_tools")
    tools = []
    async for item in container2.query_items(
        "SELECT c.id, c.tool_name, c.server_id, c.is_available, c.tenant_id FROM c",
        enable_cross_partition_query=True,
    ):
        tools.append(item)
    print()
    print("=== MCP DISCOVERED TOOLS ===")
    for t in tools:
        print(f"  tool={t.get('tool_name')}, server_id={t.get('server_id')}, available={t.get('is_available')}, tenant={t.get('tenant_id')}")
    print(f"Total: {len(tools)}")

    container3 = await get_cosmos_container("agent_mcp_tools")
    links = []
    async for item in container3.query_items(
        "SELECT c.id, c.agent_id, c.mcp_tool_id, c.tenant_id FROM c",
        enable_cross_partition_query=True,
    ):
        links.append(item)
    print()
    print("=== AGENT-MCP-TOOL LINKS ===")
    for lnk in links:
        print(f"  agent_id={lnk.get('agent_id')}, mcp_tool_id={lnk.get('mcp_tool_id')}, tenant={lnk.get('tenant_id')}")
    print(f"Total: {len(links)}")


asyncio.run(main())
