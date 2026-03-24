"use client";

interface SubscriptionCardProps {
  id: string;
  subscriptionId: string;
  displayName: string;
  resourceCount?: number;
  onDisconnect: (id: string) => void;
}

export function SubscriptionCard({
  id,
  subscriptionId,
  displayName,
  resourceCount,
  onDisconnect,
}: SubscriptionCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="text-base font-semibold text-gray-900">{displayName}</h3>
      <p className="mt-1 text-xs font-mono text-gray-500">{subscriptionId}</p>
      {resourceCount !== undefined && (
        <p className="mt-1 text-sm text-gray-500">
          {resourceCount} resources discovered
        </p>
      )}
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={() => {
            if (
              window.confirm(
                "This will remove all discovered resources and connections associated with this subscription. Are you sure?"
              )
            ) {
              onDisconnect(id);
            }
          }}
          className="text-sm text-red-600 hover:text-red-700"
        >
          Disconnect
        </button>
      </div>
    </div>
  );
}
