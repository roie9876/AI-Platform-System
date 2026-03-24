"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";

interface EvalRun {
  id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  summary: { total_cases?: number; passed?: number; failed?: number; avg_score?: number } | null;
  created_at: string;
}

interface EvalResult {
  id: string;
  test_case_id: string;
  actual_output: string | null;
  score: number | null;
  metrics: {
    similarity_score?: number;
    keyword_match_rate?: number;
    input_tokens?: number;
    output_tokens?: number;
  } | null;
  status: string;
  error_message: string | null;
  input_message?: string;
  expected_output?: string;
}

export default function RunResultsPage() {
  const params = useParams();
  const runId = params.runId as string;

  const [run, setRun] = useState<EvalRun | null>(null);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [r, res] = await Promise.all([
        apiFetch<EvalRun>(`/api/v1/evaluations/runs/${runId}`),
        apiFetch<EvalResult[]>(`/api/v1/evaluations/runs/${runId}/results`),
      ]);
      setRun(r);
      setResults(res);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;

  const summary = run?.summary;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/dashboard/evaluations" className="text-sm text-gray-500 hover:text-gray-700">← Evaluations</Link>
        <h1 className="text-2xl font-bold text-gray-900">
          Run {run ? new Date(run.created_at).toLocaleDateString() : ""}
        </h1>
        {run && (
          <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
            run.status === "completed" ? "bg-green-100 text-green-800"
            : run.status === "failed" ? "bg-red-100 text-red-800"
            : "bg-yellow-100 text-yellow-800"
          }`}>{run.status}</span>
        )}
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="rounded-lg border bg-white p-4 text-center">
            <div className="text-2xl font-bold">{summary.total_cases ?? 0}</div>
            <div className="text-xs text-gray-500">Total Cases</div>
          </div>
          <div className="rounded-lg border bg-white p-4 text-center">
            <div className="text-2xl font-bold text-green-600">{summary.passed ?? 0}</div>
            <div className="text-xs text-gray-500">Passed</div>
          </div>
          <div className="rounded-lg border bg-white p-4 text-center">
            <div className="text-2xl font-bold text-red-600">{summary.failed ?? 0}</div>
            <div className="text-xs text-gray-500">Failed</div>
          </div>
          <div className="rounded-lg border bg-white p-4 text-center">
            <div className="text-2xl font-bold">
              {summary.avg_score != null ? `${(summary.avg_score * 100).toFixed(0)}%` : "—"}
            </div>
            <div className="text-xs text-gray-500">Avg Score</div>
          </div>
          <div className="rounded-lg border bg-white p-4 text-center">
            <div className="text-2xl font-bold">
              {results.reduce((s, r) => s + (r.metrics?.input_tokens ?? 0) + (r.metrics?.output_tokens ?? 0), 0)}
            </div>
            <div className="text-xs text-gray-500">Total Tokens</div>
          </div>
        </div>
      )}

      <div className="rounded-lg border bg-white shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Input</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Expected</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Actual Output</th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">Score</th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <>
                <tr
                  key={r.id}
                  onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                  className="border-b hover:bg-gray-50 cursor-pointer"
                >
                  <td className="px-4 py-3 max-w-[200px] truncate">{r.input_message ?? r.test_case_id}</td>
                  <td className="px-4 py-3 max-w-[200px] truncate text-gray-600">{r.expected_output ?? "—"}</td>
                  <td className="px-4 py-3 max-w-[250px] truncate text-gray-600">{r.actual_output ?? "—"}</td>
                  <td className="px-4 py-3 text-center">
                    {r.score != null ? (
                      <div className="flex items-center gap-2 justify-center">
                        <div className="h-2 w-16 rounded-full bg-gray-200">
                          <div
                            className={`h-2 rounded-full ${r.score >= 0.7 ? "bg-green-500" : r.score >= 0.4 ? "bg-yellow-500" : "bg-red-500"}`}
                            style={{ width: `${r.score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs">{(r.score * 100).toFixed(0)}%</span>
                      </div>
                    ) : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      r.status === "passed" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                    }`}>{r.status}</span>
                  </td>
                </tr>
                {expandedId === r.id && (
                  <tr key={`${r.id}-detail`} className="border-b bg-gray-50">
                    <td colSpan={5} className="px-6 py-4 space-y-3">
                      <div>
                        <span className="text-xs font-medium text-gray-500">Full Actual Output:</span>
                        <p className="mt-1 text-sm text-gray-800 whitespace-pre-wrap">{r.actual_output}</p>
                      </div>
                      {r.error_message && (
                        <div>
                          <span className="text-xs font-medium text-red-600">Error:</span>
                          <p className="mt-1 text-sm text-red-700">{r.error_message}</p>
                        </div>
                      )}
                      {r.metrics && (
                        <div className="grid grid-cols-4 gap-4 text-sm">
                          <div><span className="text-gray-500">Similarity:</span> {r.metrics.similarity_score?.toFixed(2) ?? "—"}</div>
                          <div><span className="text-gray-500">Keyword Match:</span> {r.metrics.keyword_match_rate?.toFixed(2) ?? "—"}</div>
                          <div><span className="text-gray-500">Input Tokens:</span> {r.metrics.input_tokens ?? "—"}</div>
                          <div><span className="text-gray-500">Output Tokens:</span> {r.metrics.output_tokens ?? "—"}</div>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
