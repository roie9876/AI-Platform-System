"use client";

import { useState, useEffect, useRef } from "react";
import { apiFetch } from "@/lib/api";
import { Loader2, CheckCircle2, XCircle, Clock, Ban } from "lucide-react";

interface NodeExecution {
  id: string;
  node_id: string;
  agent_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error: string | null;
}

interface ExecutionDetail {
  id: string;
  workflow_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error: string | null;
  node_executions: NodeExecution[];
}

interface ExecutionMonitorProps {
  workflowId: string;
  executionId: string;
}

const statusConfig: Record<string, { icon: React.ReactNode; color: string; bg: string }> = {
  completed: {
    icon: <CheckCircle2 className="h-4 w-4" />,
    color: "text-green-700",
    bg: "bg-green-100",
  },
  running: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    color: "text-blue-700",
    bg: "bg-blue-100",
  },
  failed: {
    icon: <XCircle className="h-4 w-4" />,
    color: "text-red-700",
    bg: "bg-red-100",
  },
  pending: {
    icon: <Clock className="h-4 w-4" />,
    color: "text-gray-500",
    bg: "bg-gray-100",
  },
  cancelled: {
    icon: <Ban className="h-4 w-4" />,
    color: "text-gray-500",
    bg: "bg-gray-100",
  },
};

function getDuration(start: string | null, end: string | null): string {
  if (!start) return "-";
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  const diff = Math.round((e - s) / 1000);
  if (diff < 60) return `${diff}s`;
  return `${Math.floor(diff / 60)}m ${diff % 60}s`;
}

export function ExecutionMonitor({ workflowId, executionId }: ExecutionMonitorProps) {
  const [execution, setExecution] = useState<ExecutionDetail | null>(null);
  const [error, setError] = useState("");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const fetchStatus = () => {
      apiFetch<ExecutionDetail>(
        `/api/v1/workflows/${workflowId}/executions/${executionId}`
      )
        .then((data) => {
          setExecution(data);
          if (["completed", "failed", "cancelled"].includes(data.status)) {
            if (intervalRef.current) clearInterval(intervalRef.current);
          }
        })
        .catch((err) => setError(err.message));
    };

    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [workflowId, executionId]);

  const handleCancel = async () => {
    try {
      await apiFetch(
        `/api/v1/workflows/${workflowId}/executions/${executionId}/cancel`,
        { method: "POST" }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Cancel failed");
    }
  };

  if (error) {
    return (
      <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!execution) {
    return (
      <div className="flex items-center gap-2 text-gray-500 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading execution...
      </div>
    );
  }

  const cfg = statusConfig[execution.status] || statusConfig.pending;

  return (
    <div className="space-y-4">
      {/* Execution header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ${cfg.bg} ${cfg.color}`}>
            {cfg.icon}
            {execution.status}
          </span>
          <span className="text-sm text-gray-500">
            Duration: {getDuration(execution.started_at, execution.completed_at)}
          </span>
        </div>
        {execution.status === "running" && (
          <button
            type="button"
            onClick={handleCancel}
            className="rounded-md border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Node execution timeline */}
      <div className="space-y-2">
        <h4 className="text-sm font-medium text-gray-700">Node Executions</h4>
        {execution.node_executions.length === 0 ? (
          <p className="text-sm text-gray-400">No node executions yet</p>
        ) : (
          <div className="space-y-2">
            {execution.node_executions.map((ne) => {
              const neCfg = statusConfig[ne.status] || statusConfig.pending;
              return (
                <NodeExecutionCard key={ne.id} ne={ne} cfg={neCfg} />
              );
            })}
          </div>
        )}
      </div>

      {/* Final output */}
      {execution.status === "completed" && execution.output_data && (
        <div className="rounded-md border border-green-200 bg-green-50 p-4">
          <h4 className="text-sm font-medium text-green-800 mb-2">Output</h4>
          <pre className="text-sm text-green-700 whitespace-pre-wrap">
            {JSON.stringify(execution.output_data, null, 2)}
          </pre>
        </div>
      )}

      {/* Error */}
      {execution.status === "failed" && execution.error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4">
          <h4 className="text-sm font-medium text-red-800 mb-1">Error</h4>
          <p className="text-sm text-red-700">{execution.error}</p>
        </div>
      )}
    </div>
  );
}

function NodeExecutionCard({
  ne,
  cfg,
}: {
  ne: NodeExecution;
  cfg: { icon: React.ReactNode; color: string; bg: string };
}) {
  const [expanded, setExpanded] = useState(false);
  const output = ne.output_data?.response as string | undefined;

  return (
    <div className="rounded-md border border-gray-200 bg-white p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={cfg.color}>{cfg.icon}</span>
          <span className="text-sm font-medium text-gray-900">
            Node {ne.node_id.slice(0, 8)}
          </span>
          <span className={`text-xs ${cfg.color}`}>{ne.status}</span>
        </div>
        <span className="text-xs text-gray-400">
          {getDuration(ne.started_at, ne.completed_at)}
        </span>
      </div>

      {ne.error && (
        <p className="mt-2 text-sm text-red-600">{ne.error}</p>
      )}

      {output && (
        <div className="mt-2">
          <p className="text-sm text-gray-600">
            {expanded ? output : output.slice(0, 200)}
            {output.length > 200 && (
              <button
                type="button"
                onClick={() => setExpanded(!expanded)}
                className="ml-1 text-blue-600 hover:text-blue-700 text-xs"
              >
                {expanded ? "Show less" : "Show more"}
              </button>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
