"use client";

import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";

interface ChartCardProps {
  title: string;
  loading?: boolean;
  children: ReactNode;
  className?: string;
}

export function ChartCard({ title, loading, children, className }: ChartCardProps) {
  return (
    <div className={`rounded-lg border bg-white p-5 shadow-sm ${className ?? ""}`}>
      <h3 className="mb-4 text-sm font-semibold text-gray-700">{title}</h3>
      <div className="relative min-h-[250px]">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 z-10 rounded">
            <Loader2 className="h-6 w-6 animate-spin text-[#7C3AED]" />
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
