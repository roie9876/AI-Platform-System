import {
  InteractionRequiredAuthError,
} from "@azure/msal-browser";
import { getMsalInstance, getLoginScopes } from "@/lib/msal";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

let _currentTenantId: string | null = null;

export function setCurrentTenantId(id: string | null) {
  _currentTenantId = id;
}

async function getAccessToken(forceRefresh = false): Promise<string | null> {
  let instance;
  try {
    instance = getMsalInstance();
  } catch {
    console.warn("[apiFetch] MSAL not initialized yet");
    return null;
  }

  const account = instance.getActiveAccount();
  if (!account) {
    console.warn("[apiFetch] No active MSAL account");
    return null;
  }

  try {
    const response = await instance.acquireTokenSilent({
      scopes: getLoginScopes(),
      account,
      forceRefresh,
    });
    return response.accessToken;
  } catch (error) {
    console.error("[apiFetch] acquireTokenSilent failed:", error);
    if (error instanceof InteractionRequiredAuthError) {
      await instance.acquireTokenRedirect({ scopes: getLoginScopes() });
      return null;
    }
    // Don't re-throw MSAL errors — proceed without token so the API
    // returns a proper 401 instead of a cryptic "Failed to fetch"
    return null;
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

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (networkError) {
    console.error("[apiFetch] Network error for", url, networkError);
    throw new Error(`Network error: Unable to reach API at ${url}`);
  }

  // Retry once on 401 with a forced token refresh (handles expired cached tokens)
  if (response.status === 401 && token) {
    const freshToken = await getAccessToken(true);
    if (freshToken && freshToken !== token) {
      headers["Authorization"] = `Bearer ${freshToken}`;
      try {
        response = await fetch(url, { ...options, headers });
      } catch (networkError) {
        console.error("[apiFetch] Network error on retry for", url, networkError);
        throw new Error(`Network error: Unable to reach API at ${url}`);
      }
    }
  }

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
