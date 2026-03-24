const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Request failed", code: "UNKNOWN" }));
    const detail = Array.isArray(error.detail)
      ? error.detail.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join(', ')
      : error.detail;
    throw new Error(detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json();
}
