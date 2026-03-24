"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";
import { SubscriptionCard } from "@/components/azure/subscription-card";
import { ResourceCard } from "@/components/azure/resource-card";

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
  {
    value: "Microsoft.Search/searchServices",
    label: "AI Search",
  },
  {
    value: "Microsoft.DocumentDB/databaseAccounts",
    label: "Cosmos DB",
  },
  {
    value: "Microsoft.DBforPostgreSQL/flexibleServers",
    label: "PostgreSQL",
  },
];

export default function AzureSubscriptionsPage() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Connect flow
  const [showConnectForm, setShowConnectForm] = useState(false);
  const [accessToken, setAccessToken] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);
  const [discovered, setDiscovered] = useState<DiscoveredSubscription[]>([]);

  // Resource discovery
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [selectedResourceType, setSelectedResourceType] = useState(
    RESOURCE_TYPES[0].value
  );
  const [resources, setResources] = useState<DiscoveredResource[]>([]);
  const [isDiscovering, setIsDiscovering] = useState(false);

  useEffect(() => {
    loadSubscriptions();
  }, []);

  async function loadSubscriptions() {
    try {
      const data = await apiFetch<Subscription[]>(
        "/api/v1/azure/subscriptions"
      );
      setSubscriptions(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  async function handleDiscover() {
    if (!accessToken.trim()) return;
    setIsConnecting(true);
    setError("");
    try {
      const data = await apiFetch<DiscoveredSubscription[]>(
        "/api/v1/azure/subscriptions/discover",
        {
          headers: { "X-Azure-Token": accessToken },
        }
      );
      setDiscovered(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Discovery failed");
    } finally {
      setIsConnecting(false);
    }
  }

  async function handleConnectSubscription(sub: DiscoveredSubscription) {
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
    setIsDiscovering(true);
    apiFetch<{ resources: DiscoveredResource[] }>(
      `/api/v1/azure/subscriptions/${selectedSubId}/resources?resource_type=${encodeURIComponent(selectedResourceType)}`
    )
      .then((data) => setResources(data.resources || []))
      .catch(() => setResources([]))
      .finally(() => setIsDiscovering(false));
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
        <button
          type="button"
          onClick={() => setShowConnectForm(true)}
          className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
        >
          Connect subscription
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Connect form */}
      {showConnectForm && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-2">
            Connect Azure Subscription
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            In production, you&apos;ll sign in with your Azure credentials. For
            this PoC, paste an Azure access token.
          </p>
          <textarea
            value={accessToken}
            onChange={(e) => setAccessToken(e.target.value)}
            placeholder="Paste your Azure access token here..."
            rows={3}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-[#7C3AED] focus:outline-none focus:ring-1 focus:ring-[#7C3AED]"
          />
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={handleDiscover}
              disabled={isConnecting || !accessToken.trim()}
              className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9] disabled:opacity-50"
            >
              {isConnecting ? "Discovering..." : "Discover subscriptions"}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowConnectForm(false);
                setDiscovered([]);
                setAccessToken("");
              }}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>

          {/* Discovered subscriptions */}
          {discovered.length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Discovered Subscriptions
              </h3>
              <div className="space-y-2">
                {discovered.map((sub) => (
                  <div
                    key={sub.subscriptionId}
                    className="flex items-center justify-between rounded-md border border-gray-200 p-3"
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
            </div>
          )}
        </div>
      )}

      {/* Connected subscriptions */}
      {subscriptions.length === 0 && !showConnectForm ? (
        <div className="text-center py-16">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            No subscriptions connected
          </h2>
          <p className="text-sm text-gray-500 max-w-md mx-auto mb-4">
            Connect your Azure subscription to discover AI services, databases,
            and other resources. You&apos;ll sign in with the same credentials
            you use for Azure Portal.
          </p>
          <button
            type="button"
            onClick={() => setShowConnectForm(true)}
            className="rounded-md bg-[#7C3AED] px-4 py-2 text-sm font-medium text-white hover:bg-[#6D28D9]"
          >
            Connect subscription
          </button>
        </div>
      ) : (
        <>
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

              {isDiscovering ? (
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
