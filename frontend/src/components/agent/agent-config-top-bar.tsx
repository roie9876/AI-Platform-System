"use client";

import { ArrowLeft, ChevronDown, MoreHorizontal } from "lucide-react";
import Link from "next/link";

interface AgentConfigTopBarProps {
  agentName: string;
  agentId: string;
  version?: number;
  lastSaved?: string;
  activeTab?: "playground" | "traces" | "monitor" | "evaluation";
  onTabChange?: (tab: string) => void;
}

const subNavTabs = [
  { id: "playground", label: "Playground" },
  { id: "traces", label: "Traces" },
  { id: "monitor", label: "Monitor" },
  { id: "evaluation", label: "Evaluation" },
] as const;

export function AgentConfigTopBar({
  agentName,
  agentId,
  version,
  lastSaved,
  activeTab = "playground",
  onTabChange,
}: AgentConfigTopBarProps) {
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
            className="text-sm text-gray-700 hover:text-gray-900"
          >
            Save
          </button>
          <button
            type="button"
            className="flex items-center gap-1 rounded-md border border-gray-200 px-3 py-1 text-sm text-gray-700"
          >
            Preview
            <ChevronDown className="h-3 w-3" />
          </button>
          <button type="button" className="text-gray-400 hover:text-gray-600">
            <MoreHorizontal className="h-5 w-5" />
          </button>
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
