"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { PreviewBadge } from "@/components/ui/preview-badge";
import { ResourcePicker } from "@/components/azure/resource-picker";

interface Subscription {
  id: string;
  subscription_id: string;
  display_name: string;
}

interface AzureResource {
  resource_id: string;
  name: string;
  region: string;
  resource_group?: string;
}

interface DiscoveredResource {
  id: string;
  name: string;
  type: string;
  location: string;
  resourceGroup: string | null;
}

interface SearchIndex {
  name: string;
}

interface ConnectionResponse {
  id: string;
  resource_name: string;
  endpoint: string | null;
  health_status: string;
  config: Record<string, unknown> | null;
}

interface SearchIndexListResponse {
  connection_id: string;
  resource_name: string;
  indexes: SearchIndex[];
  count: number;
}

interface AgentKnowledgeIndexInfo {
  connection_id: string;
  resource_name: string;
  index_names: string[];
}

interface AgentKnowledgeResponse {
  agent_id: string;
  connections: AgentKnowledgeIndexInfo[];
  total_indexes: number;
}

export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<"bases" | "indexes">("bases");
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [aiSearchResources, setAiSearchResources] = useState<AzureResource[]>(
    []
  );
  const [loadingResources, setLoadingResources] = useState(false);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(
    null
  );
  const [authType, setAuthType] = useState("api_key");
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [indexes, setIndexes] = useState<SearchIndex[]>([]);
  const [selectedIndexes, setSelectedIndexes] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Subscription[]>("/api/v1/azure/subscriptions")
      .then(setSubscriptions)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedSubId) {
      setAiSearchResources([]);
      return;
    }
    setLoadingResources(true);
    apiFetch<{ resources: DiscoveredResource[] }>(
      `/api/v1/azure/subscriptions/${selectedSubId}/resources?resource_type=${encodeURIComponent("Microsoft.Search/searchServices")}`
    )
      .then((data) =>
        setAiSearchResources(
          (data.resources || []).map((r) => ({
            resource_id: r.id,
            name: r.name,
            region: r.location,
            resource_group: r.resourceGroup ?? undefined,
          }))
        )
      )
      .catch(() => setAiSearchResources([]))
      .finally(() => setLoadingResources(false));
  }, [selectedSubId]);

  async function handleConnect() {
    if (!selectedResourceId || !selectedSubId) return;
    setError("");
    const resource = aiSearchResources.find(
      (r) => r.resource_id === selectedResourceId
    );
    if (!resource) return;

    try {
      const conn = await apiFetch<ConnectionResponse>(
        "/api/v1/azure/connections",
        {
          method: "POST",
          body: JSON.stringify({
            azure_subscription_id: selectedSubId,
            resource_type: "Microsoft.Search/searchServices",
            resource_name: resource.name,
            resource_id: selectedResourceId,
            auth_type: authType,
            region: resource.region,
          }),
        }
      );
      setConnectionId(conn.id);

      const idxData = await apiFetch<SearchIndexListResponse>(
        `/api/v1/knowledge/connections/${conn.id}/indexes`
      );
      setIndexes(idxData.indexes);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Connection failed");
    }
  }

  async function handleSaveIndexes() {
    if (!connectionId || selectedIndexes.length === 0) return;
    setSaving(true);
    try {
      await apiFetch(`/api/v1/knowledge/connections/${connectionId}/indexes`, {
        method: "POST",
        body: JSON.stringify({ index_names: selectedIndexes }),
      });
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function toggleIndex(name: string) {
    setSelectedIndexes((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  }

  const tabs = [
    { id: "bases" as const, label: "Knowledge bases" },
    { id: "indexes" as const, label: "Indexes" },
  ];

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-6 flex items-center gap-3">
        <h1 className="text-xl font-semibold text-gray-900">Knowledge</h1>
        <PreviewBadge />
      </div>

      {/* Tabs */}
      <div className="mb-6 flex border-b border-gray-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium ${
              activeTab === tab.id
                ? "border-b-2 border-[#7C3AED] text-[#7C3AED]"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {activeTab === "bases" && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-1">
            Ground your agent in enterprise knowledge
          </h2>
          <p className="text-sm text-gray-500 mb-1">
            Connect your agent to combine multiple data sources behind an
            agentic retrieval engine.
          </p>
          <p className="text-sm italic text-gray-600 mb-6">
            Connect to an AI Search resource to get started
          </p>

          {/* Subscription selector */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Azure Subscription
            </label>
            <select
              value={selectedSubId || ""}
              onChange={(e) => setSelectedSubId(e.target.value || null)}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
            >
              <option value="">Select subscription</option>
              {subscriptions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name}
                </option>
              ))}
            </select>
          </div>

          {/* Resource picker */}
          <div className="mb-4">
            <ResourcePicker
              resources={aiSearchResources}
              value={selectedResourceId}
              onChange={(r) => setSelectedResourceId(r?.resource_id ?? null)}
              label="Azure AI Search resource *"
              loading={loadingResources}
            />
          </div>

          {/* Auth type */}
          {selectedResourceId && (
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Auth Type *
              </label>
              <select
                value={authType}
                onChange={(e) => setAuthType(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
              >
                <option value="api_key">API Key</option>
                <option value="managed_identity">Managed Identity</option>
              </select>
            </div>
          )}

          {/* Connect button */}
          {selectedResourceId && !connectionId && (
            <div className="mb-4 flex items-center gap-4">
              <button
                type="button"
                onClick={handleConnect}
                className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
              >
                Connect
              </button>
              <a
                href="#"
                className="text-sm text-[#2563EB] hover:underline"
                onClick={(e) => e.preventDefault()}
              >
                Not sure? Create new resource
              </a>
            </div>
          )}

          {/* After connection — Index browser */}
          {connectionId && (
            <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-gray-900">
                  Saved info
                </h3>
                <button
                  type="button"
                  onClick={() => {
                    setConnectionId(null);
                    setIndexes([]);
                    setSelectedIndexes([]);
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  ×
                </button>
              </div>

              {indexes.length === 0 ? (
                <p className="text-sm text-gray-500">No indexes found</p>
              ) : (
                <>
                  <div className="space-y-2">
                    {indexes.map((idx) => (
                      <label
                        key={idx.name}
                        className="flex items-center gap-2 text-sm"
                      >
                        <input
                          type="checkbox"
                          checked={selectedIndexes.includes(idx.name)}
                          onChange={() => toggleIndex(idx.name)}
                          className="rounded border-gray-300 text-[#7C3AED] focus:ring-[#7C3AED]"
                        />
                        <span className="text-gray-900">{idx.name}</span>
                      </label>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={handleSaveIndexes}
                    disabled={saving || selectedIndexes.length === 0}
                    className="mt-4 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
                  >
                    {saving ? "Saving..." : "Save selected indexes"}
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === "indexes" && (
        <div className="text-sm text-gray-500">
          Index browsing coming soon.
        </div>
      )}
    </div>
  );
}
