"use client";

import { useState, useEffect, useCallback } from "react";
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
  // Telegram
  telegram_enabled: boolean;
  telegram_bot_token: string;
  telegram_bot_token_secret: string;
  telegram_use_existing_secret: boolean;
  telegram_allowed_users: string;
  dm_policy: "open" | "allowlist" | "pairing";
  telegram_group_rules: TelegramGroupRule[];
}

// ------------------------------------------------------------------ //
//  Helpers
// ------------------------------------------------------------------ //

export interface DiscoveredGroup {
  key: string;
  display_name: string;
  channel: "whatsapp" | "telegram";
  group_id: string;
  message_count?: number;
  last_message_at?: string;
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
//  Group Picker — select from discovered live groups
// ------------------------------------------------------------------ //

function GroupPicker<T extends WhatsAppGroupRule | TelegramGroupRule>({
  groups,
  loading,
  onRefresh,
  existingRules,
  onAddGroup,
  channel,
}: {
  groups: DiscoveredGroup[];
  loading: boolean;
  onRefresh: () => void;
  existingRules: T[];
  onAddGroup: (group: DiscoveredGroup) => void;
  channel: "whatsapp" | "telegram";
}) {
  const channelGroups = groups.filter((g) => g.channel === channel);
  const existingIds = new Set(
    existingRules.map((r) =>
      channel === "whatsapp"
        ? (r as WhatsAppGroupRule).group_jid
        : (r as TelegramGroupRule).group_id
    )
  );

  if (channelGroups.length === 0 && !loading) {
    return null;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
          Discovered Groups
        </span>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="flex items-center gap-1 rounded-md bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-200 transition-colors disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <RefreshCw className="h-3 w-3" />
          )}
          Refresh
        </button>
      </div>

