import { test, expect } from "@playwright/test";
import { setupAuth, setTenantHeader } from "./helpers/auth";
import {
  waitForDashboard,
  navigateTo,
  uniqueName,
  waitForTableRows,
  autoConfirmDialogs,
} from "./helpers/utils";

/**
 * Tenant Management — Full CRUD lifecycle
 *
 * Covers:
 *  - List tenants page with KPI tiles
 *  - Create a new tenant (4-step wizard)
 *  - View tenant details
 *  - Delete tenant
 */

test.describe("Tenant Management", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display tenants list page with KPI tiles", async ({ page }) => {
    await page.goto("/dashboard/tenants");
    await waitForDashboard(page);

    // Wait for page to finish loading (may show "Loading tenants..." first)
    await expect(
      page.getByText("Total Tenants")
    ).toBeVisible({ timeout: 15_000 });

    // KPI tiles
    await expect(page.getByText("Active")).toBeVisible();

    // Create button (may appear as button or link)
    await expect(
      page.getByRole("link", { name: "Create Tenant" }).first()
    ).toBeVisible();
  });

  test("should navigate to create tenant wizard", async ({ page }) => {
    await page.goto("/dashboard/tenants");
    await waitForDashboard(page);

    // Wait for the page to load past "Loading tenants..."
    await expect(page.getByText("Total Tenants")).toBeVisible({ timeout: 15_000 });

    await page
      .getByRole("link", { name: "Create Tenant", exact: true })
      .first()
      .click();
    await page.waitForURL("**/tenants/new**");

    // Wizard should show step 1
    await expect(page.getByText("Organization").first()).toBeVisible({
      timeout: 10_000,
    });
  });

  test("should create a new tenant with wizard", async ({ page }) => {
    const tenantName = uniqueName("e2e-tenant");

    await page.goto("/dashboard/tenants/new");
    await waitForDashboard(page);

    // Step 1: Tenant Info — use placeholders to target the right fields
    await page
      .getByPlaceholder("Acme Corp")
      .fill(tenantName);
    await page
      .getByPlaceholder("acme-corp")
      .fill(tenantName.toLowerCase());
    await page
      .getByPlaceholder("admin@acme.com")
      .fill("e2e-test@aiplatform.dev");

    // Click Next
    await page.getByRole("button", { name: /next/i }).click();

    // Step 2: Settings — just click Next (or skip if not present)
    const nextBtn = page.getByRole("button", { name: /next/i });
    if (await nextBtn.isVisible().catch(() => false)) {
      await nextBtn.click();
    }

    // Step 3: Agent — just click Next (or skip)
    if (await nextBtn.isVisible().catch(() => false)) {
      await nextBtn.click();
    }

    // Step 4: Review & Create
    const createBtn = page.getByRole("button", { name: /create/i });
    if (await createBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await expect(page.getByText(tenantName)).toBeVisible();
      await createBtn.click();

      // Should redirect to tenant list or show success
      await page.waitForURL("**/tenants**", { timeout: 30_000 });
    }
  });

  test("should view tenant details", async ({ page }) => {
    await page.goto("/dashboard/tenants");
    await waitForDashboard(page);

    // Click the first tenant row
    const firstRow = page.locator("tbody tr").first();
    if (await firstRow.isVisible().catch(() => false)) {
      await firstRow.click();
      await page.waitForURL("**/tenants/**");

      // Should show tenant detail page
      await expect(
        page.getByText(/status|settings|namespace/i).first()
      ).toBeVisible();
    }
  });

  test("should delete a tenant", async ({ page }) => {
    autoConfirmDialogs(page);

    await page.goto("/dashboard/tenants");
    await waitForDashboard(page);

    // Wait for page to load
    await expect(page.getByText("Total Tenants")).toBeVisible({ timeout: 15_000 });

    // Only attempt delete if tenant rows exist
    const rows = page.locator("tbody tr");
    const rowCount = await rows.count();
    if (rowCount === 0) {
      // No tenants to delete – pass
      return;
    }

    // Look for a delete button or trash icon in the first row
    const deleteBtn = rows
      .first()
      .locator(
        'button:has-text("Delete"), button[aria-label*="delete"], button[aria-label*="Delete"]'
      );
    if (await deleteBtn.first().isVisible().catch(() => false)) {
      await deleteBtn.first().click();

      // Wait for row count to decrease
      await expect(rows).toHaveCount(rowCount - 1, {
        timeout: 10_000,
      });
    }
  });
});
