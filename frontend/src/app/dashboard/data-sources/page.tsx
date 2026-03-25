"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import {
  FolderOpen,
  Cloud,
  Database,
  FileText,
  HardDrive,
  Globe,
  Server,
  Lock,
  ArrowRight,
} from "lucide-react";

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

interface ConnectorType {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  category: "cloud" | "database" | "saas" | "file";
  available: boolean;
}

const connectorTypes: ConnectorType[] = [
  {
    id: "sharepoint",
    name: "SharePoint",
    description: "Connect to Microsoft SharePoint sites, document libraries, and lists",
    icon: <FileText className="h-5 w-5 text-blue-600" />,
    category: "saas",
    available: true,
  },
  {
    id: "onedrive",
    name: "OneDrive",
    description: "Access files and folders from OneDrive for Business or personal accounts",
    icon: <Cloud className="h-5 w-5 text-sky-500" />,
    category: "cloud",
    available: true,
  },
  {
    id: "azure_blob",
    name: "Azure Blob Storage",
    description: "Connect to Azure Blob Storage containers and access unstructured data",
    icon: <HardDrive className="h-5 w-5 text-blue-500" />,
    category: "cloud",
    available: true,
  },
  {
    id: "aws_s3",
    name: "Amazon S3",
    description: "Connect to AWS S3 buckets for object storage and data lake access",
    icon: <HardDrive className="h-5 w-5 text-orange-500" />,
    category: "cloud",
    available: true,
  },
  {
    id: "sql_server",
    name: "SQL Server",
    description: "Connect to Microsoft SQL Server or Azure SQL databases",
    icon: <Database className="h-5 w-5 text-red-500" />,
    category: "database",
    available: true,
  },
  {
    id: "postgresql",
    name: "PostgreSQL",
    description: "Connect to PostgreSQL or Azure Database for PostgreSQL",
    icon: <Database className="h-5 w-5 text-blue-700" />,
    category: "database",
    available: true,
  },
  {
    id: "cosmos_db",
    name: "Azure Cosmos DB",
    description: "Connect to Azure Cosmos DB NoSQL, MongoDB, or other API accounts",
    icon: <Database className="h-5 w-5 text-green-600" />,
    category: "database",
    available: true,
  },
  {
    id: "google_drive",
    name: "Google Drive",
    description: "Connect to Google Drive files and shared drives",
    icon: <Cloud className="h-5 w-5 text-green-500" />,
    category: "cloud",
    available: true,
  },
  {
    id: "confluence",
    name: "Confluence",
    description: "Index and search Atlassian Confluence spaces and pages",
    icon: <Globe className="h-5 w-5 text-blue-500" />,
    category: "saas",
    available: true,
  },
  {
    id: "snowflake",
    name: "Snowflake",
    description: "Connect to Snowflake data warehouse for analytics data access",
    icon: <Server className="h-5 w-5 text-cyan-500" />,
    category: "database",
    available: false,
  },
  {
    id: "databricks",
    name: "Databricks",
    description: "Connect to Databricks Unity Catalog and lakehouse data",
    icon: <Server className="h-5 w-5 text-red-600" />,
    category: "database",
    available: false,
  },
  {
    id: "servicenow",
    name: "ServiceNow",
    description: "Connect to ServiceNow for ITSM data and knowledge articles",
    icon: <Globe className="h-5 w-5 text-green-700" />,
    category: "saas",
    available: false,
  },
];

const categoryLabels: Record<string, string> = {
  cloud: "Cloud Storage",
  database: "Databases",
  saas: "SaaS Applications",
  file: "File Sources",
};

const typeColors: Record<string, string> = {
  file: "bg-blue-100 text-blue-800",
  url: "bg-green-100 text-green-800",
  sharepoint: "bg-blue-100 text-blue-800",
  onedrive: "bg-sky-100 text-sky-800",
  azure_blob: "bg-blue-100 text-blue-800",
  aws_s3: "bg-orange-100 text-orange-800",
  sql_server: "bg-red-100 text-red-800",
  postgresql: "bg-blue-100 text-blue-800",
  cosmos_db: "bg-green-100 text-green-800",
  google_drive: "bg-green-100 text-green-800",
  confluence: "bg-blue-100 text-blue-800",
};

export default function DataSourcesPage() {
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [deleting, setDeleting] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<"connected" | "connectors">("connectors");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

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
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Data Sources</h1>
          <p className="text-sm text-gray-500 mt-1">
            Connect to enterprise data stores, cloud storage, and SaaS applications
          </p>
        </div>
        <Link
          href="/dashboard/data-sources/new"
          className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] transition-colors"
        >
          Add Data Source
        </Link>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-6 border-b border-gray-200">
        <button
          type="button"
          onClick={() => setActiveView("connectors")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeView === "connectors"
              ? "border-[#7C3AED] text-[#7C3AED]"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Available Connectors
          <span className="ml-1.5 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
            {connectorTypes.length}
          </span>
        </button>
        <button
          type="button"
          onClick={() => setActiveView("connected")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeView === "connected"
              ? "border-[#7C3AED] text-[#7C3AED]"
              : "border-transparent text-gray-500 hover:text-gray-700"
          }`}
        >
          Connected
          <span className="ml-1.5 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
            {dataSources.length}
          </span>
        </button>
      </div>

      {activeView === "connectors" && (
        <>
          {/* Category filter */}
          <div className="flex items-center gap-2 mb-6">
            {["all", "cloud", "database", "saas"].map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setCategoryFilter(cat)}
                className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                  categoryFilter === cat
                    ? "bg-[#7C3AED] text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {cat === "all" ? "All" : categoryLabels[cat]}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {connectorTypes
              .filter((c) => categoryFilter === "all" || c.category === categoryFilter)
              .map((connector) => (
                <div
                  key={connector.id}
                  className={`relative rounded-lg border bg-white p-5 shadow-sm transition-colors ${
                    connector.available
                      ? "border-gray-200 hover:border-[#7C3AED] hover:shadow-md cursor-pointer"
                      : "border-gray-100 opacity-60"
                  }`}
                  onClick={() => {
                    if (connector.available) {
                      window.location.href = `/dashboard/data-sources/new?type=${connector.id}`;
                    }
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-50">
                      {connector.icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-gray-900">
                          {connector.name}
                        </h3>
                        {!connector.available && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                            <Lock className="h-2.5 w-2.5" />
                            Coming Soon
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                        {connector.description}
                      </p>
                    </div>
                    {connector.available && (
                      <ArrowRight className="h-4 w-4 text-gray-300 shrink-0 mt-1" />
                    )}
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${
                      connector.category === "cloud"
                        ? "bg-sky-100 text-sky-700"
                        : connector.category === "database"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-green-100 text-green-700"
                    }`}>
                      {categoryLabels[connector.category]}
                    </span>
                  </div>
                </div>
              ))}
          </div>
        </>
      )}

      {activeView === "connected" && (
        <>
          {dataSources.length === 0 ? (
            <div className="text-center py-12">
              <FolderOpen className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 mb-4">No data sources connected yet.</p>
              <button
                type="button"
                onClick={() => setActiveView("connectors")}
                className="text-[#7C3AED] hover:text-[#6D28D9] font-medium"
              >
                Browse available connectors →
              </button>
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
        </>
      )}
    </div>
  );
}
