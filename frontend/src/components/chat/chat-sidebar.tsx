"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { MessageSquare, Trash2, Plus } from "lucide-react";

interface Thread {
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
  threads: Thread[];
  total: number;
}

interface ChatSidebarProps {
  agentId: string;
  agentName: string;
  agentStatus: string;
  activeThreadId: string | null;
  onNewChat: () => void;
  onSelectThread: (threadId: string) => void;
  onDeleteThread: (threadId: string) => void;
  refreshKey?: number;
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

export function ChatSidebar({
  agentId,
  agentName,
  agentStatus,
  activeThreadId,
  onNewChat,
  onSelectThread,
  onDeleteThread,
  refreshKey,
}: ChatSidebarProps) {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [loading, setLoading] = useState(true);

  const loadThreads = useCallback(async () => {
    try {
      const data = await apiFetch<ThreadListResponse>(
        `/api/v1/threads?agent_id=${agentId}`
      );
      setThreads(data.threads);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    loadThreads();
  }, [loadThreads, refreshKey]);

  const statusColors: Record<string, string> = {
    active: "bg-green-400",
    inactive: "bg-gray-400",
    error: "bg-red-400",
  };

  return (
    <div className="w-64 bg-gray-900 text-white flex flex-col border-r border-gray-700">
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-center gap-2 mb-1">
          <span
            className={`w-2 h-2 rounded-full ${
              statusColors[agentStatus] || statusColors.inactive
            }`}
          />
          <h2 className="text-sm font-semibold truncate">{agentName}</h2>
        </div>
        <p className="text-xs text-gray-400 capitalize">{agentStatus}</p>
      </div>

      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 rounded-md border border-gray-600 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {loading ? (
          <p className="text-xs text-gray-500 px-2">Loading threads...</p>
        ) : threads.length === 0 ? (
          <p className="text-xs text-gray-500 px-2">
            Start your first conversation
          </p>
        ) : (
          <div className="space-y-1">
            {threads.map((thread) => (
              <div
                key={thread.id}
                onClick={() => onSelectThread(thread.id)}
                className={`group flex items-start gap-2 rounded-md px-2 py-2 cursor-pointer transition-colors ${
                  thread.id === activeThreadId
                    ? "bg-gray-700 text-white"
                    : "text-gray-300 hover:bg-gray-800"
                }`}
              >
                <MessageSquare className="h-4 w-4 mt-0.5 flex-shrink-0 text-gray-500" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">
                    {thread.title || "New conversation"}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-gray-500">
                      {timeAgo(thread.updated_at)}
                    </span>
                    {thread.last_message_preview && (
                      <span className="text-[10px] text-gray-500 truncate">
                        {thread.last_message_preview.slice(0, 50)}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteThread(thread.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-gray-600 transition-opacity"
                >
                  <Trash2 className="h-3.5 w-3.5 text-gray-400 hover:text-red-400" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
