"use client";

import { useState, useRef, useEffect } from "react";
import { Paperclip, X } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string, file?: File) => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled: boolean;
}

export function ChatInput({
  onSend,
  onStop,
  isStreaming,
  disabled,
}: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 150) + "px";
    }
  }, [message]);

  const handleSubmit = () => {
    const trimmed = message.trim();
    if (!trimmed || isStreaming || disabled) return;
    onSend(trimmed, attachedFile || undefined);
    setMessage("");
    setAttachedFile(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const ALLOWED_EXTENSIONS = ["pdf", "txt", "md", "docx", "png", "jpg", "jpeg", "gif", "webp"];

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
      alert("Unsupported file type. Allowed: PDF, TXT, MD, DOCX, PNG, JPG, GIF, WEBP");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert("File too large. Maximum size is 10 MB.");
      return;
    }
    setAttachedFile(file);
    // Reset input so the same file can be re-selected
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const isImageFile = (file: File) => {
    return /\.(png|jpe?g|gif|webp)$/i.test(file.name);
  };

  return (
    <div className="border-t border-gray-200 p-4 bg-white">
      {attachedFile && (
        <div className="mb-2 flex items-center gap-2 rounded-md bg-blue-50 border border-blue-200 px-3 py-1.5 text-sm text-blue-800 w-fit">
          {isImageFile(attachedFile) ? (
            <img
              src={URL.createObjectURL(attachedFile)}
              alt={attachedFile.name}
              className="h-10 w-10 rounded object-cover"
            />
          ) : (
            <Paperclip className="h-3.5 w-3.5" />
          )}
          <span className="truncate max-w-[200px]">{attachedFile.name}</span>
          <span className="text-blue-500 text-xs">({formatFileSize(attachedFile.size)})</span>
          <button
            onClick={() => setAttachedFile(null)}
            className="ml-1 text-blue-400 hover:text-blue-600"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      <div className="flex gap-2 items-end">
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md,.docx,.png,.jpg,.jpeg,.gif,.webp"
          onChange={handleFileSelect}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isStreaming || disabled}
          title="Attach a file (PDF, TXT, MD, DOCX, PNG, JPG, GIF, WEBP)"
          className="rounded-md border border-gray-300 p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <Paperclip className="h-4 w-4" />
        </button>
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={attachedFile ? "Ask a question about the file..." : "Type a message... (Shift+Enter for new line)"}
          disabled={isStreaming || disabled}
          rows={1}
          className="flex-1 resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:bg-gray-50"
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!message.trim() || disabled}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
