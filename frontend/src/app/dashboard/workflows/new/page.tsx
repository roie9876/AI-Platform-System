"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { WorkflowCanvas, type WorkflowCanvasRef } from "@/components/workflow/workflow-canvas";
import { WorkflowTypeSelect } from "@/components/workflow/workflow-type-help";

interface AgentOption {
  id: string;
  name: string;
  description: string | null;
}

interface AgentListResponse {
  agents: AgentOption[];
  total: number;
}

export default function NewWorkflowPage() {
  const router = useRouter();
  const canvasRef = useRef<WorkflowCanvasRef>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [workflowType, setWorkflowType] = useState("sequential");
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<AgentListResponse>("/api/v1/agents")
      .then((data) => setAgents(data.agents))
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    if (!name.trim()) {
      setError("Name is required");
      return;
    }

    const flow = canvasRef.current?.getFlow();
    if (!flow || flow.nodes.length === 0) {
      setError("Add at least one agent node to the workflow");
      return;
    }

    setSaving(true);
    setError("");

    try {
      const nodes = flow.nodes.map((node, index) => ({
        agent_id: (node.data as Record<string, unknown>).agentId as string,
        name: (node.data as Record<string, unknown>).label as string,
        node_type: (node.data as Record<string, unknown>).nodeType as string || "agent",
        position_x: node.position.x,
        position_y: node.position.y,
        execution_order: index,
        _temp_id: node.id, // for edge mapping
      }));

      // First create workflow with nodes only to get real node IDs
      const createBody = {
        name: name.trim(),
        description: description.trim() || undefined,
        workflow_type: workflowType,
        nodes: nodes.map(({ _temp_id, ...n }) => n),
      };

      const created = await apiFetch<{ id: string; nodes: { id: string; agent_id: string; execution_order: number }[] }>(
        "/api/v1/workflows",
        { method: "POST", body: JSON.stringify(createBody) }
      );

      // Map temp IDs to real node IDs by execution_order
      if (flow.edges.length > 0 && created.nodes.length > 0) {
        const tempToReal = new Map<string, string>();
        nodes.forEach((n, i) => {
          const realNode = created.nodes.find((rn) => rn.execution_order === i);
          if (realNode) tempToReal.set(n._temp_id, realNode.id);
        });

        const edges = flow.edges
          .map((edge) => ({
            source_node_id: tempToReal.get(edge.source),
            target_node_id: tempToReal.get(edge.target),
            edge_type: (edge.data as Record<string, unknown>)?.edgeType as string || "default",
            output_mapping: (edge.data as Record<string, unknown>)?.outputMapping as Record<string, string> || null,
            condition: (edge.data as Record<string, unknown>)?.condition as Record<string, string> || null,
          }))
          .filter((e) => e.source_node_id && e.target_node_id);

        if (edges.length > 0) {
          // Update workflow with edges by re-saving
          for (const edge of edges) {
            await apiFetch(`/api/v1/workflows/${created.id}/edges`, {
              method: "POST",
              body: JSON.stringify(edge),
            });
          }
        }
      }

      router.push(`/dashboard/workflows/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save workflow");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold text-gray-900">Create Workflow</h1>
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard/workflows"
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </Link>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving..." : "Save Workflow"}
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-3 rounded-md bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex gap-4">
          <div className="flex-1">
            <label htmlFor="wf-name" className="block text-sm font-medium text-gray-700 mb-1">
              Name
            </label>
            <input
              id="wf-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="My Workflow"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="wf-desc" className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <input
              id="wf-desc"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="w-48">
            <WorkflowTypeSelect
              value={workflowType}
              onChange={setWorkflowType}
            />
          </div>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1">
        <WorkflowCanvas ref={canvasRef} agents={agents} />
      </div>
    </div>
  );
}
