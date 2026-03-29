import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/auth";

/**
 * Login & Auth Flow
 *
 * Covers:
 *  - Landing page redirects unauthenticated users
 *  - Login page renders Microsoft sign-in button
 *  - Authenticated users redirect to /dashboard/agents
 *  - /register redirects to /login
 */

test.describe("Authentication", () => {
  test("should show login page with Microsoft sign-in", async ({ page }) => {
    // Do NOT set up auth — test unauthenticated flow
    await page.goto("/login");

    await expect(
      page.getByText(/sign in|microsoft|login/i).first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test("should show sign-in button on landing page", async ({ page }) => {
    await page.goto("/");

    // Landing page should have a sign-in or get-started button
    await expect(
      page
        .getByRole("link", { name: /sign in|get started|login/i })
        .or(page.getByRole("button", { name: /sign in|get started/i }))
        .first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test("should redirect authenticated users to dashboard", async ({
    page,
  }) => {
    await setupAuth(page);
    await page.goto("/");

    // Should redirect to dashboard
    await page.waitForURL("**/dashboard/**", { timeout: 15_000 });
  });

  test("/register should redirect to /login", async ({ page }) => {
    await page.goto("/register");

    await page.waitForURL("**/login**", { timeout: 10_000 });
  });
});
