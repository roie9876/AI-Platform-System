"use client";

interface AgentConfigLayoutProps {
  agentId: string;
  agentName: string;
  leftPanel: React.ReactNode;
  rightPanel: React.ReactNode;
}

export function AgentConfigLayout({
  leftPanel,
  rightPanel,
}: AgentConfigLayoutProps) {
  return (
    <div className="flex h-full">
      <div className="flex-1 min-w-[580px] overflow-y-auto border-r border-gray-200 bg-white p-6">
        {leftPanel}
      </div>
      <div className="w-[480px] flex-shrink-0 overflow-y-auto bg-gray-50">{rightPanel}</div>
    </div>
  );
}
