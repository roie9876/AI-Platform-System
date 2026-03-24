"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Activity, Coins, DollarSign, Gauge } from "lucide-react";
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
import { KpiTile, KpiTileGrid } from "@/components/observability/kpi-tiles";
import { AnalyticsToolbar } from "@/components/observability/analytics-toolbar";
import { ChartCard } from "@/components/observability/chart-card";

function fmtNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toString();
}
function fmtCost(n: number): string {
  return `$${n.toFixed(2)}`;
}
function fmtLatency(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

interface DashboardData {
  total_requests: number;
  total_tokens: number;
  total_cost: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  requests_per_minute: number;
  tokens_per_minute: number;
  cost_per_request: number;
  trend_requests_pct: number;
  trend_tokens_pct: number;
  trend_cost_pct: number;
  trend_latency_pct: number;
}

interface TokenTimeSeries {
  items: { timestamp: string; input_tokens: number; output_tokens: number }[];
}

interface CostBreakdown {
  items: { name: string; total_cost: number; total_tokens: number }[];
}

export default function ObservabilityPage() {
  const [timeRange, setTimeRange] = useState("24h");
  const [granularity, setGranularity] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [tokenData, setTokenData] = useState<TokenTimeSeries | null>(null);
  const [costData, setCostData] = useState<CostBreakdown | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [d, t, c] = await Promise.all([
        apiFetch<DashboardData>(`/api/v1/observability/dashboard?time_range=${timeRange}`),
        apiFetch<TokenTimeSeries>(`/api/v1/observability/tokens?time_range=${timeRange}&granularity=${granularity}`),
        apiFetch<CostBreakdown>(`/api/v1/observability/costs?time_range=${timeRange}&group_by=agent`),
      ]);
      setDashboard(d);
      setTokenData(t);
      setCostData(c);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [timeRange, granularity]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const trendDir = (pct: number) =>
    pct > 0 ? "up" as const : pct < 0 ? "down" as const : "flat" as const;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Observability</h1>

      <AnalyticsToolbar
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        granularity={granularity}
        onGranularityChange={setGranularity}
        onRefresh={fetchData}
        loading={loading}
      />

      <KpiTileGrid>
        <KpiTile
          title="Requests"
          value={dashboard ? fmtNum(dashboard.total_requests) : "—"}
          subtitle={dashboard ? `${dashboard.requests_per_minute.toFixed(1)} rpm` : undefined}
          icon={<Activity className="h-5 w-5" />}
          colorClass="text-blue-500"
          trend={dashboard ? { direction: trendDir(dashboard.trend_requests_pct), pct: Math.abs(dashboard.trend_requests_pct) } : undefined}
        />
        <KpiTile
          title="Tokens"
          value={dashboard ? fmtNum(dashboard.total_tokens) : "—"}
          subtitle={dashboard ? `${fmtNum(dashboard.tokens_per_minute)} tpm` : undefined}
          icon={<Coins className="h-5 w-5" />}
          colorClass="text-purple-500"
          trend={dashboard ? { direction: trendDir(dashboard.trend_tokens_pct), pct: Math.abs(dashboard.trend_tokens_pct) } : undefined}
        />
        <KpiTile
          title="Cost"
          value={dashboard ? fmtCost(dashboard.total_cost) : "—"}
          subtitle={dashboard ? `avg ${fmtCost(dashboard.cost_per_request)}/req` : undefined}
          icon={<DollarSign className="h-5 w-5" />}
          colorClass="text-green-500"
          trendGood="down"
          trend={dashboard ? { direction: trendDir(dashboard.trend_cost_pct), pct: Math.abs(dashboard.trend_cost_pct) } : undefined}
        />
        <KpiTile
          title="Latency"
          value={dashboard ? fmtLatency(dashboard.avg_latency_ms) : "—"}
          subtitle={dashboard ? `p95: ${fmtLatency(dashboard.p95_latency_ms)}` : undefined}
          icon={<Gauge className="h-5 w-5" />}
          colorClass="text-amber-500"
          trendGood="down"
          trend={dashboard ? { direction: trendDir(dashboard.trend_latency_pct), pct: Math.abs(dashboard.trend_latency_pct) } : undefined}
        />
      </KpiTileGrid>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Token Usage Over Time" loading={loading}>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={tokenData?.items ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area type="monotone" dataKey="input_tokens" stackId="1" fill="#818CF8" stroke="#6366F1" name="Input" />
              <Area type="monotone" dataKey="output_tokens" stackId="1" fill="#C084FC" stroke="#A855F7" name="Output" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Cost by Agent" loading={loading}>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={costData?.items ?? []} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => fmtCost(Number(v))} />
              <Bar dataKey="total_cost" fill="#7C3AED" name="Cost" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="flex gap-3">
        <Link href="/dashboard/observability/tokens" className="rounded-md border px-4 py-2 text-sm font-medium text-[#7C3AED] hover:bg-[#F5F3FF]">
          View Tokens →
        </Link>
        <Link href="/dashboard/observability/costs" className="rounded-md border px-4 py-2 text-sm font-medium text-[#7C3AED] hover:bg-[#F5F3FF]">
          View Costs →
        </Link>
        <Link href="/dashboard/observability/logs" className="rounded-md border px-4 py-2 text-sm font-medium text-[#7C3AED] hover:bg-[#F5F3FF]">
          View Logs →
        </Link>
      </div>
    </div>
  );
}
