"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { AnalyticsToolbar } from "@/components/observability/analytics-toolbar";

interface LogEntry {
  id: string;
  agent_name: string;
  event_type: string;
  model_name: string;
  duration_ms: number;
  input_tokens: number;
  output_tokens: number;
  status: string;
  created_at: string;
  state_snapshot: Record<string, unknown>;
}

interface LogsResponse {
  items: LogEntry[];
  total: number;
}

const EVENT_COLORS: Record<string, string> = {
  model_response: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
  tool_call: "bg-blue-100 text-blue-800",
};

export default function LogsPage() {
  const [timeRange, setTimeRange] = useState("24h");
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const limit = 25;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<LogsResponse>(
        `/api/v1/observability/logs?time_range=${timeRange}&limit=${limit}&offset=${offset}`
      );
      setLogs(data.items);
      setTotal(data.total);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [timeRange, offset]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/dashboard/observability" className="text-sm text-gray-500 hover:text-gray-700">← Dashboard</Link>
        <h1 className="text-2xl font-bold text-gray-900">Execution Logs</h1>
      </div>

      <AnalyticsToolbar
        timeRange={timeRange}
        onTimeRangeChange={(r) => { setTimeRange(r); setOffset(0); }}
        onRefresh={fetchData}
        loading={loading}
      />

      <div className="rounded-lg border bg-white shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Time</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Agent</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Event</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Model</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Duration</th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">Tokens</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log) => (
              <>
                <tr
                  key={log.id}
                  onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                  className="border-b hover:bg-gray-50 cursor-pointer"
                >
                  <td className="px-4 py-3 text-gray-500">{new Date(log.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 font-medium text-gray-900">{log.agent_name}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${EVENT_COLORS[log.event_type] ?? "bg-gray-100 text-gray-800"}`}>
                      {log.event_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{log.model_name}</td>
                  <td className="px-4 py-3 text-right text-gray-600">{log.duration_ms}ms</td>
                  <td className="px-4 py-3 text-right text-gray-600">{(log.input_tokens ?? 0) + (log.output_tokens ?? 0)}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      log.status === "success" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                    }`}>
                      {log.status}
                    </span>
                  </td>
                </tr>
                {expandedId === log.id && (
                  <tr key={`${log.id}-detail`} className="border-b bg-gray-50">
                    <td colSpan={7} className="px-6 py-4">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="font-medium text-gray-700">Input Tokens:</span> {log.input_tokens}
                        </div>
                        <div>
                          <span className="font-medium text-gray-700">Output Tokens:</span> {log.output_tokens}
                        </div>
                      </div>
                      {log.state_snapshot && (
                        <pre className="mt-3 rounded bg-gray-100 p-3 text-xs text-gray-700 overflow-auto max-h-40">
                          {JSON.stringify(log.state_snapshot, null, 2)}
                        </pre>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
            {logs.length === 0 && !loading && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-500">No execution logs found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {total > offset + limit && (
        <div className="flex justify-center">
          <button
            onClick={() => setOffset(offset + limit)}
            className="rounded-md border px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
          >
            Load more ({total - offset - limit} remaining)
          </button>
        </div>
      )}
    </div>
  );
}
