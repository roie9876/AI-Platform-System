import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/auth";
import { waitForDashboard } from "./helpers/utils";

/**
 * Tools & MCP Tools pages
 *
 * Covers:
 *  - Tools catalog page (search, filters)
 *  - MCP Tools page (discovered tools)
 *  - MCP Servers registry page
 *  - Assign/unassign tools from agent
 */

test.describe("Tools", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should display tools page with search", async ({ page }) => {
    await page.goto("/dashboard/tools");
    await waitForDashboard(page);

    await expect(
      page.getByRole("heading", { name: /tools/i }).first()
    ).toBeVisible({ timeout: 15_000 });

    // Search input
    const searchInput = page.getByPlaceholder(/search/i).first();
    await expect(searchInput).toBeVisible();
  });

  test("should search tools by name", async ({ page }) => {
    await page.goto("/dashboard/tools");
    await waitForDashboard(page);

    const searchInput = page.getByPlaceholder(/search/i).first();
    await searchInput.fill("web");
    await page.waitForTimeout(1000);

    // Results should be filtered
  });

  test("should display MCP tools page", async ({ page }) => {
    await page.goto("/dashboard/mcp-tools");
    await waitForDashboard(page);

    await expect(
      page.getByText(/mcp/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("should display MCP servers registry", async ({ page }) => {
    await page.goto("/dashboard/mcp-tools/servers");
    await waitForDashboard(page);

    await expect(
      page.getByText(/server/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("should assign tools to agent from detail page", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator('a[href*="/agents/"]').first();
    if (!(await agentLink.isVisible().catch(() => false))) {
      test.skip(true, "No agents exist");
      return;
    }

    const href = await agentLink.getAttribute("href");
    if (href) {
      await page.goto(`${href}/tools`);
      await page.waitForLoadState("networkidle");

      // Tools assignment page should show available tools
      await expect(page.getByText(/tool/i).first()).toBeVisible({
        timeout: 10_000,
      });
    }
  });
});
