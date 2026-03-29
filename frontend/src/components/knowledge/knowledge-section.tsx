"use client";

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import Link from "next/link";
import { Database, X, Plus } from "lucide-react";

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

interface ConnectionResponse {
  id: string;
  resource_name: string;
  resource_type: string;
  config?: Record<string, unknown>;
}

interface KnowledgeSectionProps {
  agentId: string;
}

export function KnowledgeSection({ agentId }: KnowledgeSectionProps) {
  const [knowledge, setKnowledge] = useState<AgentKnowledgeResponse | null>(
    null
  );
  const [removing, setRemoving] = useState<string | null>(null);
  const [showAttach, setShowAttach] = useState(false);
  const [allConnections, setAllConnections] = useState<ConnectionResponse[]>(
    []
  );
  const [attaching, setAttaching] = useState<string | null>(null);

  const loadKnowledge = useCallback(() => {
    apiFetch<AgentKnowledgeResponse>(
      `/api/v1/knowledge/agents/${agentId}/indexes`
    )
      .then(setKnowledge)
      .catch(() => {});
  }, [agentId]);

  useEffect(() => {
    loadKnowledge();
  }, [loadKnowledge]);

  async function loadAvailableConnections() {
    try {
      const conns = await apiFetch<ConnectionResponse[]>(
        "/api/v1/azure/connections"
      );
      // Filter to search services with selected indexes
      const searchConns = conns.filter(
        (c) =>
          c.resource_type === "Microsoft.Search/searchServices" &&
          ((c.config?.selected_indexes as string[]) || []).length > 0
      );
      setAllConnections(searchConns);
    } catch {
      setAllConnections([]);
    }
  }

  async function handleAttach(connectionId: string) {
    setAttaching(connectionId);
    try {
      await apiFetch(
        `/api/v1/knowledge/agents/${agentId}/attach/${connectionId}`,
        { method: "POST" }
      );
      setShowAttach(false);
      loadKnowledge();
    } catch {
      // ignore
    } finally {
      setAttaching(null);
    }
  }

  async function handleDetach(connectionId: string) {
    if (
      !confirm("Detach this knowledge from this agent?")
    )
      return;
    setRemoving(connectionId);
    try {
      await apiFetch(
        `/api/v1/knowledge/agents/${agentId}/detach/${connectionId}`,
        { method: "DELETE" }
      );
      loadKnowledge();
    } catch {
      // ignore
    } finally {
      setRemoving(null);
    }
  }

  function openAttach() {
    loadAvailableConnections();
    setShowAttach(true);
  }

  // Connections already attached to this agent
  const attachedIds = new Set(
    (knowledge?.connections || []).map((c) => c.connection_id)
  );
  // Available = all tenant connections minus already attached
  const availableConnections = allConnections.filter(
    (c) => !attachedIds.has(c.id)
  );

  const hasConnections = knowledge && knowledge.total_indexes > 0;

  return (
    <CollapsibleSection title="Knowledge" defaultOpen={false}>
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
                    onClick={() => handleDetach(conn.connection_id)}
                    disabled={removing === conn.connection_id}
                    className="rounded p-0.5 text-gray-400 opacity-0 hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 disabled:opacity-50"
                    title="Detach knowledge from agent"
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

          {/* Attach more button */}
          {!showAttach && (
            <button
              type="button"
              onClick={openAttach}
              className="flex items-center gap-1 text-xs text-[#2563EB] hover:underline"
            >
              <Plus className="h-3 w-3" /> Attach knowledge
            </button>
          )}

          {/* Attach picker */}
          {showAttach && (
            <div className="rounded-md border border-dashed border-gray-300 p-2 space-y-1">
              {availableConnections.length === 0 ? (
                <p className="text-xs text-gray-500">
                  No additional knowledge available.{" "}
                  <Link
                    href="/dashboard/knowledge"
                    className="text-[#2563EB] hover:underline"
                  >
                    Create one →
                  </Link>
                </p>
              ) : (
                availableConnections.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => handleAttach(c.id)}
                    disabled={attaching === c.id}
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-gray-50 disabled:opacity-50"
                  >
                    <Database className="h-3.5 w-3.5 text-gray-400" />
                    <span>
                      {(c.config?.knowledge_name as string) || c.resource_name}
                    </span>
                    <span className="ml-auto text-xs text-gray-400">
                      {((c.config?.selected_indexes as string[]) || []).length}{" "}
                      index
                      {((c.config?.selected_indexes as string[]) || [])
                        .length !== 1
                        ? "es"
                        : ""}
                    </span>
                  </button>
                ))
              )}
              <button
                type="button"
                onClick={() => setShowAttach(false)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Cancel
              </button>
            </div>
          )}

          <Link
            href="/dashboard/knowledge"
            className="inline-block text-xs text-[#2563EB] hover:underline"
          >
            Manage Knowledge →
          </Link>
        </div>
      ) : (
        <div className="space-y-2 text-sm text-gray-500">
          <p>No knowledge attached to this agent.</p>

          {!showAttach ? (
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={openAttach}
                className="flex items-center gap-1 text-[#2563EB] hover:underline"
              >
                <Plus className="h-3.5 w-3.5" /> Attach existing
              </button>
              <Link
                href={`/dashboard/knowledge?attachTo=${agentId}`}
                className="text-[#2563EB] hover:underline"
              >
                Create new →
              </Link>
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-gray-300 p-2 space-y-1">
              {availableConnections.length === 0 ? (
                <p className="text-xs text-gray-500">
                  No knowledge available.{" "}
                  <Link
                    href={`/dashboard/knowledge?attachTo=${agentId}`}
                    className="text-[#2563EB] hover:underline"
                  >
                    Create one →
                  </Link>
                </p>
              ) : (
                availableConnections.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => handleAttach(c.id)}
                    disabled={attaching === c.id}
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-gray-50 disabled:opacity-50"
                  >
                    <Database className="h-3.5 w-3.5 text-gray-400" />
                    <span>
                      {(c.config?.knowledge_name as string) || c.resource_name}
                    </span>
                  </button>
                ))
              )}
              <button
                type="button"
                onClick={() => setShowAttach(false)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}
    </CollapsibleSection>
  );
}
