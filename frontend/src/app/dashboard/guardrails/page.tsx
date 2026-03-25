"use client";

import { useState } from "react";
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Search,
  Plus,
  ToggleLeft,
  ToggleRight,
  AlertTriangle,
  Ban,
  Eye,
  Zap,
  FileText,
  Globe,
  Lock,
  ChevronRight,
  Settings,
  ExternalLink,
} from "lucide-react";

/* ── Types ─────────────────────────────────────────────────── */

type Severity = "block" | "warn" | "log";
type PolicyCategory = "content-safety" | "pii" | "rate-limit" | "custom";

interface Policy {
  id: string;
  name: string;
  description: string;
  category: PolicyCategory;
  severity: Severity;
  enabled: boolean;
  scope: "global" | "tenant" | "agent";
  appliesTo: "input" | "output" | "both";
  config?: Record<string, unknown>;
}

interface BlocklistEntry {
  id: string;
  name: string;
  description: string;
  termCount: number;
  enabled: boolean;
  lastUpdated: string;
  scope: "global" | "tenant";
}

interface Integration {
  id: string;
  name: string;
  provider: string;
  description: string;
  icon: string;
  status: "connected" | "available" | "coming-soon";
  features: string[];
}

/* ── Mock Data ─────────────────────────────────────────────── */

const MOCK_POLICIES: Policy[] = [
  {
    id: "p1",
    name: "Hate Speech Filter",
    description: "Blocks content containing hate speech, slurs, or discriminatory language targeting protected groups.",
    category: "content-safety",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "both",
  },
  {
    id: "p2",
    name: "Violence & Self-Harm Detection",
    description: "Detects and blocks content promoting violence, self-harm, or graphic violent descriptions.",
    category: "content-safety",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "both",
  },
  {
    id: "p3",
    name: "Sexual Content Filter",
    description: "Filters explicit sexual content and inappropriate material from agent responses.",
    category: "content-safety",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "output",
  },
  {
    id: "p4",
    name: "PII Detection — Email & Phone",
    description: "Detects and redacts email addresses and phone numbers from agent outputs to prevent data leakage.",
    category: "pii",
    severity: "warn",
    enabled: true,
    scope: "global",
    appliesTo: "output",
  },
  {
    id: "p5",
    name: "PII Detection — SSN & Credit Card",
    description: "Blocks responses containing Social Security numbers, credit card numbers, or other financial identifiers.",
    category: "pii",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "output",
  },
  {
    id: "p6",
    name: "PII Detection — Names & Addresses",
    description: "Warns when agent outputs contain personal names or physical addresses that may constitute PII.",
    category: "pii",
    severity: "warn",
    enabled: false,
    scope: "tenant",
    appliesTo: "output",
  },
  {
    id: "p7",
    name: "Rate Limit — Per User",
    description: "Limits each user to 60 requests per minute to prevent abuse and ensure fair resource usage.",
    category: "rate-limit",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "input",
    config: { rpm: 60 },
  },
  {
    id: "p8",
    name: "Rate Limit — Per Agent",
    description: "Limits each agent to 200 requests per minute to prevent runaway loops or excessive usage.",
    category: "rate-limit",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "input",
    config: { rpm: 200 },
  },
  {
    id: "p9",
    name: "Rate Limit — Per Tenant",
    description: "Limits each tenant to 1000 requests per minute across all agents and users.",
    category: "rate-limit",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "input",
    config: { rpm: 1000 },
  },
  {
    id: "p10",
    name: "Prompt Injection Detection",
    description: "Detects attempts to override system instructions or manipulate agent behavior via crafted inputs.",
    category: "content-safety",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "input",
  },
  {
    id: "p11",
    name: "Jailbreak Detection",
    description: "Identifies and blocks common jailbreak patterns that attempt to bypass safety guidelines.",
    category: "content-safety",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "input",
  },
  {
    id: "p12",
    name: "Competitor Mention Filter",
    description: "Warns when agent responses mention competitor products or services by name.",
    category: "custom",
    severity: "warn",
    enabled: false,
    scope: "tenant",
    appliesTo: "output",
  },
  {
    id: "p13",
    name: "Max Token Output Limit",
    description: "Limits agent response length to 4096 tokens to prevent excessively long outputs.",
    category: "custom",
    severity: "block",
    enabled: true,
    scope: "global",
    appliesTo: "output",
    config: { maxTokens: 4096 },
  },
  {
    id: "p14",
    name: "Grounding Enforcement",
    description: "Ensures agent responses are grounded in provided context and knowledge, reducing hallucinations.",
    category: "custom",
    severity: "warn",
    enabled: false,
    scope: "agent",
    appliesTo: "output",
  },
];

