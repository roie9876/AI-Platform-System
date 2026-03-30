"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { getCurrentTenantId } from "@/lib/api";
import { getMsalInstance, getLoginScopes } from "@/lib/msal";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import { ChatMessages } from "@/components/chat/chat-messages";
import { ChatInput } from "@/components/chat/chat-input";
import { ConfigPanel } from "@/components/chat/config-panel";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Agent {
  id: string;
  name: string;
  status: string;
  system_prompt: string | null;
  temperature: number;
  max_tokens: number;
  timeout_seconds: number;
  model_endpoint_id: string | null;
  current_config_version: number;
}

interface ThreadMessage {
  id: string;
  thread_id: string;
  role: string;
  content: string;
  message_metadata: Record<string, unknown> | null;
  sequence_number: number;
  created_at: string;
}

interface ThreadMessagesResponse {
  messages: ThreadMessage[];
  total: number;
}

interface ThreadResponse {
  id: string;
  title: string | null;
  agent_id: string;
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  sources?: Array<{ type: string; index?: string; name?: string }>;
  attachment?: { name: string; size: number };
}

export default function ChatPage() {
  const params = useParams();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  const lastUserMessageRef = useRef<string>("");

  useEffect(() => {
    apiFetch<Agent>(`/api/v1/agents/${agentId}`)
      .then(setAgent)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [agentId]);

  const handleSend = useCallback(
    async (userMessage: string, file?: File) => {
      if (!agent) return;

      setError(null);
      lastUserMessageRef.current = userMessage;

      // Auto-create thread if none exists
      let threadId = activeThreadId;
      if (!threadId) {
        try {
          const thread = await apiFetch<ThreadResponse>("/api/v1/threads", {
            method: "POST",
            body: JSON.stringify({ agent_id: agentId }),
          });
          threadId = thread.id;
          setActiveThreadId(thread.id);
        } catch {
          // Fall back to stateless mode
        }
      }

      const userMsg: Message = {
        role: "user",
        content: userMessage,
        ...(file ? { attachment: { name: file.name, size: file.size } } : {}),
      };
      setMessages((prev) => [...prev, userMsg]);

      const assistantMsg: Message = { role: "assistant", content: "" };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

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

        if (file) {
          // Use multipart/form-data upload endpoint
          const formData = new FormData();
          formData.append("message", userMessage);
          formData.append("file", file);
          if (threadId) {
            formData.append("thread_id", threadId);
          }

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
          // Standard JSON chat endpoint
          const body: Record<string, unknown> = { message: userMessage };
          if (threadId) {
            body.thread_id = threadId;
          } else {
            const history = messages.map((m) => ({
              role: m.role,
              content: m.content,
            }));
            if (history.length > 0) {
              body.conversation_history = history;
            }
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
          const err = await response
            .json()
            .catch(() => ({ detail: `HTTP ${response.status}` }));
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

              if (data.error) {
                setError(data.error);
                break;
              }

              if (data.sources) {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last && last.role === "assistant") {
                    updated[updated.length - 1] = {
                      ...last,
                      sources: data.sources,
                    };
                  }
                  return updated;
                });
              }

              if (data.content) {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last && last.role === "assistant") {
                    updated[updated.length - 1] = {
                      ...last,
                      content: last.content + data.content,
                    };
                  }
                  return updated;
                });
              }

              if (data.done) break;
            } catch {
              // skip malformed JSON
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          // User stopped streaming
        } else {
          setError(
            err instanceof Error ? err.message : "Failed to send message"
          );
        }
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
        // Refresh sidebar to update thread title/preview
        setSidebarRefreshKey((k) => k + 1);
      }
    },
    [agent, agentId, messages, activeThreadId]
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handleNewChat = useCallback(async () => {
    try {
      const thread = await apiFetch<ThreadResponse>("/api/v1/threads", {
        method: "POST",
        body: JSON.stringify({ agent_id: agentId }),
      });
      setActiveThreadId(thread.id);
      setMessages([]);
      setError(null);
      setSidebarRefreshKey((k) => k + 1);
    } catch {
      // Fallback to just clearing state
      setActiveThreadId(null);
      setMessages([]);
      setError(null);
    }
  }, [agentId]);

  const handleSelectThread = useCallback(
    async (threadId: string) => {
      setActiveThreadId(threadId);
      setError(null);
      try {
        const data = await apiFetch<ThreadMessagesResponse>(
          `/api/v1/threads/${threadId}/messages`
        );
        setMessages(
          data.messages.map((m) => {
            const msg: Message = { role: m.role as Message["role"], content: m.content };
            if (m.message_metadata && typeof m.message_metadata === "object") {
              const meta = m.message_metadata as Record<string, unknown>;
              if (Array.isArray(meta.sources)) {
                msg.sources = meta.sources as Message["sources"];
              }
            }
            return msg;
          })
        );
      } catch {
        setMessages([]);
      }
    },
    []
  );

  const handleDeleteThread = useCallback(
    async (threadId: string) => {
      try {
        await apiFetch(`/api/v1/threads/${threadId}`, { method: "DELETE" });
        if (threadId === activeThreadId) {
          setActiveThreadId(null);
          setMessages([]);
        }
        setSidebarRefreshKey((k) => k + 1);
      } catch {
        // silently handle
      }
    },
    [activeThreadId]
  );

  const handleRetry = useCallback(() => {
    if (lastUserMessageRef.current) {
      setMessages((prev) => prev.slice(0, -2));
      setError(null);
      handleSend(lastUserMessageRef.current);
    }
  }, [handleSend]);

  const handleConfigUpdate = useCallback(
    (config: {
      system_prompt: string;
      temperature: number;
      max_tokens: number;
      timeout_seconds: number;
      model_endpoint_id: string | null;
      current_config_version: number;
    }) => {
      setAgent((prev) =>
        prev
          ? {
              ...prev,
              system_prompt: config.system_prompt,
              temperature: config.temperature,
              max_tokens: config.max_tokens,
              timeout_seconds: config.timeout_seconds,
              model_endpoint_id: config.model_endpoint_id,
              current_config_version: config.current_config_version,
            }
          : prev
      );
    },
    []
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">Loading agent...</p>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-red-600">Agent not found</p>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      <ChatSidebar
        agentId={agentId}
        agentName={agent.name}
        agentStatus={agent.status}
        activeThreadId={activeThreadId}
        onNewChat={handleNewChat}
        onSelectThread={handleSelectThread}
        onDeleteThread={handleDeleteThread}
        refreshKey={sidebarRefreshKey}
      />

      {/* Chat center */}
      <div className="flex-1 flex flex-col bg-white">
        <ChatMessages
          messages={messages}
          isStreaming={isStreaming}
          agentName={agent.name}
          error={error}
          onRetry={handleRetry}
        />
        <ChatInput
          onSend={handleSend}
          onStop={handleStop}
          isStreaming={isStreaming}
          disabled={!agent.model_endpoint_id}
        />
        {!agent.model_endpoint_id && (
          <p className="text-xs text-amber-600 px-4 pb-2">
            Assign a model endpoint to this agent before chatting.
          </p>
        )}
      </div>

      <ConfigPanel
        agentId={agent.id}
        systemPrompt={agent.system_prompt || ""}
        temperature={agent.temperature}
        maxTokens={agent.max_tokens}
        timeoutSeconds={agent.timeout_seconds}
        modelEndpointId={agent.model_endpoint_id}
        configVersion={agent.current_config_version}
        onConfigUpdate={handleConfigUpdate}
      />
    </div>
  );
}
