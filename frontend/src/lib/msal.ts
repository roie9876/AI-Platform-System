import { PublicClientApplication, Configuration } from "@azure/msal-browser";

// Azure CLI's well-known public client ID — no app registration needed
const AZURE_CLI_CLIENT_ID = "04b07795-a710-4532-9f57-d672f9e2b8c8";

const msalConfig: Configuration = {
  auth: {
    clientId: process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || AZURE_CLI_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${process.env.NEXT_PUBLIC_AZURE_TENANT_ID || "common"}`,
    redirectUri: typeof window !== "undefined" ? window.location.origin : "",
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

export const azureLoginScopes = [
  "https://management.azure.com/user_impersonation",
];
