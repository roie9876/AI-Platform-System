"use client";

import { useState, useRef, useEffect } from "react";
import { ArrowLeft, ChevronDown, MoreHorizontal, Trash2 } from "lucide-react";
import Link from "next/link";

type TabId = "playground" | "traces" | "monitor" | "evaluation" | "whatsapp" | "telegram";

interface AgentConfigTopBarProps {
  agentName: string;
  agentId: string;
  version?: number;
  lastSaved?: string;
  activeTab?: TabId;
  onTabChange?: (tab: string) => void;
  onSave?: () => void;
  isSaving?: boolean;
  onDelete?: () => void;
  visibleTabs?: TabId[];
}

const allTabs: { id: TabId; label: string }[] = [
  { id: "playground", label: "Playground" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "telegram", label: "Telegram" },
  { id: "traces", label: "Traces" },
  { id: "monitor", label: "Monitor" },
  { id: "evaluation", label: "Evaluation" },
];

export type { TabId };

export function AgentConfigTopBar({
  agentName,
  agentId,
  version,
  lastSaved,
  activeTab = "playground",
  onTabChange,
  onSave,
  isSaving,
  onDelete,
  visibleTabs,
}: AgentConfigTopBarProps) {
  const subNavTabs = visibleTabs
    ? allTabs.filter((t) => visibleTabs.includes(t.id))
    : allTabs.filter((t) => !["whatsapp", "telegram"].includes(t.id));
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="w-full bg-white">
      {/* Row 1 */}
      <div className="flex h-14 items-center justify-between border-b border-gray-200 px-4">
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/agents"
            className="text-gray-400 hover:text-gray-600"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <span className="text-lg font-semibold text-gray-900">
            {agentName}
          </span>
        </div>

        {version && (
          <button
            type="button"
            className="flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-sm text-gray-500"
          >
            v{version} {lastSaved && `saved ${lastSaved}`}
            <ChevronDown className="h-3 w-3" />
          </button>
        )}

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onSave}
            disabled={isSaving}
            className="text-sm font-medium text-gray-700 hover:text-gray-900 disabled:opacity-50"
          >
            {isSaving ? "Saving..." : "Save"}
          </button>
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setShowMenu((prev) => !prev)}
              className="text-gray-400 hover:text-gray-600"
            >
              <MoreHorizontal className="h-5 w-5" />
            </button>
            {showMenu && (
              <div className="absolute right-0 top-8 z-50 w-44 rounded-md border border-gray-200 bg-white py-1 shadow-lg">
                <button
                  type="button"
                  onClick={() => {
                    setShowMenu(false);
                    onDelete?.();
                  }}
                  className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="h-4 w-4" />
                  Delete Agent
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Row 2 — Sub-nav tabs */}
      <div className="flex border-b border-gray-200 px-4">
        {subNavTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onTabChange?.(tab.id)}
            className={`px-4 py-2 text-sm font-medium ${
              activeTab === tab.id
                ? "border-b-2 border-[#7C3AED] text-[#7C3AED]"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  );
}
