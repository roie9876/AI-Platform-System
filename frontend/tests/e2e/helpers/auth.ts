import { Page, Route } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

/**
 * Bypasses MSAL authentication by intercepting the /api/config call
 * and injecting mock MSAL state into sessionStorage.
 *
 * This avoids the Microsoft login redirect flow entirely.
 * All API calls still go to the real backend — only the auth token
 * acquisition is mocked.
 */

// ─── SPN Auth (from auth.setup.ts) ──────────────────────────────────────────

const AUTH_FILE = path.join(__dirname, "../../../.auth/session.json");

interface SavedSession {
  accessToken: string;
  tenantId: string;
  selectedTenantId: string;
  expiresOn: number;
  savedAt: number;
}

/**
 * Load a real SPN session saved by auth.setup.ts.
 * Returns null if no session exists or it's expired.
 */
function loadRealSession(): SavedSession | null {
  try {
    if (!fs.existsSync(AUTH_FILE)) return null;
    const data: SavedSession = JSON.parse(fs.readFileSync(AUTH_FILE, "utf-8"));
    if (!data.accessToken) return null;
    if (data.expiresOn && Date.now() > data.expiresOn - 5 * 60 * 1000) {
      console.warn("⚠ SPN token expired. Re-run: npx playwright test --project=setup");
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

/**
 * Sets up authentication using an SPN token saved by auth.setup.ts.
 *
 * Strategy: Use the mock MSAL approach (fake /api/config, inject MSAL cache)
 * but with the REAL SPN token as the secret. This way:
 *  - MSAL's useIsAuthenticated → true (fake account in sessionStorage)
 *  - acquireTokenSilent → returns the real SPN token from cache
 *  - All API route requests get Bearer token + X-Tenant-Id injected
 *
 * The /api/config is intercepted to return a fake clientId so MSAL doesn't
 * talk to the real Entra endpoint. The real token is passed to the backend
 * via route interception on all /api/v1/** calls.
 */
export async function setupRealAuth(page: Page): Promise<boolean> {
  const session = loadRealSession();
  if (!session) return false;

  // Entra (AAD) tenant ID — used for MSAL authority URL
  const entraTenantId = session.tenantId;
  // Platform tenant slug — used for X-Tenant-Id header
  const platformTenantId = session.selectedTenantId || session.tenantId;
  const token = session.accessToken;

  // 1. Intercept /api/config → return fake MSAL config
  //    Uses a synthetic clientId so MSAL doesn't redirect to real login
  const FAKE_CLIENT_ID = "e2e-test-00000000-0000-0000-0000-000000000000";
  await page.route("**/api/config", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        clientId: FAKE_CLIENT_ID,
        tenantId: entraTenantId,
      }),
    });
  });

  // 2. Intercept ALL /api/v1/** calls:
  //    - /api/v1/auth/me → return synthetic user profile
  //    - everything else → inject real Bearer token + tenant header
  //    NOTE: single handler avoids Playwright route priority issues
  //    (last-registered wins, so a general pattern would shadow a specific one)
  await page.route("**/api/v1/**", async (route: Route) => {
    if (route.request().url().includes("/api/v1/auth/me")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "spn-e2e-test",
          email: "e2e-test@aiplatform.dev",
          name: "E2E Test (SPN)",
          roles: ["Platform.Admin"],
          accessible_tenants: [
            { id: platformTenantId, name: "Engineering", slug: "eng", role: "admin" },
          ],
        }),
      });
      return;
    }

    const headers = {
      ...route.request().headers(),
      authorization: `Bearer ${token}`,
      "x-tenant-id": platformTenantId,
    };
    await route.continue({ headers });
  });

  // 3. Inject MSAL sessionStorage cache so useIsAuthenticated → true
  await page.addInitScript(
    ({ clientId, tid, tok }) => {
      const homeAccountId = `spn-e2e-test.${tid}`;
      const accountKey = `${homeAccountId}-login.microsoftonline.com-${tid}`;
      const credKey = `${homeAccountId}-login.microsoftonline.com-accesstoken-${clientId}-${tid}-api://${clientId}/access_as_user`;
      const idKey = `${homeAccountId}-login.microsoftonline.com-idtoken-${clientId}-${tid}-`;

      sessionStorage.setItem(accountKey, JSON.stringify({
        homeAccountId,
        environment: "login.microsoftonline.com",
        realm: tid,
        localAccountId: "spn-e2e-test",
        username: "e2e-test@aiplatform.dev",
        name: "E2E Test (SPN)",
        authorityType: "MSSTS",
        clientInfo: "",
      }));
      sessionStorage.setItem(credKey, JSON.stringify({
        homeAccountId,
        environment: "login.microsoftonline.com",
        credentialType: "AccessToken",
        clientId,
        realm: tid,
        secret: tok,
        target: `api://${clientId}/access_as_user`,
        cachedAt: String(Math.floor(Date.now() / 1000)),
        expiresOn: String(Math.floor(Date.now() / 1000) + 3600),
        extendedExpiresOn: String(Math.floor(Date.now() / 1000) + 7200),
      }));
      sessionStorage.setItem(idKey, JSON.stringify({
        homeAccountId,
        environment: "login.microsoftonline.com",
        credentialType: "IdToken",
        clientId,
        realm: tid,
        secret: tok,
      }));
      sessionStorage.setItem("msal.account.keys", JSON.stringify([accountKey]));
      sessionStorage.setItem(`msal.token.keys.${clientId}`, JSON.stringify({
        idToken: [idKey],
        accessToken: [credKey],
        refreshToken: [],
      }));
      sessionStorage.setItem(`msal.${clientId}.active-account`, homeAccountId);
    },
    { clientId: FAKE_CLIENT_ID, tid: entraTenantId, tok: token }
  );

  return true;
}

