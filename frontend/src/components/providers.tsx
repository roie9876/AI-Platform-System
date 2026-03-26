"use client";

import { ReactNode, useEffect, useState } from "react";
import { MsalProvider } from "@azure/msal-react";
import { PublicClientApplication, EventType, AuthenticationResult, EventMessage } from "@azure/msal-browser";
import { initializeMsal } from "@/lib/msal";
import { AuthProvider } from "@/contexts/auth-context";

export function Providers({ children }: { children: ReactNode }) {
  const [msalInstance, setMsalInstance] = useState<PublicClientApplication | null>(null);

  useEffect(() => {
    initializeMsal().then((instance) => {
      // Set active account from cache if available (covers page refresh after login)
      const accounts = instance.getAllAccounts();
      if (accounts.length > 0 && !instance.getActiveAccount()) {
        instance.setActiveAccount(accounts[0]);
      }

      // Listen for login success and redirect completion to set active account
      instance.addEventCallback((event: EventMessage) => {
        if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
          const result = event.payload as AuthenticationResult;
          if (result.account) {
            instance.setActiveAccount(result.account);
          }
        }
        // After MsalProvider processes redirect, set account from cache
        if (event.eventType === EventType.HANDLE_REDIRECT_END) {
          const accts = instance.getAllAccounts();
          if (accts.length > 0 && !instance.getActiveAccount()) {
            instance.setActiveAccount(accts[0]);
          }
        }
      });

      setMsalInstance(instance);
    });
  }, []);

  if (!msalInstance) return null;

  return (
    <MsalProvider instance={msalInstance}>
      <AuthProvider>{children}</AuthProvider>
    </MsalProvider>
  );
}
