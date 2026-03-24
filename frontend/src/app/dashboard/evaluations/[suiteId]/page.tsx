"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Play, Plus, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface TestSuite {
  id: string;
  name: string;
  description: string | null;
  agent_id: string;
}

interface TestCase {
  id: string;
  input_message: string;
  expected_output: string | null;
  expected_keywords: string[] | null;
  order_index: number;
}

interface EvalRun {
  id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  summary: { total_cases?: number; passed?: number; failed?: number; avg_score?: number } | null;
  created_at: string;
}

export default function SuiteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const suiteId = params.suiteId as string;

  const [suite, setSuite] = useState<TestSuite | null>(null);
  const [cases, setCases] = useState<TestCase[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [showAddCase, setShowAddCase] = useState(false);
  const [caseForm, setCaseForm] = useState({ input_message: "", expected_output: "", expected_keywords: "" });
  const [selectedRuns, setSelectedRuns] = useState<string[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, c, r] = await Promise.all([
        apiFetch<TestSuite>(`/api/v1/evaluations/test-suites/${suiteId}`),
        apiFetch<TestCase[]>(`/api/v1/evaluations/test-suites/${suiteId}/cases`),
        apiFetch<EvalRun[]>(`/api/v1/evaluations/runs?test_suite_id=${suiteId}`),
      ]);
      setSuite(s);
      setCases(c);
      setRuns(r);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [suiteId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAddCase = async () => {
    if (!caseForm.input_message) return;
    try {
      await apiFetch(`/api/v1/evaluations/test-suites/${suiteId}/cases`, {
        method: "POST",
        body: JSON.stringify({
          input_message: caseForm.input_message,
          expected_output: caseForm.expected_output || null,
          expected_keywords: caseForm.expected_keywords
            ? caseForm.expected_keywords.split(",").map((k) => k.trim())
            : null,
        }),
      });
      setShowAddCase(false);
      setCaseForm({ input_message: "", expected_output: "", expected_keywords: "" });
      fetchData();
    } catch {
      // silently handle
    }
  };

  const handleRunEval = async () => {
    setRunning(true);
    try {
      const run = await apiFetch<EvalRun>(`/api/v1/evaluations/test-suites/${suiteId}/run`, { method: "POST" });
      // Poll until complete
      let status = run.status;
      let runId = run.id;
      while (status === "running" || status === "pending") {
        await new Promise((r) => setTimeout(r, 2000));
        const updated = await apiFetch<EvalRun>(`/api/v1/evaluations/runs/${runId}`);
        status = updated.status;
      }
      fetchData();
    } catch {
      // silently handle
    } finally {
      setRunning(false);
    }
  };

  const toggleRunSelect = (runId: string) => {
    setSelectedRuns((prev) =>
      prev.includes(runId) ? prev.filter((id) => id !== runId) : prev.length < 2 ? [...prev, runId] : prev
    );
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/dashboard/evaluations" className="text-sm text-gray-500 hover:text-gray-700">← Evaluations</Link>
        <h1 className="text-2xl font-bold text-gray-900">{suite?.name}</h1>
        <button
          onClick={handleRunEval}
          disabled={running || cases.length === 0}
          className="ml-auto flex items-center gap-2 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
        >
          <Play className="h-4 w-4" />
          {running ? "Evaluating..." : "Run Evaluation"}
        </button>
      </div>

      {suite?.description && <p className="text-sm text-gray-500">{suite.description}</p>}

      {/* Test Cases */}
      <div className="rounded-lg border bg-white shadow-sm">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <h3 className="font-semibold text-gray-900">Test Cases ({cases.length})</h3>
          <button onClick={() => setShowAddCase(true)} className="flex items-center gap-1 text-sm text-[#7C3AED] hover:underline">
            <Plus className="h-4 w-4" /> Add Test Case
          </button>
        </div>

        {showAddCase && (
          <div className="border-b p-5 space-y-3 bg-gray-50">
            <input
              placeholder="Input message"
              value={caseForm.input_message}
              onChange={(e) => setCaseForm({ ...caseForm, input_message: e.target.value })}
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
            <input
              placeholder="Expected output (optional)"
              value={caseForm.expected_output}
              onChange={(e) => setCaseForm({ ...caseForm, expected_output: e.target.value })}
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
            <input
              placeholder="Expected keywords (comma-separated)"
              value={caseForm.expected_keywords}
              onChange={(e) => setCaseForm({ ...caseForm, expected_keywords: e.target.value })}
              className="w-full rounded-md border px-3 py-2 text-sm"
            />
            <div className="flex gap-2">
              <button onClick={handleAddCase} className="rounded-md bg-[#7C3AED] px-3 py-1.5 text-sm text-white hover:bg-[#6D28D9]">Add</button>
              <button onClick={() => setShowAddCase(false)} className="rounded-md border px-3 py-1.5 text-sm text-gray-600">Cancel</button>
            </div>
          </div>
        )}

        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-5 py-2 text-left font-medium text-gray-600">#</th>
              <th className="px-5 py-2 text-left font-medium text-gray-600">Input Message</th>
              <th className="px-5 py-2 text-left font-medium text-gray-600">Expected Output</th>
              <th className="px-5 py-2 text-left font-medium text-gray-600">Keywords</th>
            </tr>
          </thead>
          <tbody>
            {cases.map((tc, i) => (
              <tr key={tc.id} className="border-t">
                <td className="px-5 py-2 text-gray-500">{i + 1}</td>
                <td className="px-5 py-2 text-gray-900">{tc.input_message}</td>
                <td className="px-5 py-2 text-gray-600">{tc.expected_output ?? "—"}</td>
                <td className="px-5 py-2">
                  {tc.expected_keywords?.map((k) => (
                    <span key={k} className="mr-1 inline-block rounded bg-gray-100 px-1.5 py-0.5 text-xs">{k}</span>
                  )) ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Run History */}
      <div className="rounded-lg border bg-white shadow-sm">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <h3 className="font-semibold text-gray-900">Run History</h3>
          {selectedRuns.length === 2 && (
            <button
              onClick={() => router.push(`/dashboard/evaluations/runs/${selectedRuns[0]}?compare=${selectedRuns[1]}`)}
              className="text-sm text-[#7C3AED] hover:underline"
            >
              Compare Selected
            </button>
          )}
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-5 py-2 text-left font-medium text-gray-600">Select</th>
              <th className="px-5 py-2 text-left font-medium text-gray-600">Date</th>
              <th className="px-5 py-2 text-left font-medium text-gray-600">Status</th>
              <th className="px-5 py-2 text-right font-medium text-gray-600">Total</th>
              <th className="px-5 py-2 text-right font-medium text-gray-600">Passed</th>
              <th className="px-5 py-2 text-right font-medium text-gray-600">Failed</th>
              <th className="px-5 py-2 text-right font-medium text-gray-600">Avg Score</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.id}
                className="border-t hover:bg-gray-50 cursor-pointer"
                onClick={() => router.push(`/dashboard/evaluations/runs/${run.id}`)}
              >
                <td className="px-5 py-2" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selectedRuns.includes(run.id)}
                    onChange={() => toggleRunSelect(run.id)}
                    className="rounded"
                  />
                </td>
                <td className="px-5 py-2 text-gray-500">{new Date(run.created_at).toLocaleString()}</td>
                <td className="px-5 py-2">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                    run.status === "completed" ? "bg-green-100 text-green-800"
                    : run.status === "failed" ? "bg-red-100 text-red-800"
                    : "bg-yellow-100 text-yellow-800"
                  }`}>{run.status}</span>
                </td>
                <td className="px-5 py-2 text-right">{run.summary?.total_cases ?? "—"}</td>
                <td className="px-5 py-2 text-right text-green-600">{run.summary?.passed ?? "—"}</td>
                <td className="px-5 py-2 text-right text-red-600">{run.summary?.failed ?? "—"}</td>
                <td className="px-5 py-2 text-right font-medium">
                  {run.summary?.avg_score != null ? (run.summary.avg_score * 100).toFixed(0) + "%" : "—"}
                </td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr><td colSpan={7} className="px-5 py-8 text-center text-gray-500">No runs yet. Add test cases and run an evaluation.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
