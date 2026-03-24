"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { GitBranch, Play } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface WorkflowResponse {
  id: string;
  name: string;
  description: string | null;
  workflow_type: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface WorkflowListResponse {
  workflows: WorkflowResponse[];
  total: number;
}

const typeColors: Record<string, string> = {
  sequential: "bg-blue-100 text-blue-800",
  parallel: "bg-purple-100 text-purple-800",
  autonomous: "bg-amber-100 text-amber-800",
  custom: "bg-green-100 text-green-800",
};

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<WorkflowListResponse>("/api/v1/workflows")
      .then((data) => setWorkflows(data.workflows))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading workflows...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
        <Link
          href="/dashboard/workflows/new"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Create Workflow
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {workflows.length === 0 ? (
        <div className="text-center py-12">
          <GitBranch className="mx-auto h-12 w-12 text-gray-300 mb-4" />
          <p className="text-gray-500 mb-4">
            No workflows yet. Create your first multi-agent workflow.
          </p>
          <Link
            href="/dashboard/workflows/new"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Create Workflow →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {workflows.map((wf) => (
            <Link
              key={wf.id}
              href={`/dashboard/workflows/${wf.id}`}
              className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-lg font-semibold text-gray-900 truncate">
                  {wf.name}
                </h3>
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    typeColors[wf.workflow_type] || "bg-gray-100 text-gray-800"
                  }`}
                >
                  {wf.workflow_type}
                </span>
              </div>
              {wf.description && (
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                  {wf.description}
                </p>
              )}
              <div className="flex items-center justify-between text-xs text-gray-400">
                <div className="flex items-center gap-1">
                  <GitBranch className="h-3 w-3" />
                  <span>workflow</span>
                </div>
                <span>
                  {new Date(wf.updated_at).toLocaleDateString()}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
