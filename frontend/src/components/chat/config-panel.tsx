"use client";

import { useState, useEffect } from "react";
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

interface ConfigPanelProps {
  agentId: string;
  systemPrompt: string;
  temperature: number;
  maxTokens: number;
  timeoutSeconds: number;
  modelEndpointId: string | null;
  configVersion: number;
  onConfigUpdate: (config: {
    system_prompt: string;
    temperature: number;
    max_tokens: number;
    timeout_seconds: number;
    model_endpoint_id: string | null;
    current_config_version: number;
  }) => void;
}

export function ConfigPanel({
  agentId,
  systemPrompt,
  temperature,
  maxTokens,
  timeoutSeconds,
  modelEndpointId,
  configVersion,
  onConfigUpdate,
}: ConfigPanelProps) {
  const [endpoints, setEndpoints] = useState<ModelEndpoint[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [form, setForm] = useState({
    system_prompt: systemPrompt,
    temperature: temperature,
    max_tokens: maxTokens,
    timeout_seconds: timeoutSeconds,
    model_endpoint_id: modelEndpointId || "",
  });

  useEffect(() => {
    apiFetch<ModelEndpointListResponse>("/api/v1/model-endpoints")
      .then((data) => setEndpoints(data.endpoints))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setForm({
      system_prompt: systemPrompt,
      temperature: temperature,
      max_tokens: maxTokens,
      timeout_seconds: timeoutSeconds,
      model_endpoint_id: modelEndpointId || "",
    });
  }, [systemPrompt, temperature, maxTokens, timeoutSeconds, modelEndpointId]);

  const handleApply = async () => {
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const updated = await apiFetch<{
        system_prompt: string;
        temperature: number;
        max_tokens: number;
        timeout_seconds: number;
        model_endpoint_id: string | null;
        current_config_version: number;
      }>(`/api/v1/agents/${agentId}`, {
        method: "PUT",
        body: JSON.stringify({
          system_prompt: form.system_prompt || null,
          temperature: form.temperature,
          max_tokens: form.max_tokens,
          timeout_seconds: form.timeout_seconds,
          model_endpoint_id: form.model_endpoint_id || null,
        }),
      });
      onConfigUpdate(updated);
      setSuccess("Config applied");
      setTimeout(() => setSuccess(""), 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update config");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="w-80 border-l border-gray-200 bg-white flex flex-col overflow-y-auto">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-900">Configuration</h3>
        <p className="text-xs text-gray-400 mt-0.5">v{configVersion}</p>
      </div>

      <div className="p-4 space-y-4 flex-1">
        {/* Model Endpoint Selector */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Model Endpoint
          </label>
          <select
            value={form.model_endpoint_id}
            onChange={(e) =>
              setForm({ ...form, model_endpoint_id: e.target.value })
            }
            className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">None</option>
            {endpoints.map((ep) => (
              <option key={ep.id} value={ep.id}>
                {ep.name} ({ep.model_name})
              </option>
            ))}
          </select>
        </div>

        {/* System Prompt */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            System Prompt
          </label>
          <textarea
            rows={4}
            value={form.system_prompt}
            onChange={(e) =>
              setForm({ ...form, system_prompt: e.target.value })
            }
            className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Temperature */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
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

        {/* Max Tokens */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Max Tokens
          </label>
          <input
            type="number"
            min={1}
            max={128000}
            value={form.max_tokens}
            onChange={(e) =>
              setForm({
                ...form,
                max_tokens: parseInt(e.target.value) || 0,
              })
            }
            className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        {/* Timeout */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
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
            className="w-full rounded-md border border-gray-300 px-2 py-1.5 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Apply button */}
      <div className="p-4 border-t border-gray-200">
        {error && (
          <p className="text-xs text-red-600 mb-2">{error}</p>
        )}
        {success && (
          <p className="text-xs text-green-600 mb-2">{success}</p>
        )}
        <button
          onClick={handleApply}
          disabled={saving}
          className="w-full rounded-md bg-blue-600 px-3 py-2 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {saving ? "Applying..." : "Apply Changes"}
        </button>
      </div>
    </div>
  );
}
