"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { getLoginScopes } from "@/lib/msal";
import { apiFetch } from "@/lib/api";

export interface AccessibleTenant {
  id: string;
  name: string;
  slug: string;
  role: string;
}

interface User {
  id: string;
  email: string;
  full_name: string;
  tenant_id: string;
  roles: string[];
  accessible_tenants: AccessibleTenant[];
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { instance, accounts, inProgress } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const [user, setUser] = useState<User | null>(null);
  const loading = inProgress !== InteractionStatus.None;

  useEffect(() => {
    if (isAuthenticated && accounts.length > 0) {
      const account = accounts[0];
      instance.setActiveAccount(account);
      const claims = account.idTokenClaims as Record<string, unknown> | undefined;
      if (claims) {
        const basicUser: User = {
          id: (claims.oid as string) || "",
          email: (claims.preferred_username as string) || "",
          full_name: (claims.name as string) || "",
          tenant_id: (claims.tid as string) || "",
          roles: (claims.roles as string[]) || [],
          accessible_tenants: [],
        };
        setUser(basicUser);

        // Fetch enriched user info from backend (group-resolved roles + tenant access)
        apiFetch<{
          id: string;
          email: string;
          full_name: string;
          tenant_id: string;
          roles: string[];
          accessible_tenants: AccessibleTenant[];
        }>("/api/v1/auth/me")
          .then((me) => {
            setUser((prev) => ({
              ...prev!,
              roles: me.roles,
              accessible_tenants: me.accessible_tenants || [],
            }));
          })
          .catch((err) => {
            console.error("Failed to fetch enriched user profile:", err);
          });
      }
    } else if (!loading) {
      setUser(null);
    }
  }, [isAuthenticated, accounts, loading, instance]);

  const login = async () => {
    if (inProgress !== InteractionStatus.None) return;
    try {
      await instance.loginRedirect({ scopes: getLoginScopes(), prompt: "select_account" });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "";
      if (!msg.includes("interaction_in_progress")) {
        console.error("Login failed:", e);
      }
    }
  };

  const logout = async () => {
    await instance.logoutRedirect();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
