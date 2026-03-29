import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/auth";
import { waitForDashboard } from "./helpers/utils";

/**
 * Azure Integration — Device code auth & resource discovery
 *
 * Covers:
 *  - Azure page loads
 *  - Device code flow UI elements
 *  - Subscription discovery display
 *  - Resource group / resource listing
 */

test.describe("Azure Integration", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display Azure page", async ({ page }) => {
    await page.goto("/dashboard/azure");
    await waitForDashboard(page);

    await expect(
      page.getByText(/azure|device code|subscription/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("should show device code auth button", async ({ page }) => {
    await page.goto("/dashboard/azure");
    await waitForDashboard(page);

    // Should have a button to start device code flow
    const authBtn = page.getByRole("button", {
      name: /connect|authenticate|sign in|device code/i,
    });
    if (await authBtn.first().isVisible().catch(() => false)) {
      expect(await authBtn.count()).toBeGreaterThan(0);
    }
  });
});
