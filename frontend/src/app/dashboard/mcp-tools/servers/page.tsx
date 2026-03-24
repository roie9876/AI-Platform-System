"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import Link from "next/link";
import {
  ArrowLeft,
  Plus,
  Server,
  Trash2,
  RefreshCw,
  Loader2,
  CheckCircle2,
  XCircle,
  HelpCircle,
  X,
} from "lucide-react";

interface MCPServer {
  id: string;
  name: string;
  url: string;
  description: string | null;
  auth_type: string;
  auth_header_name: string | null;
  is_active: boolean;
  status: string;
  status_message: string | null;
  created_at: string;
  updated_at: string;
}

interface MCPServerListResponse {
  servers: MCPServer[];
  total: number;
}

export default function MCPServersPage() {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAddForm, setShowAddForm] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [checkingId, setCheckingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [authType, setAuthType] = useState("none");
  const [authHeaderName, setAuthHeaderName] = useState("");
  const [authCredential, setAuthCredential] = useState("");

  const fetchServers = useCallback(async () => {
    try {
      const data = await apiFetch<MCPServerListResponse>("/api/v1/mcp-servers/");
      setServers(data.servers);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load servers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchServers();
  }, [fetchServers]);

  function resetForm() {
    setName("");
    setUrl("");
    setDescription("");
    setAuthType("none");
    setAuthHeaderName("");
    setAuthCredential("");
    setShowAddForm(false);
  }

  async function handleAddServer(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setError("");
    try {
      await apiFetch("/api/v1/mcp-servers/", {
        method: "POST",
        body: JSON.stringify({
          name,
          url,
          description: description || undefined,
          auth_type: authType,
          auth_header_name: authHeaderName || undefined,
          auth_credential_ref: authCredential || undefined,
        }),
      });
      resetForm();
      await fetchServers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add server");
    } finally {
      setFormLoading(false);
    }
  }

  async function handleCheckStatus(serverId: string) {
    setCheckingId(serverId);
    try {
      await apiFetch(`/api/v1/mcp-servers/${serverId}/check-status`, {
        method: "POST",
      });
      await fetchServers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Status check failed");
    } finally {
      setCheckingId(null);
    }
  }

  async function handleDelete(serverId: string) {
    if (!confirm("Delete this MCP server? Its discovered tools will also be removed.")) return;
    setDeletingId(serverId);
    try {
      await apiFetch(`/api/v1/mcp-servers/${serverId}`, { method: "DELETE" });
      setServers((prev) => prev.filter((s) => s.id !== serverId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete server");
    } finally {
      setDeletingId(null);
    }
  }

  function statusIcon(status: string) {
    switch (status) {
      case "connected":
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case "error":
      case "unreachable":
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <HelpCircle className="h-4 w-4 text-gray-400" />;
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/mcp-tools"
            className="rounded-md p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">MCP Servers</h1>
            <p className="text-sm text-gray-500">
              Register and manage remote MCP server connections
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-2 rounded-lg bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
        >
          <Plus className="h-4 w-4" />
          Add Server
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
          <button onClick={() => setError("")} className="float-right text-red-400 hover:text-red-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Add Server Form */}
      {showAddForm && (
        <form
          onSubmit={handleAddServer}
          className="mb-6 rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
        >
          <h2 className="mb-4 text-lg font-semibold text-gray-900">Register New MCP Server</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="My MCP Server"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">
                URL <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                required
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://mcp-server.example.com/sse"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Auth Type</label>
              <select
                value={authType}
                onChange={(e) => setAuthType(e.target.value)}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
              >
                <option value="none">None</option>
                <option value="bearer">Bearer Token</option>
                <option value="api_key">API Key</option>
                <option value="custom_header">Custom Header</option>
              </select>
            </div>
            {authType !== "none" && (
              <>
                {(authType === "api_key" || authType === "custom_header") && (
                  <div>
                    <label className="mb-1 block text-sm font-medium text-gray-700">
                      Header Name
                    </label>
                    <input
                      type="text"
                      value={authHeaderName}
                      onChange={(e) => setAuthHeaderName(e.target.value)}
                      placeholder={authType === "api_key" ? "X-API-Key" : "X-Custom-Header"}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
                    />
                  </div>
                )}
                <div className={authType === "bearer" ? "sm:col-span-2" : ""}>
                  <label className="mb-1 block text-sm font-medium text-gray-700">
                    {authType === "bearer" ? "Token" : "Credential"}
                  </label>
                  <input
                    type="password"
                    value={authCredential}
                    onChange={(e) => setAuthCredential(e.target.value)}
                    placeholder="Enter credential"
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
                  />
                </div>
              </>
            )}
          </div>
          <div className="mt-4 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={resetForm}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={formLoading}
              className="flex items-center gap-2 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
            >
              {formLoading && <Loader2 className="h-4 w-4 animate-spin" />}
              Register Server
            </button>
          </div>
        </form>
      )}

      {/* Server List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
        </div>
      ) : servers.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 py-12 text-center">
          <Server className="mx-auto h-10 w-10 text-gray-300" />
          <h3 className="mt-3 text-lg font-medium text-gray-900">No MCP servers registered</h3>
          <p className="mt-1 text-sm text-gray-500">
            Click &quot;Add Server&quot; to register your first MCP server.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {servers.map((server) => (
            <div
              key={server.id}
              className="rounded-lg border border-gray-200 bg-white px-5 py-4 shadow-sm"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  {statusIcon(server.status)}
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">{server.name}</h3>
                    <p className="mt-0.5 text-xs text-gray-500 font-mono break-all">{server.url}</p>
                    {server.description && (
                      <p className="mt-1 text-xs text-gray-400">{server.description}</p>
                    )}
                    {server.status_message && (
                      <p className={`mt-1 text-xs ${server.status === "error" ? "text-red-500" : "text-green-600"}`}>
                        {server.status_message}
                      </p>
                    )}
                    <div className="mt-2 flex items-center gap-3 text-xs text-gray-400">
                      <span>Auth: {server.auth_type}</span>
                      <span>Status: {server.status}</span>
                      <span>Added: {new Date(server.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => handleCheckStatus(server.id)}
                    disabled={checkingId === server.id}
                    className="rounded-md border border-gray-200 p-2 text-gray-400 hover:bg-gray-50 hover:text-[#7C3AED] disabled:opacity-50"
                    title="Check connection status"
                  >
                    {checkingId === server.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(server.id)}
                    disabled={deletingId === server.id}
                    className="rounded-md border border-gray-200 p-2 text-gray-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-50"
                    title="Delete server"
                  >
                    {deletingId === server.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
