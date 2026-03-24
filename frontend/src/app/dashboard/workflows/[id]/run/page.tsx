"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Play, ArrowLeft } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { ExecutionMonitor } from "@/components/workflow/execution-monitor";

interface WorkflowResponse {
  id: string;
  name: string;
  description: string | null;
  workflow_type: string;
}

interface ExecutionResponse {
  id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
}

interface ExecutionListResponse {
  executions: ExecutionResponse[];
  total: number;
}

function getDuration(start: string | null, end: string | null): string {
  if (!start) return "-";
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const diff = Math.round((e - s) / 1000);
  if (diff < 60) return `${diff}s`;
  return `${Math.floor(diff / 60)}m ${diff % 60}s`;
}

export default function RunWorkflowPage() {
  const params = useParams();
  const workflowId = params.id as string;

  const [workflow, setWorkflow] = useState<WorkflowResponse | null>(null);
  const [message, setMessage] = useState("");
  const [activeExecutionId, setActiveExecutionId] = useState<string | null>(null);
  const [executions, setExecutions] = useState<ExecutionResponse[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<WorkflowResponse>(`/api/v1/workflows/${workflowId}`)
      .then(setWorkflow)
      .catch((err) => setError(err.message));

    apiFetch<ExecutionListResponse>(`/api/v1/workflows/${workflowId}/executions`)
      .then((data) => setExecutions(data.executions))
      .catch(() => {});
  }, [workflowId]);

  const handleRun = async () => {
    if (!message.trim()) {
      setError("Enter a message to run the workflow");
      return;
    }

    setRunning(true);
    setError("");

    try {
      const result = await apiFetch<{ id: string }>(
        `/api/v1/workflows/${workflowId}/execute`,
        {
          method: "POST",
          body: JSON.stringify({ message: message.trim() }),
        }
      );
      setActiveExecutionId(result.id);
      // Refresh execution list
      apiFetch<ExecutionListResponse>(`/api/v1/workflows/${workflowId}/executions`)
        .then((data) => setExecutions(data.executions))
        .catch(() => {});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start execution");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Link
          href={`/dashboard/workflows/${workflowId}`}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
        <h1 className="text-xl font-bold text-gray-900">
          Run: {workflow?.name || "Workflow"}
        </h1>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Input section */}
      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
        <label htmlFor="wf-message" className="block text-sm font-medium text-gray-700 mb-2">
          Message
        </label>
        <textarea
          id="wf-message"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Enter the message to send to the workflow..."
          rows={3}
          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
        />
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            <Play className="h-4 w-4" />
            {running ? "Starting..." : "Run Workflow"}
          </button>
        </div>
      </div>

      {/* Active execution monitor */}
      {activeExecutionId && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Current Execution</h3>
          <ExecutionMonitor workflowId={workflowId} executionId={activeExecutionId} />
        </div>
      )}

      {/* Execution history */}
      {executions.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white">
          <div className="px-4 py-3 border-b border-gray-200">
            <h3 className="text-sm font-medium text-gray-700">Execution History</h3>
          </div>
          <div className="divide-y divide-gray-100">
            {executions.map((exec) => {
              const statusColor =
                exec.status === "completed"
                  ? "text-green-700 bg-green-100"
                  : exec.status === "running"
                  ? "text-blue-700 bg-blue-100"
                  : exec.status === "failed"
                  ? "text-red-700 bg-red-100"
                  : "text-gray-500 bg-gray-100";

              return (
                <button
                  key={exec.id}
                  type="button"
                  onClick={() => setActiveExecutionId(exec.id)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 text-left"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-gray-500 font-mono">
                      {exec.id.slice(0, 8)}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor}`}
                    >
                      {exec.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span>{getDuration(exec.started_at, exec.completed_at)}</span>
                    <span>
                      {exec.started_at
                        ? new Date(exec.started_at).toLocaleString()
                        : "-"}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
