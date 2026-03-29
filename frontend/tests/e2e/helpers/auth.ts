import { Page, Route } from "@playwright/test";

/**
 * Bypasses MSAL authentication by intercepting the /api/config call
 * and injecting mock MSAL state into sessionStorage.
 *
 * This avoids the Microsoft login redirect flow entirely.
 * All API calls still go to the real backend — only the auth token
 * acquisition is mocked.
 */

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
