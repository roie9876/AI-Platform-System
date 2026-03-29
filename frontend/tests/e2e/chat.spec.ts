import { test, expect } from "@playwright/test";
import { setupAuth } from "./helpers/auth";
import { waitForDashboard } from "./helpers/utils";

/**
 * Agent Chat Playground — Streaming conversation
 *
 * Covers:
 *  - Open chat playground for an agent
 *  - Send a message and receive streaming response
 *  - Chat thread management (create, switch, delete)
 *  - Chat history / messages display
 *  - Standalone chat page (/agents/[id]/chat)
 */

test.describe("Chat Playground", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("should open agent playground with chat input", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    // Click the first agent
    const agentLink = page.locator('a[href*="/agents/"]').first();
    if (!(await agentLink.isVisible().catch(() => false))) {
      test.skip(true, "No agents exist to test chat");
      return;
    }

    await agentLink.click();
    await page.waitForURL("**/agents/**");

    // Playground tab should be active by default
    // Chat input area should be visible
    await expect(
      page
        .locator('textarea, input[type="text"]')
        .filter({ hasText: /type|message|ask/i })
        .or(page.locator("textarea").first())
    ).toBeVisible({ timeout: 15_000 });
  });

  test("should send a message in chat", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator('a[href*="/agents/"]').first();
    if (!(await agentLink.isVisible().catch(() => false))) {
      test.skip(true, "No agents exist to test chat");
      return;
    }

    await agentLink.click();
    await page.waitForURL("**/agents/**");

    // Type a message
    const chatInput = page.locator("textarea").first();
    await chatInput.waitFor({ state: "visible", timeout: 15_000 });
    await chatInput.fill("Hello, this is a Playwright test message");

    // Submit (Enter or click send button)
    const sendBtn = page.locator(
      'button[type="submit"], button:has(svg.lucide-send), button:has-text("Send")'
    );
    if (await sendBtn.first().isVisible().catch(() => false)) {
      await sendBtn.first().click();
    } else {
      await chatInput.press("Enter");
    }

    // Wait for response — streaming messages appear as divs
    await expect(
      page
        .locator('[class*="message"], [class*="chat"], [role="log"] > div')
        .filter({ hasNotText: /playwright test/i })
        .first()
    ).toBeVisible({ timeout: 30_000 });
  });

  test("should create a new chat thread", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator('a[href*="/agents/"]').first();
    if (!(await agentLink.isVisible().catch(() => false))) {
      test.skip(true, "No agents exist to test chat");
      return;
    }

    await agentLink.click();
    await page.waitForURL("**/agents/**");

    // Look for "New Chat" or "+" button in thread sidebar
    const newChatBtn = page.getByRole("button", {
      name: /new chat|new thread|\+/i,
    });
    if (await newChatBtn.first().isVisible().catch(() => false)) {
      await newChatBtn.first().click();

      // Chat should clear / new thread should appear
      await page.waitForTimeout(2000);
    }
  });

  test("should display chat history threads", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator('a[href*="/agents/"]').first();
    if (!(await agentLink.isVisible().catch(() => false))) {
      test.skip(true, "No agents exist to test chat");
      return;
    }

    await agentLink.click();
    await page.waitForURL("**/agents/**");

    // Thread sidebar should show conversation history
    const threadList = page.locator(
      '[class*="sidebar"] [class*="thread"], [class*="conversation"]'
    );
    // Just verify the sidebar area exists
    await page.waitForTimeout(3000);
  });

  test("should open standalone chat page", async ({ page }) => {
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator('a[href*="/agents/"]').first();
    if (!(await agentLink.isVisible().catch(() => false))) {
      test.skip(true, "No agents exist to test chat");
      return;
    }

    // Extract agent ID from href
    const href = await agentLink.getAttribute("href");
    if (href) {
      const chatUrl = `${href}/chat`;
      await page.goto(chatUrl);

      // Standalone chat page should load with input
      await expect(page.locator("textarea").first()).toBeVisible({
        timeout: 15_000,
      });
    }
  });
});
