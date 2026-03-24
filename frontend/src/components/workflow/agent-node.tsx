"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Bot } from "lucide-react";

export interface AgentNodeData {
  label: string;
  agentName: string;
  nodeType: string;
  agentId: string;
  [key: string]: unknown;
}

const nodeTypeColors: Record<string, string> = {
  agent: "bg-blue-100 text-blue-800 border-blue-200",
  sub_agent: "bg-purple-100 text-purple-800 border-purple-200",
  aggregator: "bg-green-100 text-green-800 border-green-200",
  router: "bg-amber-100 text-amber-800 border-amber-200",
};

function AgentNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as AgentNodeData;
  const colorClasses = nodeTypeColors[nodeData.nodeType] || nodeTypeColors.agent;

  return (
    <div
      className={`rounded-lg border bg-white shadow-sm px-4 py-3 min-w-[160px] ${
        selected ? "ring-2 ring-blue-500 border-blue-500" : "border-gray-200"
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />
      <div className="flex items-center gap-2 mb-1">
        <Bot className="h-4 w-4 text-gray-500 shrink-0" />
        <span className="text-sm font-medium text-gray-900 truncate">
          {nodeData.label}
        </span>
      </div>
      <span
        className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${colorClasses}`}
      >
        {nodeData.nodeType}
      </span>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-blue-500 !border-2 !border-white"
      />
    </div>
  );
}

export const AgentNode = memo(AgentNodeComponent);
