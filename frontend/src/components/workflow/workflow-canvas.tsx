"use client";

import {
  useCallback,
  useRef,
  useState,
  forwardRef,
  useImperativeHandle,
  type DragEvent,
} from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type Edge,
  type ReactFlowInstance,
  MarkerType,
  type EdgeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Bot } from "lucide-react";
import { AgentNode } from "./agent-node";
import { EdgeConfigDialog } from "./edge-config-dialog";

interface AgentOption {
  id: string;
  name: string;
  description: string | null;
}

interface WorkflowCanvasProps {
  initialNodes?: Node[];
  initialEdges?: Edge[];
  agents: AgentOption[];
}

export interface WorkflowCanvasRef {
  getFlow: () => { nodes: Node[]; edges: Edge[] };
}

const nodeTypes = { agentNode: AgentNode };

const edgeTypeStyles: Record<string, { stroke: string; strokeDasharray?: string }> = {
  default: { stroke: "#6366f1" },
  conditional: { stroke: "#f59e0b", strokeDasharray: "5 5" },
  error: { stroke: "#ef4444", strokeDasharray: "8 4" },
};

function makeEdgeStyle(edgeType: string = "default"): Partial<Edge> {
  const style = edgeTypeStyles[edgeType] || edgeTypeStyles.default;
  return {
    animated: true,
    style: { strokeWidth: 2, ...style },
    markerEnd: { type: MarkerType.ArrowClosed, color: style.stroke, width: 16, height: 16 },
    label: edgeType === "conditional" ? "conditional" : edgeType === "error" ? "on error" : "output → input",
    labelStyle: { fontSize: 10, fontWeight: 500, fill: style.stroke },
    labelBgStyle: { fill: "white", fillOpacity: 0.9 },
    labelBgPadding: [4, 2] as [number, number],
  };
}

export const WorkflowCanvas = forwardRef<WorkflowCanvasRef, WorkflowCanvasProps>(
  function WorkflowCanvas({ initialNodes = [], initialEdges = [], agents }, ref) {
    const styledInitialEdges = initialEdges.map((e) => ({
      ...e,
      ...makeEdgeStyle((e.data as Record<string, unknown>)?.edgeType as string),
    }));

    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(styledInitialEdges);
    const reactFlowInstance = useRef<ReactFlowInstance | null>(null);

    // Edge config dialog state
    const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);

    useImperativeHandle(ref, () => ({
      getFlow: () => ({ nodes, edges }),
    }));

    const onConnect = useCallback(
      (params: Connection) => {
        const newEdge: Edge = {
          ...params,
          id: `edge-${Date.now()}`,
          data: { edgeType: "default", outputMapping: null, condition: null },
          ...makeEdgeStyle("default"),
        } as Edge;
        setEdges((eds) => addEdge(newEdge, eds));
      },
      [setEdges]
    );

    const onEdgeClick: EdgeMouseHandler = useCallback((_event, edge) => {
      setSelectedEdge(edge);
    }, []);

    const handleEdgeSave = useCallback(
      (data: {
        edgeType: string;
        outputMapping: Record<string, string> | null;
        condition: Record<string, string> | null;
      }) => {
        if (!selectedEdge) return;
        setEdges((eds) =>
          eds.map((e) =>
            e.id === selectedEdge.id
              ? {
                  ...e,
                  data: {
                    ...(e.data || {}),
                    edgeType: data.edgeType,
                    outputMapping: data.outputMapping,
                    condition: data.condition,
                  },
                  ...makeEdgeStyle(data.edgeType),
                }
              : e
          )
        );
        setSelectedEdge(null);
      },
      [selectedEdge, setEdges]
    );

    const handleEdgeDelete = useCallback(() => {
      if (!selectedEdge) return;
      setEdges((eds) => eds.filter((e) => e.id !== selectedEdge.id));
      setSelectedEdge(null);
    }, [selectedEdge, setEdges]);

    const getNodeLabel = (nodeId: string): string => {
      const node = nodes.find((n) => n.id === nodeId);
      return (node?.data as Record<string, unknown>)?.label as string || nodeId;
    };

    const onDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
    }, []);

    const onDrop = useCallback(
      (event: DragEvent<HTMLDivElement>) => {
        event.preventDefault();
        const agentData = event.dataTransfer.getData("application/reactflow");
        if (!agentData || !reactFlowInstance.current) return;

        const agent = JSON.parse(agentData) as AgentOption;
        const position = reactFlowInstance.current.screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        });

        const newNode: Node = {
          id: `node-${Date.now()}`,
          type: "agentNode",
          position,
          data: {
            label: agent.name,
            agentName: agent.name,
            nodeType: "agent",
            agentId: agent.id,
          },
        };

        setNodes((nds) => [...nds, newNode]);
      },
      [setNodes]
    );

    const onDragStart = (event: DragEvent<HTMLDivElement>, agent: AgentOption) => {
      event.dataTransfer.setData("application/reactflow", JSON.stringify(agent));
      event.dataTransfer.effectAllowed = "move";
    };

    return (
      <div className="flex h-full">
        {/* Agent sidebar panel */}
        <div className="w-56 border-r border-gray-200 bg-gray-50 p-3 overflow-y-auto">
          <h3 className="text-xs font-semibold text-gray-500 uppercase mb-2">
            Available Agents
          </h3>
          {agents.length === 0 ? (
            <p className="text-xs text-gray-400">No agents available</p>
          ) : (
            <div className="space-y-1.5">
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  draggable
                  onDragStart={(e) => onDragStart(e, agent)}
                  className="flex items-center gap-2 rounded-md border border-gray-200 bg-white p-2 cursor-grab hover:shadow-sm transition-shadow"
                >
                  <Bot className="h-4 w-4 text-gray-500 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {agent.name}
                    </p>
                    {agent.description && (
                      <p className="text-[10px] text-gray-500 truncate">
                        {agent.description}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* React Flow canvas */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeClick={onEdgeClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onInit={(instance) => {
              reactFlowInstance.current = instance;
            }}
            nodeTypes={nodeTypes}
            fitView
            className="bg-gray-50"
          >
            <Background gap={16} size={1} />
            <Controls />
            <MiniMap
              nodeStrokeWidth={3}
              className="!bg-white !border-gray-200"
            />
          </ReactFlow>
        </div>

        {/* Edge config dialog */}
        {selectedEdge && (
          <EdgeConfigDialog
            open={!!selectedEdge}
            sourceLabel={getNodeLabel(selectedEdge.source)}
            targetLabel={getNodeLabel(selectedEdge.target)}
            edgeType={
              (selectedEdge.data as Record<string, unknown>)?.edgeType as string ||
              "default"
            }
            outputMapping={
              (selectedEdge.data as Record<string, unknown>)?.outputMapping as Record<string, string> | null
            }
            condition={
              (selectedEdge.data as Record<string, unknown>)?.condition as Record<string, string> | null
            }
            onSave={handleEdgeSave}
            onDelete={handleEdgeDelete}
            onClose={() => setSelectedEdge(null)}
          />
        )}
      </div>
    );
  }
);
