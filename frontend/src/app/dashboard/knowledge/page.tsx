"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { ResourcePicker } from "@/components/azure/resource-picker";
import {
  Search,
  Brain,
  Mic,
  Plus,
  Trash2,
  Pencil,
  RefreshCw,
  ChevronLeft,
  Database,
} from "lucide-react";

/* ─── Types ─── */

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
  resource_id: string;
  name: string;
  resource_type: string;
  region: string;
  resource_group: string | null;
}

interface SearchIndex {
  name: string;
}

interface ConnectionResponse {
  id: string;
  resource_name: string;
  resource_type: string;
  resource_id: string;
  endpoint: string | null;
  region: string | null;
  auth_type: string;
  health_status: string;
  last_health_check: string | null;
  config: Record<string, unknown> | null;
  agent_ids: string[] | null;
  created_at: string;
  updated_at: string;
}

interface SearchIndexListResponse {
  connection_id: string;
  resource_name: string;
  indexes: SearchIndex[];
  count: number;
}

/* ─── Resource type definitions ─── */

interface ResourceTypeDef {
  key: string;
  arm: string;
  label: string;
  icon: typeof Search;
  description: string;
}

const RESOURCE_TYPES: ResourceTypeDef[] = [
  {
    key: "ai-search",
    arm: "Microsoft.Search/searchServices",
    label: "Azure AI Search",
    icon: Search,
    description: "Full-text & vector search indexes",
  },
  {
    key: "cognitive",
    arm: "Microsoft.CognitiveServices/accounts",
    label: "Azure AI Services",
    icon: Brain,
    description: "Content Understanding, Language, Vision",
  },
  {
    key: "speech",
    arm: "Microsoft.CognitiveServices/accounts",
    label: "Azure Speech",
    icon: Mic,
    description: "Speech-to-text, text-to-speech",
  },
];

/* ─── Helpers ─── */

function resourceTypeLabel(arm: string): string {
  return RESOURCE_TYPES.find((r) => r.arm === arm)?.label ?? arm;
}

function ResourceTypeIcon({ arm }: { arm: string }) {
  const def = RESOURCE_TYPES.find((r) => r.arm === arm);
  const Icon = def?.icon ?? Database;
  return <Icon className="h-5 w-5 text-[#7C3AED]" />;
}

function statusColor(status: string) {
  if (status === "connected") return "bg-green-100 text-green-700";
  if (status === "error") return "bg-red-100 text-red-700";
  return "bg-gray-100 text-gray-600";
}

/* ─── Page ─── */

type View = "list" | "create" | "edit";

