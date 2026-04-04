"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch, getCurrentTenantId } from "@/lib/api";
import { getMsalInstance, getLoginScopes } from "@/lib/msal";
import { AgentConfigTopBar } from "@/components/agent/agent-config-top-bar";
import { AgentConfigLayout } from "@/components/agent/agent-config-layout";
import { AgentTracesPanel } from "@/components/agent/agent-traces-panel";
import { AgentMonitorPanel } from "@/components/agent/agent-monitor-panel";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { KnowledgeSection } from "@/components/knowledge/knowledge-section";
import { ToolCatalogModal } from "@/components/tools/tool-catalog-modal";
import { Info, MoreVertical, Send, Square, Loader2, Database, FileText, Trash2, Brain, Plus, MessageSquare, Clock, Puzzle, X, Shield, Paperclip, Smartphone, RefreshCw } from "lucide-react";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import { CodeExecutionBlock, type ToolCallEvent, type ToolResultEvent } from "@/components/chat/code-execution-block";
import { ChannelWizard, type ChannelWizardState, type WhatsAppGroupRule, type TelegramGroupRule } from "@/components/agent/channel-wizard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface ChatSource {
  type: string;
  index?: string;
  name?: string;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  attachment?: { name: string; size: number; previewUrl?: string };
  toolCalls?: ToolCallEvent[];
  toolResults?: ToolResultEvent[];
}