/**
 * Smart auth — uses SPN token if available, falls back to mock.
 */
export async function setupSmartAuth(page: Page, tenantId?: string): Promise<void> {
  const usedReal = await setupRealAuth(page);
  if (usedReal) {
    console.log("🔑 Using SPN token (fully automated)");
    return;
  }
  if (process.env.PLAYWRIGHT_API_TOKEN) {
    console.log("🔑 Using PLAYWRIGHT_API_TOKEN env var");
    await setupAuth(page, tenantId);
    return;
  }
  console.log("🔑 Using mock auth (API calls may fail with 401)");
  await setupAuth(page, tenantId);
}

// ─── Mock Auth (original) ────────────────────────────────────────────────────

const MOCK_CLIENT_ID = "00000000-0000-0000-0000-000000000000";
const MOCK_TENANT_ID = "00000000-0000-0000-0000-000000000001";
const MOCK_USER = {
  username: "playwright-test@aiplatform.dev",
  name: "Playwright Test User",
  localAccountId: "test-user-id-001",
  environment: "login.microsoftonline.com",
  tenantId: MOCK_TENANT_ID,
  homeAccountId: `test-user-id-001.${MOCK_TENANT_ID}`,
};

/**
 * Create a fake JWT-like token for testing.
 * The backend will receive this as a Bearer token.
 * If the backend validates JWTs strictly, set PLAYWRIGHT_API_TOKEN env var instead.
 */
