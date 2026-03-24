"use client";

import { useState, useEffect } from "react";
import { X, ArrowRight, AlertTriangle, GitBranch } from "lucide-react";

interface EdgeConfigDialogProps {
  open: boolean;
  sourceLabel: string;
  targetLabel: string;
  edgeType: string;
  outputMapping: Record<string, string> | null;
  condition: Record<string, string> | null;
  onSave: (data: {
    edgeType: string;
    outputMapping: Record<string, string> | null;
    condition: Record<string, string> | null;
  }) => void;
  onDelete: () => void;
  onClose: () => void;
}

const edgeTypeOptions = [
  {
    value: "default",
    label: "Default",
    description: "Always pass output to next agent",
    icon: ArrowRight,
    color: "text-blue-600 bg-blue-50 border-blue-200",
  },
  {
    value: "conditional",
    label: "Conditional",
    description: "Only pass if condition is met",
    icon: GitBranch,
    color: "text-amber-600 bg-amber-50 border-amber-200",
  },
  {
    value: "error",
    label: "Error Handler",
    description: "Only triggered if source agent fails",
    icon: AlertTriangle,
    color: "text-red-600 bg-red-50 border-red-200",
  },
];

export function EdgeConfigDialog({
  open,
  sourceLabel,
  targetLabel,
  edgeType: initialEdgeType,
  outputMapping: initialMapping,
  condition: initialCondition,
  onSave,
  onDelete,
  onClose,
}: EdgeConfigDialogProps) {
  const [edgeType, setEdgeType] = useState(initialEdgeType);
  const [conditionKey, setConditionKey] = useState("");
  const [conditionValue, setConditionValue] = useState("");
  const [mappingEntries, setMappingEntries] = useState<
    { key: string; value: string }[]
  >([]);

  useEffect(() => {
    setEdgeType(initialEdgeType);
    if (initialCondition) {
      setConditionKey(initialCondition.key || "");
      setConditionValue(initialCondition.value || "");
    } else {
      setConditionKey("");
      setConditionValue("");
    }
    if (initialMapping) {
      setMappingEntries(
        Object.entries(initialMapping).map(([key, value]) => ({ key, value }))
      );
    } else {
      setMappingEntries([]);
    }
  }, [initialEdgeType, initialCondition, initialMapping]);

  if (!open) return null;

  const handleSave = () => {
    const condition =
      edgeType === "conditional" && conditionKey
        ? { key: conditionKey, value: conditionValue }
        : null;

    const outputMapping =
      mappingEntries.length > 0
        ? Object.fromEntries(
            mappingEntries
              .filter((e) => e.key && e.value)
              .map((e) => [e.key, e.value])
          )
        : null;

    onSave({ edgeType, outputMapping, condition });
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-2xl w-[480px] max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div>
            <h3 className="text-base font-semibold text-gray-900">
              Configure Connection
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              <span className="font-medium">{sourceLabel}</span>
              {" → "}
              <span className="font-medium">{targetLabel}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md hover:bg-gray-100"
          >
            <X className="h-4 w-4 text-gray-400" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-5">
          {/* Edge Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Connection Type
            </label>
            <div className="space-y-2">
              {edgeTypeOptions.map((opt) => {
                const Icon = opt.icon;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setEdgeType(opt.value)}
                    className={`w-full flex items-center gap-3 rounded-lg border p-3 text-left transition-all ${
                      edgeType === opt.value
                        ? `${opt.color} ring-1 ring-current`
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <div>
                      <p className="text-sm font-medium">{opt.label}</p>
                      <p className="text-xs text-gray-500">
                        {opt.description}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Condition (for conditional edges) */}
          {edgeType === "conditional" && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <label className="block text-sm font-medium text-amber-800 mb-2">
                Condition
              </label>
              <p className="text-xs text-amber-600 mb-3">
                Only pass data to the next agent when the source output contains
                a matching key/value.
              </p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-amber-700 mb-1">
                    Key
                  </label>
                  <input
                    type="text"
                    value={conditionKey}
                    onChange={(e) => setConditionKey(e.target.value)}
                    placeholder="e.g. status"
                    className="w-full rounded-md border border-amber-300 bg-white px-2.5 py-1.5 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-amber-700 mb-1">
                    Value
                  </label>
                  <input
                    type="text"
                    value={conditionValue}
                    onChange={(e) => setConditionValue(e.target.value)}
                    placeholder="e.g. success"
                    className="w-full rounded-md border border-amber-300 bg-white px-2.5 py-1.5 text-sm focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Data Passing Info */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              What gets passed?
            </label>
            <p className="text-xs text-gray-500 mb-3">
              By default, the full text response from{" "}
              <strong>{sourceLabel}</strong> is sent as the input message to{" "}
              <strong>{targetLabel}</strong>. Add output mappings below to
              customize this.
            </p>

            {/* Output Mapping */}
            <div className="space-y-2">
              {mappingEntries.map((entry, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={entry.key}
                    onChange={(e) => {
                      const updated = [...mappingEntries];
                      updated[i] = { ...updated[i], key: e.target.value };
                      setMappingEntries(updated);
                    }}
                    placeholder="target key"
                    className="flex-1 rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs focus:border-blue-500 focus:outline-none"
                  />
                  <span className="text-xs text-gray-400">←</span>
                  <input
                    type="text"
                    value={entry.value}
                    onChange={(e) => {
                      const updated = [...mappingEntries];
                      updated[i] = { ...updated[i], value: e.target.value };
                      setMappingEntries(updated);
                    }}
                    placeholder="source key"
                    className="flex-1 rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs focus:border-blue-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() =>
                      setMappingEntries(mappingEntries.filter((_, j) => j !== i))
                    }
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setMappingEntries([...mappingEntries, { key: "", value: "" }])
                }
                className="text-xs text-blue-600 hover:text-blue-700 font-medium"
              >
                + Add mapping
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
          <button
            type="button"
            onClick={onDelete}
            className="text-sm text-red-600 hover:text-red-700 font-medium"
          >
            Remove connection
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
