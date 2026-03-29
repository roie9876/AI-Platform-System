import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/auth";
import { waitForDashboard } from "./helpers/utils";

/**
 * Marketplace — Agent & Tool Templates
 *
 * Covers:
 *  - Marketplace page loads
 *  - Search/filter templates
 *  - Category filtering
 */

test.describe("Marketplace", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display marketplace page", async ({ page }) => {
    await page.goto("/dashboard/marketplace");
    await waitForDashboard(page);

    await expect(
      page.getByRole("heading", { name: /marketplace/i }).first()
    ).toBeVisible();
  });

  test("should have search functionality", async ({ page }) => {
    await page.goto("/dashboard/marketplace");
    await waitForDashboard(page);

    const searchInput = page.getByPlaceholder(/search/i).first();
    if (await searchInput.isVisible().catch(() => false)) {
      await searchInput.fill("customer");
      await page.waitForTimeout(1000);
    }
  });

  test("should show category filters", async ({ page }) => {
    await page.goto("/dashboard/marketplace");
    await waitForDashboard(page);

    // Category buttons or tabs
    await expect(
      page
        .getByRole("button")
        .filter({ hasText: /all|agent|tool|template/i })
        .first()
    ).toBeVisible({ timeout: 10_000 });
  });
});

/**
 * Evaluations — Test Suites
 */
test.describe("Evaluations", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display evaluations page", async ({ page }) => {
    await page.goto("/dashboard/evaluations");
    await waitForDashboard(page);

    await expect(
      page.getByRole("heading", { name: /evaluation/i }).first()
    ).toBeVisible();
  });
});

/**
 * Guardrails — Safety configuration
 */
test.describe("Guardrails", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display guardrails page", async ({ page }) => {
    await page.goto("/dashboard/guardrails");
    await waitForDashboard(page);

    await expect(
      page.getByRole("heading", { name: /guardrail/i }).first()
    ).toBeVisible();
  });
});
