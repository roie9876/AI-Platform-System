"use client";

import { useState, useRef, useEffect } from "react";
import { RegionBadge } from "@/components/ui/region-badge";

interface AzureResource {
  resource_id: string;
  name: string;
  region: string;
  resource_group?: string;
}

interface ResourcePickerProps {
  resources: AzureResource[];
  value: string | null;
  onChange: (resource: AzureResource | null) => void;
  placeholder?: string;
  label?: string;
  loading?: boolean;
}

export function ResourcePicker({
  resources,
  value,
  onChange,
  placeholder = "Select a resource",
  label,
  loading,
}: ResourcePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = resources.find((r) => r.resource_id === value) ?? null;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      {label && (
        <label className="mb-1 block text-sm font-medium text-gray-700">
          {label}
        </label>
      )}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex h-10 w-full items-center justify-between rounded-md border border-gray-200 bg-white px-3 text-sm"
      >
        <span className={selected ? "text-gray-900" : "text-gray-400"}>
          {loading
            ? "Loading resources..."
            : selected
              ? selected.name
              : placeholder}
        </span>
        <svg
          className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {isOpen && !loading && (
        <div className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md border border-gray-200 bg-white shadow-lg">
          {resources.length === 0 ? (
            <div className="px-3 py-2 text-sm text-gray-500">
              No resources found
            </div>
          ) : (
            resources.map((r) => (
              <button
                key={r.resource_id}
                type="button"
                onClick={() => {
                  onChange(r);
                  setIsOpen(false);
                }}
                className={`w-full px-3 py-2 text-left hover:bg-gray-50 ${
                  r.resource_id === value ? "bg-gray-50" : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900">
                    {r.name}
                  </span>
                  <RegionBadge region={r.region} />
                </div>
                {r.resource_group && (
                  <p className="text-xs text-gray-500">{r.resource_group}</p>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