export default function KnowledgePage() {
  const searchParams = useSearchParams();
  const attachToAgentId = searchParams.get("attachTo");

  const [view, setView] = useState<View>("list");
  const [connections, setConnections] = useState<ConnectionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  /* ─ Create flow state ─ */
  const [selectedType, setSelectedType] = useState<ResourceTypeDef>(RESOURCE_TYPES[0]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [resources, setResources] = useState<AzureResource[]>([]);
  const [loadingResources, setLoadingResources] = useState(false);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const [authType, setAuthType] = useState("api_key");
  const [newConnectionId, setNewConnectionId] = useState<string | null>(null);
  const [indexes, setIndexes] = useState<SearchIndex[]>([]);
  const [selectedIndexes, setSelectedIndexes] = useState<string[]>([]);
  const [knowledgeName, setKnowledgeName] = useState("");
  const [saving, setSaving] = useState(false);

  /* ─ Edit flow state ─ */
  const [editConnection, setEditConnection] = useState<ConnectionResponse | null>(null);
  const [editIndexes, setEditIndexes] = useState<SearchIndex[]>([]);
  const [editSelectedIndexes, setEditSelectedIndexes] = useState<string[]>([]);
  const [editKnowledgeName, setEditKnowledgeName] = useState("");
  const [editLoading, setEditLoading] = useState(false);

  /* ─ Delete state ─ */
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  /* ─── Load connections ─── */
  const loadConnections = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<ConnectionResponse[]>("/api/v1/azure/connections");
      setConnections(data);
    } catch {
      /* empty tenant — no connections yet */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  /* ─── Load subscriptions when entering create flow ─── */
  useEffect(() => {
    if (view === "create" && subscriptions.length === 0) {
      apiFetch<Subscription[]>("/api/v1/azure/subscriptions")
        .then(setSubscriptions)
        .catch(() => {});
    }
  }, [view, subscriptions.length]);

  /* ─── Discover resources when subscription or type changes ─── */
  useEffect(() => {
    if (!selectedSubId) {
      setResources([]);
      return;
    }
    setLoadingResources(true);
    apiFetch<{ resources: DiscoveredResource[] }>(
      `/api/v1/azure/subscriptions/${selectedSubId}/resources?resource_type=${encodeURIComponent(selectedType.arm)}`
    )
      .then((data) =>
        setResources(
          (data.resources || []).map((r) => ({
            resource_id: r.resource_id,
            name: r.name,
            region: r.region,
            resource_group: r.resource_group ?? undefined,
          }))
        )
      )
      .catch(() => setResources([]))
      .finally(() => setLoadingResources(false));
  }, [selectedSubId, selectedType]);

  /* ─── Handlers ─── */

  function resetCreateFlow() {
    setSelectedSubId(null);
    setResources([]);
    setSelectedResourceId(null);
    setAuthType("api_key");
    setNewConnectionId(null);
    setIndexes([]);
    setSelectedIndexes([]);
    setKnowledgeName("");
    setSelectedType(RESOURCE_TYPES[0]);
    setError("");
  }

  async function handleConnect() {
    if (!selectedResourceId || !selectedSubId) return;
    setError("");
    const resource = resources.find((r) => r.resource_id === selectedResourceId);
    if (!resource) return;

    try {
      const conn = await apiFetch<ConnectionResponse>("/api/v1/azure/connections", {
        method: "POST",
        body: JSON.stringify({
          azure_subscription_id: selectedSubId,
          resource_type: selectedType.arm,
          resource_name: resource.name,
          resource_id: selectedResourceId,
          auth_type: authType,
          region: resource.region,
        }),
      });
      setNewConnectionId(conn.id);

      // For AI Search, load indexes
      if (selectedType.arm === "Microsoft.Search/searchServices") {
        const idxData = await apiFetch<SearchIndexListResponse>(
          `/api/v1/knowledge/connections/${conn.id}/indexes`
        );
        setIndexes(idxData.indexes);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Connection failed");
    }
  }

  async function handleSaveIndexes() {
    if (!newConnectionId || selectedIndexes.length === 0) return;
    setSaving(true);
    try {
      await apiFetch(`/api/v1/knowledge/connections/${newConnectionId}/indexes`, {
        method: "POST",
        body: JSON.stringify({
          index_names: selectedIndexes,
          knowledge_name: knowledgeName || undefined,
        }),
      });

      // Auto-attach to agent if redirected from agent page
      if (attachToAgentId) {
        try {
          await apiFetch(
            `/api/v1/knowledge/agents/${attachToAgentId}/attach/${newConnectionId}`,
            { method: "POST" }
          );
        } catch {
          // Attachment is best-effort; connection still created
        }
      }

      resetCreateFlow();
      setView("list");
      await loadConnections();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveNonSearchConnection() {
    // For non AI-Search types, just save the connection with a name
    if (!newConnectionId) return;
    setSaving(true);
    try {
      await apiFetch(`/api/v1/azure/connections/${newConnectionId}`, {
        method: "PATCH",
        body: JSON.stringify({
          config: { knowledge_name: knowledgeName || undefined },
        }),
      });
      resetCreateFlow();
      setView("list");
      await loadConnections();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    setDeleting(true);
    try {
      await apiFetch(`/api/v1/azure/connections/${id}`, { method: "DELETE" });
      setDeleteId(null);
      await loadConnections();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  async function openEdit(conn: ConnectionResponse) {
    setEditConnection(conn);
    setEditKnowledgeName(
      (conn.config?.knowledge_name as string) || conn.resource_name
    );
    setEditSelectedIndexes(
      (conn.config?.selected_indexes as string[]) || []
    );
    setView("edit");

    // For AI Search, load fresh indexes
    if (conn.resource_type === "Microsoft.Search/searchServices") {
      setEditLoading(true);
      try {
        const idxData = await apiFetch<SearchIndexListResponse>(
          `/api/v1/knowledge/connections/${conn.id}/indexes`
        );
        setEditIndexes(idxData.indexes);
      } catch {
        setEditIndexes([]);
      } finally {
        setEditLoading(false);
      }
    }
  }

  async function handleEditSave() {
    if (!editConnection) return;
    setSaving(true);
    try {
      const config = { ...(editConnection.config || {}) };
      config.knowledge_name = editKnowledgeName || undefined;
      if (editConnection.resource_type === "Microsoft.Search/searchServices") {
        config.selected_indexes = editSelectedIndexes;
      }
      await apiFetch(`/api/v1/azure/connections/${editConnection.id}`, {
        method: "PATCH",
        body: JSON.stringify({ config }),
      });
      setEditConnection(null);
      setView("list");
      await loadConnections();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleHealthCheck(id: string) {
    try {
      await apiFetch(`/api/v1/azure/connections/${id}/health-check`, {
        method: "POST",
      });
      await loadConnections();
    } catch {
      /* silently ignore */
    }
  }

  function toggleIndex(name: string, list: string[], setter: (v: string[]) => void) {
    setter(list.includes(name) ? list.filter((n) => n !== name) : [...list, name]);
  }

  /* ─── Render: List View ─── */

  if (view === "list") {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold text-gray-900">Knowledge</h1>
          </div>
          <button
            type="button"
            onClick={() => {
              resetCreateFlow();
              setView("create");
            }}
            className="flex items-center gap-2 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
          >
            <Plus className="h-4 w-4" />
            Add connection
          </button>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {attachToAgentId && (
          <div className="mb-4 rounded-md bg-blue-50 border border-blue-200 p-3 text-sm text-blue-700">
            New knowledge created here will be automatically attached to the agent you came from.
          </div>
        )}

        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : connections.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-gray-200 p-12 text-center">
            <Database className="mx-auto h-10 w-10 text-gray-300" />
            <h3 className="mt-3 text-sm font-medium text-gray-900">
              No knowledge connections yet
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Connect Azure resources to ground your agents in enterprise
              knowledge.
            </p>
            <button
              type="button"
              onClick={() => {
                resetCreateFlow();
                setView("create");
              }}
              className="mt-4 inline-flex items-center gap-2 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
            >
              <Plus className="h-4 w-4" />
              Add your first connection
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {connections.map((conn) => {
              const name =
                (conn.config?.knowledge_name as string) || conn.resource_name;
              const selectedIdx =
                (conn.config?.selected_indexes as string[]) || [];
              const agentCount = (conn.agent_ids || []).length;
              return (
                <div
                  key={conn.id}
                  className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:border-gray-300"
                >
                  <div className="flex items-center gap-4">
                    <ResourceTypeIcon arm={conn.resource_type} />
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {resourceTypeLabel(conn.resource_type)}
                        {conn.region && ` · ${conn.region}`}
                        {selectedIdx.length > 0 &&
                          ` · ${selectedIdx.length} index${selectedIdx.length > 1 ? "es" : ""}`}
                        {` · ${agentCount} agent${agentCount !== 1 ? "s" : ""}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusColor(conn.health_status)}`}
                    >
                      {conn.health_status}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleHealthCheck(conn.id)}
                      className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      title="Health check"
                    >
                      <RefreshCw className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => openEdit(conn)}
                      className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      title="Edit"
                    >
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteId(conn.id)}
                      className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600"
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Delete confirmation dialog */}
        {deleteId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-lg">
              <h3 className="text-sm font-semibold text-gray-900">
                Delete connection?
              </h3>
              <p className="mt-2 text-sm text-gray-500">
                This will permanently remove this knowledge connection. Agents
                using it will lose access.
              </p>
              <div className="mt-4 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setDeleteId(null)}
                  className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(deleteId)}
                  disabled={deleting}
                  className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleting ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  /* ─── Render: Create View ─── */

  if (view === "create") {
    const isSearch = selectedType.arm === "Microsoft.Search/searchServices";

    return (
      <div className="mx-auto max-w-4xl p-6">
        <button
          type="button"
          onClick={() => {
            resetCreateFlow();
            setView("list");
          }}
          className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to connections
        </button>

        <div className="mb-6 flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">
            Add knowledge connection
          </h1>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Step 1: Resource type */}
        <div className="mb-6">
          <label className="mb-2 block text-sm font-medium text-gray-700">
            Resource type
          </label>
          <div className="grid grid-cols-3 gap-3">
            {RESOURCE_TYPES.map((rt) => {
              const Icon = rt.icon;
              return (
                <button
                  key={rt.key}
                  type="button"
                  onClick={() => {
                    setSelectedType(rt);
                    setSelectedResourceId(null);
                    setNewConnectionId(null);
                    setIndexes([]);
                  }}
                  className={`flex flex-col items-center gap-2 rounded-lg border-2 p-4 text-center transition ${
                    selectedType.key === rt.key
                      ? "border-[#7C3AED] bg-purple-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <Icon
                    className={`h-6 w-6 ${selectedType.key === rt.key ? "text-[#7C3AED]" : "text-gray-400"}`}
                  />
                  <span className="text-sm font-medium text-gray-900">
                    {rt.label}
                  </span>
                  <span className="text-xs text-gray-500">
                    {rt.description}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Step 2: Subscription */}
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

        {/* Step 3: Resource picker */}
        <div className="mb-4">
          <ResourcePicker
            resources={resources}
            value={selectedResourceId}
            onChange={(r) => setSelectedResourceId(r?.resource_id ?? null)}
            label={`${selectedType.label} resource *`}
            loading={loadingResources}
          />
        </div>

        {/* Step 4: Auth type */}
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
        {selectedResourceId && !newConnectionId && (
          <button
            type="button"
            onClick={handleConnect}
            className="mb-4 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
          >
            Connect
          </button>
        )}

        {/* After connection */}
        {newConnectionId && (
          <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4">
            {/* Knowledge name */}
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Knowledge base name
              </label>
              <input
                type="text"
                value={knowledgeName}
                onChange={(e) => setKnowledgeName(e.target.value)}
                placeholder="e.g. Product documentation"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
              />
            </div>

            {/* AI Search: index selection */}
            {isSearch && indexes.length > 0 && (
              <>
                <label className="mb-2 block text-sm font-medium text-gray-700">
                  Select indexes
                </label>
                <div className="space-y-2">
                  {indexes.map((idx) => (
                    <label
                      key={idx.name}
                      className="flex items-center gap-2 text-sm"
                    >
                      <input
                        type="checkbox"
                        checked={selectedIndexes.includes(idx.name)}
                        onChange={() =>
                          toggleIndex(idx.name, selectedIndexes, setSelectedIndexes)
                        }
                        className="rounded border-gray-300 text-[#7C3AED] focus:ring-[#7C3AED]"
                      />
                      <span className="text-gray-900">{idx.name}</span>
                    </label>
                  ))}
                </div>
              </>
            )}

            {isSearch && indexes.length === 0 && (
              <p className="text-sm text-gray-500">No indexes found in this search service.</p>
            )}

            <button
              type="button"
              onClick={isSearch ? handleSaveIndexes : handleSaveNonSearchConnection}
              disabled={saving || (isSearch && selectedIndexes.length === 0)}
              className="mt-4 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save connection"}
            </button>
          </div>
        )}
      </div>
    );
  }

  /* ─── Render: Edit View ─── */

  if (view === "edit" && editConnection) {
    const isSearch =
      editConnection.resource_type === "Microsoft.Search/searchServices";

    return (
      <div className="mx-auto max-w-4xl p-6">
        <button
          type="button"
          onClick={() => {
            setEditConnection(null);
            setView("list");
          }}
          className="mb-4 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ChevronLeft className="h-4 w-4" />
          Back to connections
        </button>

        <div className="mb-6 flex items-center gap-3">
          <h1 className="text-xl font-semibold text-gray-900">
            Edit connection
          </h1>
        </div>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Read-only info */}
        <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <div className="flex items-center gap-3">
            <ResourceTypeIcon arm={editConnection.resource_type} />
            <div>
              <p className="text-sm font-medium text-gray-900">
                {editConnection.resource_name}
              </p>
              <p className="text-xs text-gray-500">
                {resourceTypeLabel(editConnection.resource_type)}
                {editConnection.region && ` · ${editConnection.region}`}
              </p>
            </div>
          </div>
        </div>

        {/* Editable name */}
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Knowledge base name
          </label>
          <input
            type="text"
            value={editKnowledgeName}
            onChange={(e) => setEditKnowledgeName(e.target.value)}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
          />
        </div>

        {/* AI Search: edit index selection */}
        {isSearch && (
          <div className="mb-4">
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Selected indexes
            </label>
            {editLoading ? (
              <p className="text-sm text-gray-500">Loading indexes...</p>
            ) : editIndexes.length === 0 ? (
              <p className="text-sm text-gray-500">No indexes found.</p>
            ) : (
              <div className="space-y-2">
                {editIndexes.map((idx) => (
                  <label
                    key={idx.name}
                    className="flex items-center gap-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={editSelectedIndexes.includes(idx.name)}
                      onChange={() =>
                        toggleIndex(idx.name, editSelectedIndexes, setEditSelectedIndexes)
                      }
                      className="rounded border-gray-300 text-[#7C3AED] focus:ring-[#7C3AED]"
                    />
                    <span className="text-gray-900">{idx.name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleEditSave}
            disabled={saving}
            className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save changes"}
          </button>
          <button
            type="button"
            onClick={() => {
              setEditConnection(null);
              setView("list");
            }}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return null;
}
