"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/api";
import {
  MessageCircle,
  Phone,
  Users,
  Shield,
  Eye,
  Globe,
  Lock,
  Ban,
  UserCheck,
  AtSign,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Search,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Info,
  Settings2,
  QrCode,
} from "lucide-react";
import type { WhatsAppGroupRule, ChannelWizardState, DiscoveredGroup } from "./channel-wizard";

// ------------------------------------------------------------------ //
//  Policy card (reusable)
// ------------------------------------------------------------------ //

const POLICY_LABELS = {
  active: { label: "Agent responds", icon: Globe, color: "text-green-600 bg-green-50 border-green-200" },
  open: { label: "Open to all", icon: Globe, color: "text-green-600 bg-green-50 border-green-200" },
  observe: { label: "Silent monitor", icon: Eye, color: "text-purple-600 bg-purple-50 border-purple-200" },
  allowlist: { label: "Approved only", icon: UserCheck, color: "text-blue-600 bg-blue-50 border-blue-200" },
  pairing: { label: "Pairing code", icon: Lock, color: "text-amber-600 bg-amber-50 border-amber-200" },
  blocked: { label: "Blocked", icon: Ban, color: "text-red-600 bg-red-50 border-red-200" },
  disabled: { label: "Disabled", icon: Ban, color: "text-gray-600 bg-gray-50 border-gray-200" },
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
//  Section wrapper
// ------------------------------------------------------------------ //

function Section({ title, icon: Icon, description, children }: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 bg-gray-50/50">
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-green-600" />
          <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        </div>
        {description && (
          <p className="mt-1 text-xs text-gray-500">{description}</p>
        )}
      </div>
      <div className="px-5 py-4 space-y-4">
        {children}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Per-group rule row
// ------------------------------------------------------------------ //

function GroupRuleCard({
  rule,
  idx,
  isExpanded,
  onToggle,
  onUpdate,
  onRemove,
  discoveredGroups,
  existingJids,
  observeGuardActive,
}: {
  rule: WhatsAppGroupRule;
  idx: number;
  isExpanded: boolean;
  onToggle: () => void;
  onUpdate: (patch: Partial<WhatsAppGroupRule>) => void;
  onRemove: () => void;
  discoveredGroups: DiscoveredGroup[];
  existingJids: Set<string>;
  observeGuardActive: boolean;
}) {
  const waGroups = discoveredGroups.filter((g) => g.channel === "whatsapp");
  const resolved = Boolean(rule.group_jid);
  const policyInfo = POLICY_LABELS[rule.policy] || POLICY_LABELS.active;
  const PolicyIcon = policyInfo.icon;
  const displayName = rule.group_name || rule.group_jid || `Group ${idx + 1}`;

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
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
            {(rule.require_mention || (observeGuardActive && rule.policy !== "observe")) && " · @mention required"}
            {observeGuardActive && rule.policy !== "observe" && !rule.require_mention && " (forced)"}
            {rule.instructions && " · custom instructions"}
          </span>
        </div>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
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

      {isExpanded && (
        <div className="border-t border-gray-100 px-5 py-4 space-y-4 bg-gray-50/30">
          {/* Group name */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Group name</label>
            <input
              type="text"
              placeholder="e.g. Sales Team"
              value={rule.group_name}
              onChange={(e) => onUpdate({ group_name: e.target.value })}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
            />
          </div>

          {/* Group ID resolution */}
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
                  <strong>Pending resolution.</strong> Pick a matching group below, or wait — the system resolves the JID automatically when the first message arrives.
                </p>
              </div>
              {(() => {
                const availableGroups = waGroups.filter((g) => !existingJids.has(g.group_id));
                if (availableGroups.length === 0) return (
                  <p className="text-xs text-gray-500 italic">No undiscovered groups available.</p>
                );
                const sorted = [...availableGroups].sort((a, b) => {
                  if (a.has_name && !b.has_name) return -1;
                  if (!a.has_name && b.has_name) return 1;
                  return (a.display_name || "").localeCompare(b.display_name || "");
                });
                return (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Pick from discovered groups</label>
                    <select
                      className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
                      value=""
                      onChange={(e) => {
                        const picked = sorted.find((g) => g.group_id === e.target.value);
                        if (picked) {
                          onUpdate({ group_jid: picked.group_id, group_name: rule.group_name || picked.display_name });
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

          {/* Policy */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">Agent behavior in this group</label>
            <div className="grid grid-cols-1 gap-2">
              <PolicyCard value="active" selected={rule.policy === "active"} onClick={() => onUpdate({ policy: "active" })}
                description="Agent responds to messages (sender filtering uses the global approved phones)." />
              <PolicyCard value="observe" selected={rule.policy === "observe"} onClick={() => onUpdate({ policy: "observe", require_mention: false })}
                description="Agent silently monitors all messages and stores them. Only the owner can interact." />
              <PolicyCard value="blocked" selected={rule.policy === "blocked"} onClick={() => onUpdate({ policy: "blocked" })}
                description="Agent ignores all messages in this group." />
            </div>
          </div>

          {/* Require @mention */}
          {rule.policy !== "blocked" && rule.policy !== "observe" && (
            <div className="space-y-1">
              <label className={`flex items-center gap-2 text-sm text-gray-700 select-none ${observeGuardActive ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}>
                <input
                  type="checkbox"
                  checked={observeGuardActive ? true : rule.require_mention}
                  onChange={(e) => onUpdate({ require_mention: e.target.checked })}
                  disabled={observeGuardActive}
                  className="rounded border-gray-300 text-green-600 focus:ring-green-500 disabled:opacity-50"
                />
                <AtSign className="h-3.5 w-3.5 text-gray-400" />
                Require @mention to respond
                {observeGuardActive && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 px-2 py-0.5 text-[10px] font-medium text-purple-700 border border-purple-200">
                    <Lock className="h-2.5 w-2.5" /> Forced by observe mode
                  </span>
                )}
              </label>
            </div>
          )}

          {/* Per-group instructions */}
          {rule.policy !== "blocked" && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Group-specific instructions <span className="font-normal text-gray-400">(optional)</span>
              </label>
              <textarea
                placeholder="Extra instructions for this group, appended to the system prompt."
                value={rule.instructions}
                onChange={(e) => onUpdate({ instructions: e.target.value })}
                rows={3}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500 resize-y"
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Main component
// ------------------------------------------------------------------ //

interface WhatsAppManagementTabProps {
  agentId: string;
  channels: ChannelWizardState;
  onChannelsChange: (channels: ChannelWizardState) => void;
  whatsappStatus?: string | null;
  onLinkWhatsApp?: () => void;
  whatsappQrUrl?: string | null;
  whatsappLinking?: boolean;
}

export function WhatsAppManagementTab({
  agentId,
  channels,
  onChannelsChange,
  whatsappStatus,
  onLinkWhatsApp,
  whatsappQrUrl,
  whatsappLinking,
}: WhatsAppManagementTabProps) {
  const update = (patch: Partial<ChannelWizardState>) =>
    onChannelsChange({ ...channels, ...patch });

  // Live group discovery
  const [discoveredGroups, setDiscoveredGroups] = useState<DiscoveredGroup[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [cacheRefreshing, setCacheRefreshing] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  const fetchGroups = useCallback(async () => {
    if (!agentId) return;
    setGroupsLoading(true);
    try {
      const data = await apiFetch<{ groups: DiscoveredGroup[] }>(
        `/api/v1/agents/${agentId}/groups`
      );
      setDiscoveredGroups(data.groups || []);
    } catch { /* silently fail */ } finally {
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
    } catch { /* silently fail */ } finally {
      setCacheRefreshing(false);
    }
  }, [agentId, fetchGroups]);

  useEffect(() => { fetchGroups(); }, [fetchGroups]);

  // Click-outside for suggestions
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const waGroups = discoveredGroups.filter((g) => g.channel === "whatsapp");
  const existingJids = new Set(channels.whatsapp_group_rules.map((r) => r.group_jid).filter(Boolean));

  const suggestions = waGroups.filter(
    (g) =>
      !existingJids.has(g.group_id) &&
      (!searchQuery.trim() ||
        g.display_name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const addFromDiscovery = (g: DiscoveredGroup) => {
    const rule: WhatsAppGroupRule = {
      group_name: g.display_name,
      group_jid: g.group_id,
      policy: "active",
      require_mention: true,
      allowed_phones: [],
      instructions: "",
    };
    update({ whatsapp_group_rules: [...channels.whatsapp_group_rules, rule] });
    setExpandedIdx(channels.whatsapp_group_rules.length);
    setSearchQuery("");
    setShowSuggestions(false);
  };

  const addManual = () => {
    const name = searchQuery.trim();
    if (!name) return;
    const match = waGroups.find(
      (g) => g.display_name.toLowerCase() === name.toLowerCase()
    );
    if (match && !existingJids.has(match.group_id)) {
      addFromDiscovery(match);
      return;
    }
    const rule: WhatsAppGroupRule = {
      group_name: name,
      group_jid: "",
      policy: "active",
      require_mention: true,
      allowed_phones: [],
      instructions: "",
    };
    update({ whatsapp_group_rules: [...channels.whatsapp_group_rules, rule] });
    setExpandedIdx(channels.whatsapp_group_rules.length);
    setSearchQuery("");
    setShowSuggestions(false);
  };

  const updateRule = (idx: number, patch: Partial<WhatsAppGroupRule>) => {
    update({
      whatsapp_group_rules: channels.whatsapp_group_rules.map((r, i) =>
        i === idx ? { ...r, ...patch } : r
      ),
    });
  };

  const removeRule = (idx: number) => {
    update({
      whatsapp_group_rules: channels.whatsapp_group_rules.filter((_, i) => i !== idx),
    });
    if (expandedIdx === idx) setExpandedIdx(null);
    else if (expandedIdx !== null && expandedIdx > idx) setExpandedIdx(expandedIdx - 1);
  };

  // When any group is in observe mode, groupAllowFrom is set to ["*"]
  // globally.  To prevent the bot from going wild in non-observe groups,
  // the backend forces requireMention=true on them.  The UI reflects this.
  const hasObserveGroups = channels.whatsapp_group_rules.some(
    (r) => r.policy === "observe"
  );

  const isConnected = whatsappStatus === "connected";

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto py-6 px-4 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-green-100">
              <MessageCircle className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">WhatsApp</h2>
              <p className="text-sm text-gray-500">Manage direct messages, groups, and behavior</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Enable toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-xs text-gray-500">Enabled</span>
              <div className="relative">
                <input
                  type="checkbox"
                  checked={channels.whatsapp_enabled}
                  onChange={(e) => update({ whatsapp_enabled: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-gray-200 peer-focus:ring-2 peer-focus:ring-green-300 rounded-full peer peer-checked:bg-green-500 transition-colors" />
                <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow peer-checked:translate-x-4 transition-transform" />
              </div>
            </label>
            {/* Connection status */}
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
              isConnected
                ? "bg-green-50 text-green-700 border border-green-200"
                : "bg-gray-50 text-gray-600 border border-gray-200"
            }`}>
              <span className={`h-2 w-2 rounded-full ${isConnected ? "bg-green-500" : "bg-gray-400"}`} />
              {isConnected ? "Connected" : whatsappStatus || "Not linked"}
            </span>
          </div>
        </div>

        {!channels.whatsapp_enabled ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
            <MessageCircle className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-600">WhatsApp is disabled</p>
            <p className="text-xs text-gray-400 mt-1">Enable WhatsApp above to configure messaging settings.</p>
          </div>
        ) : (
          <>
            {/* Connection / QR section */}
            {!isConnected && (
              <div className="rounded-xl border border-green-200 bg-green-50 p-5">
                <div className="flex items-start gap-3">
                  <QrCode className="h-6 w-6 text-green-600 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <h4 className="text-sm font-semibold text-green-900">Link WhatsApp</h4>
                    <p className="text-xs text-green-700 mt-1">
                      Scan a QR code with WhatsApp on your phone to connect. The session persists on the agent&apos;s storage — no token or password needed.
                    </p>
                    {whatsappQrUrl && (
                      <div className="mt-3 flex justify-center">
                        <img src={whatsappQrUrl} alt="WhatsApp QR Code" className="h-48 w-48 rounded-lg border border-green-200" />
                      </div>
                    )}
                    {onLinkWhatsApp && (
                      <button
                        type="button"
                        onClick={onLinkWhatsApp}
                        disabled={whatsappLinking}
                        className="mt-3 inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        {whatsappLinking ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <QrCode className="h-4 w-4" />
                        )}
                        {whatsappLinking ? "Generating QR…" : "Generate QR Code"}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Section 1: Direct Messages */}
            <Section
              title="Direct Messages"
              icon={Phone}
              description="Control who can send private messages to the agent."
            >
              <div className="grid grid-cols-1 gap-2">
                <PolicyCard
                  value="open"
                  selected={channels.whatsapp_dm_policy === "open"}
                  onClick={() => update({ whatsapp_dm_policy: "open" })}
                  description="Anyone with the phone number can send direct messages."
                />
                <PolicyCard
                  value="allowlist"
                  selected={channels.whatsapp_dm_policy === "allowlist"}
                  onClick={() => update({ whatsapp_dm_policy: "allowlist" })}
                  description="Only approved phone numbers can send direct messages."
                />
                <PolicyCard
                  value="pairing"
                  selected={channels.whatsapp_dm_policy === "pairing"}
                  onClick={() => update({ whatsapp_dm_policy: "pairing" })}
                  description="New users request a pairing code, you approve each one."
                />
              </div>
              {channels.whatsapp_dm_policy === "allowlist" && (
                <div className="mt-3">
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Approved phone numbers
                  </label>
                  <input
                    type="text"
                    placeholder="+972501234567, +14155551234"
                    value={channels.whatsapp_allowed_phones}
                    onChange={(e) => update({ whatsapp_allowed_phones: e.target.value })}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
                  />
                  <p className="mt-1 text-xs text-gray-400">
                    International format with country code, comma-separated.
                  </p>
                </div>
              )}
            </Section>

            {/* Section 2: Default Group Policy */}
            <Section
              title="Group Defaults"
              icon={Shield}
              description="Default behavior for ALL groups. Override specific groups below."
            >
              <div className="grid grid-cols-1 gap-2">
                <PolicyCard
                  value="allowlist"
                  selected={channels.whatsapp_group_policy === "allowlist"}
                  onClick={() => update({ whatsapp_group_policy: "allowlist" })}
                  description="Agent stays silent in all groups unless you add a specific rule below. This is the safest default."
                />
                <PolicyCard
                  value="open"
                  selected={channels.whatsapp_group_policy === "open"}
                  onClick={() => update({ whatsapp_group_policy: "open" })}
                  description="Agent responds in every group it's added to. Per-group rules below can override."
                />
              </div>
              <div className="flex gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3 mt-2">
                <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
                <div className="text-xs text-blue-800">
                  <p>
                    <strong>What happens to unlisted groups?</strong>{" "}
                    {channels.whatsapp_group_policy === "allowlist"
                      ? "Groups not listed below are completely invisible to the agent — messages are dropped before reaching the AI."
                      : "Groups not listed below still receive responses. The agent uses @mention gating by default."}
                  </p>
                </div>
              </div>
            </Section>

            {/* Section 3: Per-Group Rules */}
            <Section
              title="Per-Group Rules"
              icon={Users}
              description="Override the default behavior for specific groups."
            >
              {/* Search / Add */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={refreshGroupCache}
                    disabled={groupsLoading || cacheRefreshing}
                    title="Sync group names from WhatsApp (brief reconnect)"
                    className="flex items-center gap-1 rounded-md bg-green-50 px-2.5 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 border border-green-200 transition-colors disabled:opacity-50"
                  >
                    {cacheRefreshing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                    {cacheRefreshing ? "Syncing…" : "Sync from WhatsApp"}
                  </button>
                </div>
              </div>

              <div ref={searchRef} className="relative">
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
                    <input
                      type="text"
                      placeholder="Search or type a group name to add…"
                      value={searchQuery}
                      onChange={(e) => { setSearchQuery(e.target.value); setShowSuggestions(true); }}
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
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="px-3 py-2.5 text-xs text-gray-500">
                        {searchQuery.trim()
                          ? "No matching groups. Press Enter to add by name."
                          : "All discovered groups already added."}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* No groups hint */}
              {waGroups.length === 0 && !groupsLoading && (
                <div className="flex gap-2.5 rounded-lg border border-amber-200 bg-amber-50 p-3 mt-3">
                  <AlertCircle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                  <div className="text-xs text-amber-800 space-y-1">
                    <p className="font-medium">No groups discovered yet</p>
                    <p>Groups appear when any message is sent while WhatsApp is linked. You can still type a name above and add it manually.</p>
                  </div>
                </div>
              )}

              {/* Observe mode safety banner */}
              {hasObserveGroups && (
                <div className="flex gap-2.5 rounded-lg border border-purple-200 bg-purple-50 p-3 mt-3">
                  <Eye className="h-4 w-4 text-purple-500 shrink-0 mt-0.5" />
                  <div className="text-xs text-purple-800">
                    <p>
                      <strong>Observe mode active.</strong>{" "}
                      To capture all messages in observed groups, the agent accepts messages from all senders.
                      For safety, <strong>@mention is forced on all other groups</strong> — the agent will only respond when explicitly mentioned.
                    </p>
                  </div>
                </div>
              )}

              {/* Rules list */}
              {channels.whatsapp_group_rules.length === 0 ? (
                <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/50 p-6 text-center mt-3">
                  <Users className="h-8 w-8 mx-auto text-gray-300 mb-2" />
                  <p className="text-sm font-medium text-gray-600">No per-group rules</p>
                  <p className="text-xs text-gray-400 mt-1 max-w-sm mx-auto">
                    The default group policy applies to all groups. Add a rule above to customize specific groups.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 mt-3">
                  {channels.whatsapp_group_rules.map((rule, idx) => (
                    <GroupRuleCard
                      key={idx}
                      rule={rule}
                      idx={idx}
                      isExpanded={expandedIdx === idx}
                      onToggle={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                      onUpdate={(patch) => updateRule(idx, patch)}
                      onRemove={() => removeRule(idx)}
                      discoveredGroups={discoveredGroups}
                      existingJids={existingJids}
                      observeGuardActive={hasObserveGroups}
                    />
                  ))}
                </div>
              )}
            </Section>

            {/* Section 4: Global Instructions */}
            <Section
              title="Channel Instructions"
              icon={Settings2}
              description="Extra instructions applied to ALL WhatsApp conversations (DMs and groups). Appended to the agent's system prompt."
            >
              <textarea
                rows={4}
                placeholder="Example: Keep messages short and use emoji. Always respond in the language the user writes in."
                value={channels.whatsapp_channel_instructions}
                onChange={(e) => update({ whatsapp_channel_instructions: e.target.value })}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500 resize-y"
              />
              <p className="text-xs text-gray-400">
                Leave empty to use only the main system prompt. Per-group instructions are stacked on top of these.
              </p>
            </Section>
          </>
        )}
      </div>
    </div>
  );
}
