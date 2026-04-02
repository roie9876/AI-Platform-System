"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { ChannelWizard, type ChannelWizardState, type WhatsAppGroupRule, type TelegramGroupRule } from "@/components/agent/channel-wizard";

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
    agent_type: "standard" as "standard" | "openclaw",
    model_endpoint_id: "",
    temperature: 0,
    max_tokens: 0,
    timeout_seconds: 30,
    // OpenClaw-specific fields
    enable_web_browsing: true,
    enable_shell: false,
    enable_deep_research: false,
    // Gmail fields
    gmail_enabled: false,
    gmail_email: "",
    gmail_app_password: "",
    gmail_app_password_secret: "",
    gmail_display_name: "OpenClaw Agent",
    gmail_use_existing_secret: true,
  });

  const [channels, setChannels] = useState<ChannelWizardState>({
    whatsapp_enabled: false,
    whatsapp_dm_policy: "open",
    whatsapp_allowed_phones: "",
    whatsapp_group_policy: "open",
    whatsapp_group_rules: [],
    telegram_enabled: false,
    telegram_bot_token: "",
    telegram_bot_token_secret: "",
    telegram_use_existing_secret: false,
    telegram_allowed_users: "",
    dm_policy: "allowlist",
    telegram_group_rules: [],
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
      const payload: Record<string, unknown> = {
        name: form.name,
        description: form.description || null,
        system_prompt: form.system_prompt || null,
        agent_type: form.agent_type,
        model_endpoint_id: form.model_endpoint_id || null,
        temperature: form.temperature,
        max_tokens: form.max_tokens || null,
        timeout_seconds: form.timeout_seconds,
      };

      if (form.agent_type === "openclaw") {
        payload.openclaw_config = {
          channels: {
            telegram_enabled: channels.telegram_enabled,
            telegram_bot_token: channels.telegram_use_existing_secret
              ? null
              : channels.telegram_bot_token || null,
            telegram_bot_token_secret: channels.telegram_use_existing_secret
              ? channels.telegram_bot_token_secret || null
              : null,
            telegram_allowed_users: channels.telegram_allowed_users
              ? channels.telegram_allowed_users.split(",").map((s: string) => s.trim())
              : [],
            dm_policy: channels.dm_policy,
            telegram_group_rules: channels.telegram_group_rules,
          },
          gmail: form.gmail_enabled
            ? {
                gmail_enabled: true,
                gmail_email: form.gmail_email || null,
                gmail_app_password: form.gmail_use_existing_secret
                  ? null
                  : form.gmail_app_password || null,
                gmail_app_password_secret: form.gmail_use_existing_secret
                  ? form.gmail_app_password_secret || "gmail-app-password"
                  : null,
                gmail_display_name: form.gmail_display_name || "OpenClaw Agent",
              }
            : null,
          whatsapp: channels.whatsapp_enabled
            ? {
                whatsapp_enabled: true,
                whatsapp_dm_policy: channels.whatsapp_dm_policy,
                whatsapp_allowed_phones: channels.whatsapp_allowed_phones
                  ? channels.whatsapp_allowed_phones.split(",").map((s: string) => s.trim())
                  : [],
                whatsapp_group_policy: channels.whatsapp_group_policy,
                whatsapp_group_rules: channels.whatsapp_group_rules,
              }
            : null,
          enable_web_browsing: form.enable_web_browsing,
          enable_shell: form.enable_shell,
          enable_deep_research: form.enable_deep_research,
        };
      }

      await apiFetch("/api/v1/agents", {
        method: "POST",
        body: JSON.stringify(payload),
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

        {/* Agent Type Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Agent Type
          </label>
          <div className="flex gap-4">
            <label
              className={`flex-1 relative flex cursor-pointer rounded-lg border p-4 ${
                form.agent_type === "standard"
                  ? "border-blue-500 bg-blue-50 ring-2 ring-blue-500"
                  : "border-gray-300 hover:border-gray-400"
              }`}
            >
              <input
                type="radio"
                name="agent_type"
                value="standard"
                checked={form.agent_type === "standard"}
                onChange={() => setForm({ ...form, agent_type: "standard" })}
                className="sr-only"
              />
              <div>
                <span className="block text-sm font-medium text-gray-900">
                  Standard Agent
                </span>
                <span className="mt-1 block text-xs text-gray-500">
                  Chat via web UI, platform tools, model endpoints
                </span>
              </div>
            </label>
            <label
              className={`flex-1 relative flex cursor-pointer rounded-lg border p-4 ${
                form.agent_type === "openclaw"
                  ? "border-purple-500 bg-purple-50 ring-2 ring-purple-500"
                  : "border-gray-300 hover:border-gray-400"
              }`}
            >
              <input
                type="radio"
                name="agent_type"
                value="openclaw"
                checked={form.agent_type === "openclaw"}
                onChange={() => setForm({ ...form, agent_type: "openclaw" })}
                className="sr-only"
              />
              <div>
                <span className="block text-sm font-medium text-gray-900">
                  OpenClaw Agent
                </span>
                <span className="mt-1 block text-xs text-gray-500">
                  Autonomous — Telegram, web browsing, deep research, shell
                </span>
              </div>
            </label>
          </div>
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

        {/* OpenClaw Configuration (shown only when OpenClaw type selected) */}
        {form.agent_type === "openclaw" && (
          <div className="rounded-lg border border-purple-200 bg-purple-50/50 p-4 space-y-4">
            <h3 className="text-sm font-semibold text-purple-900">
              OpenClaw Configuration
            </h3>

            {/* Capabilities */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide">
                Capabilities
              </label>
              <div className="flex flex-wrap gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.enable_web_browsing}
                    onChange={(e) =>
                      setForm({ ...form, enable_web_browsing: e.target.checked })
                    }
                    className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                  />
                  Web Browsing
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.enable_shell}
                    onChange={(e) =>
                      setForm({ ...form, enable_shell: e.target.checked })
                    }
                    className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                  />
                  Shell Access
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    checked={form.enable_deep_research}
                    onChange={(e) =>
                      setForm({ ...form, enable_deep_research: e.target.checked })
                    }
                    className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                  />
                  Deep Research (GPT-5.4)
                </label>
              </div>
            </div>

            {/* Messaging Channels */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide">
                Messaging Channels
              </label>
              <ChannelWizard state={channels} onChange={setChannels} mode="create" />
            </div>

            {/* Gmail Integration */}
            <div className="space-y-3">
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <input
                  type="checkbox"
                  checked={form.gmail_enabled}
                  onChange={(e) =>
                    setForm({ ...form, gmail_enabled: e.target.checked })
                  }
                  className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                />
                Enable Gmail Access
              </label>

              {form.gmail_enabled && (
                <div className="ml-6 space-y-3">
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">
                      Gmail Address *
                    </label>
                    <input
                      type="email"
                      placeholder="agent@gmail.com"
                      value={form.gmail_email}
                      onChange={(e) =>
                        setForm({ ...form, gmail_email: e.target.value })
                      }
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm text-gray-600 mb-1">
                      Display Name
                    </label>
                    <input
                      type="text"
                      placeholder="OpenClaw Agent"
                      value={form.gmail_display_name}
                      onChange={(e) =>
                        setForm({ ...form, gmail_display_name: e.target.value })
                      }
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    />
                  </div>

                  {/* App Password Source */}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide mb-2">
                      App Password
                    </label>
                    <div className="flex gap-4 mb-3">
                      <label
                        className={`flex-1 relative flex cursor-pointer rounded-lg border p-3 ${
                          form.gmail_use_existing_secret
                            ? "border-purple-500 bg-purple-50 ring-1 ring-purple-500"
                            : "border-gray-300 hover:border-gray-400"
                        }`}
                      >
                        <input
                          type="radio"
                          name="gmail_password_source"
                          checked={form.gmail_use_existing_secret}
                          onChange={() =>
                            setForm({ ...form, gmail_use_existing_secret: true })
                          }
                          className="sr-only"
                        />
                        <div>
                          <span className="block text-xs font-medium text-gray-900">
                            Use existing Key Vault secret
                          </span>
                          <span className="mt-0.5 block text-xs text-gray-500">
                            Re-use a previously stored app password
                          </span>
                        </div>
                      </label>
                      <label
                        className={`flex-1 relative flex cursor-pointer rounded-lg border p-3 ${
                          !form.gmail_use_existing_secret
                            ? "border-purple-500 bg-purple-50 ring-1 ring-purple-500"
                            : "border-gray-300 hover:border-gray-400"
                        }`}
                      >
                        <input
                          type="radio"
                          name="gmail_password_source"
                          checked={!form.gmail_use_existing_secret}
                          onChange={() =>
                            setForm({ ...form, gmail_use_existing_secret: false })
                          }
                          className="sr-only"
                        />
                        <div>
                          <span className="block text-xs font-medium text-gray-900">
                            Enter new App Password
                          </span>
                          <span className="mt-0.5 block text-xs text-gray-500">
                            Store a new password in Key Vault
                          </span>
                        </div>
                      </label>
                    </div>

                    {form.gmail_use_existing_secret ? (
                      <div>
                        <input
                          type="text"
                          placeholder="gmail-app-password"
                          value={form.gmail_app_password_secret}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              gmail_app_password_secret: e.target.value,
                            })
                          }
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                        />
                        <p className="mt-1 text-xs text-gray-500">
                          Default: gmail-app-password from Key Vault.
                        </p>
                      </div>
                    ) : (
                      <div>
                        <input
                          type="password"
                          placeholder="xxxx xxxx xxxx xxxx"
                          value={form.gmail_app_password}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              gmail_app_password: e.target.value,
                            })
                          }
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                        />
                        <p className="mt-1 text-xs text-gray-500">
                          From Google Account → Security → 2-Step Verification → App Passwords.
                          Will be securely stored in Azure Key Vault.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

          </div>
        )}

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
              min={0}
              max={128000}
              placeholder="Model default"
              value={form.max_tokens || ""}
              onChange={(e) =>
                setForm({ ...form, max_tokens: parseInt(e.target.value) || 0 })
              }
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-400">
              Leave empty to use the model&apos;s native max.
            </p>
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
