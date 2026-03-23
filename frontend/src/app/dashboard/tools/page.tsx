"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface Tool {
  id: string;
  name: string;
  description: string | null;
  input_schema: Record<string, unknown>;
  is_platform_tool: boolean;
  timeout_seconds: number;
  updated_at: string;
}

interface ToolListResponse {
  tools: Tool[];
  total: number;
}

export default function ToolsPage() {
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<ToolListResponse>("/api/v1/tools")
      .then((data) => setTools(data.tools))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading tools...</p>
      </div>
    );
  }

  const schemaPropertyCount = (schema: Record<string, unknown>) => {
    const props = schema.properties as Record<string, unknown> | undefined;
    return props ? Object.keys(props).length : 0;
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Tools</h1>
        <Link
          href="/dashboard/tools/new"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Register Tool
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {tools.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">
            No tools registered. Register your first tool to get started.
          </p>
          <Link
            href="/dashboard/tools/new"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Register Tool →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {tools.map((tool) => (
            <div
              key={tool.id}
              className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-lg font-semibold text-gray-900 truncate">
                  {tool.name}
                </h3>
                <span className="inline-flex items-center rounded-full bg-blue-100 text-blue-800 px-2.5 py-0.5 text-xs font-medium">
                  {schemaPropertyCount(tool.input_schema)} params
                </span>
              </div>
              {tool.description && (
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                  {tool.description}
                </p>
              )}
              <div className="flex items-center gap-2 text-xs text-gray-400">
                {tool.is_platform_tool && (
                  <span className="inline-flex items-center rounded-full bg-purple-100 text-purple-800 px-2 py-0.5">
                    Platform
                  </span>
                )}
                <span>Timeout: {tool.timeout_seconds}s</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
