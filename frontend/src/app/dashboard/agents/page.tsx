"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useTenant } from "@/contexts/tenant-context";

interface Agent {
  id: string;
  name: string;
  description: string | null;
  status: string;
  model_endpoint_id: string | null;
  current_config_version: number;
  updated_at: string;
}

interface AgentListResponse {
  agents: Agent[];
  total: number;
}

const statusColors: Record<string, string> = {
  active: "bg-green-100 text-green-800",
  inactive: "bg-gray-100 text-gray-800",
  error: "bg-red-100 text-red-800",
};

export default function AgentsPage() {
  const router = useRouter();
  const { selectedTenantId } = useTenant();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const handleDelete = async (e: React.MouseEvent, agentId: string, agentName: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Delete agent "${agentName}"? This cannot be undone.`)) return;
    try {
      await apiFetch(`/api/v1/agents/${agentId}`, { method: "DELETE" });
      setAgents((prev) => prev.filter((a) => a.id !== agentId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete agent");
    }
  };

  useEffect(() => {
    apiFetch<AgentListResponse>("/api/v1/agents")
      .then((data) => setAgents(data.agents))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedTenantId]);

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading agents...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Agents</h1>
        <Link
          href="/dashboard/agents/new"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Create Agent
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {agents.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">
            No agents yet. Create your first agent to get started.
          </p>
          <Link
            href="/dashboard/agents/new"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Create Agent →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {agents.map((agent) => (
            <Link
              key={agent.id}
              href={`/dashboard/agents/${agent.id}`}
              className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-lg font-semibold text-gray-900 truncate">
                  {agent.name}
                </h3>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      statusColors[agent.status] || statusColors.inactive
                    }`}
                  >
                    {agent.status}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => handleDelete(e, agent.id, agent.name)}
                    className="text-gray-300 hover:text-red-500 transition-colors"
                    title="Delete agent"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
              {agent.description && (
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                  {agent.description}
                </p>
              )}
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span>v{agent.current_config_version}</span>
                <span>
                  {new Date(agent.updated_at).toLocaleDateString()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
