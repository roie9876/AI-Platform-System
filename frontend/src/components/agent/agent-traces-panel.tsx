"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { AnalyticsToolbar } from "@/components/observability/analytics-toolbar";
import { ChevronDown, ChevronRight } from "lucide-react";

interface TraceLog {
  id: string;
  thread_id: string;
  event_type: string;
  duration_ms: number | null;
  token_count: { input_tokens: number; output_tokens: number } | null;
  model_name: string | null;
  tool_calls: Array<{ name: string; [key: string]: unknown }> | null;
  estimated_cost: number;
  state_snapshot: Record<string, unknown> | null;
  agent_name: string | null;
  created_at: string | null;
}

interface TraceListResponse {
  logs: TraceLog[];
  total: number;
}

const STATUS_STYLES: Record<string, string> = {
  model_response: "bg-green-100 text-green-700",
  tool_call: "bg-yellow-100 text-yellow-700",
  error: "bg-red-100 text-red-700",
};

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function AgentTracesPanel({ agentId }: { agentId: string }) {
  const [timeRange, setTimeRange] = useState("24h");
  const [logs, setLogs] = useState<TraceLog[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const pageSize = 20;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<TraceListResponse>(
        `/api/v1/observability/logs?agent_id=${agentId}&time_range=${timeRange}&limit=${pageSize}&offset=${page * pageSize}`
      );
      setLogs(data.logs);
      setTotal(data.total);
    } catch {
      setLogs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [agentId, timeRange, page]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      <AnalyticsToolbar
        timeRange={timeRange}
        onTimeRangeChange={(r) => { setTimeRange(r); setPage(0); }}
        onRefresh={fetchLogs}
        loading={loading}
      />

      <div className="rounded-lg border bg-white shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-8" />
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Thread ID</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Start Time</th>
              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Duration</th>
              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Tokens In</th>
              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Tokens Out</th>
              <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Cost</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tools Called</th>
            </tr>
          </thead>
          <tbody>
            {loading && logs.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-3 py-12 text-center text-gray-400">
                  Loading traces...
                </td>
              </tr>
            ) : logs.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-3 py-12 text-center text-gray-400">
                  No traces found for this agent in the selected time range
                </td>
              </tr>
            ) : (
              logs.map((log) => {
                const isExpanded = expandedId === log.id;
                const toolNames =
                  log.tool_calls && log.tool_calls.length > 0
                    ? log.tool_calls.map((tc) => String(tc.name)).join(", ")
                    : "—";
                return (
                  <React.Fragment key={log.id}>
                    <tr
                      className="border-b hover:bg-gray-50 cursor-pointer"
                      onClick={() => setExpandedId(isExpanded ? null : log.id)}
                    >
                      <td className="px-3 py-2 text-gray-400">
                        {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs" title={log.thread_id}>
                        {log.thread_id.slice(0, 8)}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[log.event_type] || "bg-gray-100 text-gray-700"}`}>
                          {log.event_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-600">{formatDateTime(log.created_at)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {log.duration_ms != null ? `${log.duration_ms}ms` : "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {log.token_count?.input_tokens ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {log.token_count?.output_tokens ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        ${log.estimated_cost.toFixed(4)}
                      </td>
                      <td className="px-3 py-2 text-gray-600">{log.model_name || "—"}</td>
                      <td className="px-3 py-2 text-gray-600 max-w-[160px] truncate" title={toolNames}>
                        {toolNames}
                      </td>
                    </tr>
                    {isExpanded && (() => {
                      const snap = (log.state_snapshot ?? {}) as Record<string, unknown>;
                      return (
                      <tr key={`${log.id}-detail`} className="bg-gray-50">
                        <td colSpan={10} className="px-6 py-4">
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                            <div>
                              <h4 className="font-medium text-gray-900 mb-2">Execution Details</h4>
                              <dl className="space-y-1 text-gray-600">
                                <div className="flex gap-2">
                                  <dt className="font-medium text-gray-500 w-28">Thread ID:</dt>
                                  <dd className="font-mono text-xs">{log.thread_id}</dd>
                                </div>
                                <div className="flex gap-2">
                                  <dt className="font-medium text-gray-500 w-28">Model:</dt>
                                  <dd>{log.model_name || "—"}</dd>
                                </div>
                                <div className="flex gap-2">
                                  <dt className="font-medium text-gray-500 w-28">Duration:</dt>
                                  <dd>{log.duration_ms != null ? `${log.duration_ms}ms` : "—"}</dd>
                                </div>
                                <div className="flex gap-2">
                                  <dt className="font-medium text-gray-500 w-28">Input Tokens:</dt>
                                  <dd>{log.token_count?.input_tokens ?? "—"}</dd>
                                </div>
                                <div className="flex gap-2">
                                  <dt className="font-medium text-gray-500 w-28">Output Tokens:</dt>
                                  <dd>{log.token_count?.output_tokens ?? "—"}</dd>
                                </div>
                                <div className="flex gap-2">
                                  <dt className="font-medium text-gray-500 w-28">Est. Cost:</dt>
                                  <dd>${log.estimated_cost.toFixed(6)}</dd>
                                </div>
                              </dl>
                            </div>
                            <div>
                              <h4 className="font-medium text-gray-900 mb-2">Context</h4>
                              <dl className="space-y-1 text-gray-600">
                                {!!snap.channel && (
                                  <div className="flex gap-2">
                                    <dt className="font-medium text-gray-500 w-28">Channel:</dt>
                                    <dd>
                                      <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
                                        {String(snap.channel)}
                                      </span>
                                    </dd>
                                  </div>
                                )}
                                {snap.reasoning_tokens != null && Number(snap.reasoning_tokens) > 0 && (
                                  <div className="flex gap-2">
                                    <dt className="font-medium text-gray-500 w-28">Reasoning:</dt>
                                    <dd className="tabular-nums">{Number(snap.reasoning_tokens).toLocaleString()} tokens</dd>
                                  </div>
                                )}
                                {snap.cached_tokens != null && Number(snap.cached_tokens) > 0 && (
                                  <div className="flex gap-2">
                                    <dt className="font-medium text-gray-500 w-28">Cached:</dt>
                                    <dd className="tabular-nums">{Number(snap.cached_tokens).toLocaleString()} tokens</dd>
                                  </div>
                                )}
                                {snap.message_count != null && (
                                  <div className="flex gap-2">
                                    <dt className="font-medium text-gray-500 w-28">Messages:</dt>
                                    <dd>{String(snap.message_count)}</dd>
                                  </div>
                                )}
                                {!!snap.api_type && (
                                  <div className="flex gap-2">
                                    <dt className="font-medium text-gray-500 w-28">API:</dt>
                                    <dd>{String(snap.api_type)}</dd>
                                  </div>
                                )}
                                {snap.stream != null && (
                                  <div className="flex gap-2">
                                    <dt className="font-medium text-gray-500 w-28">Streaming:</dt>
                                    <dd>{snap.stream ? "Yes" : "No"}</dd>
                                  </div>
                                )}
                              </dl>
                              {!!snap.last_user_message && (
                                <div className="mt-3">
                                  <h4 className="font-medium text-gray-900 mb-1">Last User Message</h4>
                                  <div className="rounded bg-white border px-3 py-2 text-xs text-gray-700 max-h-20 overflow-auto whitespace-pre-wrap">
                                    {String(snap.last_user_message)}
                                  </div>
                                </div>
                              )}
                            </div>
                            <div>
                              {log.tool_calls && log.tool_calls.length > 0 && (
                                <div className="mb-3">
                                  <h4 className="font-medium text-gray-900 mb-2">Tool Calls ({log.tool_calls.length})</h4>
                                  <ul className="space-y-1">
                                    {log.tool_calls.map((tc, i) => (
                                      <li key={i} className="rounded bg-white px-3 py-1.5 border text-xs font-mono">
                                        {String(tc.name)}
                                        {tc.arguments ? (
                                          <span className="text-gray-400 ml-2">
                                            ({typeof tc.arguments === "string" ? tc.arguments : JSON.stringify(tc.arguments)})
                                          </span>
                                        ) : null}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {snap.rag_sources ? (
                                <div>
                                  <h4 className="font-medium text-gray-900 mb-2">RAG Sources</h4>
                                  <pre className="rounded bg-white border px-3 py-2 text-xs overflow-auto max-h-32">
                                    {JSON.stringify(snap.rag_sources, null, 2)}
                                  </pre>
                                </div>
                              ) : null}
                            </div>
                          </div>
                        </td>
                      </tr>
                      );
                    })()}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>
            Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded-md border px-3 py-1 text-sm disabled:opacity-50 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="rounded-md border px-3 py-1 text-sm disabled:opacity-50 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
