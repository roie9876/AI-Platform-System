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
 * Auth:
 *   Tests use API-level auth by mocking MSAL and injecting tokens.
 *   Set these env vars before running:
 *     PLAYWRIGHT_BASE_URL   — default: https://c9f9gagpbsf9fpe7.fz71.alb.azure.com
 *     PLAYWRIGHT_API_TOKEN  — a valid Bearer token (optional, uses mock by default)
 *     PLAYWRIGHT_TENANT_ID  — tenant to test against
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
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
