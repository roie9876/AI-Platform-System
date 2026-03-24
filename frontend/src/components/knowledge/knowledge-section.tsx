"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import Link from "next/link";
import { Database, X } from "lucide-react";

interface AgentKnowledgeIndexInfo {
  connection_id: string;
  resource_name: string;
  knowledge_name: string | null;
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
  const [removing, setRemoving] = useState<string | null>(null);

  function loadKnowledge() {
    apiFetch<AgentKnowledgeResponse>(
      `/api/v1/knowledge/agents/${agentId}/indexes`
    )
      .then(setKnowledge)
      .catch(() => {});
  }

  useEffect(() => {
    loadKnowledge();
  }, [agentId]);

  async function handleRemove(connectionId: string) {
    if (!confirm("Remove this knowledge connection? This will delete it for all agents.")) return;
    setRemoving(connectionId);
    try {
      await apiFetch(`/api/v1/azure/connections/${connectionId}`, { method: "DELETE" });
      loadKnowledge();
    } catch {
      // ignore
    } finally {
      setRemoving(null);
    }
  }

  const hasConnections = knowledge && knowledge.total_indexes > 0;

  return (
    <CollapsibleSection
      title="Knowledge"
      defaultOpen={false}
    >
      {hasConnections ? (
        <div className="space-y-3">
          {knowledge.connections.map((conn) => (
            <div
              key={conn.connection_id}
              className="group rounded-md border border-gray-200 px-3 py-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-[#7C3AED]" />
                  <span className="text-sm font-medium text-gray-900">
                    {conn.knowledge_name || conn.resource_name}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    {conn.index_names.length} index
                    {conn.index_names.length !== 1 ? "es" : ""}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemove(conn.connection_id)}
                    disabled={removing === conn.connection_id}
                    className="rounded p-0.5 text-gray-400 opacity-0 hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 disabled:opacity-50"
                    title="Remove knowledge connection"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              {conn.knowledge_name && (
                <p className="mt-0.5 ml-6 text-xs text-gray-400">
                  {conn.resource_name}
                </p>
              )}
              <ul className="mt-1.5 ml-6 space-y-0.5">
                {conn.index_names.map((name) => (
                  <li key={name} className="text-xs text-gray-600">
                    {name}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <Link
            href="/dashboard/knowledge"
            className="inline-block text-xs text-[#2563EB] hover:underline"
          >
            Manage Knowledge →
          </Link>
        </div>
      ) : (
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
      )}
    </CollapsibleSection>
  );
}