const MOCK_BLOCKLISTS: BlocklistEntry[] = [
  {
    id: "bl1",
    name: "Profanity List",
    description: "Standard profanity and inappropriate language filter",
    termCount: 847,
    enabled: true,
    lastUpdated: "2026-03-15",
    scope: "global",
  },
  {
    id: "bl2",
    name: "Competitor Names",
    description: "Brand names and product names of direct competitors",
    termCount: 34,
    enabled: false,
    lastUpdated: "2026-03-10",
    scope: "tenant",
  },
  {
    id: "bl3",
    name: "Internal Code Names",
    description: "Internal project code names that should not appear in external communications",
    termCount: 12,
    enabled: true,
    lastUpdated: "2026-03-20",
    scope: "tenant",
  },
  {
    id: "bl4",
    name: "Regulated Financial Terms",
    description: "Financial advice terms that require compliance review before use",
    termCount: 156,
    enabled: true,
    lastUpdated: "2026-02-28",
    scope: "global",
  },
];

const MOCK_INTEGRATIONS: Integration[] = [
  {
    id: "int1",
    name: "Azure AI Content Safety",
    provider: "Microsoft",
    description: "Enterprise-grade content moderation using Azure AI. Detects harmful content across text and images with configurable severity thresholds.",
    icon: "azure",
    status: "connected",
    features: ["Hate speech", "Violence", "Self-harm", "Sexual content", "Custom categories"],
  },
  {
    id: "int2",
    name: "Azure AI Prompt Shields",
    provider: "Microsoft",
    description: "Detects and blocks prompt injection and jailbreak attacks in real-time before they reach the model.",
    icon: "azure",
    status: "connected",
    features: ["Prompt injection", "Jailbreak detection", "Indirect attacks"],
  },
  {
    id: "int3",
    name: "Microsoft Presidio",
    provider: "Microsoft",
    description: "Open-source PII detection and anonymization engine. Supports 50+ PII entity types across multiple languages.",
    icon: "presidio",
    status: "available",
    features: ["PII detection", "Anonymization", "Custom recognizers", "Multi-language"],
  },
  {
    id: "int4",
    name: "Groundedness Detection",
    provider: "Microsoft",
    description: "Validates that model outputs are grounded in provided context, reducing hallucinations and fabricated information.",
    icon: "azure",
    status: "available",
    features: ["Hallucination detection", "Source attribution", "Confidence scoring"],
  },
  {
    id: "int5",
    name: "LlamaGuard",
    provider: "Meta",
    description: "Open-source safety classifier for LLM inputs and outputs based on customizable safety taxonomies.",
    icon: "meta",
    status: "coming-soon",
    features: ["Customizable taxonomy", "Input/output classification", "Open-source"],
  },
];

/* ── Helpers ───────────────────────────────────────────────── */

const SEVERITY_STYLES: Record<Severity, { bg: string; text: string; label: string }> = {
  block: { bg: "bg-red-100", text: "text-red-700", label: "Block" },
  warn: { bg: "bg-amber-100", text: "text-amber-700", label: "Warn" },
  log: { bg: "bg-blue-100", text: "text-blue-700", label: "Log Only" },
};

const CATEGORY_META: Record<PolicyCategory, { label: string; icon: typeof Shield; color: string }> = {
  "content-safety": { label: "Content Safety", icon: ShieldAlert, color: "text-red-500" },
  pii: { label: "PII Protection", icon: Eye, color: "text-purple-500" },
  "rate-limit": { label: "Rate Limiting", icon: Zap, color: "text-amber-500" },
  custom: { label: "Custom", icon: Settings, color: "text-gray-500" },
};

const STATUS_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  connected: { bg: "bg-green-50", text: "text-green-700", dot: "bg-green-500" },
  available: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-500" },
  "coming-soon": { bg: "bg-gray-50", text: "text-gray-500", dot: "bg-gray-400" },
};

/* ── Component ─────────────────────────────────────────────── */

