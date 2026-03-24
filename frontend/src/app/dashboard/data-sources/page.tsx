"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface DataSource {
  id: string;
  name: string;
  description: string | null;
  source_type: string;
  status: string;
  created_at: string;
}

interface DataSourceListResponse {
  data_sources: DataSource[];
  total: number;
}

const typeColors: Record<string, string> = {
  file: "bg-blue-100 text-blue-800",
  url: "bg-green-100 text-green-800",
};

export default function DataSourcesPage() {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<DataSourceListResponse>("/api/v1/data-sources")
      .then((data) => setDataSources(data.data_sources))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleEdit = (ds: DataSource) => {
    setEditing(ds.id);
    setEditName(ds.name);
    setEditDescription(ds.description || "");
  };

  const handleSave = async (ds: DataSource) => {
    try {
      const updated = await apiFetch<{ data_source: DataSource }>(
        `/api/v1/data-sources/${ds.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            name: editName,
            description: editDescription || null,
            source_type: ds.source_type,
            connection_config: {},
          }),
        }
      );
      setDataSources((prev) =>
        prev.map((d) => (d.id === ds.id ? updated.data_source : d))
      );
      setEditing(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiFetch(`/api/v1/data-sources/${id}`, { method: "DELETE" });
      setDataSources((prev) => prev.filter((d) => d.id !== id));
      setDeleting(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-gray-500">Loading data sources...</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Data Sources</h1>
        <Link
          href="/dashboard/data-sources/new"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          Add Data Source
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {dataSources.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">No data sources connected.</p>
          <Link
            href="/dashboard/data-sources/new"
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            Add Data Source →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {dataSources.map((ds) => (
            <div
              key={ds.id}
              className="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
            >
              <div className="flex items-start justify-between mb-2">
                {editing === ds.id ? (
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="text-lg font-semibold text-gray-900 border border-gray-300 rounded px-2 py-1 w-full mr-2"
                  />
                ) : (
                  <h3 className="text-lg font-semibold text-gray-900 truncate">
                    {ds.name}
                  </h3>
                )}
                <span
                  className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium shrink-0 ${
                    typeColors[ds.source_type] || "bg-gray-100 text-gray-800"
                  }`}
                >
                  {ds.source_type}
                </span>
              </div>

              {editing === ds.id ? (
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Description (optional)"
                  rows={2}
                  className="w-full text-sm text-gray-600 border border-gray-300 rounded px-2 py-1 mb-3"
                />
              ) : (
                ds.description && (
                  <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                    {ds.description}
                  </p>
                )
              )}

              <div className="text-xs text-gray-400 mb-3">
                Status: {ds.status}
              </div>

              <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
                {editing === ds.id ? (
                  <>
                    <button
                      onClick={() => handleSave(ds)}
                      className="text-xs font-medium text-green-600 hover:text-green-700"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditing(null)}
                      className="text-xs font-medium text-gray-500 hover:text-gray-700"
                    >
                      Cancel
                    </button>
                  </>
                ) : deleting === ds.id ? (
                  <>
                    <span className="text-xs text-red-600">Delete?</span>
                    <button
                      onClick={() => handleDelete(ds.id)}
                      className="text-xs font-medium text-red-600 hover:text-red-700"
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setDeleting(null)}
                      className="text-xs font-medium text-gray-500 hover:text-gray-700"
                    >
                      No
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => handleEdit(ds)}
                      className="text-xs font-medium text-blue-600 hover:text-blue-700"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setDeleting(ds.id)}
                      className="text-xs font-medium text-red-600 hover:text-red-700"
                    >
                      Delete
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
