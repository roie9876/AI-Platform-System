"use client";

import { useAuth } from "@/contexts/auth-context";
import { useRouter } from "next/navigation";
import { ProtectedRoute } from "@/components/protected-route";
import { FoundrySidebar } from "@/components/layout/foundry-sidebar";

function DashboardLayoutInner({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* Top bar */}
      <header className="flex h-12 shrink-0 items-center justify-end border-b border-gray-200 bg-white px-6">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => router.push("/dashboard/azure")}
            className="flex items-center gap-1.5 rounded-md border border-gray-200 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="M2 20a2.4 2.4 0 0 0 2 1h16a2.4 2.4 0 0 0 2-1L13.7 2.4a1.6 1.6 0 0 0-3.4 0Z"/><path d="M2 20h20"/></svg>
            Azure
          </button>
          <span className="text-sm text-gray-600">{user?.full_name}</span>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Sidebar + Main */}
      <div className="flex flex-1 overflow-hidden">
        <FoundrySidebar />
        <main className="flex-1 overflow-auto bg-gray-50">
          {children}
        </main>
      </div>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <DashboardLayoutInner>{children}</DashboardLayoutInner>
    </ProtectedRoute>
  );
}
