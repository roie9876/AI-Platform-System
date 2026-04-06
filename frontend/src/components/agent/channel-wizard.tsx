"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/api";
import {
  MessageCircle,
  Send,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Globe,
  Lock,
  Ban,
  Users,
  UserCheck,
  AtSign,
  Info,
  RefreshCw,
  Loader2,
  CheckCircle2,
  Search,
  AlertCircle,
} from "lucide-react";

// ------------------------------------------------------------------ //
//  Types
// ------------------------------------------------------------------ //

export interface WhatsAppGroupRule {
  group_name: string;
  group_jid: string;
  policy: "open" | "allowlist" | "blocked";
  require_mention: boolean;
  allowed_phones: string[];
  instructions: string;
}

export interface TelegramGroupRule {
  group_name: string;
  group_id: string;
  policy: "open" | "allowlist" | "blocked";
  require_mention: boolean;
  allowed_users: string[];
  instructions: string;
}

export interface ChannelWizardState {
  // WhatsApp
  whatsapp_enabled: boolean;
  whatsapp_dm_policy: "open" | "allowlist" | "pairing";
  whatsapp_allowed_phones: string;
  whatsapp_group_policy: "open" | "allowlist";
  whatsapp_group_rules: WhatsAppGroupRule[];
  whatsapp_channel_instructions: string;
  // Telegram
  telegram_enabled: boolean;
  telegram_bot_token: string;
  telegram_bot_token_secret: string;
  telegram_use_existing_secret: boolean;
  telegram_allowed_users: string;
  dm_policy: "open" | "allowlist" | "pairing";
  telegram_group_rules: TelegramGroupRule[];
  telegram_channel_instructions: string;
}

// ------------------------------------------------------------------ //
//  Helpers
// ------------------------------------------------------------------ //

export interface DiscoveredGroup {
  key: string;
  display_name: string;
  channel: "whatsapp" | "telegram";
  group_id: string;
  has_name?: boolean;
  message_count?: number;
  last_message_at?: string;
  has_session?: boolean;
}

const POLICY_LABELS = {
  open: { label: "Anyone can interact", icon: Globe, color: "text-green-600 bg-green-50 border-green-200" },
  allowlist: { label: "Only approved contacts", icon: UserCheck, color: "text-blue-600 bg-blue-50 border-blue-200" },
  pairing: { label: "Require pairing code", icon: Lock, color: "text-amber-600 bg-amber-50 border-amber-200" },
  blocked: { label: "Agent is blocked", icon: Ban, color: "text-red-600 bg-red-50 border-red-200" },
} as const;