export default function GuardrailsPage() {
  const [tab, setTab] = useState<"policies" | "blocklists" | "integrations">("policies");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<"all" | PolicyCategory>("all");
  const [policies, setPolicies] = useState<Policy[]>(MOCK_POLICIES);
  const [blocklists, setBlocklists] = useState<BlocklistEntry[]>(MOCK_BLOCKLISTS);

  /* ── Policy toggle ── */
  const togglePolicy = (id: string) => {
    setPolicies((prev) =>
      prev.map((p) => (p.id === id ? { ...p, enabled: !p.enabled } : p))
    );
  };

  /* ── Blocklist toggle ── */
  const toggleBlocklist = (id: string) => {
    setBlocklists((prev) =>
      prev.map((b) => (b.id === id ? { ...b, enabled: !b.enabled } : b))
    );
  };

  /* ── Filtered policies ── */
  const filteredPolicies = policies.filter((p) => {
    if (categoryFilter !== "all" && p.category !== categoryFilter) return false;
    if (search && !p.name.toLowerCase().includes(search.toLowerCase()) && !p.description.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  /* ── Stats ── */
  const enabledCount = policies.filter((p) => p.enabled).length;
  const blockCount = policies.filter((p) => p.enabled && p.severity === "block").length;
  const warnCount = policies.filter((p) => p.enabled && p.severity === "warn").length;

  /* ── Tabs ── */
  const tabs = [
    { id: "policies" as const, label: "Policies", count: policies.length },
    { id: "blocklists" as const, label: "Blocklists", count: blocklists.length },
    { id: "integrations" as const, label: "Integrations", count: MOCK_INTEGRATIONS.length },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Guardrails</h1>
          <p className="text-sm text-gray-500 mt-1">
            Safety policies, content filters, and rate limits applied to agent inputs and outputs
          </p>
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] transition-colors">
          <Plus className="h-4 w-4" /> Create Policy
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-green-100 p-2">
              <ShieldCheck className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{enabledCount}</p>
              <p className="text-xs text-gray-500">Active Policies</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-red-100 p-2">
              <ShieldX className="h-5 w-5 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{blockCount}</p>
              <p className="text-xs text-gray-500">Blocking Rules</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-amber-100 p-2">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{warnCount}</p>
              <p className="text-xs text-gray-500">Warning Rules</p>
            </div>
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-purple-100 p-2">
              <Ban className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{blocklists.filter((b) => b.enabled).length}</p>
              <p className="text-xs text-gray-500">Active Blocklists</p>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? "border-[#7C3AED] text-[#7C3AED]"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.label}
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${tab === t.id ? "bg-[#7C3AED]/10 text-[#7C3AED]" : "bg-gray-100 text-gray-500"}`}>
              {t.count}
            </span>
          </button>
        ))}
      </div>

      {/* ─── Policies Tab ─── */}
      {tab === "policies" && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search policies..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#7C3AED]/30 focus:border-[#7C3AED]"
              />
            </div>
            <div className="flex gap-1">
              {(["all", "content-safety", "pii", "rate-limit", "custom"] as const).map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(cat)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-full transition-colors ${
                    categoryFilter === cat
                      ? "bg-[#7C3AED] text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {cat === "all" ? "All" : CATEGORY_META[cat].label}
                </button>
              ))}
            </div>
          </div>

          {/* Policy List */}
          <div className="space-y-2">
            {filteredPolicies.map((policy) => {
              const catMeta = CATEGORY_META[policy.category];
              const sevStyle = SEVERITY_STYLES[policy.severity];
              const CatIcon = catMeta.icon;
              return (
                <div
                  key={policy.id}
                  className={`rounded-lg border bg-white p-4 transition-all hover:shadow-sm ${
                    !policy.enabled ? "opacity-60" : ""
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3 flex-1">
                      <div className={`mt-0.5 ${catMeta.color}`}>
                        <CatIcon className="h-5 w-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-gray-900">{policy.name}</h3>
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${sevStyle.bg} ${sevStyle.text}`}>
                            {sevStyle.label}
                          </span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                            {policy.appliesTo === "both" ? "Input + Output" : policy.appliesTo === "input" ? "Input" : "Output"}
                          </span>
                          <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500 capitalize">
                            {policy.scope}
                          </span>
                        </div>
                        <p className="text-sm text-gray-500 mt-1">{policy.description}</p>
                        {policy.config && (
                          <div className="flex gap-3 mt-2">
                            {Object.entries(policy.config).map(([key, val]) => (
                              <span key={key} className="text-xs text-gray-400">
                                {key}: <span className="font-mono text-gray-600">{String(val)}</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => togglePolicy(policy.id)}
                      className="ml-4 flex-shrink-0"
                      title={policy.enabled ? "Disable policy" : "Enable policy"}
                    >
                      {policy.enabled ? (
                        <ToggleRight className="h-6 w-6 text-[#7C3AED]" />
                      ) : (
                        <ToggleLeft className="h-6 w-6 text-gray-300" />
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ─── Blocklists Tab ─── */}
      {tab === "blocklists" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Custom term lists that block or flag specific words and phrases in agent interactions.
            </p>
            <button className="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
              <Plus className="h-4 w-4" /> New Blocklist
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {blocklists.map((bl) => (
              <div
                key={bl.id}
                className={`rounded-lg border bg-white p-5 transition-all hover:shadow-sm ${
                  !bl.enabled ? "opacity-60" : ""
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-red-50 p-2">
                      <FileText className="h-5 w-5 text-red-500" />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900">{bl.name}</h3>
                      <p className="text-xs text-gray-500 mt-0.5">{bl.description}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => toggleBlocklist(bl.id)}
                    title={bl.enabled ? "Disable" : "Enable"}
                  >
                    {bl.enabled ? (
                      <ToggleRight className="h-6 w-6 text-[#7C3AED]" />
                    ) : (
                      <ToggleLeft className="h-6 w-6 text-gray-300" />
                    )}
                  </button>
                </div>
                <div className="flex items-center gap-4 mt-4 text-xs text-gray-400">
                  <span className="flex items-center gap-1">
                    <Ban className="h-3 w-3" /> {bl.termCount} terms
                  </span>
                  <span className="capitalize">{bl.scope}</span>
                  <span>Updated {new Date(bl.lastUpdated).toLocaleDateString()}</span>
                </div>
                <button className="mt-3 flex items-center gap-1 text-xs text-[#7C3AED] hover:text-[#6D28D9] font-medium">
                  Manage Terms <ChevronRight className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ─── Integrations Tab ─── */}
      {tab === "integrations" && (
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            Connect external safety and moderation services to enhance guardrail capabilities.
          </p>

          <div className="space-y-3">
            {MOCK_INTEGRATIONS.map((integ) => {
              const statusStyle = STATUS_STYLES[integ.status];
              return (
                <div
                  key={integ.id}
                  className="rounded-lg border bg-white p-5 transition-all hover:shadow-sm"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className="rounded-lg bg-gray-100 p-3 flex-shrink-0">
                        {integ.icon === "azure" ? (
                          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none">
                            <path d="M13.05 4.24L7.81 18.5H3l5.24-14.26h4.81z" fill="#0078D4" />
                            <path d="M17.25 18.5H21l-4.57-5.08 2.72-7.42L13.05 18.5h4.2z" fill="#0078D4" opacity="0.8" />
                            <path d="M13.05 4.24l-2.33 8.68L17.15 6l2 .02L13.05 4.24z" fill="#0078D4" opacity="0.6" />
                          </svg>
                        ) : integ.icon === "presidio" ? (
                          <Lock className="h-6 w-6 text-blue-600" />
                        ) : (
                          <Globe className="h-6 w-6 text-blue-500" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold text-gray-900">{integ.name}</h3>
                          <span className={`inline-flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full ${statusStyle.bg} ${statusStyle.text}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${statusStyle.dot}`} />
                            {integ.status === "connected" ? "Connected" : integ.status === "available" ? "Available" : "Coming Soon"}
                          </span>
                          <span className="text-xs text-gray-400">{integ.provider}</span>
                        </div>
                        <p className="text-sm text-gray-500 mt-1">{integ.description}</p>
                        <div className="flex flex-wrap gap-1.5 mt-3">
                          {integ.features.map((f) => (
                            <span key={f} className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                              {f}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="ml-4 flex-shrink-0">
                      {integ.status === "connected" ? (
                        <button className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 border rounded-lg px-3 py-1.5 transition-colors">
                          <Settings className="h-3.5 w-3.5" /> Configure
                        </button>
                      ) : integ.status === "available" ? (
                        <button className="flex items-center gap-1 text-xs text-white bg-[#7C3AED] hover:bg-[#6D28D9] rounded-lg px-3 py-1.5 transition-colors">
                          <ExternalLink className="h-3.5 w-3.5" /> Connect
                        </button>
                      ) : (
                        <span className="text-xs text-gray-400 italic">Coming soon</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
