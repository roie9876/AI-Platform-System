"use client";

import { ReactNode, useEffect, useState } from "react";
import { MsalProvider } from "@azure/msal-react";
import { PublicClientApplication, EventType, AuthenticationResult, EventMessage } from "@azure/msal-browser";
import { initializeMsal } from "@/lib/msal";
import { AuthProvider } from "@/contexts/auth-context";

export function Providers({ children }: { children: ReactNode }) {
  const [msalInstance, setMsalInstance] = useState<PublicClientApplication | null>(null);

  useEffect(() => {
    initializeMsal().then(async (instance) => {
      // Listen for login success and redirect completion to set active account
      instance.addEventCallback((event: EventMessage) => {
        if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
          const result = event.payload as AuthenticationResult;
          if (result.account) {
            instance.setActiveAccount(result.account);
          }
        }
      });

      // CRITICAL: handleRedirectPromise must be called to process the auth code
      // from the URL after login redirect. Without this, acquireTokenSilent has
      // no cached tokens and all API calls return 401.
      try {
        const result = await instance.handleRedirectPromise();
        if (result?.account) {
          instance.setActiveAccount(result.account);
        }
      } catch (err) {
        console.error("[Providers] handleRedirectPromise failed:", err);
      }

      // Set active account from cache if available (covers page refresh after login)
      const accounts = instance.getAllAccounts();
      if (accounts.length > 0 && !instance.getActiveAccount()) {
        instance.setActiveAccount(accounts[0]);
      }

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