function PolicyCard({
  value,
  selected,
  onClick,
  description,
}: {
  value: keyof typeof POLICY_LABELS;
  selected: boolean;
  onClick: () => void;
  description: string;
}) {
  const p = POLICY_LABELS[value];
  const Icon = p.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-start gap-3 rounded-lg border p-3 text-left transition-all ${
        selected
          ? `${p.color} ring-2 ring-current/20`
          : "border-gray-200 hover:border-gray-300 bg-white"
      }`}
    >
      <Icon className={`h-5 w-5 mt-0.5 shrink-0 ${selected ? "" : "text-gray-400"}`} />
      <div>
        <span className="block text-sm font-medium">{p.label}</span>
        <span className="block text-xs text-gray-500 mt-0.5">{description}</span>
      </div>
    </button>
  );
}

// ------------------------------------------------------------------ //
//  WhatsApp Groups Manager — unified name-first UX
// ------------------------------------------------------------------ //

function WhatsAppGroupsManager({
  rules,
  onChange,
  discoveredGroups,
  groupsLoading,
  onRefresh,
  onRefreshCache,
  cacheRefreshing,
}: {
  rules: WhatsAppGroupRule[];
  onChange: (rules: WhatsAppGroupRule[]) => void;
  discoveredGroups: DiscoveredGroup[];
  groupsLoading: boolean;
  onRefresh: () => void;
  onRefreshCache?: () => void;
  cacheRefreshing?: boolean;
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const searchRef = useRef<HTMLDivElement>(null);

  const waGroups = discoveredGroups.filter((g) => g.channel === "whatsapp");
  const existingJids = new Set(rules.map((r) => r.group_jid).filter(Boolean));

  // Filter suggestions: discovered groups that match the query and aren't already added
  const suggestions = waGroups.filter(
    (g) =>
      !existingJids.has(g.group_id) &&
      (!searchQuery.trim() ||
        g.display_name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Click-outside to close suggestions
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const addFromDiscovery = (g: DiscoveredGroup) => {
    const rule: WhatsAppGroupRule = {
      group_name: g.display_name,
      group_jid: g.group_id,
      policy: "open",
      require_mention: false,
      allowed_phones: [],
      instructions: "",
    };
    onChange([...rules, rule]);
    setExpandedIdx(rules.length);
    setSearchQuery("");
    setShowSuggestions(false);
  };

  const addManual = () => {
    const name = searchQuery.trim();
    if (!name) return;
    // Check if it's an exact match first
    const match = waGroups.find(
      (g) => g.display_name.toLowerCase() === name.toLowerCase()
    );
    if (match && !existingJids.has(match.group_id)) {
      addFromDiscovery(match);
      return;
    }
    // Add as a "pending" rule — JID will be resolved when a message arrives
    const rule: WhatsAppGroupRule = {
      group_name: name,
      group_jid: "",
      policy: "open",
      require_mention: false,
      allowed_phones: [],
      instructions: "",
    };
    onChange([...rules, rule]);
    setExpandedIdx(rules.length);
    setSearchQuery("");
    setShowSuggestions(false);
  };

  const updateRule = (idx: number, patch: Partial<WhatsAppGroupRule>) => {
    onChange(rules.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  };

  const removeRule = (idx: number) => {
    onChange(rules.filter((_, i) => i !== idx));
    if (expandedIdx === idx) setExpandedIdx(null);
    else if (expandedIdx !== null && expandedIdx > idx) setExpandedIdx(expandedIdx - 1);
  };

  const isResolved = (rule: WhatsAppGroupRule) => Boolean(rule.group_jid);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold text-gray-800">Group Rules</span>
          <p className="text-xs text-gray-500 mt-0.5">
            Configure which groups the agent responds in and how.
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          {onRefreshCache && (
            <button
              type="button"
              onClick={onRefreshCache}
              disabled={groupsLoading || cacheRefreshing}
              title="Sync group names directly from WhatsApp (causes brief reconnect)"
              className="flex items-center gap-1 rounded-md bg-green-50 px-2.5 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 border border-green-200 transition-colors disabled:opacity-50"
            >
              {cacheRefreshing ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              {cacheRefreshing ? "Syncing…" : "Sync from WhatsApp"}
            </button>
          )}
          <button
            type="button"
            onClick={onRefresh}
            disabled={groupsLoading}
            title="Refresh discovered groups"
            className="flex items-center gap-1 rounded-md bg-gray-100 px-2.5 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            {groupsLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Refresh
          </button>
        </div>
      </div>

      {/* Search / Add bar */}
      <div ref={searchRef} className="relative">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Type a group name to search or add…"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { e.preventDefault(); addManual(); }
                if (e.key === "Escape") setShowSuggestions(false);
              }}
              className="w-full rounded-md border border-gray-300 pl-9 pr-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
            />
          </div>
          <button
            type="button"
            onClick={addManual}
            disabled={!searchQuery.trim()}
            className="flex items-center gap-1.5 rounded-md bg-green-600 px-3 py-2 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add
          </button>
        </div>

        {/* Suggestions dropdown */}
        {showSuggestions && (
          <div className="absolute z-10 mt-1 w-full rounded-md border border-gray-200 bg-white shadow-lg overflow-hidden">
            {groupsLoading ? (
              <div className="flex items-center gap-2 px-3 py-3 text-xs text-gray-500">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Loading discovered groups…
              </div>
            ) : suggestions.length > 0 ? (
              <ul className="max-h-64 overflow-y-auto divide-y divide-gray-100">
                {suggestions.map((g) => (
                  <li key={g.group_id}>
                    <button
                      type="button"
                      onMouseDown={(e) => { e.preventDefault(); addFromDiscovery(g); }}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-green-50 transition-colors"
                    >
                      <Users className="h-4 w-4 shrink-0 text-green-500" />
                      <div className="flex-1 min-w-0">
                        <span className="block text-sm font-medium text-gray-800 truncate">{g.display_name}</span>
                        {g.message_count != null && g.message_count > 0 && (
                          <span className="block text-xs text-gray-400">{g.message_count} messages seen</span>
                        )}
                      </div>
                      <CheckCircle2 className="h-3.5 w-3.5 text-green-400 opacity-0 group-hover:opacity-100" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="px-3 py-2.5">
                <p className="text-xs text-gray-600 font-medium">
                  {searchQuery.trim() ? "No matching discovered groups" : "All discovered groups are already added"}
                </p>
                {searchQuery.trim() && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    Press Enter or click Add to save &quot;{searchQuery}&quot; — the group ID will be resolved automatically when the first message arrives.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* How discovery works — shown when no groups yet */}
      {waGroups.length === 0 && !groupsLoading && (
        <div className="flex gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3">
          <AlertCircle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
          <div className="text-xs text-amber-800 space-y-1">
            <p className="font-medium">No groups discovered yet</p>
            <p>
              A group appears in the search list the moment <strong>any message</strong> is sent in it while WhatsApp is linked.
              You can still type the group name above and add it now — the system will automatically match it to the real group ID when the first message arrives.
            </p>
          </div>
        </div>
      )}

      {/* Configured group rules list */}
      {rules.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/50 p-5 text-center">
          <Users className="h-7 w-7 mx-auto text-gray-300 mb-2" />
          <p className="text-sm font-medium text-gray-600">No group rules configured</p>
          <p className="text-xs text-gray-400 mt-1 max-w-xs mx-auto">
            The default policy above applies to all groups. Add a rule above to configure specific behavior for individual groups.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule, idx) => {
            const isExpanded = expandedIdx === idx;
            const resolved = isResolved(rule);
            const policyInfo = POLICY_LABELS[rule.policy];
            const PolicyIcon = policyInfo.icon;
            const displayName = rule.group_name || rule.group_jid || `Group ${idx + 1}`;

            return (
              <div key={idx} className="rounded-lg border border-gray-200 bg-white overflow-hidden">
                {/* Card header — always visible */}
                <button
                  type="button"
                  onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                  className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-gray-50 transition-colors"
                >
                  <Users className={`h-4 w-4 shrink-0 ${resolved ? "text-green-500" : "text-amber-400"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800 truncate">{displayName}</span>
                      {resolved ? (
                        <span className="inline-flex items-center gap-0.5 rounded-full bg-green-50 px-1.5 py-0.5 text-[10px] font-medium text-green-700">
                          <CheckCircle2 className="h-2.5 w-2.5" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-0.5 rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                          <AlertCircle className="h-2.5 w-2.5" /> Pending
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">
                      <PolicyIcon className="inline h-3 w-3 mr-0.5" />
                      {policyInfo.label}
                      {rule.require_mention && " · @mention required"}
                      {rule.instructions && " · custom instructions"}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); removeRule(idx); }}
                    className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                    title="Remove rule"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-gray-400 shrink-0" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-gray-400 shrink-0" />
                  )}
                </button>

                {/* Expanded settings */}
                {isExpanded && (
                  <div className="border-t border-gray-100 px-4 py-3 space-y-3 bg-gray-50/30">
                    {/* Group name (editable label) */}
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Group name
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Sales Team"
                        value={rule.group_name}
                        onChange={(e) => updateRule(idx, { group_name: e.target.value })}
                        className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
                      />
                    </div>

                    {/* Group ID — technical detail, read-only */}
                    {rule.group_jid ? (
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          Group ID <span className="font-normal text-gray-400">(auto-resolved)</span>
                        </label>
                        <div className="flex items-center gap-2 rounded-md border border-gray-200 bg-gray-100 px-3 py-1.5">
                          <span className="text-xs font-mono text-gray-500 flex-1 truncate">{rule.group_jid}</span>
                          <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 p-2.5">
                          <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
                          <p className="text-xs text-amber-800">
                            <strong>Pending resolution.</strong> Pick a matching group below. Groups with names appear first; unnamed groups show their ID.
                          </p>
                        </div>
                        {/* Manual picker from discovered groups */}
                        {(() => {
                          const availableGroups = waGroups.filter(
                            (g) => !existingJids.has(g.group_id)
                          );
                          if (availableGroups.length === 0) return (
                            <p className="text-xs text-gray-500 italic">
                              No groups discovered yet. Make sure the bot&apos;s phone is added to the WhatsApp group.
                            </p>
                          );
                          // Sort: named groups first, then unnamed
                          const sorted = [...availableGroups].sort((a, b) => {
                            if (a.has_name && !b.has_name) return -1;
                            if (!a.has_name && b.has_name) return 1;
                            return (a.display_name || "").localeCompare(b.display_name || "");
                          });
                          return (
                            <div>
                              <label className="block text-xs font-medium text-gray-600 mb-1">
                                Pick from discovered groups
                              </label>
                              <select
                                className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
                                value=""
                                onChange={(e) => {
                                  const picked = sorted.find(
                                    (g) => g.group_id === e.target.value
                                  );
                                  if (picked) {
                                    updateRule(idx, {
                                      group_jid: picked.group_id,
                                      group_name: rule.group_name || picked.display_name,
                                    });
                                  }
                                }}
                              >
                                <option value="">— Select a group —</option>
                                {sorted.map((g) => (
                                  <option key={g.group_id} value={g.group_id}>
                                    {g.has_name ? g.display_name : `📱 ${g.group_id}`}
                                  </option>
                                ))}
                              </select>
                            </div>
                          );
                        })()}
                      </div>
                    )}

                    {/* Access policy */}
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-2">
                        Who can interact with the agent in this group?
                      </label>
                      <div className="grid grid-cols-1 gap-2">
                        <PolicyCard
                          value="open"
                          selected={rule.policy === "open"}
                          onClick={() => updateRule(idx, { policy: "open" })}
                          description="The agent responds to all messages from any group member."
                        />
                        <PolicyCard
                          value="allowlist"
                          selected={rule.policy === "allowlist"}
                          onClick={() => updateRule(idx, { policy: "allowlist" })}
                          description="The agent only responds to messages from approved phone numbers."
                        />
                        <PolicyCard
                          value="blocked"
                          selected={rule.policy === "blocked"}
                          onClick={() => updateRule(idx, { policy: "blocked" })}
                          description="The agent silently ignores all messages in this group."
                        />
                      </div>
                    </div>

                    {/* Allowed phones (allowlist only) */}
                    {rule.policy === "allowlist" && (
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">
                          Approved phone numbers
                        </label>
                        <input
                          type="text"
                          placeholder="+972501234567, +14155551234"
                          value={rule.allowed_phones.join(", ")}
                          onChange={(e) =>
                            updateRule(idx, {
                              allowed_phones: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                            })
                          }
                          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
                        />
                        <p className="mt-1 text-xs text-gray-400">International format, comma-separated.</p>
                      </div>
                    )}

                    {/* Require @mention */}
                    {rule.policy !== "blocked" && (
                      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={rule.require_mention}
                          onChange={(e) => updateRule(idx, { require_mention: e.target.checked })}
                          className="rounded border-gray-300 text-green-600 focus:ring-green-500"
                        />
                        <AtSign className="h-3.5 w-3.5 text-gray-400" />
                        Require @mention to respond
                      </label>
                    )}

                    {/* Per-group instructions */}
                    {rule.policy !== "blocked" && (
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">
                          Group-specific instructions <span className="font-normal text-gray-400">(optional)</span>
                        </label>
                        <textarea
                          placeholder="Extra instructions added to the system prompt only for this group. Example: You are helping the Sales team. Focus on lead qualification and pricing questions."
                          value={rule.instructions}
                          onChange={(e) => updateRule(idx, { instructions: e.target.value })}
                          rows={3}
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500 resize-y"
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Telegram Group Rules Editor (simple — Telegram IDs are discoverable)
// ------------------------------------------------------------------ //

function TelegramGroupRulesEditor({
  rules,
  onChange,
  discoveredGroups,
  groupsLoading,
  onRefresh,
}: {
  rules: TelegramGroupRule[];
  onChange: (rules: TelegramGroupRule[]) => void;
  discoveredGroups: DiscoveredGroup[];
  groupsLoading: boolean;
  onRefresh: () => void;
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const tgGroups = discoveredGroups.filter((g) => g.channel === "telegram");
  const existingIds = new Set(rules.map((r) => r.group_id).filter(Boolean));

  const addFromDiscovery = (g: DiscoveredGroup) => {
    const rule: TelegramGroupRule = {
      group_name: g.display_name,
      group_id: g.group_id,
      policy: "open",
      require_mention: true,
      allowed_users: [],
      instructions: "",
    };
    onChange([...rules, rule]);
    setExpandedIdx(rules.length);
  };

  const addManual = () => {
    onChange([...rules, { group_name: "", group_id: "", policy: "open", require_mention: true, allowed_users: [], instructions: "" }]);
    setExpandedIdx(rules.length);
  };

  const updateRule = (idx: number, patch: Partial<TelegramGroupRule>) => {
    onChange(rules.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  };

  const removeRule = (idx: number) => {
    onChange(rules.filter((_, i) => i !== idx));
    if (expandedIdx === idx) setExpandedIdx(null);
    else if (expandedIdx !== null && expandedIdx > idx) setExpandedIdx(expandedIdx - 1);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold text-gray-800">Group Rules</span>
          <p className="text-xs text-gray-500 mt-0.5">Configure per-group behavior overrides.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={groupsLoading}
            className="flex items-center gap-1 rounded-md bg-gray-100 px-2.5 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-200 transition-colors disabled:opacity-50"
          >
            {groupsLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Refresh
          </button>
          <button
            type="button"
            onClick={addManual}
            className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Group
          </button>
        </div>
      </div>

      {/* Discovered groups to add */}
      {tgGroups.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white divide-y divide-gray-100 max-h-48 overflow-y-auto">
          {tgGroups.map((g) => {
            const alreadyAdded = existingIds.has(g.group_id);
            return (
              <div key={g.group_id} className="flex items-center gap-3 px-3 py-2.5">
                <Users className="h-4 w-4 shrink-0 text-blue-500" />
                <span className="flex-1 text-sm text-gray-800 truncate">{g.display_name}</span>
                {alreadyAdded ? (
                  <span className="text-xs text-green-600 flex items-center gap-1"><CheckCircle2 className="h-3 w-3" />Added</span>
                ) : (
                  <button type="button" onClick={() => addFromDiscovery(g)} className="text-xs text-blue-700 hover:underline">Add rule</button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {rules.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/50 p-4 text-center">
          <Users className="h-6 w-6 mx-auto text-gray-300 mb-1" />
          <p className="text-xs text-gray-500">No per-group rules. The default policy applies to all groups.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule, idx) => {
            const isExpanded = expandedIdx === idx;
            const policyInfo = POLICY_LABELS[rule.policy];
            const PolicyIcon = policyInfo.icon;
            const displayName = rule.group_name || rule.group_id || `Group ${idx + 1}`;
            return (
              <div key={idx} className="rounded-lg border border-gray-200 bg-white overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedIdx(isExpanded ? null : idx)}
                  className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-gray-50 transition-colors"
                >
                  <PolicyIcon className={`h-4 w-4 shrink-0 ${rule.policy === "blocked" ? "text-red-500" : rule.policy === "allowlist" ? "text-blue-500" : "text-green-500"}`} />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-gray-800 truncate block">{displayName}</span>
                    <span className="text-xs text-gray-400">
                      {policyInfo.label}{rule.require_mention && " · @mention required"}{rule.instructions && " · custom instructions"}
                    </span>
                  </div>
                  <button type="button" onClick={(e) => { e.stopPropagation(); removeRule(idx); }} className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                  {isExpanded ? <ChevronUp className="h-4 w-4 text-gray-400 shrink-0" /> : <ChevronDown className="h-4 w-4 text-gray-400 shrink-0" />}
                </button>
                {isExpanded && (
                  <div className="border-t border-gray-100 px-4 py-3 space-y-3 bg-gray-50/30">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Group name</label>
                        <input type="text" placeholder="e.g. Dev Team" value={rule.group_name} onChange={(e) => updateRule(idx, { group_name: e.target.value })}
                          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Group ID</label>
                        <input type="text" placeholder="-1001234567890" value={rule.group_id} onChange={(e) => updateRule(idx, { group_id: e.target.value })}
                          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-2">Who can interact in this group?</label>
                      <div className="grid grid-cols-1 gap-2">
                        <PolicyCard value="open" selected={rule.policy === "open"} onClick={() => updateRule(idx, { policy: "open" })} description="Agent responds to everyone." />
                        <PolicyCard value="allowlist" selected={rule.policy === "allowlist"} onClick={() => updateRule(idx, { policy: "allowlist" })} description="Only approved user IDs can interact." />
                        <PolicyCard value="blocked" selected={rule.policy === "blocked"} onClick={() => updateRule(idx, { policy: "blocked" })} description="Agent ignores all messages in this group." />
                      </div>
                    </div>
                    {rule.policy === "allowlist" && (
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Allowed user IDs</label>
                        <input type="text" placeholder="123456789, 987654321" value={rule.allowed_users.join(", ")}
                          onChange={(e) => updateRule(idx, { allowed_users: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
                          className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
                        <p className="mt-1 text-xs text-gray-400">Use /start with @userinfobot to find Telegram user IDs.</p>
                      </div>
                    )}
                    {rule.policy !== "blocked" && (
                      <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
                        <input type="checkbox" checked={rule.require_mention} onChange={(e) => updateRule(idx, { require_mention: e.target.checked })}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                        <AtSign className="h-3.5 w-3.5 text-gray-400" />
                        Require @mention to respond
                      </label>
                    )}
                    {rule.policy !== "blocked" && (
                      <div>
                        <label className="block text-xs font-medium text-gray-600 mb-1">Group-specific instructions <span className="font-normal text-gray-400">(optional)</span></label>
                        <textarea rows={3} placeholder="Extra context for this group appended to the system prompt."
                          value={rule.instructions} onChange={(e) => updateRule(idx, { instructions: e.target.value })}
                          className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y" />
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}



interface ChannelWizardProps {
  state: ChannelWizardState;
  onChange: (state: ChannelWizardState) => void;
  agentId?: string;
  /** "create" hides group rules (groups unknown yet); "manage" shows everything */
  mode?: "create" | "manage";
}

export function ChannelWizard({ state, onChange, agentId, mode = "manage" }: ChannelWizardProps) {
  const update = (patch: Partial<ChannelWizardState>) =>
    onChange({ ...state, ...patch });

  // ---- Live group discovery ----
  const [discoveredGroups, setDiscoveredGroups] = useState<DiscoveredGroup[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [cacheRefreshing, setCacheRefreshing] = useState(false);

  const fetchGroups = useCallback(async () => {
    if (!agentId) return;
    setGroupsLoading(true);
    try {
      const data = await apiFetch<{ groups: DiscoveredGroup[] }>(
        `/api/v1/agents/${agentId}/groups`
      );
      setDiscoveredGroups(data.groups || []);
    } catch {
      // silently fail
    } finally {
      setGroupsLoading(false);
    }
  }, [agentId]);

  const refreshGroupCache = useCallback(async () => {
    if (!agentId) return;
    setCacheRefreshing(true);
    try {
      await apiFetch(`/api/v1/agents/${agentId}/groups/refresh-cache`, { method: "POST" });
      await new Promise((r) => setTimeout(r, 5000));
      await fetchGroups();
    } catch {
      // silently fail
    } finally {
      setCacheRefreshing(false);
    }
  }, [agentId, fetchGroups]);

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  return (
    <div className="space-y-5">
      {/* ============ WhatsApp ============ */}
      <div className="rounded-lg border border-gray-200 overflow-hidden">
        <label className="flex items-center gap-3 px-4 py-3 bg-white cursor-pointer hover:bg-gray-50 transition-colors">
          <input
            type="checkbox"
            checked={state.whatsapp_enabled}
            onChange={(e) => update({ whatsapp_enabled: e.target.checked })}
            className="rounded border-gray-300 text-green-600 focus:ring-green-500"
          />
          <MessageCircle className="h-5 w-5 text-green-500" />
          <div>
            <span className="text-sm font-medium text-gray-900">WhatsApp</span>
            <span className="block text-xs text-gray-500">
              Connect via QR code after deploying the agent
            </span>
          </div>
        </label>

        {state.whatsapp_enabled && (
          <div className="border-t border-gray-100 px-4 py-4 bg-gray-50/30 space-y-5">
            {/* Info banner */}
            <div className="flex gap-2 rounded-md bg-green-50 border border-green-200 p-3">
              <Info className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
              <p className="text-xs text-green-800">
                {mode === "create"
                  ? "After deploying, link WhatsApp by scanning a QR code from the agent page. You'll then be able to configure per-group policies."
                  : "Link WhatsApp by scanning a QR code. The session persists on the agent's storage — no token or password needed."}
              </p>
            </div>

            {/* Everything below is manage-mode only */}
            {mode === "manage" && (
              <>
                {/* ── 1. Channel-wide instructions ── */}
                <section>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    Global Instructions
                  </h4>
                  <textarea
                    rows={3}
                    placeholder="Instructions that apply to ALL WhatsApp conversations (DMs and groups). Appended to the agent's system prompt for every WhatsApp interaction.&#10;&#10;Example: Keep messages short and use emoji. Always respond in the language the user writes in."
                    value={state.whatsapp_channel_instructions}
                    onChange={(e) => update({ whatsapp_channel_instructions: e.target.value })}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
                  />
                  <p className="mt-1 text-xs text-gray-400">
                    Leave empty to use only the main system prompt. Per-group instructions are stacked on top of these.
                  </p>
                </section>

                {/* ── 2. Direct Messages ── */}
                <section>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    Direct Messages
                  </h4>
                  <div className="grid grid-cols-1 gap-2">
                    <PolicyCard
                      value="open"
                      selected={state.whatsapp_dm_policy === "open"}
                      onClick={() => update({ whatsapp_dm_policy: "open" })}
                      description="Anyone who has the phone number can send a direct message."
                    />
                    <PolicyCard
                      value="allowlist"
                      selected={state.whatsapp_dm_policy === "allowlist"}
                      onClick={() => update({ whatsapp_dm_policy: "allowlist" })}
                      description="Only phone numbers you specify below can send direct messages. Leave empty to block all DMs."
                    />
                    <PolicyCard
                      value="pairing"
                      selected={state.whatsapp_dm_policy === "pairing"}
                      onClick={() => update({ whatsapp_dm_policy: "pairing" })}
                      description="Users request access with a code. You approve each one."
                    />
                  </div>
                  {state.whatsapp_dm_policy === "allowlist" && (
                    <div className="mt-3">
                      <label className="block text-xs font-medium text-gray-600 mb-1">
                        Approved phone numbers (for direct messages)
                      </label>
                      <input
                        type="text"
                        placeholder="+972501234567, +14155551234"
                        value={state.whatsapp_allowed_phones}
                        onChange={(e) => update({ whatsapp_allowed_phones: e.target.value })}
                        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
                      />
                      <p className="mt-1 text-xs text-gray-400">
                        International format with country code, comma-separated. Leave empty to block all direct messages.
                      </p>
                    </div>
                  )}
                </section>

                {/* ── 3. Groups ── */}
                <section>
                  <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                    Groups
                  </h4>

                  {/* Default group policy */}
                  <div className="mb-3">
                    <p className="text-xs text-gray-600 mb-2">
                      <span className="font-medium">Default for all groups</span> — applies to any group that doesn&apos;t have a specific rule below.
                    </p>
                    <div className="grid grid-cols-1 gap-2">
                      <PolicyCard
                        value="open"
                        selected={state.whatsapp_group_policy === "open"}
                        onClick={() => update({ whatsapp_group_policy: "open" })}
                        description="The agent responds in every group it's added to. Add rules below to override specific groups."
                      />
                      <PolicyCard
                        value="allowlist"
                        selected={state.whatsapp_group_policy === "allowlist"}
                        onClick={() => update({ whatsapp_group_policy: "allowlist" })}
                        description="The agent stays silent in all groups unless you add a specific rule for that group below."
                      />
                    </div>
                  </div>

                  {/* Divider with context */}
                  <div className="relative my-4">
                    <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
                    <div className="relative flex justify-center">
                      <span className="bg-gray-50 px-2 text-xs text-gray-400">Per-group overrides</span>
                    </div>
                  </div>

                  {/* Unified group manager */}
                  <WhatsAppGroupsManager
                    rules={state.whatsapp_group_rules}
                    onChange={(rules) => update({ whatsapp_group_rules: rules })}
                    discoveredGroups={discoveredGroups}
                    groupsLoading={groupsLoading}
                    onRefresh={fetchGroups}
                    onRefreshCache={refreshGroupCache}
                    cacheRefreshing={cacheRefreshing}
                  />
                </section>
              </>
            )}
          </div>
        )}
      </div>

      {/* ============ Telegram ============ */}
      <div className="rounded-lg border border-gray-200 overflow-hidden">
        <label className="flex items-center gap-3 px-4 py-3 bg-white cursor-pointer hover:bg-gray-50 transition-colors">
          <input
            type="checkbox"
            checked={state.telegram_enabled}
            onChange={(e) => update({ telegram_enabled: e.target.checked })}
            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <Send className="h-5 w-5 text-blue-500" />
          <div>
            <span className="text-sm font-medium text-gray-900">Telegram</span>
            <span className="block text-xs text-gray-500">
              Connect with a Bot Token from @BotFather
            </span>
          </div>
        </label>

        {state.telegram_enabled && (
          <div className="border-t border-gray-100 px-4 py-4 bg-gray-50/30 space-y-4">
            {/* Bot Token — always shown */}
            <div>
              <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide mb-2">
                Bot Token
              </label>
              <div className="flex gap-3 mb-3">
                <label
                  className={`flex-1 relative flex cursor-pointer rounded-lg border p-3 ${
                    state.telegram_use_existing_secret
                      ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500"
                      : "border-gray-300 hover:border-gray-400"
                  }`}
                >
                  <input
                    type="radio"
                    name="tg_token_src"
                    checked={state.telegram_use_existing_secret}
                    onChange={() => update({ telegram_use_existing_secret: true })}
                    className="sr-only"
                  />
                  <div>
                    <span className="block text-xs font-medium text-gray-900">
                      Use existing Key Vault secret
                    </span>
                    <span className="mt-0.5 block text-xs text-gray-500">
                      Reference a stored bot token
                    </span>
                  </div>
                </label>
                <label
                  className={`flex-1 relative flex cursor-pointer rounded-lg border p-3 ${
                    !state.telegram_use_existing_secret
                      ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500"
                      : "border-gray-300 hover:border-gray-400"
                  }`}
                >
                  <input
                    type="radio"
                    name="tg_token_src"
                    checked={!state.telegram_use_existing_secret}
                    onChange={() => update({ telegram_use_existing_secret: false })}
                    className="sr-only"
                  />
                  <div>
                    <span className="block text-xs font-medium text-gray-900">
                      Enter Bot Token
                    </span>
                    <span className="mt-0.5 block text-xs text-gray-500">
                      Paste from @BotFather, stored in Key Vault
                    </span>
                  </div>
                </label>
              </div>

              {state.telegram_use_existing_secret ? (
                <input
                  type="text"
                  placeholder="Secret name in Key Vault"
                  value={state.telegram_bot_token_secret}
                  onChange={(e) =>
                    update({ telegram_bot_token_secret: e.target.value })
                  }
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              ) : (
                <input
                  type="password"
                  placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                  value={state.telegram_bot_token}
                  onChange={(e) =>
                    update({ telegram_bot_token: e.target.value })
                  }
                  className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              )}
            </div>

            {/* Create-mode hint */}
            {mode === "create" && (
              <div className="flex gap-2 rounded-md bg-blue-50 border border-blue-200 p-3">
                <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" />
                <p className="text-xs text-blue-800">
                  After deploying, you&apos;ll be able to browse your Telegram
                  groups and configure per-group policies from the agent page.
                </p>
              </div>
            )}

            {/* Policies & group rules — manage mode only */}
            {mode === "manage" && (
              <>
                {/* Channel-level instructions */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide mb-2">
                    Telegram Channel Instructions
                  </label>
                  <textarea
                    rows={3}
                    placeholder="Instructions that apply to ALL Telegram conversations (DMs and groups). These are appended to the agent's system prompt for every Telegram interaction.&#10;&#10;Example: When responding on Telegram, use markdown formatting. Always respond in the same language the user writes in."
                    value={state.telegram_channel_instructions}
                    onChange={(e) => update({ telegram_channel_instructions: e.target.value })}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <p className="mt-1 text-xs text-gray-400">
                    Leave empty to use only the main system prompt. Per-group instructions (below) are added on top of these.
                  </p>
                </div>

                {/* DM Policy */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide mb-2">
                    Direct Messages — Who can message the bot privately?
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    <PolicyCard
                      value="open"
                      selected={state.dm_policy === "open"}
                      onClick={() => update({ dm_policy: "open" })}
                      description="Anyone who finds the bot can start a direct conversation."
                    />
                    <PolicyCard
                      value="allowlist"
                      selected={state.dm_policy === "allowlist"}
                      onClick={() => update({ dm_policy: "allowlist" })}
                      description="Only Telegram user IDs you specify below can start a conversation."
                    />
                    <PolicyCard
                      value="pairing"
                      selected={state.dm_policy === "pairing"}
                      onClick={() => update({ dm_policy: "pairing" })}
                      description="Users must pair with a code before chatting."
                    />
                  </div>
                </div>

                {/* Allowed users (for DMs) */}
                {state.dm_policy === "allowlist" && (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Approved Telegram user IDs
                    </label>
                    <input
                      type="text"
                      placeholder="123456789, 987654321"
                      value={state.telegram_allowed_users}
                      onChange={(e) =>
                        update({ telegram_allowed_users: e.target.value })
                      }
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <p className="mt-1 text-xs text-gray-400">
                      Comma-separated. Send /start to @userinfobot to find your ID.
                    </p>
                  </div>
                )}

                {/* Per-group rules */}
                <TelegramGroupRulesEditor
                  rules={state.telegram_group_rules}
                  onChange={(rules) => update({ telegram_group_rules: rules })}
                  discoveredGroups={discoveredGroups}
                  groupsLoading={groupsLoading}
                  onRefresh={fetchGroups}
                />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
