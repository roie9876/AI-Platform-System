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
import { apiFetch } from "@/lib/api";

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
  const [selectedTenantId, setSelectedTenantId] = useState<string | null>(
    user?.tenant_id ?? null
  );
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

  useEffect(() => {
    if (!selectedTenantId && user?.tenant_id) {
      setSelectedTenantId(user.tenant_id);
    }
  }, [user?.tenant_id, selectedTenantId]);

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
