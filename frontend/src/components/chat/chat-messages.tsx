"use client";

import { useEffect, useRef } from "react";

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

interface ChatMessagesProps {
  messages: Message[];
  isStreaming: boolean;
  agentName: string;
  error: string | null;
  onRetry?: () => void;
}

export function ChatMessages({
  messages,
  isStreaming,
  agentName,
  error,
  onRetry,
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  if (messages.length === 0 && !error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400 text-sm">
          Start a conversation with {agentName}
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages
        .filter((m) => m.role !== "system")
        .map((message, i) => (
          <div
            key={i}
            className={`flex ${
              message.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-900"
              }`}
            >
              {message.role === "assistant" && (
                <p className="text-xs text-gray-500 mb-1 font-medium">
                  {agentName}
                </p>
              )}
              <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              {message.role === "assistant" &&
                isStreaming &&
                i === messages.length - 1 && (
                  <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1" />
                )}
            </div>
          </div>
        ))}

      {error && (
        <div className="flex justify-start">
          <div className="max-w-[80%] rounded-lg px-4 py-2 border border-red-200 bg-red-50">
            <p className="text-sm text-red-700">{error}</p>
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-1 text-xs text-red-600 hover:text-red-800 font-medium"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
