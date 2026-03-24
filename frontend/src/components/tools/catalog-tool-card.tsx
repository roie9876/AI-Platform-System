import { PreviewBadge } from "@/components/ui/preview-badge";
import { McpBadge } from "@/components/ui/mcp-badge";
import { Wrench } from "lucide-react";

interface CatalogToolCardProps {
  name: string;
  description: string;
  iconName?: string;
  badges?: string[];
  selected?: boolean;
  onClick?: () => void;
}

function Badge({ label }: { label: string }) {
  if (label === "Preview") return <PreviewBadge />;
  if (label === "Local MCP") return <McpBadge type="local" />;
  if (label === "Remote MCP") return <McpBadge type="remote" />;
  return (
    <span className="inline-flex items-center rounded-sm bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-700">
      {label}
    </span>
  );
}

export function CatalogToolCard({
  name,
  description,
  badges,
  selected,
  onClick,
}: CatalogToolCardProps) {
  return (
    <div
      onClick={onClick}
      className={`flex gap-3 rounded-lg border bg-white p-3 cursor-pointer hover:border-gray-300 ${
        selected
          ? "border-[#7C3AED] ring-1 ring-[#7C3AED]"
          : "border-gray-200"
      }`}
    >
      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-gray-100">
        <Wrench className="h-5 w-5 text-gray-500" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-gray-900">{name}</p>
        <p className="text-xs text-gray-500 line-clamp-1">{description}</p>
        {badges && badges.length > 0 && (
          <div className="mt-1 flex flex-wrap gap-1">
            {badges.map((b) => (
              <Badge key={b} label={b} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
