"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";
import { useAuth } from "@/contexts/auth-context";
import { apiFetch, setCurrentTenantId } from "@/lib/api";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  admin_email: string;
  status: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface TenantContextType {
  tenants: Tenant[];
  selectedTenantId: string | null;
  setSelectedTenantId: (id: string) => void;
  selectedTenant: Tenant | null;
  loading: boolean;
  refreshTenants: () => void;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export function TenantProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const isPlatformAdmin = user?.roles?.includes("platform_admin") ?? false;
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchTenants = useCallback(async () => {
    if (!isPlatformAdmin) return;
    setLoading(true);
    try {
      const data = await apiFetch<{ tenants: Tenant[] }>("/api/v1/tenants");
      setTenants(data.tenants);
    } catch {
      setTenants([]);
    } finally {
      setLoading(false);
    }
  }, [isPlatformAdmin]);

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

  // For non-platform-admins, populate tenants from accessible_tenants
  useEffect(() => {
    if (!isPlatformAdmin && user?.accessible_tenants?.length) {
      setTenants(
        user.accessible_tenants.map((t) => ({
          id: t.id,
          name: t.name,
          slug: t.slug,
          admin_email: "",
          status: "active",
          settings: {},
          created_at: "",
          updated_at: "",
        }))
      );
    }
  }, [isPlatformAdmin, user?.accessible_tenants]);

  // Default to first tenant when tenants load and no valid selection exists
  useEffect(() => {
    if (tenants.length > 0) {
      const currentValid = tenants.some((t) => t.id === selectedTenantId);
      if (!currentValid) {
        setSelectedTenantId(tenants[0].id);
      }
    }
  }, [tenants, selectedTenantId]);

  useEffect(() => {
    setCurrentTenantId(selectedTenantId);
  }, [selectedTenantId]);

  const selectedTenant =
    tenants.find((t) => t.id === selectedTenantId) ?? null;

  return (
    <TenantContext.Provider
      value={{
        tenants,
        selectedTenantId,
        setSelectedTenantId,
        selectedTenant,
        loading,
        refreshTenants: fetchTenants,
      }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  const context = useContext(TenantContext);
  if (!context)
    throw new Error("useTenant must be used within TenantProvider");
  return context;
}
