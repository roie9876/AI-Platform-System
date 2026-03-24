"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { apiFetch } from "@/lib/api";
import { AnalyticsToolbar } from "@/components/observability/analytics-toolbar";
import { ChartCard } from "@/components/observability/chart-card";

const COLORS = ["#6366F1", "#A855F7", "#EC4899", "#F59E0B", "#10B981"];

interface TokenSeries {
  items: { timestamp: string; input_tokens: number; output_tokens: number; total: number }[];
}

interface AgentTokens {
  items: { name: string; tokens_over_time: { timestamp: string; tokens: number }[] }[];
}

export default function TokensPage() {
  const [timeRange, setTimeRange] = useState("24h");
  const [granularity, setGranularity] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [tokenData, setTokenData] = useState<TokenSeries | null>(null);
  const [byAgent, setByAgent] = useState<AgentTokens | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [t, a] = await Promise.all([
        apiFetch<TokenSeries>(`/api/v1/observability/tokens?time_range=${timeRange}&granularity=${granularity}`),
        apiFetch<AgentTokens>(`/api/v1/observability/costs?time_range=${timeRange}&group_by=agent`),
      ]);
      setTokenData(t);
      setByAgent(a);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [timeRange, granularity]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/dashboard/observability" className="text-sm text-gray-500 hover:text-gray-700">← Dashboard</Link>
        <h1 className="text-2xl font-bold text-gray-900">Token Analytics</h1>
      </div>

      <AnalyticsToolbar
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        granularity={granularity}
        onGranularityChange={setGranularity}
        onRefresh={fetchData}
        loading={loading}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Tokens by Agent" loading={loading}>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={byAgent?.items ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="total_tokens" stroke={COLORS[0]} name="Tokens" />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Input vs Output Tokens" loading={loading}>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={tokenData?.items ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="input_tokens" stackId="1" fill="#818CF8" stroke="#6366F1" name="Input" />
              <Area type="monotone" dataKey="output_tokens" stackId="1" fill="#C084FC" stroke="#A855F7" name="Output" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Token Throughput" loading={loading} className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={tokenData?.items ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area type="monotone" dataKey="total" fill="#7C3AED" stroke="#6D28D9" name="Total Tokens" fillOpacity={0.3} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
