"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, FileText, X, Download, AlertCircle } from "lucide-react";

type Preview =
  | { kind: "text"; content: string }
  | { kind: "json"; content: string }
  | { kind: "image"; url: string }
  | { kind: "pdf"; url: string }
  | { kind: "binary"; size: number };

interface FileInfo {
  name: string;
  size: number;
  type: string;
  lastModified: number;
}

const MAX_TEXT_BYTES = 5 * 1024 * 1024; // 5MB cap for text preview

const TEXT_EXTENSIONS = new Set([
  "txt", "md", "markdown", "log", "csv", "tsv", "yml", "yaml", "xml",
  "html", "htm", "css", "scss", "less", "js", "mjs", "cjs", "ts", "tsx",
  "jsx", "py", "rb", "go", "rs", "java", "kt", "c", "h", "cpp", "hpp",
  "cs", "php", "sh", "bash", "zsh", "ps1", "sql", "ini", "toml", "env",
  "conf", "cfg", "properties", "dockerfile", "gitignore", "editorconfig",
]);

function getExtension(name: string): string {
  const idx = name.lastIndexOf(".");
  return idx >= 0 ? name.slice(idx + 1).toLowerCase() : "";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function isTextFile(file: File): boolean {
  if (file.type.startsWith("text/")) return true;
  if (file.type === "application/json" || file.type === "application/xml") return true;
  if (file.type === "application/javascript") return true;
  return TEXT_EXTENSIONS.has(getExtension(file.name));
}

export default function FileUploadPage() {
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const objectUrlRef = useRef<string | null>(null);

  const clearPreview = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setFileInfo(null);
    setPreview(null);
    setError(null);
    if (inputRef.current) inputRef.current.value = "";
  }, []);

  const loadFile = useCallback(async (file: File) => {
    clearPreview();
    setLoading(true);
    setError(null);
    setFileInfo({
      name: file.name,
      size: file.size,
      type: file.type || "unknown",
      lastModified: file.lastModified,
    });

    try {
      const ext = getExtension(file.name);

      if (file.type.startsWith("image/")) {
        const url = URL.createObjectURL(file);
        objectUrlRef.current = url;
        setPreview({ kind: "image", url });
      } else if (file.type === "application/pdf" || ext === "pdf") {
        const url = URL.createObjectURL(file);
        objectUrlRef.current = url;
        setPreview({ kind: "pdf", url });
      } else if (isTextFile(file)) {
        if (file.size > MAX_TEXT_BYTES) {
          setError(`File too large to preview (${formatBytes(file.size)}). Limit is ${formatBytes(MAX_TEXT_BYTES)}.`);
        } else {
          const text = await file.text();
          if (file.type === "application/json" || ext === "json") {
            try {
              const parsed = JSON.parse(text);
              setPreview({ kind: "json", content: JSON.stringify(parsed, null, 2) });
            } catch {
              setPreview({ kind: "text", content: text });
            }
          } else {
            setPreview({ kind: "text", content: text });
          }
        }
      } else {
        setPreview({ kind: "binary", size: file.size });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to read file");
    } finally {
      setLoading(false);
    }
  }, [clearPreview]);

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    void loadFile(files[0]);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(true);
  };

  const onDragLeave = () => setDragActive(false);

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">File Upload</h1>
        <p className="mt-1 text-sm text-gray-600">
          Upload a file to preview its contents. Files are processed locally in your browser.
        </p>
      </div>

      {/* Dropzone */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-10 transition-colors ${
          dragActive
            ? "border-[#7C3AED] bg-[#F5F3FF]"
            : "border-gray-300 bg-white hover:border-gray-400"
        }`}
      >
        <Upload className="h-10 w-10 text-gray-400" />
        <p className="mt-3 text-sm font-medium text-gray-900">
          Drag and drop a file here, or click to browse
        </p>
        <p className="mt-1 text-xs text-gray-500">
          Text, JSON, CSV, images, and PDFs are previewed inline.
        </p>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* File info */}
      {fileInfo && (
        <div className="mt-6 rounded-lg border border-gray-200 bg-white p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="rounded-md bg-gray-100 p-2">
                <FileText className="h-5 w-5 text-gray-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">{fileInfo.name}</p>
                <p className="text-xs text-gray-500">
                  {formatBytes(fileInfo.size)} · {fileInfo.type} ·{" "}
                  {new Date(fileInfo.lastModified).toLocaleString()}
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={clearPreview}
              className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
              aria-label="Clear file"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="mt-4 text-sm text-gray-500">Reading file…</div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Preview */}
      {preview && (
        <div className="mt-4 overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="flex items-center justify-between border-b border-gray-200 bg-gray-50 px-4 py-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-gray-600">
              Preview
            </span>
            <span className="text-xs text-gray-500">{preview.kind}</span>
          </div>

          {preview.kind === "text" && (
            <pre className="max-h-[600px] overflow-auto p-4 text-xs leading-relaxed text-gray-800">
              {preview.content}
            </pre>
          )}

          {preview.kind === "json" && (
            <pre className="max-h-[600px] overflow-auto p-4 font-mono text-xs leading-relaxed text-gray-800">
              {preview.content}
            </pre>
          )}

          {preview.kind === "image" && (
            <div className="flex justify-center bg-gray-50 p-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview.url}
                alt={fileInfo?.name ?? "uploaded image"}
                className="max-h-[600px] max-w-full object-contain"
              />
            </div>
          )}

          {preview.kind === "pdf" && (
            <iframe
              src={preview.url}
              title={fileInfo?.name ?? "uploaded pdf"}
              className="h-[700px] w-full"
            />
          )}

          {preview.kind === "binary" && fileInfo && (
            <div className="flex flex-col items-center gap-3 p-8 text-center">
              <p className="text-sm text-gray-600">
                This file type cannot be previewed inline.
              </p>
              <a
                href={URL.createObjectURL(new Blob([]))}
                onClick={(e) => {
                  e.preventDefault();
                  if (inputRef.current?.files?.[0]) {
                    const url = URL.createObjectURL(inputRef.current.files[0]);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = fileInfo.name;
                    a.click();
                    URL.revokeObjectURL(url);
                  }
                }}
                className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
              >
                <Download className="h-4 w-4" />
                Download
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
