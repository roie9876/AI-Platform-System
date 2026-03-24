"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { KpiTile } from "@/components/observability/kpi-tiles";
import { ChartCard } from "@/components/observability/chart-card";
import { AnalyticsToolbar } from "@/components/observability/analytics-toolbar";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts";
import { Activity, AlertTriangle, Clock, Zap, DollarSign, Timer } from "lucide-react";

interface DashboardSummary {
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
  avg_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  success_count: number;
  error_count: number;
  requests_per_minute: number;
}

interface TokenTimeSeries {
  time_bucket: string;
  input_tokens: number;
  output_tokens: number;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function formatTimeBucket(bucket: string): string {
  const d = new Date(bucket);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AgentMonitorPanel({ agentId }: { agentId: string }) {
  const [timeRange, setTimeRange] = useState("7d");
  const [granularity, setGranularity] = useState("1h");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [tokenData, setTokenData] = useState<TokenTimeSeries[]>([]);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(true);

  const fetchSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const data = await apiFetch<DashboardSummary>(
        `/api/v1/observability/dashboard?agent_id=${agentId}&time_range=${timeRange}`
      );
      setSummary(data);
    } catch {
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, [agentId, timeRange]);

  const fetchChartData = useCallback(async () => {
    setChartLoading(true);
    try {
      const data = await apiFetch<{ data: TokenTimeSeries[] }>(
        `/api/v1/observability/tokens?agent_id=${agentId}&time_range=${timeRange}&granularity=${granularity}`
      );
      setTokenData(data.data);
    } catch {
      setTokenData([]);
    } finally {
      setChartLoading(false);
    }
  }, [agentId, timeRange, granularity]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  useEffect(() => {
    fetchChartData();
  }, [fetchChartData]);

  const handleRefresh = () => {
    fetchSummary();
    fetchChartData();
  };

  if (!summaryLoading && !summary) {
    return (
      <div className="text-gray-500 text-center py-12">
        No monitoring data available for this agent.
      </div>
    );
  }

  const errorRate =
    summary && summary.total_requests > 0
      ? ((summary.error_count / summary.total_requests) * 100).toFixed(1)
      : "0.0";

  const chartData = tokenData.map((d) => ({
    ...d,
    total_tokens: d.input_tokens + d.output_tokens,
    time_label: formatTimeBucket(d.time_bucket),
  }));

  return (
    <div className="space-y-6">
      <AnalyticsToolbar
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        granularity={granularity}
        onGranularityChange={setGranularity}
        onRefresh={handleRefresh}
        loading={summaryLoading || chartLoading}
      />

      {/* KPI Tiles — 3x2 grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <KpiTile
          title="Total Requests"
          value={summary ? formatNumber(summary.total_requests) : "—"}
          unit="requests"
          icon={<Activity className="h-5 w-5" />}
          colorClass="text-blue-500"
        />
        <KpiTile
          title="Error Rate"
          value={summary ? errorRate : "—"}
          unit="%"
          icon={<AlertTriangle className="h-5 w-5" />}
          colorClass="text-red-500"
          trendGood="down"
        />
        <KpiTile
          title="Avg Latency"
          value={summary ? summary.avg_latency_ms.toFixed(0) : "—"}
          unit="ms"
          icon={<Clock className="h-5 w-5" />}
          colorClass="text-yellow-500"
          trendGood="down"
        />
        <KpiTile
          title="Total Tokens"
          value={summary ? formatNumber(summary.total_tokens) : "—"}
          unit="tokens"
          icon={<Zap className="h-5 w-5" />}
          colorClass="text-purple-500"
        />
        <KpiTile
          title="Total Cost"
          value={summary ? `$${summary.total_cost.toFixed(4)}` : "—"}
          icon={<DollarSign className="h-5 w-5" />}
          colorClass="text-green-500"
        />
        <KpiTile
          title="P95 Latency"
          value={summary ? summary.p95_latency_ms.toFixed(0) : "—"}
          unit="ms"
          icon={<Timer className="h-5 w-5" />}
          colorClass="text-orange-500"
          trendGood="down"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Token Usage Over Time" loading={chartLoading}>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="time_label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Area
                type="monotone"
                dataKey="input_tokens"
                name="Input Tokens"
                fill="#BFDBFE"
                stroke="#3B82F6"
                fillOpacity={0.6}
              />
              <Area
                type="monotone"
                dataKey="output_tokens"
                name="Output Tokens"
                fill="#DDD6FE"
                stroke="#8B5CF6"
                fillOpacity={0.6}
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Token Consumption Trend" loading={chartLoading}>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="time_label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="total_tokens"
                name="Total Tokens"
                stroke="#7C3AED"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