interface Agent {
  id: string;
  name: string;
  description: string | null;
  system_prompt: string | null;
  agent_type?: string;
  status: string;
  temperature: number;
  max_tokens: number | null;
  timeout_seconds: number;
  model_endpoint_id: string | null;
  current_config_version: number;
  whatsapp_status?: string | null;
  openclaw_config?: {
    channels?: {
      telegram_enabled?: boolean;
      telegram_bot_token_secret?: string;
      telegram_allowed_users?: string[];
      dm_policy?: string;
      telegram_channel_instructions?: string;
    };
    gmail?: {
      gmail_enabled?: boolean;
      gmail_email?: string;
      gmail_app_password_secret?: string;
      gmail_display_name?: string;
    };
    whatsapp?: {
      whatsapp_enabled?: boolean;
      whatsapp_dm_policy?: string;
      whatsapp_allowed_phones?: string[];
      whatsapp_group_policy?: string;
      whatsapp_group_rules?: WhatsAppGroupRule[];
      whatsapp_channel_instructions?: string;
    };
    telegram_group_rules?: TelegramGroupRule[];
    telegram_channel_instructions?: string;
    enable_web_browsing?: boolean;
    enable_shell?: boolean;
    enable_deep_research?: boolean;
  } | null;
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

interface AgentMemoryItem {
  id: string;
  agent_id: string;
  content: string;
  memory_type: string;
  source_thread_id: string | null;
  created_at: string;
}

interface AgentMCPTool {
  id: string;
  agent_id: string;
  mcp_tool_id: string;
  tool_name: string;
  description: string | null;
  server_id: string;
  server_name: string;
  is_available: boolean;
  created_at: string;
}

interface MCPDiscoveredToolItem {
  id: string;
  server_id: string;
  tool_name: string;
  description: string | null;
  is_available: boolean;
}

interface MCPDiscoveredToolListResponse {
  tools: MCPDiscoveredToolItem[];
  total: number;
}

interface AgentMemoryListResponse {
  memories: AgentMemoryItem[];
  total: number;
}

interface ThreadItem {
  id: string;
  title: string | null;
  agent_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview: string | null;
}

interface ThreadListResponse {
  threads: ThreadItem[];
  total: number;
}

interface ThreadMessageItem {
  id: string;
  role: string;
  content: string;
  message_metadata: Record<string, unknown> | null;
  sequence_number: number;
  created_at: string;
}

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [endpoints, setEndpoints] = useState<ModelEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [selectedEndpointId, setSelectedEndpointId] = useState("");
  const [showCatalog, setShowCatalog] = useState(false);
  const [activeTab, setActiveTab] = useState<"playground" | "traces" | "monitor" | "evaluation">("playground");
  const [attachedTools, setAttachedTools] = useState<Tool[]>([]);
  const [rightTab, setRightTab] = useState<"chat" | "yaml" | "code">("chat");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [pendingSources, setPendingSources] = useState<ChatSource[]>([]);
  const [isSaving, setIsSaving] = useState(false);
  const [chatThreadId, setChatThreadId] = useState<string | null>(null);
  const [memories, setMemories] = useState<AgentMemoryItem[]>([]);
  const [memoriesTotal, setMemoriesTotal] = useState(0);
  const [memoriesLoading, setMemoriesLoading] = useState(false);
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [attachedMCPTools, setAttachedMCPTools] = useState<AgentMCPTool[]>([]);
  const [showMCPPicker, setShowMCPPicker] = useState(false);
  const [availableMCPTools, setAvailableMCPTools] = useState<MCPDiscoveredToolItem[]>([]);
  const [mcpActionLoading, setMcpActionLoading] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const [chatFile, setChatFile] = useState<File | null>(null);
  const chatFileInputRef = useRef<HTMLInputElement | null>(null);
  const [whatsappQrUrl, setWhatsappQrUrl] = useState<string | null>(null);
  const [whatsappLinking, setWhatsappLinking] = useState(false);
  const [whatsappError, setWhatsappError] = useState<string | null>(null);
  const [whatsappLinkStatus, setWhatsappLinkStatus] = useState<string | null>(null);
  const whatsappPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Channel config editing state
  const [channelForm, setChannelForm] = useState({
    gmail_enabled: false,
    gmail_email: "",
    gmail_app_password: "",
    gmail_app_password_secret: "",
    gmail_display_name: "OpenClaw Agent",
    gmail_use_existing_secret: true,
    enable_web_browsing: true,
    enable_shell: false,
    enable_deep_research: false,
  });
  const [channels, setChannels] = useState<ChannelWizardState>({
    whatsapp_enabled: false,
    whatsapp_dm_policy: "allowlist",
    whatsapp_allowed_phones: "",
    whatsapp_group_policy: "allowlist",
    whatsapp_group_rules: [],
    whatsapp_channel_instructions: "",
    telegram_enabled: false,
    telegram_bot_token: "",
    telegram_bot_token_secret: "",
    telegram_use_existing_secret: true,
    telegram_allowed_users: "",
    dm_policy: "allowlist",
    telegram_group_rules: [],
    telegram_channel_instructions: "",
  });
  const [channelsDirty, setChannelsDirty] = useState(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  const handleChatSend = useCallback(async () => {
    const message = chatInput.trim();
    if (!message || !agent || isStreaming) return;

    const fileToSend = chatFile;
    setChatError(null);
    setChatInput("");
    setChatFile(null);
    setPendingSources([]);
    const userMsg: ChatMessage = {
      role: "user",
      content: message,
      ...(fileToSend ? {
        attachment: {
          name: fileToSend.name,
          size: fileToSend.size,
          ...(fileToSend.type.startsWith("image/") ? { previewUrl: URL.createObjectURL(fileToSend) } : {}),
        },
      } : {}),
    };
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
      const instance = getMsalInstance();
      const account = instance.getActiveAccount();
      let authHeaders: Record<string, string> = {};
      if (account) {
        try {
          const tokenResponse = await instance.acquireTokenSilent({ scopes: getLoginScopes(), account });
          authHeaders["Authorization"] = `Bearer ${tokenResponse.accessToken}`;
        } catch { /* will get 401 */ }
      }

      const tenantId = getCurrentTenantId();
      let response: Response;

      if (fileToSend) {
        // Use multipart upload endpoint
        const formData = new FormData();
        formData.append("message", message);
        formData.append("file", fileToSend);
        if (threadId) formData.append("thread_id", threadId);

        response = await fetch(
          `${API_BASE}/api/v1/agents/${agentId}/chat/upload`,
          {
            method: "POST",
            headers: {
              ...authHeaders,
              ...(tenantId ? { "X-Tenant-Id": tenantId } : {}),
            },
            body: formData,
            signal: controller.signal,
          }
        );
      } else {
        // Standard JSON chat
        const body: Record<string, unknown> = { message };
        if (threadId) {
          body.thread_id = threadId;
        } else {
          const history = chatMessages.map((m) => ({ role: m.role, content: m.content }));
          if (history.length > 0) body.conversation_history = history;
        }

        response = await fetch(
          `${API_BASE}/api/v1/agents/${agentId}/chat`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...authHeaders,
              ...(tenantId ? { "X-Tenant-Id": tenantId } : {}),
            },
            body: JSON.stringify(body),
            signal: controller.signal,
          }
        );
      }

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
            if (data.tool_call) {
              setChatMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === "assistant") {
                  const calls = [...(last.toolCalls || []), data.tool_call as ToolCallEvent];
                  updated[updated.length - 1] = { ...last, toolCalls: calls };
                }
                return updated;
              });
            }
            if (data.tool_result) {
              setChatMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last && last.role === "assistant") {
                  const results = [...(last.toolResults || []), data.tool_result as ToolResultEvent];
                  updated[updated.length - 1] = { ...last, toolResults: results };
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
      // Refresh memories and threads after chat completes
      loadMemories();
      loadThreads();
    }
  }, [agent, agentId, chatInput, chatFile, chatMessages, chatThreadId, isStreaming]);

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

      // Include channel config if dirty (OpenClaw agents)
      if (channelsDirty && agent.agent_type === "openclaw") {
        body.openclaw_config = {
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
            telegram_channel_instructions: channels.telegram_channel_instructions || "",
          },
          telegram_group_rules: channels.telegram_group_rules,
          gmail: channelForm.gmail_enabled
            ? {
                gmail_enabled: true,
                gmail_email: channelForm.gmail_email || null,
                gmail_app_password: channelForm.gmail_use_existing_secret
                  ? null
                  : channelForm.gmail_app_password || null,
                gmail_app_password_secret: channelForm.gmail_use_existing_secret
                  ? channelForm.gmail_app_password_secret || null
                  : null,
                gmail_display_name: channelForm.gmail_display_name || "OpenClaw Agent",
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
                whatsapp_channel_instructions: channels.whatsapp_channel_instructions || "",
              }
            : null,
          enable_web_browsing: channelForm.enable_web_browsing,
          enable_shell: channelForm.enable_shell,
          enable_deep_research: channelForm.enable_deep_research,
        };
      }

      if (Object.keys(body).length === 0) return;
      const updated = await apiFetch<Agent>(`/api/v1/agents/${agentId}`, {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setAgent(updated);
      setChannelsDirty(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setIsSaving(false);
    }
  }, [agent, agentId, isSaving, systemPrompt, selectedEndpointId, channelsDirty, channelForm]);

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
        // Initialize channel form from existing config
        if (agentData.agent_type === "openclaw" && agentData.openclaw_config) {
          const oc = agentData.openclaw_config;
          const ch = oc.channels || {};
          const gm = oc.gmail || {};
          const wa = oc.whatsapp || {};
          setChannelForm({
            gmail_enabled: !!gm.gmail_enabled,
            gmail_email: gm.gmail_email || "",
            gmail_app_password: "",
            gmail_app_password_secret: gm.gmail_app_password_secret || "",
            gmail_display_name: gm.gmail_display_name || "OpenClaw Agent",
            gmail_use_existing_secret: true,
            enable_web_browsing: oc.enable_web_browsing !== false,
            enable_shell: !!oc.enable_shell,
            enable_deep_research: !!oc.enable_deep_research,
          });
          setChannels({
            whatsapp_enabled: !!wa.whatsapp_enabled,
            whatsapp_dm_policy: (wa.whatsapp_dm_policy as ChannelWizardState["whatsapp_dm_policy"]) || "allowlist",
            whatsapp_allowed_phones: Array.isArray(wa.whatsapp_allowed_phones) ? wa.whatsapp_allowed_phones.join(", ") : "",
            whatsapp_group_policy: (wa.whatsapp_group_policy as ChannelWizardState["whatsapp_group_policy"]) || "allowlist",
            whatsapp_group_rules: wa.whatsapp_group_rules || [],
            whatsapp_channel_instructions: wa.whatsapp_channel_instructions || "",
            telegram_enabled: !!ch.telegram_enabled,
            telegram_bot_token: "",
            telegram_bot_token_secret: ch.telegram_bot_token_secret || "",
            telegram_use_existing_secret: true,
            telegram_allowed_users: Array.isArray(ch.telegram_allowed_users) ? ch.telegram_allowed_users.join(", ") : "",
            dm_policy: (ch.dm_policy as ChannelWizardState["dm_policy"]) || "allowlist",
            telegram_group_rules: oc.telegram_group_rules || [],
            telegram_channel_instructions: ch.telegram_channel_instructions || "",
          });
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [agentId]);

  // Poll every 5s while agent is provisioning
  useEffect(() => {
    if (agent?.status !== "provisioning") return;
    const interval = setInterval(async () => {
      try {
        const fresh = await apiFetch<Agent>(`/api/v1/agents/${agentId}`);
        setAgent((prev) => (prev ? { ...prev, status: fresh.status, whatsapp_status: fresh.whatsapp_status } : prev));
      } catch {
        // ignore
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [agent?.status, agentId]);

  // Poll WhatsApp status every 10s when WA is enabled but not connected
  useEffect(() => {
    if (agent?.agent_type !== "openclaw") return;
    if (!agent?.openclaw_config?.whatsapp?.whatsapp_enabled) return;
    if (agent?.whatsapp_status === "connected") return;
    const interval = setInterval(async () => {
      try {
        const fresh = await apiFetch<Agent>(`/api/v1/agents/${agentId}`);
        setAgent((prev) => (prev ? { ...prev, whatsapp_status: fresh.whatsapp_status } : prev));
      } catch {
        // ignore
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [agent?.agent_type, agent?.openclaw_config?.whatsapp?.whatsapp_enabled, agent?.whatsapp_status, agentId]);

  useEffect(() => {
    loadAttachedTools();
    loadMemories();
    loadThreads();
    loadAttachedMCPTools();
  }, [agentId]);

  async function loadAttachedMCPTools() {
    try {
      const mcpTools = await apiFetch<AgentMCPTool[]>(
        `/api/v1/agents/${agentId}/mcp-tools`
      );
      setAttachedMCPTools(mcpTools);
    } catch {
      // silently handle
    }
  }

  async function handleOpenMCPPicker() {
    setShowMCPPicker(true);
    try {
      const data = await apiFetch<MCPDiscoveredToolListResponse>("/api/v1/mcp/tools");
      setAvailableMCPTools(data.tools);
    } catch {
      setAvailableMCPTools([]);
    }
  }

  async function handleAttachMCPTool(mcpToolId: string) {
    setMcpActionLoading(mcpToolId);
    try {
      await apiFetch(`/api/v1/agents/${agentId}/mcp-tools`, {
        method: "POST",
        body: JSON.stringify({ mcp_tool_id: mcpToolId }),
      });
      await loadAttachedMCPTools();
      setShowMCPPicker(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to attach MCP tool");
    } finally {
      setMcpActionLoading(null);
    }
  }

  async function handleDetachMCPTool(mcpToolId: string) {
    setMcpActionLoading(mcpToolId);
    try {
      await apiFetch(`/api/v1/agents/${agentId}/mcp-tools/${mcpToolId}`, {
        method: "DELETE",
      });
      setAttachedMCPTools((prev) => prev.filter((t) => t.mcp_tool_id !== mcpToolId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to detach MCP tool");
    } finally {
      setMcpActionLoading(null);
    }
  }

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

  async function loadMemories() {
    setMemoriesLoading(true);
    try {
      const data = await apiFetch<AgentMemoryListResponse>(
        `/api/v1/agents/${agentId}/memories`
      );
      setMemories(data.memories);
      setMemoriesTotal(data.total);
    } catch {
      // silently handle
    } finally {
      setMemoriesLoading(false);
    }
  }

  async function deleteMemory(memoryId: string) {
    try {
      await apiFetch(`/api/v1/agents/${agentId}/memories/${memoryId}`, {
        method: "DELETE",
      });
      setMemories((prev) => prev.filter((m) => m.id !== memoryId));
      setMemoriesTotal((prev) => prev - 1);
    } catch {
      // silently handle
    }
  }

  async function clearAllMemories() {
    try {
      await apiFetch(`/api/v1/agents/${agentId}/memories`, {
        method: "DELETE",
      });
      setMemories([]);
      setMemoriesTotal(0);
    } catch {
      // silently handle
    }
  }

  async function deleteThread(threadId: string) {
    try {
      await apiFetch(`/api/v1/threads/${threadId}`, { method: "DELETE" });
      setThreads((prev) => prev.filter((t) => t.id !== threadId));
      if (chatThreadId === threadId) {
        startNewThread();
      }
    } catch {
      // silently handle
    }
  }

  async function clearAllThreads() {
    try {
      await apiFetch(`/api/v1/threads?agent_id=${agentId}`, { method: "DELETE" });
      setThreads([]);
      startNewThread();
    } catch {
      // silently handle
    }
  }

  async function loadThreads() {
    setThreadsLoading(true);
    try {
      const data = await apiFetch<ThreadListResponse>(
        `/api/v1/threads?agent_id=${agentId}`
      );
      setThreads(data.threads);
    } catch {
      // silently handle
    } finally {
      setThreadsLoading(false);
    }
  }

  async function switchToThread(threadId: string) {
    setChatThreadId(threadId);
    setChatMessages([]);
    setChatError(null);
    try {
      const data = await apiFetch<{ messages: ThreadMessageItem[]; total: number }>(
        `/api/v1/threads/${threadId}/messages`
      );
      if (data.messages && data.messages.length > 0) {
        const msgs: ChatMessage[] = data.messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
          sources: m.message_metadata?.sources as ChatSource[] | undefined,
        }));
        setChatMessages(msgs);
      }
    } catch (err) {
      setChatError(err instanceof Error ? err.message : "Failed to load thread messages");
    }
  }

  function startNewThread() {
    setChatThreadId(null);
    setChatMessages([]);
    setChatError(null);
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

      {/* Tools (Platform + MCP) */}
      <CollapsibleSection
        title="Tools"
        defaultOpen={true}
        action={
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setShowCatalog(true)}
              className="rounded-md bg-[#7C3AED] px-3 py-1 text-xs font-medium text-white hover:bg-[#6D28D9]"
            >
              Add
            </button>
            <button
              type="button"
              onClick={handleOpenMCPPicker}
              className="rounded-md border border-[#7C3AED] px-3 py-1 text-xs font-medium text-[#7C3AED] hover:bg-[#F5F3FF]"
            >
              Add MCP
            </button>
          </div>
        }
      >
        {showMCPPicker && (
          <div className="mb-3 rounded-md border border-gray-200 bg-gray-50 p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-700">Select an MCP tool</span>
              <button type="button" onClick={() => setShowMCPPicker(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            {availableMCPTools.length === 0 ? (
              <p className="text-xs text-gray-400">No MCP tools available</p>
            ) : (
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {availableMCPTools
                  .filter((t) => !attachedMCPTools.some((a) => a.mcp_tool_id === t.id))
                  .map((tool) => (
                    <div key={tool.id} className="flex items-center justify-between rounded-md border border-gray-200 bg-white px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-gray-900 truncate">{tool.tool_name}</p>
                      </div>
                      <button
                        type="button"
                        disabled={mcpActionLoading === tool.id}
                        onClick={() => handleAttachMCPTool(tool.id)}
                        className="ml-2 rounded-md bg-[#7C3AED] px-2 py-1 text-xs font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
                      >
                        {mcpActionLoading === tool.id ? "..." : "Attach"}
                      </button>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}
        {attachedTools.length === 0 && attachedMCPTools.length === 0 ? (
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
                <div className="flex items-center gap-2 min-w-0">
                  <span className="inline-flex items-center rounded-full bg-blue-100 text-blue-700 px-1.5 py-0.5 text-[10px] font-semibold">TOOL</span>
                  <span className="text-sm text-gray-900">{tool.name}</span>
                </div>
                <div className="flex items-center gap-1">
                  <Info className="h-3.5 w-3.5 text-gray-400" />
                  <MoreVertical className="h-3.5 w-3.5 text-gray-400" />
                </div>
              </div>
            ))}
            {attachedMCPTools.map((tool) => (
              <div
                key={tool.id}
                className="flex items-center justify-between rounded-md border border-gray-200 px-3 py-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="inline-flex items-center rounded-full bg-purple-100 text-purple-700 px-1.5 py-0.5 text-[10px] font-semibold">MCP</span>
                  <Puzzle className="h-3.5 w-3.5 shrink-0 text-[#7C3AED]" />
                  <div className="min-w-0">
                    <span className="text-sm text-gray-900 truncate block">{tool.tool_name}</span>
                    <span className="text-xs text-gray-400">{tool.server_name}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`inline-block h-2 w-2 rounded-full ${tool.is_available ? "bg-green-400" : "bg-gray-300"}`} />
                  <button
                    type="button"
                    onClick={() => handleDetachMCPTool(tool.mcp_tool_id)}
                    disabled={mcpActionLoading === tool.mcp_tool_id}
                    className="rounded p-1 text-gray-400 hover:text-red-500 hover:bg-red-50"
                    title="Remove MCP tool"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* Knowledge */}
      <KnowledgeSection agentId={agentId} />

      {/* Channels (OpenClaw agents) */}
      {agent.agent_type === "openclaw" && (
        <CollapsibleSection title="Channels" defaultOpen={false}>
          <div className="space-y-4">
            {/* Capabilities */}
            <div className="space-y-2">
              <label className="block text-xs font-medium text-gray-500 uppercase tracking-wide">Capabilities</label>
              <div className="flex flex-wrap gap-3">
                <label className="flex items-center gap-1.5 text-xs text-gray-700">
                  <input type="checkbox" checked={channelForm.enable_web_browsing}
                    onChange={(e) => { setChannelForm({ ...channelForm, enable_web_browsing: e.target.checked }); setChannelsDirty(true); }}
                    className="rounded border-gray-300 text-[#7C3AED] focus:ring-[#7C3AED]" />
                  Web Browsing
                </label>
                <label className="flex items-center gap-1.5 text-xs text-gray-700">
                  <input type="checkbox" checked={channelForm.enable_shell}
                    onChange={(e) => { setChannelForm({ ...channelForm, enable_shell: e.target.checked }); setChannelsDirty(true); }}
                    className="rounded border-gray-300 text-[#7C3AED] focus:ring-[#7C3AED]" />
                  Shell
                </label>
                <label className="flex items-center gap-1.5 text-xs text-gray-700">
                  <input type="checkbox" checked={channelForm.enable_deep_research}
                    onChange={(e) => { setChannelForm({ ...channelForm, enable_deep_research: e.target.checked }); setChannelsDirty(true); }}
                    className="rounded border-gray-300 text-[#7C3AED] focus:ring-[#7C3AED]" />
                  Deep Research
                </label>
              </div>
            </div>

            {/* WhatsApp + Telegram via Channel Wizard */}
            <div className="border-t border-gray-100 pt-3">
              <ChannelWizard
                state={channels}
                onChange={(s) => { setChannels(s); setChannelsDirty(true); }}
                agentId={agentId}
              />
            </div>

            {/* Gmail */}
            <div className="space-y-2 border-t border-gray-100 pt-3">
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <input type="checkbox" checked={channelForm.gmail_enabled}
                  onChange={(e) => { setChannelForm({ ...channelForm, gmail_enabled: e.target.checked }); setChannelsDirty(true); }}
                  className="rounded border-gray-300 text-[#7C3AED] focus:ring-[#7C3AED]" />
                Gmail
              </label>
              {channelForm.gmail_enabled && (
                <div className="ml-5 space-y-2">
                  <input type="email" placeholder="agent@gmail.com" value={channelForm.gmail_email}
                    onChange={(e) => { setChannelForm({ ...channelForm, gmail_email: e.target.value }); setChannelsDirty(true); }}
                    className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs" />
                  <input type="text" placeholder="Display name" value={channelForm.gmail_display_name}
                    onChange={(e) => { setChannelForm({ ...channelForm, gmail_display_name: e.target.value }); setChannelsDirty(true); }}
                    className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs" />
                  <div className="flex gap-3">
                    <label className={`flex-1 cursor-pointer rounded-md border p-2 text-xs ${channelForm.gmail_use_existing_secret ? "border-[#7C3AED] bg-purple-50 ring-1 ring-[#7C3AED]" : "border-gray-200"}`}>
                      <input type="radio" className="sr-only" checked={channelForm.gmail_use_existing_secret}
                        onChange={() => { setChannelForm({ ...channelForm, gmail_use_existing_secret: true }); setChannelsDirty(true); }} />
                      <span className="font-medium">Existing KV Secret</span>
                    </label>
                    <label className={`flex-1 cursor-pointer rounded-md border p-2 text-xs ${!channelForm.gmail_use_existing_secret ? "border-[#7C3AED] bg-purple-50 ring-1 ring-[#7C3AED]" : "border-gray-200"}`}>
                      <input type="radio" className="sr-only" checked={!channelForm.gmail_use_existing_secret}
                        onChange={() => { setChannelForm({ ...channelForm, gmail_use_existing_secret: false }); setChannelsDirty(true); }} />
                      <span className="font-medium">Enter Password</span>
                    </label>
                  </div>
                  {channelForm.gmail_use_existing_secret ? (
                    <input type="text" placeholder="gmail-app-password" value={channelForm.gmail_app_password_secret}
                      onChange={(e) => { setChannelForm({ ...channelForm, gmail_app_password_secret: e.target.value }); setChannelsDirty(true); }}
                      className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs" />
                  ) : (
                    <input type="password" placeholder="xxxx xxxx xxxx xxxx" value={channelForm.gmail_app_password}
                      onChange={(e) => { setChannelForm({ ...channelForm, gmail_app_password: e.target.value }); setChannelsDirty(true); }}
                      className="w-full rounded-md border border-gray-200 px-2 py-1.5 text-xs" />
                  )}
                </div>
              )}
            </div>

            {channelsDirty && (
              <p className="text-xs text-amber-600 font-medium">
                Unsaved changes — click Save to deploy updated config
              </p>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Memory */}
      <CollapsibleSection
        title="Memory"
        defaultOpen={false}
        action={
          memories.length > 0 ? (
            <button
              type="button"
              onClick={clearAllMemories}
              className="rounded-md border border-red-200 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
            >
              Clear all
            </button>
          ) : undefined
        }
      >
        {memoriesLoading ? (
          <div className="flex items-center gap-2 py-2">
            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
            <span className="text-sm text-gray-400">Loading...</span>
          </div>
        ) : memoriesTotal === 0 ? (
          <div className="flex items-center gap-2 py-2">
            <Brain className="h-4 w-4 text-gray-300" />
            <p className="text-sm text-gray-400">No memories stored yet</p>
          </div>
        ) : (
          <div className="flex items-center gap-2 py-2">
            <Brain className="h-4 w-4 text-[#7C3AED]" />
            <span className="text-sm text-gray-700">{memoriesTotal} memories stored</span>
            <span className="rounded-full bg-[#7C3AED] px-2 py-0.5 text-[10px] font-medium text-white">
              Active
            </span>
          </div>
        )}
        <p className="text-xs text-gray-400 mt-1">
          Agent recalls relevant memories automatically during conversations
        </p>
      </CollapsibleSection>

      {/* Threads / Conversation History */}
      <CollapsibleSection
        title="Conversations"
        defaultOpen={true}
        action={
          threads.length > 0 ? (
            <button
              type="button"
              onClick={clearAllThreads}
              className="rounded-md border border-red-200 px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
            >
              Clear all
            </button>
          ) : undefined
        }
      >
        <button
          type="button"
          onClick={startNewThread}
          className="flex w-full items-center gap-2 rounded-md bg-[#7C3AED] px-3 py-2 text-xs font-medium text-white hover:bg-[#6D28D9] mb-2"
        >
          <Plus className="h-3.5 w-3.5" />
          New chat
        </button>
        {threadsLoading ? (
          <div className="flex items-center justify-center py-3">
            <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
          </div>
        ) : threads.length === 0 ? (
          <p className="text-sm text-gray-400 py-2">No conversations yet</p>
        ) : (
          <div className="space-y-1">
            {threads.map((thread) => (
              <div
                key={thread.id}
                className={`group flex items-center gap-2 rounded-md px-2 py-2 cursor-pointer hover:bg-gray-100 ${
                  chatThreadId === thread.id ? "bg-gray-100 ring-1 ring-[#7C3AED]/30" : ""
                }`}
                onClick={() => switchToThread(thread.id)}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0 text-gray-400" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-gray-700 truncate">
                    {thread.title || "Untitled"}
                  </p>
                  <p className="text-[10px] text-gray-400">
                    {new Date(thread.updated_at).toLocaleDateString()} &middot; {thread.message_count} msgs
                  </p>
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); deleteThread(thread.id); }}
                  className="opacity-0 group-hover:opacity-100 rounded p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 transition-opacity"
                  title="Delete conversation"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* Guardrails */}
      <CollapsibleSection
        title="Guardrails"
        defaultOpen={false}
      >
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium text-gray-700">Content Safety</span>
            </div>
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Active</span>
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium text-gray-700">PII Detection</span>
            </div>
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Active</span>
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium text-gray-700">Prompt Injection Shield</span>
            </div>
            <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">Active</span>
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-amber-500" />
              <span className="text-sm font-medium text-gray-700">Grounding Enforcement</span>
            </div>
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">Disabled</span>
          </div>
          <a href="/dashboard/guardrails" className="block text-xs text-[#7C3AED] hover:text-[#6D28D9] font-medium mt-1">
            Manage all guardrails &rarr;
          </a>
        </div>
      </CollapsibleSection>

      {/* WhatsApp Linking (OpenClaw agents with WhatsApp enabled) */}
      {agent.agent_type === "openclaw" && agent.openclaw_config?.whatsapp?.whatsapp_enabled && (
        <CollapsibleSection title="WhatsApp" defaultOpen={true}>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Smartphone className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium text-gray-700">
                {agent.whatsapp_status === "connected"
                  ? "Connected"
                  : agent.whatsapp_status === "pending_link"
                  ? "Pending Link"
                  : "Not Linked"}
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${
                  agent.whatsapp_status === "connected"
                    ? "bg-green-100 text-green-700"
                    : "bg-amber-100 text-amber-700"
                }`}
              >
                {agent.whatsapp_status === "connected" ? "Active" : "Setup Required"}
              </span>
            </div>

            {/* Re-link button when connected */}
            {agent.whatsapp_status === "connected" && !whatsappQrUrl && (
              <button
                type="button"
                disabled={whatsappLinking}
                onClick={async () => {
                  setWhatsappLinking(true);
                  setWhatsappError(null);
                  setWhatsappLinkStatus(null);
                  if (whatsappPollRef.current) {
                    clearInterval(whatsappPollRef.current);
                    whatsappPollRef.current = null;
                  }
                  try {
                    // First logout to clear stale credentials
                    await apiFetch(`/api/v1/agents/${agentId}/whatsapp/logout`, {
                      method: "POST",
                    });
                    // Then request a fresh QR code
                    const data = await apiFetch<{ qr_data: string }>(
                      `/api/v1/agents/${agentId}/whatsapp/link`
                    );
                    setWhatsappQrUrl(data.qr_data);
                    setWhatsappLinkStatus("linking");
                    const poll = setInterval(async () => {
                      try {
                        const status = await apiFetch<{ status: string; error?: string }>(
                          `/api/v1/agents/${agentId}/whatsapp/link-status`
                        );
                        if (status.status === "connected") {
                          clearInterval(poll);
                          whatsappPollRef.current = null;
                          setWhatsappLinkStatus("connected");
                          setWhatsappQrUrl(null);
                        } else if (status.status === "failed") {
                          clearInterval(poll);
                          whatsappPollRef.current = null;
                          setWhatsappLinkStatus("failed");
                          setWhatsappError(status.error || "Linking failed");
                        }
                      } catch {
                        // Polling error — ignore, will retry
                      }
                    }, 3000);
                    whatsappPollRef.current = poll;
                    setTimeout(() => {
                      if (whatsappPollRef.current === poll) {
                        clearInterval(poll);
                        whatsappPollRef.current = null;
                      }
                    }, 150000);
                  } catch (err: unknown) {
                    setWhatsappError(
                      err instanceof Error ? err.message : "Failed to re-link"
                    );
                  } finally {
                    setWhatsappLinking(false);
                  }
                }}
                className="w-full rounded-md bg-amber-600 px-3 py-2 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {whatsappLinking ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Disconnecting &amp; Getting QR...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-3.5 w-3.5" />
                    Re-link WhatsApp
                  </>
                )}
              </button>
            )}

            {/* QR code display (shown during both initial link and re-link) */}
            {whatsappQrUrl && (
              <div className="rounded-md border border-gray-200 bg-white p-4 flex flex-col items-center gap-2">
                <img
                  src={whatsappQrUrl}
                  alt="WhatsApp QR Code"
                  className="w-48 h-48"
                />
                <p className="text-xs text-gray-400 text-center">
                  Open WhatsApp → Settings → Linked Devices → Link a Device
                </p>
                {whatsappLinkStatus === "linking" && (
                  <div className="flex items-center gap-1.5 text-xs text-amber-600">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Waiting for you to scan...
                  </div>
                )}
              </div>
            )}

            {whatsappLinkStatus === "connected" && (
              <div className="rounded-md border border-green-200 bg-green-50 p-3 text-center">
                <p className="text-sm font-medium text-green-700">WhatsApp linked successfully!</p>
                <p className="text-xs text-green-600 mt-1">Reload the page to see updated status.</p>
              </div>
            )}

            {whatsappError && (
              <p className="text-xs text-red-600">{whatsappError}</p>
            )}

            {agent.whatsapp_status !== "connected" && !whatsappQrUrl && (
              <>
                <p className="text-xs text-gray-500">
                  Scan the QR code with WhatsApp on your phone to link this agent.
                </p>
                <button
                  type="button"
                  disabled={whatsappLinking}
                  onClick={async () => {
                    setWhatsappLinking(true);
                    setWhatsappError(null);
                    setWhatsappLinkStatus(null);
                    // Clear any existing poll
                    if (whatsappPollRef.current) {
                      clearInterval(whatsappPollRef.current);
                      whatsappPollRef.current = null;
                    }
                    try {
                      const data = await apiFetch<{ qr_data: string }>(
                        `/api/v1/agents/${agentId}/whatsapp/link`
                      );
                      setWhatsappQrUrl(data.qr_data);
                      setWhatsappLinkStatus("linking");
                      // Poll for link completion every 3 seconds
                      const poll = setInterval(async () => {
                        try {
                          const status = await apiFetch<{ status: string; error?: string }>(
                            `/api/v1/agents/${agentId}/whatsapp/link-status`
                          );
                          if (status.status === "connected") {
                            clearInterval(poll);
                            whatsappPollRef.current = null;
                            setWhatsappLinkStatus("connected");
                            setWhatsappQrUrl(null);
                          } else if (status.status === "failed") {
                            clearInterval(poll);
                            whatsappPollRef.current = null;
                            setWhatsappLinkStatus("failed");
                            setWhatsappError(status.error || "Linking failed");
                          }
                        } catch {
                          // Polling error — ignore, will retry
                        }
                      }, 3000);
                      whatsappPollRef.current = poll;
                      // Auto-stop polling after 2.5 minutes
                      setTimeout(() => {
                        if (whatsappPollRef.current === poll) {
                          clearInterval(poll);
                          whatsappPollRef.current = null;
                        }
                      }, 150000);
                    } catch (err: unknown) {
                      setWhatsappError(
                        err instanceof Error ? err.message : "Failed to get QR code"
                      );
                    } finally {
                      setWhatsappLinking(false);
                    }
                  }}
                  className="w-full rounded-md bg-green-600 px-3 py-2 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {whatsappLinking ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Getting QR Code...
                    </>
                  ) : (
                    <>
                      <Smartphone className="h-3.5 w-3.5" />
                      Link WhatsApp
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </CollapsibleSection>
      )}
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

      <div className="flex-1 flex">
        {rightTab === "chat" && (
          <>
            {/* Chat area */}
            <div className="flex-1 flex flex-col p-6">
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
                      className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                        msg.role === "user"
                          ? "bg-[#7C3AED] text-white whitespace-pre-wrap"
                          : "bg-gray-100 text-gray-900"
                      }`}
                    >
                      {msg.role === "user" && msg.attachment && (
                        <div className="mb-1.5 flex items-center gap-1.5 rounded bg-white/20 px-2 py-1 text-xs">
                          {msg.attachment.previewUrl ? (
                            <img src={msg.attachment.previewUrl} alt={msg.attachment.name} className="h-8 w-8 rounded object-cover" />
                          ) : (
                            <Paperclip className="h-3 w-3" />
                          )}
                          <span className="truncate max-w-[140px]">{msg.attachment.name}</span>
                          <span className="opacity-70">({(msg.attachment.size / 1024).toFixed(0)} KB)</span>
                        </div>
                      )}
                      {/* Tool execution blocks (ChatGPT-style) */}
                      {msg.role === "assistant" && msg.toolCalls && msg.toolCalls.length > 0 && (
                        <div className="mb-2">
                          {msg.toolCalls.map((tc, ti) => (
                            <CodeExecutionBlock
                              key={ti}
                              toolCall={tc}
                              toolResult={msg.toolResults?.[ti]}
                            />
                          ))}
                        </div>
                      )}
                      {msg.role === "assistant" && msg.content ? (
                        <MarkdownRenderer content={msg.content} />
                      ) : msg.role === "user" ? (
                        msg.content
                      ) : (
                        isStreaming && i === chatMessages.length - 1 && !msg.toolCalls?.length ? (
                          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
                        ) : null
                      )}
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
              {chatFile && (
                <div className="mb-2 flex items-center gap-2 rounded-md bg-purple-50 border border-purple-200 px-3 py-1.5 text-sm text-purple-800 w-fit">
                  {chatFile.type.startsWith("image/") ? (
                    <img src={URL.createObjectURL(chatFile)} alt={chatFile.name} className="h-10 w-10 rounded object-cover" />
                  ) : (
                    <Paperclip className="h-3.5 w-3.5" />
                  )}
                  <span className="truncate max-w-[160px] text-xs">{chatFile.name}</span>
                  <button onClick={() => setChatFile(null)} className="text-purple-400 hover:text-purple-600">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
              <div className="flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-3">
                <input
                  ref={chatFileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md,.docx,.png,.jpg,.jpeg,.gif,.webp"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      const ext = f.name.split(".").pop()?.toLowerCase();
                      const allowed = ["pdf","txt","md","docx","png","jpg","jpeg","gif","webp"];
                      if (!ext || !allowed.includes(ext)) { alert("Unsupported file type."); return; }
                      if (f.size > 10 * 1024 * 1024) { alert("File too large (max 10 MB)."); return; }
                      setChatFile(f);
                    }
                    if (chatFileInputRef.current) chatFileInputRef.current.value = "";
                  }}
                  className="hidden"
                />
                <button
                  type="button"
                  onClick={() => chatFileInputRef.current?.click()}
                  disabled={isStreaming}
                  title="Attach file"
                  className="text-gray-400 hover:text-gray-600 disabled:opacity-40"
                >
                  <Paperclip className="h-4 w-4" />
                </button>
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChatSend(); } }}
                  placeholder={chatFile ? "Ask about the file..." : "Message the agent..."}
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
          </>
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
        activeTab={activeTab}
        onTabChange={(tab) => setActiveTab(tab as "playground" | "traces" | "monitor" | "evaluation")}
        onSave={handleSave}
        isSaving={isSaving}
        onDelete={async () => {
          if (!confirm(`Delete agent "${agent.name}"? This cannot be undone.`)) return;
          try {
            await apiFetch(`/api/v1/agents/${agentId}`, { method: "DELETE" });
            router.push("/dashboard/agents");
          } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Failed to delete agent");
          }
        }}
      />

      <div className="flex-1 overflow-hidden">
        {activeTab === "playground" && (
          <AgentConfigLayout
            agentId={agentId}
            agentName={agent.name}
            leftPanel={leftPanel}
            rightPanel={rightPanel}
          />
        )}
        {activeTab === "traces" && (
          <div className="h-full overflow-auto p-6">
            <AgentTracesPanel agentId={agentId} />
          </div>
        )}
        {activeTab === "monitor" && (
          <div className="h-full overflow-auto p-6">
            <AgentMonitorPanel agentId={agentId} />
          </div>
        )}
        {activeTab === "evaluation" && (
          <div className="h-full overflow-auto p-6">
            <div className="text-gray-500 text-center py-12">Evaluation tab — coming soon</div>
          </div>
        )}
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
