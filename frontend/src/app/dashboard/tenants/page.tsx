"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, Users, Bot, Activity } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { TenantStatusBadge } from "@/components/tenant/tenant-status-badge";
import { KpiTile } from "@/components/observability/kpi-tiles";

interface Tenant {
  id: string;
  name: string;
  slug: string;
  admin_email: string;
  entra_group_id?: string;
  status: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export default function TenantsPage() {
  const router = useRouter();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<{ tenants: Tenant[] }>("/api/v1/tenants")
      .then((data) => setTenants(data.tenants))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const total = tenants.length;
  const activeCount = tenants.filter((t) => t.status === "active").length;
  const suspendedCount = tenants.filter(
    (t) => t.status === "suspended"
  ).length;
  const provisioningCount = tenants.filter(
    (t) => t.status === "provisioning"
  ).length;

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading tenants...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Tenants</h1>
        <Link
          href="/dashboard/tenants/new"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Create Tenant
        </Link>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiTile
          title="Total Tenants"
          value={total}
          icon={<Building2 className="h-5 w-5" />}
          colorClass="text-blue-500"
        />
        <KpiTile
          title="Active"
          value={activeCount}
          icon={<Activity className="h-5 w-5" />}
          colorClass="text-green-500"
        />
        <KpiTile
          title="Suspended"
          value={suspendedCount}
          icon={<Users className="h-5 w-5" />}
          colorClass="text-amber-500"
        />
        <KpiTile
          title="Provisioning"
          value={provisioningCount}
          icon={<Bot className="h-5 w-5" />}
          colorClass="text-blue-500"
        />
      </div>

      {/* Empty state */}
      {tenants.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">
            No tenants yet. Create your first tenant to start onboarding teams.
          </p>
          <Link
            href="/dashboard/tenants/new"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Create Tenant →
          </Link>
        </div>
      )}

      {/* Tenant table */}
      {tenants.length > 0 && (
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Slug
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Admin Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {tenants.map((tenant) => (
                <tr
                  key={tenant.id}
                  onClick={() =>
                    router.push(`/dashboard/tenants/${tenant.id}`)
                  }
                  className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                >
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">
                    {tenant.name}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {tenant.slug}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <TenantStatusBadge status={tenant.status} />
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {tenant.admin_email}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(tenant.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
