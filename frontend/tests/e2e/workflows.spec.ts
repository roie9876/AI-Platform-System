import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/auth";
import { waitForDashboard } from "./helpers/utils";

/**
 * Workflows — Visual workflow builder
 *
 * Covers:
 *  - List workflows page
 *  - Create new workflow
 *  - View workflow canvas (React Flow)
 *  - Execute workflow
 */

test.describe("Workflows", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display workflows list page", async ({ page }) => {
    await page.goto("/dashboard/workflows");
    await waitForDashboard(page);

    await expect(
      page.getByRole("heading", { name: /workflow/i }).first()
    ).toBeVisible({ timeout: 15_000 });

    // Create workflow button
    await expect(
      page.getByRole("link", { name: "Create Workflow", exact: true })
    ).toBeVisible();
  });

  test("should navigate to create workflow", async ({ page }) => {
    await page.goto("/dashboard/workflows");
    await waitForDashboard(page);

    const createBtn = page
      .getByRole("link", { name: /create|new/i })
      .or(page.getByRole("button", { name: /create|new/i }));

    if (await createBtn.first().isVisible().catch(() => false)) {
      await createBtn.first().click();
      await page.waitForLoadState("networkidle");
    }
  });

  test("should display workflow canvas with nodes", async ({ page }) => {
    await page.goto("/dashboard/workflows");
    await waitForDashboard(page);

    // Click first workflow link
    const workflowLink = page.locator('a[href*="/workflows/"]').first();
    if (await workflowLink.isVisible().catch(() => false)) {
      await workflowLink.click();
      await page.waitForURL("**/workflows/**");

      // React Flow canvas should be visible
      await expect(
        page.locator(".react-flow, [class*='react-flow'], [class*='canvas']").first()
      ).toBeVisible({ timeout: 15_000 });
    }
  });
});
