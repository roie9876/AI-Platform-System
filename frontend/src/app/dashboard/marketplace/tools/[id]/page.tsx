"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Wrench, Download } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface ToolTemplateDetail {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  tags: string[] | null;
  tool_type: string;
  input_schema: Record<string, unknown> | null;
  config: Record<string, unknown> | null;
  author_name: string | null;
  install_count: number;
  version: string;
  is_featured: boolean;
  created_at: string;
}

export default function ToolTemplateDetailPage() {
  const params = useParams();
  const templateId = params.id as string;

  const [template, setTemplate] = useState<ToolTemplateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ tool_id: string; name: string } | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<ToolTemplateDetail>(`/api/v1/marketplace/tools/${templateId}`);
      setTemplate(data);
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [templateId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleImport = async () => {
    setImporting(true);
    try {
      const result = await apiFetch<{ tool_id: string; name: string }>(
        `/api/v1/marketplace/tools/${templateId}/import`,
        { method: "POST" }
      );
      setImportResult(result);
    } catch {
      // silently handle
    } finally {
      setImporting(false);
    }
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;
  if (!template) return <div className="text-center py-12 text-gray-500">Template not found.</div>;

  return (
    <div className="space-y-6 max-w-4xl">
      <Link href="/dashboard/marketplace" className="text-sm text-gray-500 hover:text-gray-700">← Marketplace</Link>

      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-[#F5F3FF]">
            <Wrench className="h-7 w-7 text-[#7C3AED]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{template.name}</h1>
            <div className="flex items-center gap-2 mt-1">
              <span className="rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-700">
                {template.tool_type}
              </span>
              {template.category && (
                <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                  {template.category}
                </span>
              )}
              <span className="text-xs text-gray-500">v{template.version}</span>
            </div>
          </div>
        </div>
        <button
          onClick={handleImport}
          disabled={importing || !!importResult}
          className="flex items-center gap-2 rounded-md bg-[#7C3AED] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
        >
          <Download className="h-4 w-4" />
          {importResult ? "Imported!" : importing ? "Importing..." : "Import Tool"}
        </button>
      </div>

      {importResult && (
        <div className="rounded-md bg-green-50 border border-green-200 p-4 text-sm text-green-800">
          Tool imported successfully!{" "}
          <Link href="/dashboard/tools" className="underline font-medium">
            View tools →
          </Link>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border bg-white p-4 text-center">
          <div className="text-sm text-gray-500">Author</div>
          <div className="font-medium mt-1">{template.author_name ?? "AI Platform"}</div>
        </div>
        <div className="rounded-lg border bg-white p-4 text-center">
          <div className="text-sm text-gray-500">Type</div>
          <div className="font-medium mt-1">{template.tool_type}</div>
        </div>
        <div className="rounded-lg border bg-white p-4 text-center">
          <div className="text-sm text-gray-500">Installs</div>
          <div className="font-medium mt-1">{template.install_count}</div>
        </div>
        <div className="rounded-lg border bg-white p-4 text-center">
          <div className="text-sm text-gray-500">Created</div>
          <div className="font-medium mt-1">{new Date(template.created_at).toLocaleDateString()}</div>
        </div>
      </div>

      {template.description && (
        <div className="rounded-lg border bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Description</h3>
          <p className="text-sm text-gray-600">{template.description}</p>
        </div>
      )}

      {template.input_schema && (
        <div className="rounded-lg border bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Input Schema</h3>
          <pre className="rounded bg-gray-50 p-4 text-sm text-gray-700 font-mono whitespace-pre-wrap max-h-60 overflow-auto">
            {JSON.stringify(template.input_schema, null, 2)}
          </pre>
        </div>
      )}

      {template.tags && template.tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {template.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-600">{tag}</span>
          ))}
        </div>
      )}
    </div>
  );
}
