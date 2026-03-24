"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Bot,
  Zap,
  Wrench,
  BookOpen,
  FolderOpen,
  GitBranch,
  Sparkles,
  Database,
  ClipboardCheck,
  Shield,
  Cloud,
  PanelLeftClose,
  PanelLeft,
  BarChart3,
  Store,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  enabled: boolean;
}

const navItems: NavItem[] = [
  { href: "/dashboard/agents", label: "Agents", icon: Bot, enabled: true },
  { href: "/dashboard/models", label: "Models", icon: Zap, enabled: true },
  { href: "/dashboard/tools", label: "Tools", icon: Wrench, enabled: true },
  { href: "/dashboard/knowledge", label: "Knowledge", icon: BookOpen, enabled: true },
  { href: "/dashboard/data-sources", label: "Data Sources", icon: FolderOpen, enabled: true },
  { href: "/dashboard/azure", label: "Azure", icon: Cloud, enabled: true },
  { href: "/dashboard/workflows", label: "Workflows", icon: GitBranch, enabled: true },
  { href: "/dashboard/observability", label: "Observability", icon: BarChart3, enabled: true },
  { href: "/dashboard/fine-tune", label: "Fine-tune", icon: Sparkles, enabled: false },
  { href: "/dashboard/data", label: "Data", icon: Database, enabled: false },
  { href: "/dashboard/evaluations", label: "Evaluations", icon: ClipboardCheck, enabled: true },
  { href: "/dashboard/marketplace", label: "Marketplace", icon: Store, enabled: true },
  { href: "/dashboard/guardrails", label: "Guardrails", icon: Shield, enabled: false },
];

export function FoundrySidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={`flex flex-col border-r border-gray-200 bg-white transition-all duration-200 ${
        collapsed ? "w-16" : "w-[220px]"
      }`}
    >
      {/* Header */}
      <div className="flex h-14 items-center px-4">
        {!collapsed && (
          <h1 className="text-lg font-bold text-gray-900">AI Platform</h1>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-2 py-2">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          const Icon = item.icon;

          if (!item.enabled) {
            return (
              <div
                key={item.href}
                className="flex h-10 cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-gray-400"
                title={collapsed ? item.label : undefined}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {!collapsed && (
                  <span className="text-sm font-medium">{item.label}</span>
                )}
              </div>
            );
          }

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex h-10 items-center gap-3 rounded-md px-3 py-2 transition-colors ${
                isActive
                  ? "border-l-[3px] border-[#7C3AED] bg-[#F5F3FF] text-[#7C3AED]"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon
                className={`h-5 w-5 shrink-0 ${
                  isActive ? "text-[#7C3AED]" : "text-gray-500"
                }`}
              />
              {!collapsed && (
                <span className="text-sm font-medium">{item.label}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="border-t border-gray-200 p-2">
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="flex h-10 w-full items-center justify-center rounded-md text-gray-500 hover:bg-gray-50 hover:text-gray-700"
        >
          {collapsed ? (
            <PanelLeft className="h-5 w-5" />
          ) : (
            <PanelLeftClose className="h-5 w-5" />
          )}
        </button>
      </div>
    </aside>
  );
}
