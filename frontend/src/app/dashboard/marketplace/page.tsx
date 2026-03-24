"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, Wrench, Search, Star } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface AgentTemplate {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  tags: string[] | null;
  icon_name: string | null;
  author_name: string | null;
  install_count: number;
  version: string;
  is_featured: boolean;
  created_at: string;
}

interface ToolTemplate {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  tags: string[] | null;
  tool_type: string;
  install_count: number;
  version: string;
  is_featured: boolean;
  author_name: string | null;
  created_at: string;
}

const AGENT_CATEGORIES = ["All", "customer-service", "coding", "data-analysis", "general"];
const TOOL_CATEGORIES = ["All", "integration", "utility", "ai-service", "data"];

const CATEGORY_COLORS: Record<string, string> = {
  "customer-service": "border-blue-500",
  coding: "border-indigo-500",
  "data-analysis": "border-green-500",
  general: "border-gray-400",
  integration: "border-purple-500",
  utility: "border-amber-500",
  "ai-service": "border-pink-500",
  data: "border-teal-500",
};

function fmtInstalls(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toString();
}

export default function MarketplacePage() {
  const router = useRouter();
  const [tab, setTab] = useState<"agents" | "tools">("agents");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [agents, setAgents] = useState<AgentTemplate[]>([]);
  const [tools, setTools] = useState<ToolTemplate[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (category !== "All") params.set("category", category);
      if (search) params.set("search", search);

      if (tab === "agents") {
        const data = await apiFetch<AgentTemplate[]>(`/api/v1/marketplace/agents?${params.toString()}`);
        setAgents(data);
      } else {
        const data = await apiFetch<ToolTemplate[]>(`/api/v1/marketplace/tools?${params.toString()}`);
        setTools(data);
      }
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [tab, category, search]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    setCategory("All");
  }, [tab]);

  const categories = tab === "agents" ? AGENT_CATEGORIES : TOOL_CATEGORIES;
  const featured = tab === "agents" ? agents.filter((a) => a.is_featured) : tools.filter((t) => t.is_featured);
  const items = tab === "agents" ? agents : tools;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Marketplace</h1>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        <button
          onClick={() => setTab("agents")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === "agents" ? "border-[#7C3AED] text-[#7C3AED]" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <Bot className="h-4 w-4" /> Agents
        </button>
        <button
          onClick={() => setTab("tools")}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === "tools" ? "border-[#7C3AED] text-[#7C3AED]" : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          <Wrench className="h-4 w-4" /> Tools
        </button>
      </div>

      {/* Search and filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <input
            placeholder={`Search ${tab}...`}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-md border pl-9 pr-3 py-2 text-sm"
          />
        </div>
        <div className="flex gap-1">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                category === c
                  ? "bg-[#7C3AED] text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {c === "All" ? "All" : c.replace("-", " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Featured section */}
      {featured.length > 0 && category === "All" && !search && (
        <div>
          <h2 className="flex items-center gap-1.5 text-sm font-semibold text-gray-700 mb-3">
            <Star className="h-4 w-4 text-amber-500" /> Featured
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {featured.map((item) => (
              <TemplateCard
                key={item.id}
                item={item}
                type={tab}
                onClick={() =>
                  router.push(`/dashboard/marketplace/${tab === "agents" ? "agents" : "tools"}/${item.id}`)
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* All items */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading...</div>
      ) : items.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No {tab} found.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <TemplateCard
              key={item.id}
              item={item}
              type={tab}
              onClick={() =>
                router.push(`/dashboard/marketplace/${tab === "agents" ? "agents" : "tools"}/${item.id}`)
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TemplateCard({
  item,
  type,
  onClick,
}: {
  item: AgentTemplate | ToolTemplate;
  type: "agents" | "tools";
  onClick: () => void;
}) {
  const borderColor = CATEGORY_COLORS[item.category ?? ""] ?? "border-gray-300";
  const Icon = type === "agents" ? Bot : Wrench;

  return (
    <div
      onClick={onClick}
      className={`rounded-lg border bg-white p-5 shadow-sm hover:shadow-md cursor-pointer transition-shadow border-l-4 ${borderColor}`}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100">
          <Icon className="h-5 w-5 text-gray-600" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">{item.name}</h3>
          <p className="mt-1 text-sm text-gray-500 line-clamp-2">{item.description ?? ""}</p>
        </div>
      </div>
      {item.tags && item.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {item.tags.slice(0, 3).map((tag) => (
            <span key={tag} className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600">{tag}</span>
          ))}
        </div>
      )}
      <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
        <span>{item.author_name ?? "Community"}</span>
        <span>{fmtInstalls(item.install_count)} installs · v{item.version}</span>
      </div>
    </div>
  );
}
