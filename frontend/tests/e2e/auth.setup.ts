import { test as setup } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import * as https from "https";

/**
 * Global Auth Setup — SPN (Service Principal) Token Acquisition
 *
 * Fully automated — zero human interaction required.
 *
 * This runs ONCE before all tests. It:
 *  1. Reads Entra client credentials from env vars (or fetches from Key Vault)
 *  2. Acquires an app-only token via client_credentials grant
 *  3. Saves it to .auth/session.json for all tests to reuse
 *
 * Required env vars (or fetched from Azure Key Vault):
 *   ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, ENTRA_TENANT_ID
 *
 * The saved session is valid for ~50 minutes. Re-runs automatically refresh.
 */

const AUTH_DIR = path.join(__dirname, "../../.auth");
const AUTH_FILE = path.join(AUTH_DIR, "session.json");

// Max age before we consider the token stale (50 minutes)
const MAX_TOKEN_AGE_MS = 50 * 60 * 1000;

function isTokenFresh(): boolean {
  try {
    if (!fs.existsSync(AUTH_FILE)) return false;
    const data = JSON.parse(fs.readFileSync(AUTH_FILE, "utf-8"));
    if (!data.accessToken || !data.savedAt) return false;
    return Date.now() - data.savedAt < MAX_TOKEN_AGE_MS;
  } catch {
    return false;
  }
}

async function execAz(args: string[]): Promise<string> {
  const { execFileSync } = await import("child_process");
  return execFileSync("az", args, { encoding: "utf-8" }).trim();
}

async function getCredentials(): Promise<{
  clientId: string;
  clientSecret: string;
  tenantId: string;
}> {
  const clientId = process.env.ENTRA_CLIENT_ID;
  const clientSecret = process.env.ENTRA_CLIENT_SECRET;
  const tenantId = process.env.ENTRA_TENANT_ID;

  if (clientId && clientSecret && tenantId) {
    return { clientId, clientSecret, tenantId };
  }

  // Fall back to Azure Key Vault
  console.log("  Fetching credentials from Key Vault...");
  const vaultName = "stumsft-aiplat-prod-kv";
  const [kvClientId, kvSecret, kvTenantId] = await Promise.all([
    execAz(["keyvault", "secret", "show", "--vault-name", vaultName, "--name", "entra-client-id", "--query", "value", "-o", "tsv"]),
    execAz(["keyvault", "secret", "show", "--vault-name", vaultName, "--name", "entra-client-secret", "--query", "value", "-o", "tsv"]),
    execAz(["keyvault", "secret", "show", "--vault-name", vaultName, "--name", "entra-tenant-id", "--query", "value", "-o", "tsv"]),
  ]);
  return { clientId: kvClientId, clientSecret: kvSecret, tenantId: kvTenantId };
}

function acquireToken(
  clientId: string,
  clientSecret: string,
  tenantId: string,
): Promise<{ access_token: string; expires_in: number }> {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      scope: `api://${clientId}/.default`,
      grant_type: "client_credentials",
    }).toString();

    const req = https.request(
      {
        hostname: "login.microsoftonline.com",
        path: `/${tenantId}/oauth2/v2.0/token`,
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk: Buffer) => (data += chunk.toString()));
        res.on("end", () => {
          const parsed = JSON.parse(data);
          if (parsed.error) {
            reject(new Error(`Token error: ${parsed.error_description || parsed.error}`));
          } else {
            resolve(parsed);
          }
        });
      },
    );
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

setup("authenticate with SPN", async () => {
  if (isTokenFresh()) {
    console.log("✓ Existing SPN token is still fresh — skipping");
    return;
  }

  console.log("🔐 Acquiring SPN token via client_credentials...");

  const { clientId, clientSecret, tenantId } = await getCredentials();
  const tokenResp = await acquireToken(clientId, clientSecret, tenantId);

  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  }

  const expiresOn = Date.now() + tokenResp.expires_in * 1000;

  const sessionData = {
    accessToken: tokenResp.access_token,
    tenantId,
    selectedTenantId: process.env.E2E_TENANT_ID || "eng",
    expiresOn,
    savedAt: Date.now(),
  };

  fs.writeFileSync(AUTH_FILE, JSON.stringify(sessionData, null, 2));
  console.log("✓ SPN token saved to .auth/session.json");
  console.log(`  Expires: ${new Date(expiresOn).toLocaleTimeString()}`);
  console.log(`  Tenant: ${sessionData.selectedTenantId}`);
});
