"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";

const sourceTypeOptions = [
  { value: "file", label: "File Upload" },
  { value: "url", label: "URL" },
  { value: "sharepoint", label: "SharePoint" },
  { value: "onedrive", label: "OneDrive" },
  { value: "azure_blob", label: "Azure Blob Storage" },
  { value: "aws_s3", label: "Amazon S3" },
  { value: "sql_server", label: "SQL Server" },
  { value: "postgresql", label: "PostgreSQL" },
  { value: "cosmos_db", label: "Azure Cosmos DB" },
  { value: "google_drive", label: "Google Drive" },
  { value: "confluence", label: "Confluence" },
];

export default function NewDataSourcePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedType = searchParams.get("type") || "file";
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    name: "",
    description: "",
    source_type: preselectedType,
    config: null as Record<string, unknown> | null,
    credentials: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");

    try {
      await apiFetch("/api/v1/data-sources", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          description: form.description || null,
          source_type: form.source_type,
          config: form.config,
          credentials: form.credentials || null,
        }),
      });
      router.push("/dashboard/data-sources");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create data source");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Add Data Source</h1>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Name *
          </label>
          <input
            type="text"
            required
            maxLength={255}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <textarea
            rows={2}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Source Type *
          </label>
          <select
            value={form.source_type}
            onChange={(e) => setForm({ ...form, source_type: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {sourceTypeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Credentials (optional)
          </label>
          <input
            type="password"
            value={form.credentials}
            onChange={(e) => setForm({ ...form, credentials: e.target.value })}
            placeholder="API key or access token (stored encrypted)"
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Creating..." : "Add Data Source"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/dashboard/data-sources")}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
