"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";

const providerOptions = [
  { value: "azure_openai", label: "Azure OpenAI" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "custom", label: "Custom" },
];

export default function NewModelEndpointPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    name: "",
    provider_type: "azure_openai",
    model_name: "",
    endpoint_url: "",
    auth_type: "entra_id",
    api_key: "",
    priority: 0,
  });

  const showEndpointUrl =
    form.provider_type === "azure_openai" || form.provider_type === "custom";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      await apiFetch("/api/v1/model-endpoints", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          provider_type: form.provider_type,
          model_name: form.model_name,
          endpoint_url: form.endpoint_url || null,
          auth_type: form.auth_type,
          api_key: form.auth_type === "api_key" ? form.api_key : null,
          priority: form.priority,
        }),
      });
      router.push("/dashboard/models");
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to register endpoint"
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        Register Model Endpoint
      </h1>

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
            placeholder="e.g., Production GPT-4o"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Provider *
          </label>
          <select
            value={form.provider_type}
            onChange={(e) =>
              setForm({ ...form, provider_type: e.target.value })
            }
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {providerOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Model Name *
          </label>
          <input
            type="text"
            required
            maxLength={255}
            value={form.model_name}
            onChange={(e) => setForm({ ...form, model_name: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="e.g., gpt-4o, claude-3-opus"
          />
        </div>

        {showEndpointUrl && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Endpoint URL
            </label>
            <input
              type="text"
              value={form.endpoint_url}
              onChange={(e) =>
                setForm({ ...form, endpoint_url: e.target.value })
              }
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="https://your-resource.openai.azure.com/"
            />
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Authentication *
          </label>
          <div className="space-y-2">
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="auth_type"
                value="entra_id"
                checked={form.auth_type === "entra_id"}
                onChange={(e) =>
                  setForm({ ...form, auth_type: e.target.value, api_key: "" })
                }
                className="text-blue-600"
              />
              <span className="text-sm text-gray-700">
                Entra ID (Managed Identity)
              </span>
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="auth_type"
                value="api_key"
                checked={form.auth_type === "api_key"}
                onChange={(e) =>
                  setForm({ ...form, auth_type: e.target.value })
                }
                className="text-blue-600"
              />
              <span className="text-sm text-gray-700">API Key</span>
            </label>
          </div>
        </div>

        {form.auth_type === "entra_id" && (
          <div className="rounded-md bg-blue-50 p-3 text-sm text-blue-700">
            Platform will authenticate using Managed Identity. No API key
            needed.
          </div>
        )}

        {form.auth_type === "api_key" && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API Key *
            </label>
            <input
              type="password"
              required
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="sk-..."
            />
            <p className="mt-1 text-xs text-gray-500">
              Your API key will be encrypted and stored securely.
            </p>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Priority
          </label>
          <input
            type="number"
            min={0}
            value={form.priority}
            onChange={(e) =>
              setForm({ ...form, priority: parseInt(e.target.value) || 0 })
            }
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <p className="mt-1 text-xs text-gray-500">
            Lower number = higher priority for fallback ordering.
          </p>
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Registering..." : "Register Endpoint"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/dashboard/models")}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