function createMockToken(): string {
  if (process.env.PLAYWRIGHT_API_TOKEN) {
    return process.env.PLAYWRIGHT_API_TOKEN;
  }
  // Create a JWT-shaped string (base64 header.payload.signature)
  const header = Buffer.from(JSON.stringify({ alg: "none", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(
    JSON.stringify({
      sub: MOCK_USER.localAccountId,
      name: MOCK_USER.name,
      preferred_username: MOCK_USER.username,
      oid: MOCK_USER.localAccountId,
      tid: MOCK_TENANT_ID,
      aud: `api://${MOCK_CLIENT_ID}`,
      iss: `https://login.microsoftonline.com/${MOCK_TENANT_ID}/v2.0`,
      exp: Math.floor(Date.now() / 1000) + 3600,
      iat: Math.floor(Date.now() / 1000),
      roles: ["platform_admin"],
      tenant_id: process.env.PLAYWRIGHT_TENANT_ID || "",
    })
  ).toString("base64url");
  return `${header}.${payload}.mock-signature`;
}

/**
 * Sets up auth bypass for a Playwright page.
 * Call this before navigating to any page.
 */
export async function setupAuth(page: Page, tenantId?: string) {
  const targetTenantId = tenantId || process.env.PLAYWRIGHT_TENANT_ID || "";

  // Intercept /api/config to return mock MSAL config
  await page.route("**/api/config", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        clientId: MOCK_CLIENT_ID,
        tenantId: MOCK_TENANT_ID,
      }),
    });
  });

  // Intercept /api/v1/auth/me to return mock user
  await page.route("**/api/v1/auth/me", async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: MOCK_USER.localAccountId,
        email: MOCK_USER.username,
        name: MOCK_USER.name,
        roles: ["platform_admin"],
        accessible_tenants: [
          {
            id: targetTenantId,
            name: "Test Tenant",
            slug: "test",
            role: "admin",
          },
        ],
      }),
    });
  });

  // Inject MSAL cache into sessionStorage before page loads
  const token = createMockToken();
  await page.addInitScript(
    ({ user, clientId, tenantId: tid, token: tok }) => {
      const homeAccountId = `${user.localAccountId}.${tid}`;
      const accountKey = `${homeAccountId}-login.microsoftonline.com-${tid}`;
      const credentialKey = `${homeAccountId}-login.microsoftonline.com-accesstoken-${clientId}-${tid}-api://${clientId}/access_as_user`;
      const idTokenKey = `${homeAccountId}-login.microsoftonline.com-idtoken-${clientId}-${tid}-`;

      const accountEntity = {
        homeAccountId,
        environment: "login.microsoftonline.com",
        realm: tid,
        localAccountId: user.localAccountId,
        username: user.username,
        name: user.name,
        authorityType: "MSSTS",
        clientInfo: "",
      };

      const accessTokenEntity = {
        homeAccountId,
        environment: "login.microsoftonline.com",
        credentialType: "AccessToken",
        clientId,
        realm: tid,
        secret: tok,
        target: `api://${clientId}/access_as_user`,
        cachedAt: String(Math.floor(Date.now() / 1000)),
        expiresOn: String(Math.floor(Date.now() / 1000) + 3600),
        extendedExpiresOn: String(Math.floor(Date.now() / 1000) + 7200),
      };

      const idTokenEntity = {
        homeAccountId,
        environment: "login.microsoftonline.com",
        credentialType: "IdToken",
        clientId,
        realm: tid,
        secret: tok,
      };

      sessionStorage.setItem(accountKey, JSON.stringify(accountEntity));
      sessionStorage.setItem(credentialKey, JSON.stringify(accessTokenEntity));
      sessionStorage.setItem(idTokenKey, JSON.stringify(idTokenEntity));
      sessionStorage.setItem(
        `msal.account.keys`,
        JSON.stringify([accountKey])
      );
      sessionStorage.setItem(
        `msal.token.keys.${clientId}`,
        JSON.stringify({
          idToken: [idTokenKey],
          accessToken: [credentialKey],
          refreshToken: [],
        })
      );
      sessionStorage.setItem(`msal.${clientId}.active-account`, homeAccountId);
    },
    {
      user: MOCK_USER,
      clientId: MOCK_CLIENT_ID,
      tenantId: MOCK_TENANT_ID,
      token,
    }
  );
}

/**
 * Adds the X-Tenant-Id header to all API requests.
 * Use after setupAuth to ensure multi-tenant isolation.
 */
export async function setTenantHeader(page: Page, tenantId: string) {
  await page.route("**/api/v1/**", async (route: Route) => {
    const headers = {
      ...route.request().headers(),
      "x-tenant-id": tenantId,
    };
    await route.continue({ headers });
  });
}
