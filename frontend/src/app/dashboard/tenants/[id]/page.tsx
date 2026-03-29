"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Activity, Cpu, Users, DollarSign, Trash2, AlertTriangle, Pause, XCircle, Play } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { TenantStatusBadge } from "@/components/tenant/tenant-status-badge";
import { KpiTile } from "@/components/observability/kpi-tiles";
import { ChartCard } from "@/components/observability/chart-card";

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

interface DashboardData {
  total_requests?: number;
  total_executions?: number;
  total_tokens?: number;
  total_cost?: number;
}

// --------------- Settings Tab ---------------
function SettingsTab({
  tenant,
  onUpdate,
}: {
  tenant: Tenant;
  onUpdate: (t: Tenant) => void;
}) {
  const settings = tenant.settings as Record<string, unknown>;
  const [formData, setFormData] = useState({
    display_name: (settings.display_name as string) ?? "",
    token_quota: (settings.token_quota as number) ?? 0,
    allowed_providers: Array.isArray(settings.allowed_providers)
      ? (settings.allowed_providers as string[]).join(", ")
      : "",
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    const s = tenant.settings as Record<string, unknown>;
    setFormData({
      display_name: (s.display_name as string) ?? "",
      token_quota: (s.token_quota as number) ?? 0,
      allowed_providers: Array.isArray(s.allowed_providers)
        ? (s.allowed_providers as string[]).join(", ")
        : "",
    });
  }, [tenant]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);
    try {
      const body = {
        display_name: formData.display_name,
        token_quota: Number(formData.token_quota),
        allowed_providers: formData.allowed_providers
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      const updated = await apiFetch<Tenant>(
        `/api/v1/tenants/${tenant.id}/settings`,
        {
          method: "PATCH",
          body: JSON.stringify(body),
        }
      );
      onUpdate(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <label className="block">
          <span className="text-sm font-medium text-gray-700">
            Display Name
          </span>
          <input
            type="text"
            value={formData.display_name}
            onChange={(e) =>
              setFormData((p) => ({ ...p, display_name: e.target.value }))
            }
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </label>
      </div>
      <div>
        <label className="block">
          <span className="text-sm font-medium text-gray-700">
            Token Quota
          </span>
          <input
            type="number"
            min={0}
            value={formData.token_quota}
            onChange={(e) =>
              setFormData((p) => ({ ...p, token_quota: Number(e.target.value) }))
            }
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
        </label>
      </div>
      <div>
        <label className="block">
          <span className="text-sm font-medium text-gray-700">
            Allowed Providers
          </span>
          <input
            type="text"
            value={formData.allowed_providers}
            onChange={(e) =>
              setFormData((p) => ({
                ...p,
                allowed_providers: e.target.value,
              }))
            }
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 mt-1">
            Comma-separated list (e.g., azure-openai, anthropic)
          </p>
        </label>
      </div>

      {saveError && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          {saveError}
        </div>
      )}
      {saveSuccess && (
        <div className="rounded-md bg-green-50 p-4 text-sm text-green-700">
          Settings saved successfully.
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
      >
        {saving ? "Saving..." : "Save Settings"}
      </button>
    </div>
  );
}

// --------------- Users Tab ---------------
function UsersTab({ tenant }: { tenant: Tenant }) {
  return (
    <div>
      <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Email
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Role
              </th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-gray-100">
              <td className="px-6 py-4 text-sm text-gray-900">
                {tenant.admin_email}
              </td>
              <td className="px-6 py-4 text-sm text-gray-500">Admin</td>
            </tr>
          </tbody>
        </table>
      </div>

      {tenant.entra_group_id && (
        <div className="mt-4 rounded-md bg-gray-50 p-4">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Entra Group ID</span>
          <p className="mt-1 text-sm text-gray-900 font-mono">{tenant.entra_group_id}</p>
        </div>
      )}

      <div className="mt-4 rounded-md bg-blue-50 p-4 text-sm text-blue-700">
        User management is handled through Microsoft Entra ID. Add users by
        assigning them to the tenant&apos;s Entra ID group in the Azure Portal.
        <div className="mt-2">
          <a
            href="https://portal.azure.com/#view/Microsoft_AAD_IAM/GroupsManagementMenuBlade"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Open Azure Portal →
          </a>
        </div>
      </div>
    </div>
  );
}

// --------------- Usage Tab ---------------
function UsageTab({ tenantId }: { tenantId: string }) {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<DashboardData>(`/api/v1/observability/dashboard?tenant_id=${tenantId}`)
      .then((data) => setDashboardData(data))
      .catch(() => setDashboardData(null))
      .finally(() => setLoading(false));
  }, [tenantId]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiTile
          title="API Calls"
          value={dashboardData?.total_requests ?? 0}
          icon={<Activity className="h-5 w-5" />}
          colorClass="text-blue-500"
        />
        <KpiTile
          title="Executions"
          value={dashboardData?.total_executions ?? 0}
          icon={<Cpu className="h-5 w-5" />}
          colorClass="text-purple-500"
        />
        <KpiTile
          title="Tokens"
          value={dashboardData?.total_tokens ?? 0}
          icon={<Users className="h-5 w-5" />}
          colorClass="text-green-500"
        />
        <KpiTile
          title="Est. Cost"
          value={`$${(dashboardData?.total_cost ?? 0).toFixed(2)}`}
          icon={<DollarSign className="h-5 w-5" />}
          colorClass="text-amber-500"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="API Calls (30d)" loading={loading}>
          <p className="text-sm text-gray-400 text-center mt-20">
            Chart data coming soon
          </p>
        </ChartCard>
        <ChartCard title="Token Usage (30d)" loading={loading}>
          <p className="text-sm text-gray-400 text-center mt-20">
            Chart data coming soon
          </p>
        </ChartCard>
      </div>
    </div>
  );
}

// --------------- Danger Zone Tab ---------------
function DangerZoneTab({
  tenant,
  onUpdate,
}: {
  tenant: Tenant;
  onUpdate: (t: Tenant) => void;
}) {
  const router = useRouter();
  const [transitioning, setTransitioning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmText, setConfirmText] = useState("");

  const transitionState = async (newState: string) => {
    setTransitioning(true);
    setError("");
    try {
      const updated = await apiFetch<Tenant>(
        `/api/v1/tenants/${tenant.id}/state`,
        {
          method: "PATCH",
          body: JSON.stringify({ state: newState }),
        }
      );
      onUpdate(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Transition failed");
    } finally {
      setTransitioning(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    setError("");
    try {
      await apiFetch(`/api/v1/tenants/${tenant.id}`, { method: "DELETE" });
      router.push("/dashboard/tenants");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Delete failed");
      setDeleting(false);
    }
  };

  const nextActions: Record<string, { label: string; state: string; icon: React.ReactNode; color: string }[]> = {
    active: [
      { label: "Suspend Tenant", state: "suspended", icon: <Pause className="h-4 w-4" />, color: "bg-amber-600 hover:bg-amber-700" },
    ],
    suspended: [
      { label: "Reactivate Tenant", state: "active", icon: <Play className="h-4 w-4" />, color: "bg-green-600 hover:bg-green-700" },
      { label: "Deactivate Tenant", state: "deactivated", icon: <XCircle className="h-4 w-4" />, color: "bg-red-600 hover:bg-red-700" },
    ],
    deactivated: [
      { label: "Reactivate Tenant", state: "active", icon: <Play className="h-4 w-4" />, color: "bg-green-600 hover:bg-green-700" },
    ],
  };

  const actions = nextActions[tenant.status] ?? [];
  const canDelete = tenant.status === "deactivated" || tenant.status === "provisioning";

  return (
    <div className="space-y-6">
      {error && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Status Transitions */}
      <div className="rounded-lg border border-gray-200 p-6">
        <h3 className="text-sm font-semibold text-gray-900 mb-1">Tenant Status</h3>
        <p className="text-sm text-gray-500 mb-4">
          Current status: <TenantStatusBadge status={tenant.status} />
        </p>
        <p className="text-xs text-gray-400 mb-4">
          Lifecycle: active → suspended → deactivated → deleted
        </p>
        {actions.length > 0 ? (
          <div className="flex flex-wrap gap-3">
            {actions.map((action) => (
              <button
                key={action.state}
                onClick={() => transitionState(action.state)}
                disabled={transitioning}
                className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-colors disabled:opacity-50 ${action.color}`}
              >
                {action.icon}
                {transitioning ? "Updating..." : action.label}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">No status transitions available.</p>
        )}
      </div>

      {/* Delete */}
      <div className="rounded-lg border-2 border-red-200 bg-red-50 p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold text-red-900 mb-1">Delete Tenant</h3>
            <p className="text-sm text-red-700 mb-4">
              Permanently delete this tenant and all associated Kubernetes resources.
              {!canDelete && " The tenant must be deactivated before it can be deleted."}
            </p>
            {!confirmDelete ? (
              <button
                onClick={() => setConfirmDelete(true)}
                disabled={!canDelete}
                className="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Trash2 className="h-4 w-4" />
                Delete Tenant
              </button>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-red-800 font-medium">
                  Type <span className="font-mono bg-red-100 px-1 rounded">{tenant.slug}</span> to confirm:
                </p>
                <input
                  type="text"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder={tenant.slug}
                  className="block w-full max-w-xs rounded-md border border-red-300 px-3 py-2 text-sm shadow-sm focus:border-red-500 focus:ring-1 focus:ring-red-500"
                />
                <div className="flex gap-3">
                  <button
                    onClick={handleDelete}
                    disabled={confirmText !== tenant.slug || deleting}
                    className="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Trash2 className="h-4 w-4" />
                    {deleting ? "Deleting..." : "Confirm Delete"}
                  </button>
                  <button
                    onClick={() => {
                      setConfirmDelete(false);
                      setConfirmText("");
                    }}
                    className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// --------------- Main Page ---------------
const tabs = [
  { id: "settings", label: "Settings" },
  { id: "users", label: "Users" },
  { id: "usage", label: "Usage" },
  { id: "danger", label: "Danger Zone" },
];

export default function TenantDetailPage() {
  const params = useParams();
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("settings");

  useEffect(() => {
    apiFetch<Tenant>(`/api/v1/tenants/${params.id}`)
      .then((data) => setTenant(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading tenant...</p>
      </div>
    );
  }

  if (error || !tenant) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error || "Tenant not found"}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Back button */}
      <Link
        href="/dashboard/tenants"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-4"
      >
        <ArrowLeft className="h-4 w-4" /> Back to Tenants
      </Link>

      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">
          Tenant: {tenant.name}
        </h1>
        <TenantStatusBadge status={tenant.status} />
      </div>

      {/* Tab navigation */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`pb-3 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "border-b-2 border-blue-600 text-blue-600"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      {activeTab === "settings" && (
        <SettingsTab tenant={tenant} onUpdate={setTenant} />
      )}
      {activeTab === "users" && <UsersTab tenant={tenant} />}
      {activeTab === "usage" && <UsageTab tenantId={tenant.id} />}
      {activeTab === "danger" && (
        <DangerZoneTab tenant={tenant} onUpdate={setTenant} />
      )}
    </div>
  );
}
