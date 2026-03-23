"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface ModelEndpoint {
  id: string;
  name: string;
  provider_type: string;
  model_name: string;
}

interface ModelEndpointListResponse {
  endpoints: ModelEndpoint[];
  total: number;
}

export default function NewAgentPage() {
  const router = useRouter();
  const [endpoints, setEndpoints] = useState<ModelEndpoint[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    name: "",
    description: "",
    system_prompt: "",
    model_endpoint_id: "",
    temperature: 0.7,
    max_tokens: 1024,
    timeout_seconds: 30,
  });

  useEffect(() => {
    apiFetch<ModelEndpointListResponse>("/api/v1/model-endpoints")
      .then((data) => setEndpoints(data.endpoints))
      .catch(() => {});
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      await apiFetch("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          model_endpoint_id: form.model_endpoint_id || null,
          description: form.description || null,
          system_prompt: form.system_prompt || null,
        }),
      });
      router.push("/dashboard/agents");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create agent");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Create Agent</h1>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Name *
          </label>
          <input
            type="text"
            required
            maxLength={255}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            System Prompt
          </label>
          <textarea
            rows={4}
            value={form.system_prompt}
            onChange={(e) =>
              setForm({ ...form, system_prompt: e.target.value })
            }
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Model Endpoint
          </label>
          <select
            value={form.model_endpoint_id}
            onChange={(e) =>
              setForm({ ...form, model_endpoint_id: e.target.value })
            }
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">None (assign later)</option>
            {endpoints.map((ep) => (
              <option key={ep.id} value={ep.id}>
                {ep.name} ({ep.provider_type} / {ep.model_name})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Temperature: {form.temperature}
          </label>
          <input
            type="range"
            min={0}
            max={2}
            step={0.1}
            value={form.temperature}
            onChange={(e) =>
              setForm({ ...form, temperature: parseFloat(e.target.value) })
            }
            className="w-full"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Tokens
            </label>
            <input
              type="number"
              min={1}
              max={128000}
              value={form.max_tokens}
              onChange={(e) =>
                setForm({ ...form, max_tokens: parseInt(e.target.value) || 1024 })
              }
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Timeout (seconds)
            </label>
            <input
              type="number"
              min={1}
              max={300}
              value={form.timeout_seconds}
              onChange={(e) =>
                setForm({
                  ...form,
                  timeout_seconds: parseInt(e.target.value) || 30,
                })
              }
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Creating..." : "Create Agent"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/dashboard/agents")}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
