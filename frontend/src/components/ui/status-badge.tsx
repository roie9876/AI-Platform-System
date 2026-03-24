const statusConfig = {
  connected: { color: "bg-emerald-600", label: "Connected" },
  degraded: { color: "bg-amber-600", label: "Degraded" },
  error: { color: "bg-red-600", label: "Error" },
  disconnected: { color: "bg-gray-400", label: "Disconnected" },
  unknown: { color: "bg-gray-400", label: "Unknown" },
} as const;

type Status = keyof typeof statusConfig;

export function StatusBadge({ status }: { status: Status }) {
  const config = statusConfig[status] ?? statusConfig.unknown;

  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-gray-700">
      <span className={`h-2 w-2 rounded-full ${config.color}`} />
      {config.label}
    </span>
  );
}
