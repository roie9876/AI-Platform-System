"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { PreviewBadge } from "@/components/ui/preview-badge";
import Link from "next/link";

interface AgentKnowledgeIndexInfo {
  connection_id: string;
  resource_name: string;
  index_names: string[];
}

interface AgentKnowledgeResponse {
  agent_id: string;
  connections: AgentKnowledgeIndexInfo[];
  total_indexes: number;
}

interface KnowledgeSectionProps {
  agentId: string;
}

export function KnowledgeSection({ agentId }: KnowledgeSectionProps) {
  const [knowledge, setKnowledge] = useState<AgentKnowledgeResponse | null>(
    null
  );

  useEffect(() => {
    apiFetch<AgentKnowledgeResponse>(
      `/api/v1/knowledge/agents/${agentId}/indexes`
    )
      .then(setKnowledge)
      .catch(() => {});
  }, [agentId]);

  return (
    <CollapsibleSection
      title="Knowledge"
      badge={<PreviewBadge />}
      defaultOpen={false}
    >
      {!knowledge || knowledge.total_indexes === 0 ? (
        <div className="text-sm text-gray-500">
          <p>
            Connect an AI Search resource to browse and select indexes for RAG
            retrieval.
          </p>
          <Link
            href="/dashboard/knowledge"
            className="mt-2 inline-block text-[#2563EB] hover:underline"
          >
            Set up Knowledge →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {knowledge.connections.map((conn) => (
            <div key={conn.connection_id}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-900">
                  {conn.resource_name}
                </span>
                <span className="text-xs text-gray-500">
                  {conn.index_names.length} index
                  {conn.index_names.length !== 1 ? "es" : ""}
                </span>
              </div>
              <ul className="mt-1 space-y-0.5">
                {conn.index_names.map((name) => (
                  <li key={name} className="text-xs text-gray-600">
                    {name}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </CollapsibleSection>
  );
}
