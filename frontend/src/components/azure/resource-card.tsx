import { RegionBadge } from "@/components/ui/region-badge";

interface ResourceCardProps {
  name: string;
  resourceType: string;
  region: string;
  resourceId: string;
  onClick?: (resourceId: string) => void;
  selected?: boolean;
}

export function ResourceCard({
  name,
  resourceType,
  region,
  resourceId,
  onClick,
  selected,
}: ResourceCardProps) {
  return (
    <div
      onClick={() => onClick?.(resourceId)}
      className={`rounded-lg border bg-white p-4 ${
        selected
          ? "border-[#7C3AED] ring-1 ring-[#7C3AED]"
          : "border-gray-200"
      } ${onClick ? "cursor-pointer" : ""}`}
    >
      <h4 className="text-sm font-semibold text-gray-900">{name}</h4>
      <div className="mt-2 flex items-center gap-2">
        <RegionBadge region={region} />
        <span className="text-xs text-gray-500">{resourceType}</span>
      </div>
    </div>
  );
}
