"use client";

import type { ReactNode } from "react";
import { RefreshCw } from "lucide-react";

const TIME_RANGES = ["1h", "24h", "7d", "30d"];
const GRANULARITIES = ["auto", "5m", "1h", "1d"];

interface AnalyticsToolbarProps {
  timeRange: string;
  onTimeRangeChange: (range: string) => void;
  granularity?: string;
  onGranularityChange?: (gran: string) => void;
  onRefresh: () => void;
  loading?: boolean;
  extra?: ReactNode;
}

export function AnalyticsToolbar({
  timeRange,
  onTimeRangeChange,
  granularity,
  onGranularityChange,
  onRefresh,
  loading,
  extra,
}: AnalyticsToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-white px-4 py-2 shadow-sm">
      <div className="flex items-center gap-1">
        {TIME_RANGES.map((r) => (
          <button
            key={r}
            onClick={() => onTimeRangeChange(r)}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              timeRange === r
                ? "bg-[#7C3AED] text-white"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {r}
          </button>
        ))}
      </div>

      {onGranularityChange && (
        <>
          <div className="h-5 w-px bg-gray-200" />
          <select
            value={granularity}
            onChange={(e) => onGranularityChange(e.target.value)}
            className="rounded-md border border-gray-200 bg-white px-2 py-1 text-sm text-gray-700"
          >
            {GRANULARITIES.map((g) => (
              <option key={g} value={g}>
                {g}
              </option>
            ))}
          </select>
        </>
      )}

      {extra && (
        <>
          <div className="h-5 w-px bg-gray-200" />
          {extra}
        </>
      )}

      <div className="ml-auto">
        <button
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>
    </div>
  );
}
