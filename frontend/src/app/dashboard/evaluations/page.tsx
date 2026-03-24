"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface TestSuite {
  id: string;
  name: string;
  description: string | null;
  agent_id: string;
  is_active: boolean;
  created_at: string;
}

interface Agent {
  id: string;
  name: string;
}

export default function EvaluationsPage() {
  const router = useRouter();
  const [suites, setSuites] = useState<TestSuite[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", agent_id: "" });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, a] = await Promise.all([
        apiFetch<TestSuite[]>("/api/v1/evaluations/test-suites"),
        apiFetch<{ agents: Agent[] }>("/api/v1/agents"),
      ]);
      setSuites(s);
      setAgents(a.agents ?? []);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreate = async () => {
    if (!form.name || !form.agent_id) return;
    try {
      await apiFetch("/api/v1/evaluations/test-suites", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setShowCreate(false);
      setForm({ name: "", description: "", agent_id: "" });
      fetchData();
    } catch {
      // silently handle
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Evaluations</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
        >
          <Plus className="h-4 w-4" />
          Create Test Suite
        </button>
      </div>

      {showCreate && (
        <div className="rounded-lg border bg-white p-5 shadow-sm space-y-4">
          <h3 className="font-semibold text-gray-900">New Test Suite</h3>
          <input
            placeholder="Suite name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full rounded-md border px-3 py-2 text-sm"
          />
          <textarea
            placeholder="Description (optional)"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full rounded-md border px-3 py-2 text-sm"
            rows={2}
          />
          <select
            value={form.agent_id}
            onChange={(e) => setForm({ ...form, agent_id: e.target.value })}
            className="w-full rounded-md border px-3 py-2 text-sm"
          >
            <option value="">Select an agent</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          <div className="flex gap-2">
            <button onClick={handleCreate} className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm text-white hover:bg-[#6D28D9]">Create</button>
            <button onClick={() => setShowCreate(false)} className="rounded-md border px-4 py-2 text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : suites.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">No test suites yet.</p>
          <button onClick={() => setShowCreate(true)} className="mt-2 text-sm text-[#7C3AED] hover:underline">
            Create your first test suite
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {suites.map((suite) => (
            <div
              key={suite.id}
              onClick={() => router.push(`/dashboard/evaluations/${suite.id}`)}
              className="flex items-center justify-between rounded-lg border bg-white p-4 shadow-sm hover:shadow-md cursor-pointer transition-shadow"
            >
              <div>
                <h3 className="font-semibold text-gray-900">{suite.name}</h3>
                {suite.description && <p className="text-sm text-gray-500 mt-0.5">{suite.description}</p>}
              </div>
              <div className="text-xs text-gray-400">
                {new Date(suite.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
