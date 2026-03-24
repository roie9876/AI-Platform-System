"use client";

import type { ReactNode } from "react";

interface KpiTileProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: ReactNode;
  trend?: { direction: "up" | "down" | "flat"; pct: number };
  trendGood?: "up" | "down";
  subtitle?: string;
  onClick?: () => void;
  colorClass?: string;
}

export function KpiTile({
  title,
  value,
  unit,
  icon,
  trend,
  trendGood = "up",
  subtitle,
  onClick,
  colorClass = "text-blue-500",
}: KpiTileProps) {
  const trendColor =
    trend?.direction === "flat"
      ? "text-gray-500"
      : trend?.direction === trendGood
        ? "text-green-600"
        : "text-red-600";

  const trendArrow =
    trend?.direction === "up" ? "↑" : trend?.direction === "down" ? "↓" : "→";

  const borderColor = colorClass.replace("text-", "border-");

  return (
    <div
      onClick={onClick}
      className={`rounded-lg border bg-white p-5 shadow-sm border-l-4 ${borderColor} ${
        onClick ? "cursor-pointer hover:shadow-md" : ""
      } transition-shadow`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-full bg-opacity-10 ${colorClass.replace("text-", "bg-")}`}>
          <span className={colorClass}>{icon}</span>
        </div>
        {subtitle && (
          <span className="text-xs text-gray-500">{subtitle}</span>
        )}
      </div>
      <div className="text-3xl font-bold text-gray-900">{value}</div>
      {unit && <div className="text-sm text-gray-500 mt-0.5">{unit}</div>}
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs text-gray-500">{title}</span>
        {trend && (
          <span className={`text-xs font-medium ${trendColor}`}>
            {trendArrow} {trend.pct.toFixed(1)}%
          </span>
        )}
      </div>
    </div>
  );
}

export function KpiTileGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {children}
    </div>
  );
}
