"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { SubscriptionCard } from "@/components/azure/subscription-card";
import { ResourceCard } from "@/components/azure/resource-card";
import { Cloud, LogIn, ExternalLink, Copy, Check, Loader2 } from "lucide-react";

interface Subscription {
  id: string;
  subscription_id: string;
  display_name: string;
  tenant_azure_id: string | null;
  state: string | null;
}

interface DiscoveredSubscription {
  subscriptionId: string;
  displayName: string;
  tenantId: string;
  state: string;
}

interface DiscoveredResource {
  id: string;
  name: string;
  type: string;
  location: string;
  resourceGroup: string | null;
}

const RESOURCE_TYPES = [
  { value: "Microsoft.Search/searchServices", label: "AI Search" },
  { value: "Microsoft.DocumentDB/databaseAccounts", label: "Cosmos DB" },
  { value: "Microsoft.DBforPostgreSQL/flexibleServers", label: "PostgreSQL" },
];

export default function AzureSubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Device code flow state
  const [deviceCode, setDeviceCode] = useState<{
    user_code: string;
    verification_uri: string;
    device_code: string;
    message: string;
  } | null>(null);
  const [isSigningIn, setIsSigningIn] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [copied, setCopied] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Post-auth state
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [discovered, setDiscovered] = useState<DiscoveredSubscription[]>([]);
  const [isDiscovering, setIsDiscovering] = useState(false);

  // Resource discovery
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [selectedResourceType, setSelectedResourceType] = useState(
    RESOURCE_TYPES[0].value
  );
  const [resources, setResources] = useState<DiscoveredResource[]>([]);
  const [isDiscoveringResources, setIsDiscoveringResources] = useState(false);

  useEffect(() => {
    loadSubscriptions();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  async function loadSubscriptions() {
    try {
      const data = await apiFetch<Subscription[]>(
        "/api/v1/azure/subscriptions"
      );
      setSubscriptions(data);
    } catch {
      // Silently handle — no connected subscriptions yet is normal
    } finally {
      setLoading(false);
    }
  }

  // Step 1: Start device code flow
  async function handleSignIn() {
    setIsSigningIn(true);
    setError("");
    setDeviceCode(null);
    try {
      const data = await apiFetch<{
        user_code: string;
        verification_uri: string;
        device_code: string;
        message: string;
        interval: number;
      }>("/api/v1/azure/auth/device-code", { method: "POST" });

      setDeviceCode(data);

      // Auto-copy code to clipboard
      try {
        await navigator.clipboard.writeText(data.user_code);
        setCopied(true);
        setTimeout(() => setCopied(false), 3000);
      } catch {
        // clipboard may not be available
      }

      // Open Microsoft login page
      window.open(data.verification_uri, "_blank", "noopener,noreferrer");

      // Start polling for token
      setIsPolling(true);
      const interval = Math.max(data.interval || 5, 5) * 1000;
      pollRef.current = setInterval(() => pollForToken(data.device_code), interval);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to start sign-in");
    } finally {
      setIsSigningIn(false);
    }
  }

  // Step 2: Poll for token after user completes sign-in
  async function pollForToken(dc: string) {
    try {
      const result = await apiFetch<{
        status: string;
        access_token?: string;
        error?: string;
      }>("/api/v1/azure/auth/device-code/token", {
        method: "POST",
        body: JSON.stringify({ device_code: dc }),
      });

      if (result.status === "success" && result.access_token) {
        // Stop polling
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setIsPolling(false);
        setDeviceCode(null);
        setAccessToken(result.access_token);

        // Auto-discover subscriptions
        await discoverWithToken(result.access_token);
      } else if (result.status === "expired" || result.status === "error") {
        if (pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
        setIsPolling(false);
        setDeviceCode(null);
        setError(result.error || "Sign-in failed");
      }
      // "pending" → keep polling
    } catch {
      // Network error — keep polling
    }
  }

  function handleCancelSignIn() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setIsPolling(false);
    setDeviceCode(null);
    setIsSigningIn(false);
  }

  async function handleCopyCode() {
    if (!deviceCode) return;
    try {
      await navigator.clipboard.writeText(deviceCode.user_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 3000);
    } catch {
      // fallback — code is visible, user can copy manually
    }
  }

  const discoverWithToken = useCallback(async (token: string) => {
    setIsDiscovering(true);
    try {
      const data = await apiFetch<DiscoveredSubscription[]>(
        "/api/v1/azure/subscriptions/discover",
        { headers: { "X-Azure-Token": token } }
      );
      setDiscovered(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Discovery failed");
    } finally {
      setIsDiscovering(false);
    }
  }, []);

  async function handleConnectSubscription(sub: DiscoveredSubscription) {
    if (!accessToken) return;
    try {
      await apiFetch("/api/v1/azure/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          subscription_id: sub.subscriptionId,
          display_name: sub.displayName,
          tenant_azure_id: sub.tenantId,
          access_token: accessToken,
        }),
      });
      setDiscovered((prev) =>
        prev.filter((d) => d.subscriptionId !== sub.subscriptionId)
      );
      await loadSubscriptions();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Connect failed");
    }
  }

  async function handleConnectAll() {
    for (const sub of [...discovered]) {
      await handleConnectSubscription(sub);
    }
  }

  async function handleDisconnect(id: string) {
    try {
      await apiFetch(`/api/v1/azure/subscriptions/${id}`, {
        method: "DELETE",
      });
      setSubscriptions((prev) => prev.filter((s) => s.id !== id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
    }
  }

  useEffect(() => {
    if (!selectedSubId || !selectedResourceType) {
      setResources([]);
      return;
    }
    setIsDiscoveringResources(true);
    apiFetch<{ resources: DiscoveredResource[] }>(
      `/api/v1/azure/subscriptions/${selectedSubId}/resources?resource_type=${encodeURIComponent(selectedResourceType)}`
    )
      .then((data) => setResources(data.resources || []))
      .catch(() => setResources([]))
      .finally(() => setIsDiscoveringResources(false));
  }, [selectedSubId, selectedResourceType]);

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-gray-500">Loading subscriptions...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">
          Azure Subscriptions
        </h1>
        {!deviceCode && !accessToken && (
          <button
            type="button"
            onClick={handleSignIn}
            disabled={isSigningIn}
            className="flex items-center gap-2 rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
          >
            <LogIn className="h-4 w-4" />
            {isSigningIn ? "Starting..." : "Sign in with Microsoft"}
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Device code sign-in card */}
      {deviceCode && (
        <div className="mb-6 rounded-lg border-2 border-[#7C3AED]/30 bg-white p-6 shadow-sm">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#7C3AED]/10">
              <Loader2 className="h-5 w-5 text-[#7C3AED] animate-spin" />
            </div>
            <div className="flex-1">
              <h2 className="text-base font-semibold text-gray-900 mb-1">
                Sign in to Microsoft
              </h2>
              <p className="text-sm text-gray-600 mb-4">
                A browser tab has opened. Enter this code to sign in:
              </p>

              {/* Code display */}
              <div className="flex items-center gap-3 mb-4">
                <div className="rounded-lg bg-gray-50 border-2 border-gray-200 px-6 py-3">
                  <span className="text-2xl font-mono font-bold tracking-widest text-gray-900">
                    {deviceCode.user_code}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyCode}
                  className="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                >
                  {copied ? (
                    <>
                      <Check className="h-4 w-4 text-green-600" />
                      <span className="text-green-600">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4" />
                      Copy code
                    </>
                  )}
                </button>
              </div>

              <p className="text-sm text-gray-500 mb-3">
                If the tab didn&apos;t open,{" "}
                <a
                  href={deviceCode.verification_uri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[#7C3AED] hover:underline font-medium"
                >
                  open Microsoft login
                  <ExternalLink className="h-3 w-3" />
                </a>
              </p>

              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Waiting for sign-in...
                </div>
                <button
                  type="button"
                  onClick={handleCancelSignIn}
                  className="text-sm text-gray-500 hover:text-gray-700 underline"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Discovered subscriptions after sign-in */}
      {accessToken && (discovered.length > 0 || isDiscovering) && (
        <div className="mb-6 rounded-lg border border-[#7C3AED]/20 bg-[#7C3AED]/5 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#7C3AED] text-white text-sm font-medium">
                <Check className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">Signed in successfully</p>
                <p className="text-xs text-gray-500">Microsoft account connected</p>
              </div>
            </div>
            {discovered.length > 1 && (
              <button
                type="button"
                onClick={handleConnectAll}
                className="rounded-md bg-[#7C3AED] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#6D28D9]"
              >
                Connect all ({discovered.length})
              </button>
            )}
          </div>

          {isDiscovering ? (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Discovering your subscriptions...
            </div>
          ) : discovered.length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-sm font-medium text-gray-700">
                Found {discovered.length} subscription{discovered.length > 1 ? "s" : ""}
              </h3>
              {discovered.map((sub) => (
                <div
                  key={sub.subscriptionId}
                  className="flex items-center justify-between rounded-md border border-gray-200 bg-white p-3"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {sub.displayName}
                    </p>
                    <p className="text-xs text-gray-500 font-mono">
                      {sub.subscriptionId}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleConnectSubscription(sub)}
                    className="rounded-md bg-[#7C3AED] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#6D28D9]"
                  >
                    Connect
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No additional subscriptions found.</p>
          )}
        </div>
      )}

      {/* Empty state */}
      {subscriptions.length === 0 && !deviceCode && !accessToken ? (
        <div className="text-center py-16">
          <Cloud className="h-12 w-12 text-gray-300 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            No subscriptions connected
          </h2>
          <p className="text-sm text-gray-500 max-w-md mx-auto mb-6">
            Connect your Azure subscription to discover AI services, databases,
            and other resources. Sign in with the same Microsoft account you use
            for Azure Portal.
          </p>
          <button
            type="button"
            onClick={handleSignIn}
            disabled={isSigningIn}
            className="inline-flex items-center gap-2 rounded-md bg-[#7C3AED] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
          >
            <LogIn className="h-4 w-4" />
            {isSigningIn ? "Starting..." : "Sign in with Microsoft"}
          </button>
          <p className="mt-3 text-xs text-gray-400">
            No setup required — uses your existing Microsoft credentials
          </p>
        </div>
      ) : (
        <>
          {/* Connected subscriptions */}
          {subscriptions.length > 0 && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {subscriptions.map((sub) => (
                <div key={sub.id} onClick={() => setSelectedSubId(sub.id)}>
                  <SubscriptionCard
                    id={sub.id}
                    subscriptionId={sub.subscription_id}
                    displayName={sub.display_name}
                    onDisconnect={handleDisconnect}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Resource discovery */}
          {subscriptions.length > 0 && (
            <div className="mt-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Discovered Resources
              </h2>
              <div className="mb-4 flex items-center gap-4">
                <select
                  value={selectedSubId || ""}
                  onChange={(e) => setSelectedSubId(e.target.value || null)}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
                >
                  <option value="">Select subscription</option>
                  {subscriptions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.display_name}
                    </option>
                  ))}
                </select>
                <select
                  value={selectedResourceType}
                  onChange={(e) => setSelectedResourceType(e.target.value)}
                  className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
                >
                  {RESOURCE_TYPES.map((rt) => (
                    <option key={rt.value} value={rt.value}>
                      {rt.label}
                    </option>
                  ))}
                </select>
              </div>

              {isDiscoveringResources ? (
                <p className="text-sm text-gray-500">
                  Discovering resources...
                </p>
              ) : resources.length === 0 && selectedSubId ? (
                <p className="text-sm text-gray-500">
                  No{" "}
                  {
                    RESOURCE_TYPES.find(
                      (rt) => rt.value === selectedResourceType
                    )?.label
                  }{" "}
                  resources found in connected subscriptions.
                </p>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {resources.map((r) => (
                    <ResourceCard
                      key={r.id}
                      name={r.name}
                      resourceType={r.type}
                      region={r.location}
                      resourceId={r.id}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
