import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/auth";
import { waitForDashboard } from "./helpers/utils";

/**
 * Knowledge & Data Sources pages
 *
 * Covers:
 *  - Knowledge connections page (Azure AI Search, Cognitive Services)
 *  - Data Sources page (SharePoint, OneDrive, S3, SQL, etc.)
 *  - Agent data-sources assignment
 */

test.describe("Knowledge", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display knowledge page", async ({ page }) => {
    await page.goto("/dashboard/knowledge");
    await waitForDashboard(page);

    await expect(
      page.getByRole("heading", { name: /knowledge/i }).first()
    ).toBeVisible();
  });

  test("should show Azure connection options", async ({ page }) => {
    await page.goto("/dashboard/knowledge");
    await waitForDashboard(page);

    // Should show options for Azure resources
    await expect(
      page.getByText(/connect|azure|search|resource/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Data Sources", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display data sources page", async ({ page }) => {
    await page.goto("/dashboard/data-sources");
    await waitForDashboard(page);

    await expect(
      page.getByRole("heading", { name: /data source/i }).first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test("should show connector type options", async ({ page }) => {
    await page.goto("/dashboard/data-sources");
    await waitForDashboard(page);

    // Should show connector type buttons (SharePoint, S3, SQL, etc.)
    await expect(
      page
        .getByText(/sharepoint|onedrive|s3|sql|postgres|cosmos|confluence/i)
        .first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test("should view agent data sources assignment", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator('a[href*="/agents/"]').first();
    if (!(await agentLink.isVisible().catch(() => false))) {
      test.skip(true, "No agents exist");
      return;
    }

    const href = await agentLink.getAttribute("href");
    if (href) {
      await page.goto(`${href}/data-sources`);
      await page.waitForLoadState("networkidle");

      await expect(page.getByText(/data source|knowledge/i).first()).toBeVisible({
        timeout: 10_000,
      });
    }
  });
});
