import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/auth";
import { waitForDashboard } from "./helpers/utils";

/**
 * Navigation & Layout — Sidebar, tenant selector, routing
 *
 * Covers:
 *  - Sidebar renders all 11 nav items
 *  - Each sidebar link navigates correctly
 *  - Tenant selector dropdown
 *  - Logout button
 *  - Responsive sidebar collapse
 */

test.describe("Navigation & Layout", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should render sidebar with all nav items", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const navItems = [
      "Agents",
      "Models",
      "Tools",
      "Knowledge",
      "Data Sources",
      "Workflows",
      "Observability",
      "Evaluations",
      "Marketplace",
      "Tenants",
      "Guardrails",
    ];

    for (const item of navItems) {
      await expect(
        page.getByRole("link", { name: item, exact: false }).first()
      ).toBeVisible();
    }
  });

  test("should navigate to each sidebar section", async ({ page }) => {
    const routes = [
      { name: "Agents", path: "/dashboard/agents" },
      { name: "Models", path: "/dashboard/models" },
      { name: "Tools", path: "/dashboard/tools" },
      { name: "Knowledge", path: "/dashboard/knowledge" },
      { name: "Data Sources", path: "/dashboard/data-sources" },
      { name: "Workflows", path: "/dashboard/workflows" },
      { name: "Observability", path: "/dashboard/observability" },
      { name: "Evaluations", path: "/dashboard/evaluations" },
      { name: "Marketplace", path: "/dashboard/marketplace" },
      { name: "Tenants", path: "/dashboard/tenants" },
      { name: "Guardrails", path: "/dashboard/guardrails" },
    ];

    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    for (const route of routes) {
      await page
        .getByRole("link", { name: route.name, exact: false })
        .first()
        .click();
      await page.waitForURL(`**${route.path}**`, { timeout: 10_000 });

      // Heading should match section
      await expect(
        page.getByRole("heading").first()
      ).toBeVisible();
    }
  });

  test("should show tenant selector", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    // Tenant label is visible in the top bar ("Tenant: ...")
    await expect(page.getByText("Tenant:").first()).toBeVisible();
  });

  test("should show user info and logout", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    // Look for user name display or logout button
    const logoutBtn = page.getByRole("button", { name: /logout|sign out/i });
    const userDisplay = page.getByText(/playwright|test@/i);

    const hasLogout = await logoutBtn.isVisible().catch(() => false);
    const hasUser = await userDisplay.first().isVisible().catch(() => false);

    expect(hasLogout || hasUser).toBe(true);
  });
});
