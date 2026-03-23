"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface PlatformTool {
  id: string;
  name: string;
  description: string | null;
  input_schema: Record<string, unknown>;
  service_name: string;
  is_enabled: boolean;
}

interface PlatformToolListResponse {
  tools: PlatformTool[];
  total: number;
}

export default function AgentAIServicesPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [tools, setTools] = useState<PlatformTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toggleLoading, setToggleLoading] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<PlatformToolListResponse>(`/api/v1/ai-services?agent_id=${agentId}`)
      .then((data) => setTools(data.tools))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [agentId]);

  const handleToggle = async (toolId: string, currentEnabled: boolean) => {
    setToggleLoading(toolId);
    // Optimistic update
    setTools((prev) =>
      prev.map((t) =>
        t.id === toolId ? { ...t, is_enabled: !currentEnabled } : t
      )
    );

    try {
      await apiFetch(`/api/v1/ai-services/toggle?agent_id=${agentId}`, {
        method: "POST",
        body: JSON.stringify({ tool_id: toolId, enabled: !currentEnabled }),
      });
    } catch (err: unknown) {
      // Revert on error
      setTools((prev) =>
        prev.map((t) =>
          t.id === toolId ? { ...t, is_enabled: currentEnabled } : t
        )
      );
      setError(err instanceof Error ? err.message : "Failed to toggle service");
    } finally {
      setToggleLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading AI services...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Platform AI Services</h1>
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

      <p className="text-sm text-gray-600 mb-6">
        Toggle platform AI services on or off for this agent. Enabled services will be available as tools during agent conversations.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tools.map((tool) => (
          <div
            key={tool.id}
            className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
          >
            <div className="flex items-start justify-between mb-2">
              <h3 className="text-lg font-semibold text-gray-900">
                {tool.service_name}
              </h3>
              <button
                onClick={() => handleToggle(tool.id, tool.is_enabled)}
                disabled={toggleLoading === tool.id}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  tool.is_enabled ? "bg-blue-600" : "bg-gray-200"
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    tool.is_enabled ? "translate-x-6" : "translate-x-1"
                  }`}
                />
              </button>
            </div>
            {tool.description && (
              <p className="text-sm text-gray-600 mb-2 line-clamp-3">
                {tool.description}
              </p>
            )}
            <div className="text-xs text-gray-400">
              {tool.is_enabled ? (
                <span className="text-green-600 font-medium">Enabled</span>
              ) : (
                <span>Disabled</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
