"use client";

import { ReactNode } from "react";
import { MsalProvider } from "@azure/msal-react";
import { msalInstance } from "@/lib/msal";
import { AuthProvider } from "@/contexts/auth-context";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <MsalProvider instance={msalInstance}>
      <AuthProvider>{children}</AuthProvider>
    </MsalProvider>
  );
}
