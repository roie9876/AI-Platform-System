"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { apiFetch } from "@/lib/api";
import { AnalyticsToolbar } from "@/components/observability/analytics-toolbar";
import { ChartCard } from "@/components/observability/chart-card";

function fmtCost(n: number): string {
  return `$${n.toFixed(2)}`;
}

interface CostBreakdown {
  items: { name: string; total_cost: number; total_tokens: number }[];
}

interface CostAlert {
  id: string;
  name: string;
  alert_type: string;
  threshold_amount: number;
  is_active: boolean;
  last_triggered_at: string | null;
}

export default function CostsPage() {
  const [timeRange, setTimeRange] = useState("24h");
  const [loading, setLoading] = useState(false);
  const [byAgent, setByAgent] = useState<CostBreakdown | null>(null);
  const [byModel, setByModel] = useState<CostBreakdown | null>(null);
  const [alerts, setAlerts] = useState<CostAlert[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [a, m, al] = await Promise.all([
        apiFetch<CostBreakdown>(`/api/v1/observability/costs?time_range=${timeRange}&group_by=agent`),
        apiFetch<CostBreakdown>(`/api/v1/observability/costs?time_range=${timeRange}&group_by=model`),
        apiFetch<CostAlert[]>(`/api/v1/observability/cost-alerts`),
      ]);
      setByAgent(a);
      setByModel(m);
      setAlerts(al);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const totalCost = byAgent?.items?.reduce((s, i) => s + i.total_cost, 0) ?? 0;
  const topAgent = byAgent?.items?.[0];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/dashboard/observability" className="text-sm text-gray-500 hover:text-gray-700">← Dashboard</Link>
        <h1 className="text-2xl font-bold text-gray-900">Cost Analytics</h1>
      </div>

      <AnalyticsToolbar
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        onRefresh={fetchData}
        loading={loading}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border bg-white p-5 shadow-sm">
          <div className="text-sm text-gray-500">Total Cost</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{fmtCost(totalCost)}</div>
        </div>
        <div className="rounded-lg border bg-white p-5 shadow-sm">
          <div className="text-sm text-gray-500">Avg Cost/Request</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">
            {byAgent?.items?.length ? fmtCost(totalCost / byAgent.items.length) : "—"}
          </div>
        </div>
        <div className="rounded-lg border bg-white p-5 shadow-sm">
          <div className="text-sm text-gray-500">Most Expensive Agent</div>
          <div className="text-2xl font-bold text-gray-900 mt-1">{topAgent?.name ?? "—"}</div>
          {topAgent && <div className="text-sm text-gray-500">{fmtCost(topAgent.total_cost)}</div>}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Cost by Agent" loading={loading}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={byAgent?.items ?? []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => fmtCost(Number(v))} />
              <Bar dataKey="total_cost" fill="#7C3AED" name="Cost" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Cost by Model" loading={loading}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={byModel?.items ?? []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => fmtCost(Number(v))} />
              <Bar dataKey="total_cost" fill="#6366F1" name="Cost" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {alerts.length > 0 && (
        <div className="rounded-lg border bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Cost Alerts</h3>
          <div className="space-y-2">
            {alerts.map((a) => (
              <div key={a.id} className="flex items-center justify-between rounded border px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${a.is_active ? "bg-green-500" : "bg-gray-400"}`} />
                  <span className="text-sm font-medium">{a.name}</span>
                  <span className="text-xs text-gray-500">{a.alert_type}</span>
                </div>
                <span className="text-sm text-gray-600">{fmtCost(a.threshold_amount)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
