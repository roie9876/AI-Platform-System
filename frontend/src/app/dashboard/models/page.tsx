"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { useTenant } from "@/contexts/tenant-context";

interface ModelEndpoint {
  id: string;
  name: string;
  provider_type: string;
  endpoint_url: string | null;
  model_name: string;
  auth_type: string;
  is_active: boolean;
  priority: number;
  created_at: string;
}

interface ModelEndpointListResponse {
  endpoints: ModelEndpoint[];
  total: number;
}

const providerLabels: Record<string, string> = {
  azure_openai: "Azure OpenAI",
  openai: "OpenAI",
  anthropic: "Anthropic",
  custom: "Custom",
};

const authLabels: Record<string, { label: string; color: string }> = {
  entra_id: { label: "Entra ID", color: "bg-green-100 text-green-800" },
  api_key: { label: "API Key", color: "bg-blue-100 text-blue-800" },
};

export default function ModelsPage() {
  const { selectedTenantId } = useTenant();
  const [endpoints, setEndpoints] = useState<ModelEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadEndpoints = async () => {
    try {
      const data = await apiFetch<ModelEndpointListResponse>(
        "/api/v1/model-endpoints"
      );
      setEndpoints(data.endpoints);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load endpoints");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEndpoints();
  }, [selectedTenantId]);

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Delete model endpoint "${name}"? This cannot be undone.`)) {
      return;
    }
    try {
      await apiFetch(`/api/v1/model-endpoints/${id}`, { method: "DELETE" });
      setEndpoints((prev) => prev.filter((ep) => ep.id !== id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading model endpoints...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Model Endpoints</h1>
        <Link
          href="/dashboard/models/new"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Register Endpoint
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {endpoints.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">
            No model endpoints registered. Register your first endpoint to start
            using agents.
          </p>
          <Link
            href="/dashboard/models/new"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Register Endpoint →
          </Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Provider
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Model
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Auth
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Priority
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {endpoints.map((ep) => {
                const auth = authLabels[ep.auth_type] || {
                  label: ep.auth_type,
                  color: "bg-gray-100 text-gray-800",
                };
                return (
                  <tr key={ep.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">
                      {ep.name}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {providerLabels[ep.provider_type] || ep.provider_type}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 font-mono">
                      {ep.model_name}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${auth.color}`}
                      >
                        {auth.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {ep.priority}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          ep.is_active
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {ep.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(ep.id, ep.name)}
                        className="text-red-600 hover:text-red-800 text-sm font-medium"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
