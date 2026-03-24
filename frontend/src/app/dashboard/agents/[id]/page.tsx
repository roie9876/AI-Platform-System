"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { AgentConfigTopBar } from "@/components/agent/agent-config-top-bar";
import { AgentConfigLayout } from "@/components/agent/agent-config-layout";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { KnowledgeSection } from "@/components/knowledge/knowledge-section";
import { ToolCatalogModal } from "@/components/tools/tool-catalog-modal";
import { Info, MoreVertical, Send, Square, Loader2, Database, FileText } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChatSource {
  type: string;
  index?: string;
  name?: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
}

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
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [pendingSources, setPendingSources] = useState<ChatSource[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [chatThreadId, setChatThreadId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleChatSend = useCallback(async () => {
    const message = chatInput.trim();
    if (!message || !agent || isStreaming) return;

    setChatError(null);
    setChatInput("");
    setPendingSources([]);
    const userMsg: ChatMessage = { role: "user", content: message };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatMessages((prev) => [...prev, { role: "assistant", content: "" }]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    // Auto-create thread if none
    let threadId = chatThreadId;
    if (!threadId) {
      try {
        const thread = await apiFetch<{ id: string }>("/api/v1/threads", {
          method: "POST",
          body: JSON.stringify({ agent_id: agentId }),
        });
        threadId = thread.id;
        setChatThreadId(thread.id);
      } catch {
        // Fall back to stateless
      }
    }

    try {
      const body: Record<string, unknown> = { message };
      if (threadId) {
        body.thread_id = threadId;
      } else {
        const history = chatMessages.map((m) => ({ role: m.role, content: m.content }));
        if (history.length > 0) body.conversation_history = history;
      }

      const response = await fetch(
        `${API_BASE}/api/v1/agents/${agentId}/chat`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        }
      );

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;
          try {
            const data = JSON.parse(jsonStr);
            if (data.error) { setChatError(data.error); break; }
            if (data.sources) {
              setPendingSources(data.sources);
              // Attach sources to the current assistant message
              setChatMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === "assistant") {
                  updated[updated.length - 1] = { ...last, sources: data.sources };
                }
                return updated;
              });
            }
            if (data.content) {
              setChatMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === "assistant") {
                  updated[updated.length - 1] = { ...last, content: last.content + data.content };
                }
                return updated;
              });
            }
            if (data.done) break;
          } catch { /* skip malformed */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        setChatError(err.message);
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [agent, agentId, chatInput, chatMessages, chatThreadId, isStreaming]);

  const handleSave = useCallback(async () => {
    if (!agent || isSaving) return;
    setIsSaving(true);
    try {
      const body: Record<string, unknown> = {};
      if (systemPrompt !== (agent.system_prompt || "")) {
        body.system_prompt = systemPrompt;
      }
      if (selectedEndpointId !== (agent.model_endpoint_id || "")) {
        body.model_endpoint_id = selectedEndpointId || null;
      }
      if (Object.keys(body).length === 0) return;
      const updated = await apiFetch<Agent>(`/api/v1/agents/${agentId}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setAgent(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setIsSaving(false);
    }
  }, [agent, agentId, isSaving, systemPrompt, selectedEndpointId]);

  const handleChatStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

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
        defaultOpen={false}
      >
        <p className="text-sm text-gray-400">Coming in a future release</p>
      </CollapsibleSection>

      {/* Guardrails */}
      <CollapsibleSection
        title="Guardrails"
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
          <div className="flex h-full flex-col">
            {chatMessages.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center">
                <p className="text-lg font-semibold text-gray-900">{agent.name}</p>
                <p className="mt-1 text-sm text-gray-500">
                  Use agent configuration to update the description and starter prompts
                </p>
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto space-y-4 pb-4">
                {chatMessages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg px-4 py-2 text-sm whitespace-pre-wrap ${
                        msg.role === "user"
                          ? "bg-[#7C3AED] text-white"
                          : "bg-gray-100 text-gray-900"
                      }`}
                    >
                      {msg.content || (isStreaming && i === chatMessages.length - 1 ? (
                        <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                      ) : null)}
                    </div>
                    {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {msg.sources.map((src, si) => (
                          <span
                            key={si}
                            className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2 py-0.5 text-[10px] font-medium text-purple-700"
                          >
                            {src.type === "azure_search" ? (
                              <><Database className="h-2.5 w-2.5" />{src.index}</>
                            ) : (
                              <><FileText className="h-2.5 w-2.5" />{src.name}</>
                            )}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}

            {chatError && (
              <div className="mx-4 mb-2 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">
                {chatError}
              </div>
            )}

            <div className="border-t border-gray-200 px-4 py-3">
              <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-3">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChatSend(); } }}
                  placeholder="Message the agent..."
                  className="flex-1 text-sm outline-none"
                  disabled={isStreaming}
                />
                {isStreaming ? (
                  <button
                    type="button"
                    onClick={handleChatStop}
                    className="rounded-md bg-red-500 p-1.5 text-white hover:bg-red-600"
                  >
                    <Square className="h-3 w-3" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleChatSend}
                    disabled={!chatInput.trim()}
                    className="rounded-md bg-[#7C3AED] p-1.5 text-white hover:bg-[#6D28D9] disabled:opacity-40"
                  >
                    <Send className="h-3 w-3" />
                  </button>
                )}
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
        onSave={handleSave}
        isSaving={isSaving}
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
