import { PublicClientApplication, Configuration } from "@azure/msal-browser";

const msalConfig: Configuration = {
  auth: {
    clientId: process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || "",
    authority: `https://login.microsoftonline.com/${process.env.NEXT_PUBLIC_AZURE_TENANT_ID || "common"}`,
    redirectUri: typeof window !== "undefined" ? window.location.origin : "",
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

export const loginScopes = [
  `api://${process.env.NEXT_PUBLIC_AZURE_CLIENT_ID}/access_as_user`,
];
