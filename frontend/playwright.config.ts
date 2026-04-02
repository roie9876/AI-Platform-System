import { defineConfig, devices } from "@playwright/test";

/**
 * AI Platform System — Playwright E2E Test Configuration
 *
 * Usage:
 *   npx playwright test                    # Run all tests headless
 *   npx playwright test --headed           # Watch the browser
 *   npx playwright test --ui              # Interactive UI mode
 *   npx playwright test tests/tenants.spec.ts  # Run one suite
 *
 * Auth (fully automated via SPN):
 *   Token is acquired automatically via client_credentials grant.
 *   No human interaction required.
 *
 *   Credentials are read from env vars or fetched from Key Vault:
 *     ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, ENTRA_TENANT_ID
 *     E2E_TENANT_ID  — tenant to test against (default: "eng")
 *
 *   Or set a pre-acquired token:
 *     PLAYWRIGHT_API_TOKEN  — a valid Bearer token (overrides SPN flow)
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false, // Sequential to avoid tenant conflicts
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["html", { open: "never" }], ["list"]],

  use: {
    baseURL:
      process.env.PLAYWRIGHT_BASE_URL ||
      "https://c9f9gagpbsf9fpe7.fz71.alb.azure.com",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    ignoreHTTPSErrors: true,
  },

  projects: [
    // SPN auth setup — acquires token automatically (no browser needed)
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
    },
    // Main test project — uses saved auth from setup
    {
      name: "chromium",
      testIgnore: /auth\.setup\.ts/,
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
