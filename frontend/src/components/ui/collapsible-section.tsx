"use client";

import { useState } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";

interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
}

export function CollapsibleSection({
  title,
  defaultOpen = true,
  badge,
  action,
  children,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-b border-gray-200">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex h-12 w-full items-center justify-between px-4"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-900">{title}</span>
          {badge}
        </div>
        <div className="flex items-center gap-2">
          {action && (
            <div onClick={(e) => e.stopPropagation()}>{action}</div>
          )}
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          )}
        </div>
      </button>
      <div
        className={`overflow-hidden transition-all duration-200 ${
          isOpen ? "max-h-[2000px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-4 pb-4">{children}</div>
      </div>
    </div>
  );
}
