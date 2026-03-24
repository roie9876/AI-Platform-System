"use client";

import { X, Server, Clock } from "lucide-react";

interface MCPDiscoveredTool {
  id: string;
  server_id: string;
  tool_name: string;
  description: string | null;
  input_schema: Record<string, unknown> | null;
  is_available: boolean;
  created_at: string;
  updated_at: string;
}

interface MCPToolDetailPanelProps {
  tool: MCPDiscoveredTool | null;
  serverName: string;
  onClose: () => void;
}

interface SchemaProperty {
  type?: string;
  description?: string;
  enum?: string[];
  default?: unknown;
  items?: { type?: string };
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    string: "bg-blue-100 text-blue-700",
    number: "bg-amber-100 text-amber-700",
    integer: "bg-amber-100 text-amber-700",
    boolean: "bg-green-100 text-green-700",
    object: "bg-purple-100 text-purple-700",
    array: "bg-pink-100 text-pink-700",
  };
  return (
    <span
      className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
        colors[type] || "bg-gray-100 text-gray-600"
      }`}
    >
      {type}
    </span>
  );
}

function renderSchemaProperties(schema: Record<string, unknown>) {
  const properties = schema.properties as
    | Record<string, SchemaProperty>
    | undefined;
  const required = (schema.required as string[]) || [];

  if (!properties || Object.keys(properties).length === 0) {
    return (
      <p className="text-sm text-gray-400 italic">No parameters defined</p>
    );
  }

  return (
    <div className="space-y-2">
      {Object.entries(properties).map(([name, prop]) => {
        const isRequired = required.includes(name);
        const propType =
          prop.type === "array" && prop.items?.type
            ? `${prop.items.type}[]`
            : prop.type || "any";
        return (
          <div
            key={name}
            className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2"
          >
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-900">{name}</span>
              <TypeBadge type={propType} />
              {isRequired && (
                <span className="text-[10px] font-semibold text-red-500">
                  REQUIRED
                </span>
              )}
            </div>
            {prop.description && (
              <p className="mt-0.5 text-xs text-gray-500">{prop.description}</p>
            )}
            {prop.enum && (
              <p className="mt-0.5 text-xs text-gray-400">
                Enum: {prop.enum.join(", ")}
              </p>
            )}
            {prop.default !== undefined && (
              <p className="mt-0.5 text-xs text-gray-400">
                Default: {JSON.stringify(prop.default)}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function MCPToolDetailPanel({
  tool,
  serverName,
  onClose,
}: MCPToolDetailPanelProps) {
  if (!tool) return null;

  const paramCount = tool.input_schema?.properties
    ? Object.keys(
        tool.input_schema.properties as Record<string, unknown>
      ).length
    : 0;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 z-50 flex h-full w-[420px] flex-col border-l border-gray-200 bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h2 className="text-lg font-semibold text-gray-900 truncate">
            {tool.tool_name}
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Status & Server */}
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                tool.is_available
                  ? "bg-green-100 text-green-800"
                  : "bg-gray-100 text-gray-500"
              }`}
            >
              {tool.is_available ? "Available" : "Unavailable"}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600">
              <Server className="h-3 w-3" />
              {serverName}
            </span>
          </div>

          {/* Description */}
          {tool.description && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
                Description
              </h3>
              <p className="text-sm text-gray-700 leading-relaxed">
                {tool.description}
              </p>
            </div>
          )}

          {/* Input Schema */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
              Parameters ({paramCount})
            </h3>
            {tool.input_schema ? (
              renderSchemaProperties(tool.input_schema)
            ) : (
              <p className="text-sm text-gray-400 italic">
                No schema available
              </p>
            )}
          </div>

          {/* Metadata */}
          <div className="border-t border-gray-100 pt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
              Metadata
            </h3>
            <div className="space-y-1.5 text-xs text-gray-500">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3 w-3" />
                <span>
                  Discovered:{" "}
                  {new Date(tool.created_at).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <Clock className="h-3 w-3" />
                <span>
                  Updated:{" "}
                  {new Date(tool.updated_at).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