      {loading && channelGroups.length === 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-dashed border-gray-300 bg-gray-50/50 p-4">
          <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
          <span className="text-xs text-gray-500">
            Fetching groups from the agent&apos;s live session...
          </span>
        </div>
      )}

      {channelGroups.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white divide-y divide-gray-100 max-h-64 overflow-y-auto">
          {channelGroups.map((g) => {
            const alreadyAdded = existingIds.has(g.group_id);
            return (
              <div
                key={g.key}
                className="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 transition-colors"
              >
                <Users className={`h-4 w-4 shrink-0 ${channel === "whatsapp" ? "text-green-500" : "text-blue-500"}`} />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-800 truncate block">
                    {g.display_name}
                  </span>
                  <span className="text-xs text-gray-400 font-mono truncate block">
                    {g.group_id}
                  </span>
                </div>
                {g.message_count != null && g.message_count > 0 && (
                  <span className="text-xs text-gray-400">{g.message_count} msgs</span>
                )}
                {alreadyAdded ? (
                  <span className="flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-xs text-green-600">
                    <CheckCircle2 className="h-3 w-3" />
                    Added
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => onAddGroup(g)}
                    className="flex items-center gap-1 rounded-md bg-purple-50 px-2.5 py-1 text-xs font-medium text-purple-700 hover:bg-purple-100 transition-colors"
                  >
                    <Plus className="h-3 w-3" />
                    Add Rule
                  </button>
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
//  Group Rules Editor (shared by WhatsApp & Telegram)
// ------------------------------------------------------------------ //

function GroupRulesEditor<T extends WhatsAppGroupRule | TelegramGroupRule>({
  rules,
  onChange,
  channel,
}: {
  rules: T[];
  onChange: (rules: T[]) => void;
  channel: "whatsapp" | "telegram";
}) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  const addRule = () => {
    const newRule =
      channel === "whatsapp"
        ? ({
            group_name: "",
            group_jid: "",
            policy: "open",
            require_mention: false,
            allowed_phones: [],
            instructions: "",
          } as unknown as T)
        : ({
            group_name: "",
            group_id: "",
            policy: "open",
            require_mention: true,
            allowed_users: [],
            instructions: "",
          } as unknown as T);
    onChange([...rules, newRule]);
    setExpandedIdx(rules.length);
  };

  const updateRule = (idx: number, patch: Partial<T>) => {
    const updated = rules.map((r, i) => (i === idx ? { ...r, ...patch } : r));
    onChange(updated as T[]);
  };

  const removeRule = (idx: number) => {
    onChange(rules.filter((_, i) => i !== idx));
    if (expandedIdx === idx) setExpandedIdx(null);
  };

  const idField = channel === "whatsapp" ? "group_jid" : "group_id";
  const idPlaceholder =
    channel === "whatsapp"
      ? "120363012345678@g.us"
      : "-1001234567890";
  const contactField = channel === "whatsapp" ? "allowed_phones" : "allowed_users";
  const contactPlaceholder =
    channel === "whatsapp"
      ? "+972501234567, +14155551234"
      : "123456789, 987654321";
  const contactLabel =
    channel === "whatsapp" ? "Allowed phone numbers" : "Allowed user IDs";

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-600 uppercase tracking-wide">
          Per-Group Rules
        </span>
      </div>

      {rules.length === 0 && (
        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/50 p-4 text-center">
          <Users className="h-6 w-6 mx-auto text-gray-300 mb-1" />
          <p className="text-xs text-gray-500">
            No per-group rules yet. The default policy above applies to all groups.
          </p>
          <p className="text-xs text-gray-400 mt-1">
            Select a group from the discovered list above to add a rule.
          </p>
        </div>
      )}

      {rules.map((rule, idx) => {
        const isExpanded = expandedIdx === idx;
        const policyInfo = POLICY_LABELS[rule.policy];
        const PolicyIcon = policyInfo.icon;
        const displayName =
          rule.group_name || (rule as WhatsAppGroupRule).group_jid || (rule as TelegramGroupRule).group_id || `Group ${idx + 1}`;

        return (
          <div
            key={idx}
            className="rounded-lg border border-gray-200 bg-white overflow-hidden"
          >
            {/* Collapsed header */}
            <button
              type="button"
              onClick={() => setExpandedIdx(isExpanded ? null : idx)}
              className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-gray-50 transition-colors"
            >
              <PolicyIcon className={`h-4 w-4 shrink-0 ${rule.policy === "blocked" ? "text-red-500" : rule.policy === "allowlist" ? "text-blue-500" : "text-green-500"}`} />
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-gray-800 truncate block">
                  {displayName}
                </span>
                <span className="text-xs text-gray-400">
                  {policyInfo.label}
                  {rule.require_mention && " · @mention required"}
                  {rule.instructions && " · has custom instructions"}
                </span>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  removeRule(idx);
                }}
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

            {/* Expanded details */}
            {isExpanded && (
              <div className="border-t border-gray-100 px-4 py-3 space-y-3 bg-gray-50/30">
                {/* Group name */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Group Name (label for your reference)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Sales Team, Support Group"
                    value={rule.group_name}
                    onChange={(e) => updateRule(idx, { group_name: e.target.value } as Partial<T>)}
                    className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                  />
                </div>

                {/* Group ID */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Group ID
                  </label>
                  <input
                    type="text"
                    placeholder={idPlaceholder}
                    value={(rule as unknown as Record<string, string>)[idField] || ""}
                    readOnly
                    className="w-full rounded-md border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm font-mono text-gray-500 cursor-not-allowed"
                  />
                </div>

                {/* Access policy */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-2">
                    Who can interact with the agent in this group?
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    <PolicyCard
                      value="open"
                      selected={rule.policy === "open"}
                      onClick={() => updateRule(idx, { policy: "open" } as Partial<T>)}
                      description="The agent responds to all messages from any group member."
                    />
                    <PolicyCard
                      value="allowlist"
                      selected={rule.policy === "allowlist"}
                      onClick={() => updateRule(idx, { policy: "allowlist" } as Partial<T>)}
                      description="The agent only responds to messages from approved contacts."
                    />
                    <PolicyCard
                      value="blocked"
                      selected={rule.policy === "blocked"}
                      onClick={() => updateRule(idx, { policy: "blocked" } as Partial<T>)}
                      description="The agent ignores all messages in this group."
                    />
                  </div>
                </div>

                {/* Allowed contacts (only for allowlist) */}
                {rule.policy === "allowlist" && (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      {contactLabel}
                    </label>
                    <input
                      type="text"
                      placeholder={contactPlaceholder}
                      value={(rule as unknown as Record<string, string[]>)[contactField]?.join(", ") || ""}
                      onChange={(e) =>
                        updateRule(idx, {
                          [contactField]: e.target.value
                            .split(",")
                            .map((s) => s.trim())
                            .filter(Boolean),
                        } as Partial<T>)
                      }
                      className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                    />
                  </div>
                )}

                {/* Require @mention */}
                {rule.policy !== "blocked" && (
                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={rule.require_mention}
                      onChange={(e) =>
                        updateRule(idx, { require_mention: e.target.checked } as Partial<T>)
                      }
                      className="rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                    />
                    <AtSign className="h-3.5 w-3.5 text-gray-400" />
                    <span>Require @mention to respond</span>
                  </label>
                )}

                {/* Per-group instructions */}
                {rule.policy !== "blocked" && (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Group-specific instructions
                    </label>
                    <textarea
                      placeholder="Optional instructions for this group. These are appended to the agent's main system prompt when responding in this group.&#10;&#10;Example: You are helping the Sales team. Focus on lead qualification, pricing questions, and competitive analysis."
                      value={rule.instructions}
                      onChange={(e) =>
                        updateRule(idx, { instructions: e.target.value } as Partial<T>)
                      }
                      rows={3}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500 resize-y"
                    />
                    <p className="mt-1 text-xs text-gray-400">
                      Leave empty to use the agent&apos;s default system prompt. When set, these instructions are appended to the main prompt for messages in this group.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ //
//  Main Channel Wizard
// ------------------------------------------------------------------ //

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

  const fetchGroups = useCallback(async () => {
    if (!agentId) return;
    setGroupsLoading(true);
    try {
      const res = await fetch(`/api/v1/agents/${agentId}/groups`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setDiscoveredGroups(data.groups || []);
      }
    } catch {
      // silently fail — groups section just won't appear
    } finally {
      setGroupsLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    fetchGroups();
  }, [fetchGroups]);

  const addWhatsAppGroupFromDiscovery = (g: DiscoveredGroup) => {
    const rule: WhatsAppGroupRule = {
      group_name: g.display_name,
      group_jid: g.group_id,
      policy: "open",
      require_mention: false,
      allowed_phones: [],
      instructions: "",
    };
    update({ whatsapp_group_rules: [...state.whatsapp_group_rules, rule] });
  };

  const addTelegramGroupFromDiscovery = (g: DiscoveredGroup) => {
    const rule: TelegramGroupRule = {
      group_name: g.display_name,
      group_id: g.group_id,
      policy: "open",
      require_mention: true,
      allowed_users: [],
      instructions: "",
    };
    update({ telegram_group_rules: [...state.telegram_group_rules, rule] });
  };

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
          <div className="border-t border-gray-100 px-4 py-4 bg-gray-50/30 space-y-4">
            {/* Info banner */}
            <div className="flex gap-2 rounded-md bg-green-50 border border-green-200 p-3">
              <Info className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
              <p className="text-xs text-green-800">
                {mode === "create"
                  ? "After deploying, link WhatsApp by scanning a QR code from the agent page. You'll then be able to browse your groups and set per-group policies."
                  : "Link WhatsApp by scanning a QR code. The session persists on the agent's storage — no token or password needed."}
              </p>
            </div>

            {/* Everything below is manage-mode only */}
            {mode === "manage" && (
              <>
                {/* DM Policy */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide mb-2">
                    Direct Messages — Who can message the agent privately?
                  </label>
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
                      description="Only phone numbers you specify below can send direct messages."
                    />
                    <PolicyCard
                      value="pairing"
                      selected={state.whatsapp_dm_policy === "pairing"}
                      onClick={() => update({ whatsapp_dm_policy: "pairing" })}
                      description="Users request access with a code. You approve each one."
                    />
                  </div>
                </div>

                {/* Allowed phones (for DMs) */}
                {state.whatsapp_dm_policy === "allowlist" && (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Approved phone numbers (for direct messages)
                    </label>
                    <input
                      type="text"
                      placeholder="+972501234567, +14155551234"
                      value={state.whatsapp_allowed_phones}
                      onChange={(e) =>
                        update({ whatsapp_allowed_phones: e.target.value })
                      }
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
                    />
                    <p className="mt-1 text-xs text-gray-400">
                      International format with country code, comma-separated.
                    </p>
                  </div>
                )}

                {/* Default Group Policy */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 uppercase tracking-wide mb-2">
                    Groups — Default behavior for all groups
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    <PolicyCard
                      value="open"
                      selected={state.whatsapp_group_policy === "open"}
                      onClick={() => update({ whatsapp_group_policy: "open" })}
                      description="The agent responds in any group it's added to. Override per group below."
                    />
                    <PolicyCard
                      value="allowlist"
                      selected={state.whatsapp_group_policy === "allowlist"}
                      onClick={() => update({ whatsapp_group_policy: "allowlist" })}
                      description="The agent only responds in groups you explicitly add as rules below."
                    />
                  </div>
                </div>

                {/* Discovered groups (live from agent) */}
                {agentId && (
                  <GroupPicker<WhatsAppGroupRule>
                    groups={discoveredGroups}
                    loading={groupsLoading}
                    onRefresh={fetchGroups}
                    existingRules={state.whatsapp_group_rules}
                    onAddGroup={addWhatsAppGroupFromDiscovery}
                    channel="whatsapp"
                  />
                )}

                {/* Per-group rules */}
                <GroupRulesEditor<WhatsAppGroupRule>
                  rules={state.whatsapp_group_rules}
                  onChange={(rules) => update({ whatsapp_group_rules: rules })}
                  channel="whatsapp"
                />
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

                {/* Discovered groups (live from agent) */}
                {agentId && (
                  <GroupPicker<TelegramGroupRule>
                    groups={discoveredGroups}
                    loading={groupsLoading}
                    onRefresh={fetchGroups}
                    existingRules={state.telegram_group_rules}
                    onAddGroup={addTelegramGroupFromDiscovery}
                    channel="telegram"
                  />
                )}

                {/* Per-group rules */}
                <GroupRulesEditor<TelegramGroupRule>
                  rules={state.telegram_group_rules}
                  onChange={(rules) => update({ telegram_group_rules: rules })}
                  channel="telegram"
                />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
