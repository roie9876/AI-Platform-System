"use client";

import {
  ArrowDown,
  Columns3,
  Brain,
  Network,
  HelpCircle,
  X,
} from "lucide-react";
import { useState } from "react";

const workflowTypes = [
  {
    value: "sequential",
    label: "Sequential",
    icon: ArrowDown,
    color: "text-blue-600 bg-blue-50 border-blue-200",
    badgeColor: "bg-blue-100 text-blue-700",
    description: "Chain agents in order. Output of each agent becomes the input of the next.",
    diagram: "Agent A → Agent B → Agent C",
    example:
      "Research → Summarize → Translate: First agent researches a topic, second summarizes, third translates.",
    dataFlow: "Full text response of Agent A is sent as the message to Agent B.",
  },
  {
    value: "parallel",
    label: "Parallel",
    icon: Columns3,
    color: "text-green-600 bg-green-50 border-green-200",
    badgeColor: "bg-green-100 text-green-700",
    description:
      "All agents receive the same input simultaneously. Results are collected together.",
    diagram: "Input → [Agent A, Agent B, Agent C] → Combined Results",
    example:
      "Ask 3 different agents the same question and compare their responses.",
    dataFlow: "The original input message is sent to ALL agents at the same time.",
  },
  {
    value: "autonomous",
    label: "Autonomous",
    icon: Brain,
    color: "text-purple-600 bg-purple-50 border-purple-200",
    badgeColor: "bg-purple-100 text-purple-700",
    description:
      "An AI orchestrator decides which agents to call and in what order based on the task.",
    diagram: "Input → Orchestrator → (decides) → Agent A → Agent C",
    example:
      "Ask a complex question — the orchestrator picks the right agents and crafts specific messages for each.",
    dataFlow:
      "Orchestrator analyzes available agents and creates a step-by-step plan. Each agent gets a tailored message.",
  },
  {
    value: "custom",
    label: "Custom DAG",
    icon: Network,
    color: "text-amber-600 bg-amber-50 border-amber-200",
    badgeColor: "bg-amber-100 text-amber-700",
    description:
      "Follow the exact graph you draw. Supports branching, conditional edges, and error handling.",
    diagram: "Agent A → [Agent B (if success), Agent C (if error)]",
    example:
      "Agent A analyzes text. If the output contains 'risky', route to Agent B for review. Otherwise, route to Agent C for action.",
    dataFlow:
      "Follows the edges you draw. Supports conditional routing and custom data mapping between agents.",
  },
];

export function WorkflowTypeBadge({ type }: { type: string }) {
  const wt = workflowTypes.find((t) => t.value === type) || workflowTypes[0];
  const Icon = wt.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${wt.badgeColor}`}
    >
      <Icon className="h-3 w-3" />
      {wt.label}
    </span>
  );
}

export function WorkflowTypeSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [showHelp, setShowHelp] = useState(false);

  return (
    <div>
      <div className="flex items-center gap-1 mb-1">
        <label
          htmlFor="wf-type"
          className="block text-sm font-medium text-gray-700"
        >
          Type
        </label>
        <button
          type="button"
          onClick={() => setShowHelp(true)}
          className="text-gray-400 hover:text-gray-600"
          title="Learn about workflow types"
        >
          <HelpCircle className="h-3.5 w-3.5" />
        </button>
      </div>
      <select
        id="wf-type"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        {workflowTypes.map((wt) => (
          <option key={wt.value} value={wt.value}>
            {wt.label}
          </option>
        ))}
      </select>
      {showHelp && <WorkflowTypeHelpPanel onClose={() => setShowHelp(false)} />}
    </div>
  );
}

export function WorkflowTypeHelpPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-2xl w-[600px] max-h-[85vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 sticky top-0 bg-white rounded-t-xl">
          <h3 className="text-base font-semibold text-gray-900">
            Workflow Types Explained
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md hover:bg-gray-100"
          >
            <X className="h-4 w-4 text-gray-400" />
          </button>
        </div>
        <div className="p-5 space-y-4">
          {workflowTypes.map((wt) => {
            const Icon = wt.icon;
            return (
              <div
                key={wt.value}
                className={`rounded-lg border p-4 ${wt.color}`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="h-5 w-5" />
                  <h4 className="text-sm font-semibold">{wt.label}</h4>
                </div>
                <p className="text-sm mb-3">{wt.description}</p>
                <div className="bg-white/70 rounded-md p-2.5 mb-2 font-mono text-xs text-gray-700">
                  {wt.diagram}
                </div>
                <div className="text-xs space-y-1">
                  <p>
                    <strong>Data flow:</strong> {wt.dataFlow}
                  </p>
                  <p>
                    <strong>Example:</strong> {wt.example}
                  </p>
                </div>
              </div>
            );
          })}

          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 mt-4">
            <h4 className="text-sm font-semibold text-gray-700 mb-2">
              How do agents communicate?
            </h4>
            <ul className="text-xs text-gray-600 space-y-1 list-disc list-inside">
              <li>
                The <strong>edge</strong> (arrow) between agents defines what
                data passes between them.
              </li>
              <li>
                By default, the full text response of the source agent becomes
                the input message of the target agent.
              </li>
              <li>
                Click an edge to configure <strong>output mapping</strong>{" "}
                (select specific fields) or <strong>conditions</strong> (only
                pass if a condition is met).
              </li>
              <li>
                Agents share a workflow thread so they can access each
                other&apos;s conversation history.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
