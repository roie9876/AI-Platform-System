"use client";

import { useState, useEffect, useCallback } from "react";
import { Search, Server, RefreshCw, Wrench } from "lucide-react";
import { apiFetch } from "@/lib/api";
import Link from "next/link";
import { FilterBar } from "@/components/ui/filter-bar";
import { MCPToolDetailPanel } from "@/components/tools/mcp-tool-detail-panel";

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

export default function MCPToolsPage() {
  const [tools, setTools] = useState<MCPDiscoveredTool[]>([]);
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [serverFilter, setServerFilter] = useState("all");
  const [availabilityFilter, setAvailabilityFilter] = useState("all");
  const [discovering, setDiscovering] = useState(false);
  const [selectedTool, setSelectedTool] = useState<MCPDiscoveredTool | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [toolsData, serversData] = await Promise.all([
        apiFetch<MCPDiscoveredToolListResponse>("/api/v1/mcp/tools"),
        apiFetch<MCPServerListResponse>("/api/v1/mcp-servers"),
      ]);
      setTools(toolsData.tools);
      setServers(serversData.servers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load MCP tools");
    } finally {
      setLoading(false);
    }
  }, []);

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

  const serverMap = new Map(servers.map((s) => [s.id, s]));

  const filteredTools = tools.filter((tool) => {
    if (
      searchQuery &&
      !tool.tool_name.toLowerCase().includes(searchQuery.toLowerCase()) &&
      !(tool.description || "").toLowerCase().includes(searchQuery.toLowerCase())
    ) {
      return false;
    }
    if (serverFilter !== "all" && tool.server_id !== serverFilter) return false;
    if (availabilityFilter === "available" && !tool.is_available) return false;
    if (availabilityFilter === "unavailable" && tool.is_available) return false;
    return true;
  });

  const paramCount = (schema: Record<string, unknown> | null) => {
    if (!schema) return 0;
    const props = schema.properties as Record<string, unknown> | undefined;
    return props ? Object.keys(props).length : 0;
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading MCP tools...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">MCP Tool Catalog</h1>
          <p className="text-sm text-gray-500 mt-1">
            Browse and search tools from registered MCP servers
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/mcp-tools/servers"
            className="flex items-center gap-2 rounded-md border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Server className="h-4 w-4" />
            Manage Servers
          </Link>
          <button
            onClick={handleDiscoverAll}
            disabled={discovering}
            className="flex items-center gap-2 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${discovering ? "animate-spin" : ""}`} />
            {discovering ? "Discovering..." : "Discover All"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Search + Filters */}
      <div className="mb-6 space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search tools by name or description..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-10 w-full rounded-md border border-gray-200 bg-white pl-10 pr-4 text-sm text-gray-700 outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500"
          />
        </div>
        <FilterBar
          filters={[
            {
              name: "Server",
              value: serverFilter,
              onChange: setServerFilter,
              options: [
                { label: "All Servers", value: "all" },
                ...servers.map((s) => ({ label: s.name, value: s.id })),
              ],
            },
            {
              name: "Availability",
              value: availabilityFilter,
              onChange: setAvailabilityFilter,
              options: [
                { label: "All", value: "all" },
                { label: "Available", value: "available" },
                { label: "Unavailable", value: "unavailable" },
              ],
            },
          ]}
        />
      </div>

      {/* Stats */}
      <div className="mb-4 flex items-center gap-4 text-sm text-gray-500">
        <span>{filteredTools.length} tools from {servers.length} servers</span>
        <span>·</span>
        <span>{tools.filter((t) => t.is_available).length} available, {tools.filter((t) => !t.is_available).length} unavailable</span>
      </div>

      {/* Tools Grid */}
      {filteredTools.length === 0 ? (
        <div className="text-center py-12">
          <Wrench className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500 mb-2">
            {tools.length === 0
              ? "No MCP tools discovered yet."
              : "No tools match your filters."}
          </p>
          {tools.length === 0 && (
            <p className="text-sm text-gray-400">
              Register an MCP server and click &quot;Discover All&quot; to get started.
            </p>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTools.map((tool) => {
            const server = serverMap.get(tool.server_id);
            const isSelected = selectedTool?.id === tool.id;
            return (
              <div
                key={tool.id}
                onClick={() => setSelectedTool(tool)}
                className={`rounded-lg border bg-white p-5 shadow-sm cursor-pointer transition-colors ${
                  isSelected
                    ? "border-[#7C3AED] ring-1 ring-[#7C3AED]"
                    : "border-gray-200 hover:border-gray-300"
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-md bg-violet-50">
                      <Wrench className="h-4 w-4 text-[#7C3AED]" />
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
                  {server && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-gray-600">
                      <Server className="h-3 w-3" />
                      {server.name}
                    </span>
                  )}
                  <span>{paramCount(tool.input_schema)} params</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Tool Detail Panel */}
      <MCPToolDetailPanel
        tool={selectedTool}
        serverName={selectedTool ? (serverMap.get(selectedTool.server_id)?.name || "Unknown") : ""}
        onClose={() => setSelectedTool(null)}
      />
    </div>
  );
}
