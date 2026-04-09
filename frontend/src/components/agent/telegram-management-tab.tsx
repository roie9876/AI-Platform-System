"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/api";
import {
  Send,
  Phone,
  Users,
  Shield,
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
  Eye,
  EyeOff,
  Key,
} from "lucide-react";
import type { TelegramGroupRule, ChannelWizardState, DiscoveredGroup } from "./channel-wizard";

// ------------------------------------------------------------------ //
//  Policy card
// ------------------------------------------------------------------ //

const POLICY_LABELS = {
  open: { label: "Agent responds", icon: Globe, color: "text-green-600 bg-green-50 border-green-200" },
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
          <Icon className="h-5 w-5 text-blue-500" />
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
}: {
  rule: TelegramGroupRule;
  idx: number;
  isExpanded: boolean;
  onToggle: () => void;
  onUpdate: (patch: Partial<TelegramGroupRule>) => void;
  onRemove: () => void;
}) {
  const policyInfo = POLICY_LABELS[rule.policy] || POLICY_LABELS.open;
  const PolicyIcon = policyInfo.icon;
  const displayName = rule.group_name || rule.group_id || `Group ${idx + 1}`;
  const hasId = Boolean(rule.group_id);

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
      >
        <Users className={`h-4 w-4 shrink-0 ${hasId ? "text-blue-500" : "text-amber-400"}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-800 truncate">{displayName}</span>
            {hasId && (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700">
                <CheckCircle2 className="h-2.5 w-2.5" /> ID set
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
              placeholder="e.g. Dev Team"
              value={rule.group_name}
              onChange={(e) => onUpdate({ group_name: e.target.value })}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Group ID */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Group / Chat ID <span className="font-normal text-gray-400">(numeric)</span>
            </label>
            <input
              type="text"
              placeholder="-1001234567890"
              value={rule.group_id}
              onChange={(e) => onUpdate({ group_id: e.target.value })}
              className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-400">
              Send <code className="bg-gray-200 rounded px-1">/chatid</code> in the group while the bot is present.
            </p>
          </div>

          {/* Policy */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-2">Agent behavior in this group</label>
            <div className="grid grid-cols-1 gap-2">
              <PolicyCard value="open" selected={rule.policy === "open"} onClick={() => onUpdate({ policy: "open" })}
                description="Agent responds to relevant messages." />
              <PolicyCard value="allowlist" selected={rule.policy === "allowlist"} onClick={() => onUpdate({ policy: "allowlist" })}
                description="Only approved users can interact with the agent." />
              <PolicyCard value="blocked" selected={rule.policy === "blocked"} onClick={() => onUpdate({ policy: "blocked" })}
                description="Agent ignores all messages in this group." />
            </div>
          </div>

          {/* Require @mention */}
          {rule.policy !== "blocked" && (
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={rule.require_mention}
                onChange={(e) => onUpdate({ require_mention: e.target.checked })}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <AtSign className="h-3.5 w-3.5 text-gray-400" />
              Require @mention to respond
            </label>
          )}

          {/* Per-group allowed users */}
          {rule.policy === "allowlist" && (
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Allowed user IDs</label>
              <input
                type="text"
                placeholder="123456789, 987654321"
                value={rule.allowed_users.join(", ")}
                onChange={(e) =>
                  onUpdate({
                    allowed_users: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
                className="w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <p className="mt-1 text-xs text-gray-400">Numeric Telegram user IDs, comma-separated.</p>
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
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
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

interface TelegramManagementTabProps {
  agentId: string;
  channels: ChannelWizardState;
  onChannelsChange: (channels: ChannelWizardState) => void;
}

export function TelegramManagementTab({
  agentId,
  channels,
  onChannelsChange,
}: TelegramManagementTabProps) {
  const update = (patch: Partial<ChannelWizardState>) =>
    onChannelsChange({ ...channels, ...patch });

  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [showToken, setShowToken] = useState(false);

  const addRule = () => {
    const rule: TelegramGroupRule = {
      group_name: "",
      group_id: "",
      policy: "open",
      require_mention: true,
      allowed_users: [],
      instructions: "",
    };
    update({ telegram_group_rules: [...channels.telegram_group_rules, rule] });
    setExpandedIdx(channels.telegram_group_rules.length);
  };

  const updateRule = (idx: number, patch: Partial<TelegramGroupRule>) => {
    update({
      telegram_group_rules: channels.telegram_group_rules.map((r, i) =>
        i === idx ? { ...r, ...patch } : r
      ),
    });
  };

  const removeRule = (idx: number) => {
    update({
      telegram_group_rules: channels.telegram_group_rules.filter((_, i) => i !== idx),
    });
    if (expandedIdx === idx) setExpandedIdx(null);
    else if (expandedIdx !== null && expandedIdx > idx) setExpandedIdx(expandedIdx - 1);
  };

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto py-6 px-4 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-blue-100">
              <Send className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Telegram</h2>
              <p className="text-sm text-gray-500">Manage the bot, direct messages, and groups</p>
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-xs text-gray-500">Enabled</span>
            <div className="relative">
              <input
                type="checkbox"
                checked={channels.telegram_enabled}
                onChange={(e) => update({ telegram_enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-gray-200 peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer peer-checked:bg-blue-500 transition-colors" />
              <div className="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow peer-checked:translate-x-4 transition-transform" />
            </div>
          </label>
        </div>

        {!channels.telegram_enabled ? (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
            <Send className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-600">Telegram is disabled</p>
            <p className="text-xs text-gray-400 mt-1">Enable Telegram above to configure the bot.</p>
          </div>
        ) : (
          <>
            {/* Bot Token */}
            <Section title="Bot Token" icon={Key} description="Your Telegram bot token from @BotFather.">
              {channels.telegram_use_existing_secret ? (
                <div className="flex items-center gap-2 rounded-md border border-gray-200 bg-gray-100 px-3 py-2">
                  <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                  <span className="text-sm text-gray-600 flex-1">Token stored as Kubernetes secret</span>
                  <button
                    type="button"
                    onClick={() => update({ telegram_use_existing_secret: false })}
                    className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                  >
                    Change
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="relative">
                    <input
                      type={showToken ? "text" : "password"}
                      placeholder="110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
                      value={channels.telegram_bot_token}
                      onChange={(e) => update({ telegram_bot_token: e.target.value })}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono pr-10 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />
                    <button
                      type="button"
                      onClick={() => setShowToken(!showToken)}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                    >
                      {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                  <p className="text-xs text-gray-400">
                    Created via <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-blue-500 underline">@BotFather</a>.
                    Stored securely as a Kubernetes secret after save.
                  </p>
                </div>
              )}
            </Section>

            {/* Direct Messages */}
            <Section
              title="Direct Messages"
              icon={Phone}
              description="Control who can send private messages to the bot."
            >
              <div className="grid grid-cols-1 gap-2">
                <PolicyCard
                  value="open"
                  selected={channels.dm_policy === "open"}
                  onClick={() => update({ dm_policy: "open" })}
                  description="Anyone who finds the bot can start a DM conversation."
                />
                <PolicyCard
                  value="allowlist"
                  selected={channels.dm_policy === "allowlist"}
                  onClick={() => update({ dm_policy: "allowlist" })}
                  description="Only approved Telegram user IDs can send messages."
                />
                <PolicyCard
                  value="pairing"
                  selected={channels.dm_policy === "pairing"}
                  onClick={() => update({ dm_policy: "pairing" })}
                  description="New users send /start and get a pairing code to approve."
                />
              </div>
              {channels.dm_policy === "allowlist" && (
                <div className="mt-3">
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Allowed user IDs
                  </label>
                  <input
                    type="text"
                    placeholder="123456789, 987654321"
                    value={channels.telegram_allowed_users}
                    onChange={(e) => update({ telegram_allowed_users: e.target.value })}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <p className="mt-1 text-xs text-gray-400">
                    Numeric Telegram user IDs, comma-separated. Use <code className="bg-gray-200 rounded px-1">/myid</code> to find yours.
                  </p>
                </div>
              )}
            </Section>

            {/* Per-Group Rules */}
            <Section
              title="Group Rules"
              icon={Users}
              description="Control the agent's behavior in specific Telegram groups."
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex gap-2 rounded-lg border border-blue-200 bg-blue-50 p-2.5 flex-1">
                  <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
                  <p className="text-xs text-blue-800">
                    Telegram groups require a numeric chat ID. Add the bot to the group, then
                    send <code className="bg-blue-100 rounded px-1">/chatid</code> to get it.
                  </p>
                </div>
              </div>

              {/* Rules list */}
              {channels.telegram_group_rules.length === 0 ? (
                <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/50 p-6 text-center">
                  <Users className="h-8 w-8 mx-auto text-gray-300 mb-2" />
                  <p className="text-sm font-medium text-gray-600">No group rules</p>
                  <p className="text-xs text-gray-400 mt-1 max-w-sm mx-auto">
                    Add a group to give the agent access. Without rules, the bot won&apos;t respond in any group.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {channels.telegram_group_rules.map((rule, idx) => (
                    <GroupRuleCard
                      key={idx}
                      rule={rule}
                      idx={idx}
                      isExpanded={expandedIdx === idx}
                      onToggle={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
                      onUpdate={(patch) => updateRule(idx, patch)}
                      onRemove={() => removeRule(idx)}
                    />
                  ))}
                </div>
              )}

              <button
                type="button"
                onClick={addRule}
                className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-2 text-xs font-medium text-white hover:bg-blue-700 transition-colors mt-2"
              >
                <Plus className="h-3.5 w-3.5" />
                Add Group Rule
              </button>
            </Section>

            {/* Channel Instructions */}
            <Section
              title="Channel Instructions"
              icon={Settings2}
              description="Extra instructions applied to ALL Telegram conversations (DMs and groups). Appended to the agent's system prompt."
            >
              <textarea
                rows={4}
                placeholder="Example: Use Telegram markdown formatting. Keep messages concise."
                value={channels.telegram_channel_instructions}
                onChange={(e) => update({ telegram_channel_instructions: e.target.value })}
                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-y"
              />
              <p className="text-xs text-gray-400">
                Leave empty to use only the main system prompt.
              </p>
            </Section>
          </>
        )}
      </div>
    </div>
  );
}
