"use client";

import { useAuth } from "@/contexts/auth-context";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";

function DashboardContent() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <div className="max-w-md w-full rounded-lg border border-gray-200 bg-white p-8 shadow-sm dark:border-gray-800 dark:bg-gray-950">
        <h1 className="text-2xl font-bold tracking-tight mb-2">
          Welcome, {user?.full_name}
        </h1>
        <div className="space-y-2 text-sm text-gray-600 dark:text-gray-400 mb-6">
          <p>
            <span className="font-medium text-gray-900 dark:text-gray-200">Email:</span>{" "}
            {user?.email}
          </p>
          <p>
            <span className="font-medium text-gray-900 dark:text-gray-200">Tenant:</span>{" "}
            {user?.tenant_id}
          </p>
        </div>
        <button
          onClick={handleLogout}
          className="w-full rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-900"
        >
          Logout
        </button>
      </div>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}
