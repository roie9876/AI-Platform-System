"use client";

import { useAuth } from "@/contexts/auth-context";
import { useTenant } from "@/contexts/tenant-context";

export function TenantSelector() {
  const { user } = useAuth();
  const { tenants, selectedTenantId, setSelectedTenantId, loading } =
    useTenant();

  if (!user?.roles?.includes("platform_admin")) return null;

  if (loading) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Tenant:</span>
        <span className="text-sm text-gray-400">Loading...</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-500">Tenant:</span>
      <select
        value={selectedTenantId ?? ""}
        onChange={(e) => setSelectedTenantId(e.target.value)}
        className="rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-700 bg-white min-w-[200px] focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
      >
        {tenants.map((tenant) => (
          <option key={tenant.id} value={tenant.id}>
            {tenant.name}
          </option>
        ))}
      </select>
    </div>
  );
}
