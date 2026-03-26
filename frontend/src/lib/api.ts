import {
  InteractionRequiredAuthError,
} from "@azure/msal-browser";
import { msalInstance, loginScopes } from "@/lib/msal";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

let _currentTenantId: string | null = null;

export function setCurrentTenantId(id: string | null) {
  _currentTenantId = id;
}

async function getAccessToken(): Promise<string | null> {
  const account = msalInstance.getActiveAccount();
  if (!account) return null;

  try {
    const response = await msalInstance.acquireTokenSilent({
      scopes: loginScopes,
      account,
    });
    return response.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      await msalInstance.acquireTokenRedirect({ scopes: loginScopes });
      return null;
    }
    throw error;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const token = await getAccessToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (_currentTenantId) {
    headers["X-Tenant-Id"] = _currentTenantId;
  }

  const response = await fetch(url, {
    ...options,
    headers,
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
