"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface ConfigVersion {
  id: string;
  agent_id: string;
  version_number: number;
  config_snapshot: Record<string, unknown>;
  change_description: string | null;
  created_at: string;
}

interface Agent {
  id: string;
  name: string;
  current_config_version: number;
}

export default function VersionHistoryPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [versions, setVersions] = useState<ConfigVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [rolling, setRolling] = useState<number | null>(null);
  const [error, setError] = useState("");

  const loadData = async () => {
    try {
      const [agentData, versionsData] = await Promise.all([
        apiFetch<Agent>(`/api/v1/agents/${agentId}`),
        apiFetch<ConfigVersion[]>(`/api/v1/agents/${agentId}/versions`),
      ]);
      setAgent(agentData);
      setVersions(versionsData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [agentId]);

  const handleRollback = async (versionNumber: number) => {
    if (
      !confirm(
        `Rollback to version ${versionNumber}? This will create a new version with that configuration.`
      )
    ) {
      return;
    }

    setRolling(versionNumber);
    setError("");

    try {
      await apiFetch(`/api/v1/agents/${agentId}/rollback/${versionNumber}`, {
        method: "POST",
      });
      await loadData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Rollback failed");
    } finally {
      setRolling(null);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading versions...</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Version History</h1>
          {agent && (
            <p className="text-sm text-gray-500 mt-1">
              {agent.name} — Current: v{agent.current_config_version}
            </p>
          )}
        </div>
        <Link
          href={`/dashboard/agents/${agentId}`}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Back to Agent
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {versions.length === 0 ? (
        <p className="text-gray-500">No versions recorded yet.</p>
      ) : (
        <div className="space-y-4">
          {versions.map((version) => {
            const isCurrent =
              version.version_number === agent?.current_config_version;
            return (
              <div
                key={version.id}
                className={`rounded-lg border p-4 ${
                  isCurrent
                    ? "border-blue-300 bg-blue-50"
                    : "border-gray-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900">
                      v{version.version_number}
                    </span>
                    {isCurrent && (
                      <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
                        Current
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">
                      {new Date(version.created_at).toLocaleString()}
                    </span>
                    {!isCurrent && (
                      <button
                        onClick={() => handleRollback(version.version_number)}
                        disabled={rolling !== null}
                        className="rounded-md border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
                      >
                        {rolling === version.version_number
                          ? "Rolling back..."
                          : "Rollback"}
                      </button>
                    )}
                  </div>
                </div>
                {version.change_description && (
                  <p className="text-sm text-gray-600 mb-2">
                    {version.change_description}
                  </p>
                )}
                <details className="text-xs">
                  <summary className="cursor-pointer text-gray-400 hover:text-gray-600">
                    Config snapshot
                  </summary>
                  <pre className="mt-2 p-2 bg-gray-100 rounded text-gray-700 overflow-auto">
                    {JSON.stringify(version.config_snapshot, null, 2)}
                  </pre>
                </details>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
