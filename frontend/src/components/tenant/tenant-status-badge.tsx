"use client";

const tenantStatusConfig: Record<
  string,
  { bg: string; text: string; label: string }
> = {
  provisioning: {
    bg: "bg-blue-100",
    text: "text-blue-800",
    label: "Provisioning",
  },
  active: { bg: "bg-green-100", text: "text-green-800", label: "Active" },
  suspended: {
    bg: "bg-amber-100",
    text: "text-amber-800",
    label: "Suspended",
  },
  deactivated: {
    bg: "bg-red-100",
    text: "text-red-800",
    label: "Deactivated",
  },
  deleted: { bg: "bg-gray-100", text: "text-gray-800", label: "Deleted" },
};

export function TenantStatusBadge({ status }: { status: string }) {
  const config = tenantStatusConfig[status] ?? {
    bg: "bg-gray-100",
    text: "text-gray-800",
    label: status,
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${config.bg} ${config.text}`}
    >
      {config.label}
    </span>
  );
}
