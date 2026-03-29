import { Page, expect, Locator } from "@playwright/test";

/**
 * Shared page-object helpers used across all test suites.
 */

/** Wait for the main dashboard layout to be visible (sidebar loaded). */
export async function waitForDashboard(page: Page) {
  // The sidebar renders nav links — wait for at least one
  await expect(page.locator("nav a, aside a").first()).toBeVisible({
    timeout: 15_000,
  });
}

/** Navigate via sidebar link text. */
export async function navigateTo(page: Page, label: string) {
  await page.getByRole("link", { name: label, exact: false }).first().click();
  await page.waitForLoadState("networkidle");
}

/** Click a button by its visible text. */
export async function clickButton(page: Page, text: string) {
  await page.getByRole("button", { name: text, exact: false }).first().click();
}

/** Fill an input field by label or placeholder text. */
export async function fillField(
  page: Page,
  labelOrPlaceholder: string,
  value: string
) {
  const byLabel = page.getByLabel(labelOrPlaceholder, { exact: false });
  if (await byLabel.isVisible().catch(() => false)) {
    await byLabel.fill(value);
    return;
  }
  const byPlaceholder = page.getByPlaceholder(labelOrPlaceholder, {
    exact: false,
  });
  await byPlaceholder.fill(value);
}

/** Expect a toast / alert / error banner to contain text. */
export async function expectNotification(page: Page, text: string) {
  await expect(
    page.locator('[role="alert"], [class*="toast"], [class*="notification"]')
  ).toContainText(text, { timeout: 10_000 });
}

/** Generate a unique name for test resources to avoid collisions. */
export function uniqueName(prefix: string): string {
  return `${prefix}-pw-${Date.now().toString(36)}`;
}

/** Wait for a table to have at least one row. */
export async function waitForTableRows(page: Page) {
  await expect(page.locator("tbody tr").first()).toBeVisible({
    timeout: 15_000,
  });
}

/** Confirm a browser dialog (window.confirm). */
export function autoConfirmDialogs(page: Page) {
  page.on("dialog", (dialog) => dialog.accept());
}

/** Dismiss a browser dialog (window.confirm). */
export function autoDismissDialogs(page: Page) {
  page.on("dialog", (dialog) => dialog.dismiss());
}
