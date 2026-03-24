"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { AgentConfigTopBar } from "@/components/agent/agent-config-top-bar";
import { AgentConfigLayout } from "@/components/agent/agent-config-layout";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { PreviewBadge } from "@/components/ui/preview-badge";
import { KnowledgeSection } from "@/components/knowledge/knowledge-section";
import { ToolCatalogModal } from "@/components/tools/tool-catalog-modal";
import { Info, MoreVertical } from "lucide-react";

interface Agent {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string | null;
  status: string;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
  model_endpoint_id: string | null;
  current_config_version: number;
}

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

interface AgentTool {
  id: string;
  agent_id: string;
  tool_id: string;
  tool_name?: string;
}

interface Tool {
  id: string;
  name: string;
  description: string | null;
}

interface ToolListResponse {
  tools: Tool[];
  total: number;
}

export default function AgentDetailPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [endpoints, setEndpoints] = useState<ModelEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [selectedEndpointId, setSelectedEndpointId] = useState("");
  const [showCatalog, setShowCatalog] = useState(false);
  const [attachedTools, setAttachedTools] = useState<Tool[]>([]);
  const [rightTab, setRightTab] = useState<"chat" | "yaml" | "code">("chat");
  const [chatInput, setChatInput] = useState("");

  useEffect(() => {
    Promise.all([
      apiFetch<Agent>(`/api/v1/agents/${agentId}`),
      apiFetch<ModelEndpointListResponse>("/api/v1/model-endpoints"),
    ])
      .then(([agentData, endpointsData]) => {
        setAgent(agentData);
        setEndpoints(endpointsData.endpoints);
        setSystemPrompt(agentData.system_prompt || "");
        setSelectedEndpointId(agentData.model_endpoint_id || "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [agentId]);

  useEffect(() => {
    loadAttachedTools();
  }, [agentId]);

  async function loadAttachedTools() {
    try {
      const [agentTools, allTools] = await Promise.all([
        apiFetch<AgentTool[]>(`/api/v1/agents/${agentId}/tools`),
        apiFetch<ToolListResponse>("/api/v1/tools"),
      ]);
      const attachedIds = new Set(agentTools.map((at) => at.tool_id));
      setAttachedTools(allTools.tools.filter((t) => attachedIds.has(t.id)));
    } catch {
      // silently handle
    }
  }

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading agent...</p>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="p-8">
        <p className="text-red-600">Agent not found</p>
      </div>
    );
  }

  const leftPanel = (
    <div>
      {/* Model selector */}
      <div className="mb-4">
        <select
          value={selectedEndpointId}
          onChange={(e) => setSelectedEndpointId(e.target.value)}
          className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
        >
          <option value="">Select model endpoint</option>
          {endpoints.map((ep) => (
            <option key={ep.id} value={ep.id}>
              {ep.name} ({ep.model_name})
            </option>
          ))}
        </select>
      </div>

      {/* Instructions */}
      <CollapsibleSection title="Instructions" defaultOpen={true}>
        <textarea
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          placeholder="Write your prompt here to give your agent instructions."
          className="min-h-[120px] w-full rounded-md border border-gray-200 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
        />
      </CollapsibleSection>

      {/* Tools */}
      <CollapsibleSection
        title="Tools"
        defaultOpen={true}
        action={
          <button
            type="button"
            onClick={() => setShowCatalog(true)}
            className="rounded-md bg-[#7C3AED] px-3 py-1 text-xs font-medium text-white hover:bg-[#6D28D9]"
          >
            Add
          </button>
        }
      >
        {attachedTools.length === 0 ? (
          <p className="text-sm text-gray-500">
            No tools attached. Click Add to browse the catalog.
          </p>
        ) : (
          <div className="space-y-2">
            {attachedTools.map((tool) => (
              <div
                key={tool.id}
                className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2"
              >
                <span className="text-sm text-gray-900">{tool.name}</span>
                <div className="flex items-center gap-1">
                  <Info className="h-3.5 w-3.5 text-gray-400" />
                  <MoreVertical className="h-3.5 w-3.5 text-gray-400" />
                </div>
              </div>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* Knowledge */}
      <KnowledgeSection agentId={agentId} />

      {/* Memory */}
      <CollapsibleSection
        title="Memory"
        badge={<PreviewBadge />}
        defaultOpen={false}
      >
        <p className="text-sm text-gray-400">Coming in a future release</p>
      </CollapsibleSection>

      {/* Guardrails */}
      <CollapsibleSection
        title="Guardrails"
        badge={<PreviewBadge />}
        defaultOpen={false}
      >
        <p className="text-sm text-gray-400">Coming in a future release</p>
      </CollapsibleSection>
    </div>
  );

  const rightTabs = [
    { id: "chat" as const, label: "Chat" },
    { id: "yaml" as const, label: "YAML" },
    { id: "code" as const, label: "Code" },
  ];

  const rightPanel = (
    <div className="flex h-full flex-col">
      {/* Right tab bar */}
      <div className="flex border-b border-gray-200 bg-white px-4">
        {rightTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setRightTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium ${
              rightTab === tab.id
                ? "border-b-2 border-[#7C3AED] text-[#7C3AED]"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 p-6">
        {rightTab === "chat" && (
          <div className="flex h-full flex-col items-center justify-center">
            <p className="text-lg font-semibold text-gray-900">{agent.name}</p>
            <p className="mt-1 text-sm text-gray-500">
              Use agent configuration to update the description and starter
              prompts
            </p>
            <div className="mt-8 w-full max-w-lg">
              <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-3">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Message the agent..."
                  className="flex-1 text-sm outline-none"
                />
                <button
                  type="button"
                  className="rounded-md bg-[#7C3AED] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#6D28D9]"
                >
                  Send
                </button>
              </div>
              <p className="mt-2 text-center text-xs text-gray-400">
                AI-generated content may be incorrect
              </p>
            </div>
          </div>
        )}

        {rightTab === "yaml" && (
          <pre className="rounded-md bg-white p-4 text-xs text-gray-700 border border-gray-200 overflow-auto">
            {JSON.stringify(
              {
                name: agent.name,
                description: agent.description,
                system_prompt: systemPrompt,
                model_endpoint_id: selectedEndpointId || null,
                temperature: agent.temperature,
                max_tokens: agent.max_tokens,
              },
              null,
              2
            )}
          </pre>
        )}

        {rightTab === "code" && (
          <p className="text-sm text-gray-400">Code export coming soon</p>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex h-full flex-col">
      {error && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <AgentConfigTopBar
        agentName={agent.name}
        agentId={agentId}
        version={agent.current_config_version}
      />

      <div className="flex-1 overflow-hidden">
        <AgentConfigLayout
          agentId={agentId}
          agentName={agent.name}
          leftPanel={leftPanel}
          rightPanel={rightPanel}
        />
      </div>

      <ToolCatalogModal
        isOpen={showCatalog}
        onClose={() => setShowCatalog(false)}
        agentId={agentId}
        onToolAdded={loadAttachedTools}
      />
    </div>
  );
}
