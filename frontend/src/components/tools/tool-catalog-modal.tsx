"use client";

import { useState, useEffect } from "react";
import { Search, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { CatalogToolCard } from "@/components/tools/catalog-tool-card";
import { FilterBar } from "@/components/ui/filter-bar";
import Link from "next/link";

interface Tool {
  id: string;
  name: string;
  description: string | null;
  is_platform_tool: boolean;
}

interface ToolListResponse {
  tools: Tool[];
  total: number;
}

interface CatalogEntry {
  id: string;
  name: string;
  description: string | null;
  connector_type: string;
  category: string | null;
  provider: string | null;
  icon_name: string | null;
  badges: string[] | null;
  is_builtin: boolean;
}

interface ToolCatalogModalProps {
  isOpen: boolean;
  onClose: () => void;
  agentId: string;
  onToolAdded?: () => void;
}

type Tab = "configured" | "catalog" | "custom";

export function ToolCatalogModal({
  isOpen,
  onClose,
  agentId,
  onToolAdded,
}: ToolCatalogModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>("configured");
  const [configuredTools, setConfiguredTools] = useState<Tool[]>([]);
  const [catalogEntries, setCatalogEntries] = useState<CatalogEntry[]>([]);
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);
  const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Filters
  const [typeFilter, setTypeFilter] = useState("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const [sortValue, setSortValue] = useState("featured");

  useEffect(() => {
    if (!isOpen) return;
    apiFetch<ToolListResponse>("/api/v1/tools")
      .then((data) => setConfiguredTools(data.tools))
      .catch(() => {});
    apiFetch<CatalogEntry[]>("/api/v1/catalog/entries")
      .then(setCatalogEntries)
      .catch(() => {});
  }, [isOpen]);

  if (!isOpen) return null;

  const filteredCatalog = catalogEntries.filter((entry) => {
    if (
      searchQuery &&
      !entry.name.toLowerCase().includes(searchQuery.toLowerCase())
    )
      return false;
    if (typeFilter !== "all" && entry.category !== typeFilter) return false;
    if (providerFilter !== "all" && entry.provider !== providerFilter)
      return false;
    return true;
  });

  const categories = [
    ...new Set(catalogEntries.map((e) => e.category).filter(Boolean)),
  ];

  const tabs: { id: Tab; label: string }[] = [
    { id: "configured", label: "Configured" },
    { id: "catalog", label: "Catalog" },
    { id: "custom", label: "Custom" },
  ];

  function handlePrimaryAction() {
    if (activeTab === "configured" && selectedToolId) {
      apiFetch(`/api/v1/agents/${agentId}/tools`, {
        method: "POST",
        body: JSON.stringify({ tool_id: selectedToolId }),
      })
        .then(() => {
          onToolAdded?.();
          onClose();
        })
        .catch(() => {});
    } else if (activeTab === "custom") {
      onClose();
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="flex max-h-[80vh] w-full max-w-[880px] flex-col rounded-xl bg-white">
        {/* Header */}
        <div className="p-6 pb-0">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-gray-900">
              Select a tool
            </h2>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 px-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium ${
                activeTab === tab.id
                  ? "border-b-2 border-[#7C3AED] text-[#7C3AED]"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === "configured" && (
            <div>
              <p className="mb-4 text-sm text-gray-500">
                Configured tools are ready to use with your configured
                authentication, configuration or set up.{" "}
                <a href="#" className="text-[#2563EB] hover:underline">
                  Learn more ↗
                </a>
              </p>
              {configuredTools.length === 0 ? (
                <p className="py-8 text-center text-sm text-gray-500">
                  No tools configured yet. Browse the Catalog to add tools.
                </p>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {configuredTools.map((tool) => (
                    <CatalogToolCard
                      key={tool.id}
                      name={tool.name}
                      description={tool.description || ""}
                      selected={selectedToolId === tool.id}
                      onClick={() => setSelectedToolId(tool.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === "catalog" && (
            <div>
              <p className="mb-4 text-sm text-gray-500">
                Available from the public or organizational Foundry Tool
                Catalog.{" "}
                <a href="#" className="text-[#2563EB] hover:underline">
                  Learn more ↗
                </a>
              </p>
              {/* Search bar */}
              <div className="relative mb-3">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search catalog..."
                  className="h-10 w-full rounded-md border border-gray-200 pl-10 pr-3 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
                />
              </div>
              {/* Filters */}
              <div className="mb-4">
                <FilterBar
                  filters={[
                    {
                      name: "Type",
                      value: typeFilter,
                      onChange: setTypeFilter,
                      options: [
                        { label: "All", value: "all" },
                        { label: "AI Service", value: "ai_service" },
                        { label: "Database", value: "database" },
                        ...categories
                          .filter(
                            (c) => c !== "ai_service" && c !== "database"
                          )
                          .map((c) => ({
                            label: c as string,
                            value: c as string,
                          })),
                      ],
                    },
                    {
                      name: "Provider",
                      value: providerFilter,
                      onChange: setProviderFilter,
                      options: [
                        { label: "All", value: "all" },
                        { label: "Microsoft", value: "Microsoft" },
                        { label: "Custom", value: "Custom" },
                      ],
                    },
                  ]}
                  sortOptions={[
                    { label: "Featured", value: "featured" },
                    { label: "Name", value: "name" },
                  ]}
                  sortValue={sortValue}
                  onSortChange={setSortValue}
                />
              </div>
              {/* Cards */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredCatalog.map((entry) => (
                  <CatalogToolCard
                    key={entry.id}
                    name={entry.name}
                    description={entry.description || ""}
                    iconName={entry.icon_name ?? undefined}
                    badges={entry.badges ?? undefined}
                    selected={selectedEntryId === entry.id}
                    onClick={() => setSelectedEntryId(entry.id)}
                  />
                ))}
              </div>
              {filteredCatalog.length === 0 && (
                <p className="py-8 text-center text-sm text-gray-500">
                  No catalog entries match your filters.
                </p>
              )}
            </div>
          )}

          {activeTab === "custom" && (
            <div>
              <p className="text-sm text-gray-500">
                Create a custom tool with your own configuration.
              </p>
            </div>
          )}
        </div>

        {/* Bottom action bar */}
        <div className="flex justify-end gap-3 border-t border-gray-200 p-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-gray-200 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          {activeTab === "configured" && (
            <button
              type="button"
              disabled={!selectedToolId}
              onClick={handlePrimaryAction}
              className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
            >
              Add tool
            </button>
          )}
          {activeTab === "catalog" && (
            <button
              type="button"
              disabled={!selectedEntryId}
              className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
            >
              Create
            </button>
          )}
          {activeTab === "custom" && (
            <Link
              href="/dashboard/tools/new"
              onClick={onClose}
              className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
            >
              Create custom tool
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
