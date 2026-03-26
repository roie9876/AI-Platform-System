import { PublicClientApplication, Configuration, BrowserCacheLocation } from "@azure/msal-browser";

let msalInstance: PublicClientApplication | null = null;
let loginScopes: string[] = [];

export async function initializeMsal(): Promise<PublicClientApplication> {
  if (msalInstance) return msalInstance;

  const res = await fetch("/api/config");
  const config = await res.json();
  const clientId = config.clientId || "";
  const tenantId = config.tenantId || "common";

  const msalConfig: Configuration = {
    auth: {
      clientId,
      authority: `https://login.microsoftonline.com/${tenantId}`,
      redirectUri: typeof window !== "undefined" ? window.location.origin : "",
    },
    cache: {
      cacheLocation: BrowserCacheLocation.SessionStorage,
    },
  };

  msalInstance = new PublicClientApplication(msalConfig);
  loginScopes = [`api://${clientId}/access_as_user`];

  await msalInstance.initialize();

  return msalInstance;
}

export function getMsalInstance(): PublicClientApplication {
  if (!msalInstance) throw new Error("MSAL not initialized — call initializeMsal() first");
  return msalInstance;
}

export function getLoginScopes(): string[] {
  return loginScopes;
}
