"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface DataSource {
  id: string;
  name: string;
  description: string | null;
  source_type: string;
  status: string;
}

interface DataSourceListResponse {
  data_sources: DataSource[];
  total: number;
}

interface AgentDataSource {
  id: string;
  agent_id: string;
  data_source_id: string;
}

export default function AgentDataSourcesPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [allDataSources, setAllDataSources] = useState<DataSource[]>([]);
  const [attachedIds, setAttachedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<DataSourceListResponse>("/api/v1/data-sources"),
      apiFetch<AgentDataSource[]>(`/api/v1/agents/${agentId}/data-sources`),
    ])
      .then(([dsData, agentDs]) => {
        setAllDataSources(dsData.data_sources);
        setAttachedIds(new Set(agentDs.map((ad) => ad.data_source_id)));
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [agentId]);

  const handleAttach = async (dataSourceId: string) => {
    setActionLoading(dataSourceId);
    try {
      await apiFetch(`/api/v1/agents/${agentId}/data-sources`, {
        method: "POST",
        body: JSON.stringify({ data_source_id: dataSourceId }),
      });
      setAttachedIds((prev) => new Set([...prev, dataSourceId]));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to attach data source");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDetach = async (dataSourceId: string) => {
    setActionLoading(dataSourceId);
    try {
      await apiFetch(`/api/v1/agents/${agentId}/data-sources/${dataSourceId}`, {
        method: "DELETE",
      });
      setAttachedIds((prev) => {
        const next = new Set(prev);
        next.delete(dataSourceId);
        return next;
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to detach data source");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading data sources...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Agent Data Sources</h1>
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

      {allDataSources.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">No data sources available. Add a data source first.</p>
          <Link href="/dashboard/data-sources/new" className="text-blue-600 hover:text-blue-700 font-medium">
            Add Data Source →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {allDataSources.map((ds) => {
            const isAttached = attachedIds.has(ds.id);
            return (
              <div
                key={ds.id}
                className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-lg font-semibold text-gray-900 truncate">
                    {ds.name}
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
                {ds.description && (
                  <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                    {ds.description}
                  </p>
                )}
                <div className="text-xs text-gray-400 mb-3">
                  Type: {ds.source_type} · Status: {ds.status}
                </div>
                <button
                  onClick={() =>
                    isAttached ? handleDetach(ds.id) : handleAttach(ds.id)
                  }
                  disabled={actionLoading === ds.id}
                  className={`w-full rounded-md px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
                    isAttached
                      ? "border border-red-300 text-red-700 hover:bg-red-50"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {actionLoading === ds.id
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
