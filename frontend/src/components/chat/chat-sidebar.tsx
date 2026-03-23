"use client";

interface ChatSidebarProps {
  agentName: string;
  agentStatus: string;
  onNewChat: () => void;
}

export function ChatSidebar({
  agentName,
  agentStatus,
  onNewChat,
}: ChatSidebarProps) {
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
          className="w-full rounded-md border border-gray-600 px-3 py-2 text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
        >
          + New Chat
        </button>
      </div>

      <div className="flex-1 p-3">
        <p className="text-xs text-gray-500">
          Chat history will be available in Phase 5 (Thread Management).
        </p>
      </div>
    </div>
  );
}
