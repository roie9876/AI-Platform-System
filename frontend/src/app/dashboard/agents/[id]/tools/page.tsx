"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface Tool {
  id: string;
  name: string;
  description: string | null;
  input_schema: Record<string, unknown>;
  is_platform_tool: boolean;
  timeout_seconds: number;
}

interface ToolListResponse {
  tools: Tool[];
  total: number;
}

interface AgentTool {
  id: string;
  agent_id: string;
  tool_id: string;
}

export default function AgentToolsPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [allTools, setAllTools] = useState<Tool[]>([]);
  const [attachedToolIds, setAttachedToolIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<ToolListResponse>("/api/v1/tools"),
      apiFetch<AgentTool[]>(`/api/v1/agents/${agentId}/tools`),
    ])
      .then(([toolsData, agentTools]) => {
        setAllTools(toolsData.tools);
        setAttachedToolIds(new Set(agentTools.map((at) => at.tool_id)));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [agentId]);

  const handleAttach = async (toolId: string) => {
    setActionLoading(toolId);
    try {
      await apiFetch(`/api/v1/agents/${agentId}/tools`, {
        method: "POST",
        body: JSON.stringify({ tool_id: toolId }),
      });
      setAttachedToolIds((prev) => new Set([...prev, toolId]));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to attach tool");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDetach = async (toolId: string) => {
    setActionLoading(toolId);
    try {
      await apiFetch(`/api/v1/agents/${agentId}/tools/${toolId}`, {
        method: "DELETE",
      });
      setAttachedToolIds((prev) => {
        const next = new Set(prev);
        next.delete(toolId);
        return next;
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to detach tool");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading tools...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Agent Tools</h1>
        <Link
          href={`/dashboard/agents/${agentId}`}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          ← Back to Agent
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {allTools.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">No tools available. Register a tool first.</p>
          <Link href="/dashboard/tools/new" className="text-blue-600 hover:text-blue-700 font-medium">
            Register Tool →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {allTools.map((tool) => {
            const isAttached = attachedToolIds.has(tool.id);
            return (
              <div
                key={tool.id}
                className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-lg font-semibold text-gray-900 truncate">
                    {tool.name}
                  </h3>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      isAttached
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {isAttached ? "Attached" : "Available"}
                  </span>
                </div>
                {tool.description && (
                  <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                    {tool.description}
                  </p>
                )}
                <button
                  onClick={() =>
                    isAttached ? handleDetach(tool.id) : handleAttach(tool.id)
                  }
                  disabled={actionLoading === tool.id}
                  className={`w-full mt-2 rounded-md px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
                    isAttached
                      ? "border border-red-300 text-red-700 hover:bg-red-50"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {actionLoading === tool.id
                    ? "..."
                    : isAttached
                    ? "Detach"
                    : "Attach"}
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
