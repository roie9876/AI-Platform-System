"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Play, Trash2 } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { WorkflowCanvas, type WorkflowCanvasRef } from "@/components/workflow/workflow-canvas";
import type { Node, Edge } from "@xyflow/react";

interface WorkflowNodeResponse {
  id: string;
  workflow_id: string;
  agent_id: string;
  name: string;
  node_type: string;
  position_x: number;
  position_y: number;
  config: Record<string, unknown> | null;
  execution_order: number;
}

interface WorkflowEdgeResponse {
  id: string;
  workflow_id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
}

interface WorkflowDetailResponse {
  id: string;
  name: string;
  description: string | null;
  workflow_type: string;
  is_active: boolean;
  nodes: WorkflowNodeResponse[];
  edges: WorkflowEdgeResponse[];
}

interface AgentOption {
  id: string;
  name: string;
  description: string | null;
}

interface AgentListResponse {
  agents: AgentOption[];
  total: number;
}

export default function WorkflowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workflowId = params.id as string;
  const canvasRef = useRef<WorkflowCanvasRef>(null);

  const [workflow, setWorkflow] = useState<WorkflowDetailResponse | null>(null);
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch<WorkflowDetailResponse>(`/api/v1/workflows/${workflowId}`),
      apiFetch<AgentListResponse>("/api/v1/agents"),
    ])
      .then(([wf, agentData]) => {
        setWorkflow(wf);
        setAgents(agentData.agents);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [workflowId]);

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this workflow?")) return;
    setDeleting(true);
    try {
      await apiFetch(`/api/v1/workflows/${workflowId}`, { method: "DELETE" });
      router.push("/dashboard/workflows");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading workflow...</p>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error || "Workflow not found"}
        </div>
      </div>
    );
  }

  // Map API data to React Flow format
  const initialNodes: Node[] = workflow.nodes.map((node) => ({
    id: node.id,
    type: "agentNode",
    position: { x: node.position_x, y: node.position_y },
    data: {
      label: node.name,
      agentName: node.name,
      nodeType: node.node_type,
      agentId: node.agent_id,
    },
  }));

  const initialEdges: Edge[] = workflow.edges.map((edge) => ({
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    type: "default",
  }));

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{workflow.name}</h1>
            {workflow.description && (
              <p className="text-sm text-gray-500 mt-1">{workflow.description}</p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Link
              href={`/dashboard/workflows/${workflowId}/run`}
              className="flex items-center gap-2 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
            >
              <Play className="h-4 w-4" />
              Run Workflow
            </Link>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="flex items-center gap-2 rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
              Delete
            </button>
          </div>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1">
        <WorkflowCanvas
          ref={canvasRef}
          initialNodes={initialNodes}
          initialEdges={initialEdges}
          agents={agents}
        />
      </div>
    </div>
  );
}
