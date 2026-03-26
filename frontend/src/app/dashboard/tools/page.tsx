"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useTenant } from "@/contexts/tenant-context";
import { Search, Server, RefreshCw, Wrench, Puzzle } from "lucide-react";

interface Tool {
  id: string;
  name: string;
  description: string | null;
  input_schema: Record<string, unknown>;
  is_platform_tool: boolean;
  timeout_seconds: number;
  updated_at: string;
}

interface ToolListResponse {
  tools: Tool[];
  total: number;
}

interface MCPServer {
  id: string;
  name: string;
  status: string;
}

interface MCPDiscoveredTool {
  id: string;
  server_id: string;
  tool_name: string;
  description: string | null;
  input_schema: Record<string, unknown> | null;
  is_available: boolean;
  created_at: string;
  updated_at: string;
}

interface MCPDiscoveredToolListResponse {
  tools: MCPDiscoveredTool[];
  total: number;
}

interface MCPServerListResponse {
  servers: MCPServer[];
  total: number;
}

type ActiveTab = "all" | "platform" | "mcp";

export default function ToolsPage() {
  const { selectedTenantId } = useTenant();
  const [tools, setTools] = useState<Tool[]>([]);
  const [mcpTools, setMcpTools] = useState<MCPDiscoveredTool[]>([]);
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<ActiveTab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [discovering, setDiscovering] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [toolsData, mcpToolsData, serversData] = await Promise.all([
        apiFetch<ToolListResponse>("/api/v1/tools"),
        apiFetch<MCPDiscoveredToolListResponse>("/api/v1/mcp/tools"),
        apiFetch<MCPServerListResponse>("/api/v1/mcp-servers"),
      ]);
      setTools(toolsData.tools);
      setMcpTools(mcpToolsData.tools);
      setServers(serversData.servers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load tools");
    } finally {
      setLoading(false);
    }
  }, [selectedTenantId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDiscoverAll = async () => {
    setDiscovering(true);
    try {
      await apiFetch("/api/v1/mcp/discover-all", { method: "POST" });
      await fetchData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Discovery failed");
    } finally {
      setDiscovering(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading tools...</p>
      </div>
    );
  }

  const schemaPropertyCount = (schema: Record<string, unknown> | null) => {
    if (!schema) return 0;
    const props = schema.properties as Record<string, unknown> | undefined;
    return props ? Object.keys(props).length : 0;
  };

  const serverMap = new Map(servers.map((s) => [s.id, s]));

  const filteredPlatformTools = tools.filter(
    (t) =>
      !searchQuery ||
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.description || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredMCPTools = mcpTools.filter(
    (t) =>
      !searchQuery ||
      t.tool_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.description || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  const tabs: { id: ActiveTab; label: string; count: number }[] = [
    { id: "all", label: "All Tools", count: tools.length + mcpTools.length },
    { id: "platform", label: "Platform", count: tools.length },
    { id: "mcp", label: "MCP Tools", count: mcpTools.length },
  ];

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tools</h1>
          <p className="text-sm text-gray-500 mt-1">
            Platform tools and MCP server tools in one place
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/mcp-tools/servers"
            className="flex items-center gap-2 rounded-md border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Server className="h-4 w-4" />
            MCP Servers
          </Link>
          <button
            onClick={handleDiscoverAll}
            disabled={discovering}
            className="flex items-center gap-2 rounded-md border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${discovering ? "animate-spin" : ""}`} />
            {discovering ? "Discovering..." : "Discover"}
          </button>
          <Link
            href="/dashboard/tools/new"
            className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] transition-colors"
          >
            Register Tool
          </Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-4 border-b border-gray-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-[#7C3AED] text-[#7C3AED]"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
            <span className="ml-1.5 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative mb-6">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search tools by name or description..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-10 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm text-gray-700 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Platform Tools */}
        {(activeTab === "all" || activeTab === "platform") &&
          filteredPlatformTools.map((tool) => (
            <div
              key={`tool-${tool.id}`}
              className="block rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-50">
                    <Wrench className="h-4 w-4 text-blue-600" />
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900 truncate">
                    {tool.name}
                  </h3>
                </div>
                <span className="inline-flex items-center rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 text-xs font-medium">
                  {schemaPropertyCount(tool.input_schema)} params
                </span>
              </div>
              {tool.description && (
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                  {tool.description}
                </p>
              )}
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <span className="inline-flex items-center rounded-full bg-blue-100 text-blue-700 px-2 py-0.5 font-medium">
                  Platform
                </span>
                {tool.is_platform_tool && (
                  <span className="inline-flex items-center rounded-full bg-purple-100 text-purple-800 px-2 py-0.5">
                    Built-in
                  </span>
                )}
                <span>Timeout: {tool.timeout_seconds}s</span>
              </div>
            </div>
          ))}

        {/* MCP Tools */}
        {(activeTab === "all" || activeTab === "mcp") &&
          filteredMCPTools.map((tool) => {
            const server = serverMap.get(tool.server_id);
            return (
              <div
                key={`mcp-${tool.id}`}
                className="block rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-violet-50">
                      <Puzzle className="h-4 w-4 text-[#7C3AED]" />
                    </div>
                    <h3 className="text-sm font-semibold text-gray-900 truncate">
                      {tool.tool_name}
                    </h3>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      tool.is_available
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {tool.is_available ? "Available" : "Unavailable"}
                  </span>
                </div>
                {tool.description && (
                  <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                    {tool.description}
                  </p>
                )}
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <span className="inline-flex items-center rounded-full bg-purple-100 text-purple-700 px-2 py-0.5 font-medium">
                    MCP
                  </span>
                  {server && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">
                      <Server className="h-3 w-3" />
                      {server.name}
                    </span>
                  )}
                  <span>{schemaPropertyCount(tool.input_schema)} params</span>
                </div>
              </div>
            );
          })}
      </div>

      {filteredPlatformTools.length === 0 && filteredMCPTools.length === 0 && (
        <div className="text-center py-12">
          <Wrench className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-4">
            {tools.length === 0 && mcpTools.length === 0
              ? "No tools registered yet. Register a tool or discover MCP tools."
              : "No tools match your search."}
          </p>
        </div>
      )}
    </div>
  );
}
