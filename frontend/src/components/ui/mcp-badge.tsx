export function McpBadge({ type }: { type: "local" | "remote" }) {
  return (
    <span className="inline-flex items-center rounded-sm border border-gray-200 bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-700">
      {type === "local" ? "Local MCP" : "Remote MCP"}
    </span>
  );
}
