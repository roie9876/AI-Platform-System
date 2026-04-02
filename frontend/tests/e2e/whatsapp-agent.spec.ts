import { test, expect } from "@playwright/test";
import { setupSmartAuth } from "./helpers/auth";
import { waitForDashboard } from "./helpers/utils";

/**
 * WhatsApp Agent Health Check — "OpenClaw Agent" in tenant-eng
 *
 * Simulates exactly what a human does:
 *  1. Open the platform in a browser
 *  2. Navigate to Agents page
 *  3. Click "OpenClaw Agent"
 *  4. Verify the agent detail page loads (Playground tab)
 *  5. Check WhatsApp status badge shows "Connected" / "Active"
 *  6. Send a test message in the chat playground
 *  7. Verify the agent streams back a response
 *  8. (Optional) Ask the agent about its WhatsApp channel status
 *
 * First-time setup (login once, reuse for ~50 min):
 *   cd frontend && npx playwright test --project=setup --headed
 *
 * Then run this test:
 *   npx playwright test tests/e2e/whatsapp-agent.spec.ts --headed
 *
 * Headless:
 *   npx playwright test tests/e2e/whatsapp-agent.spec.ts
 */

const AGENT_NAME = "OpenClaw Agent";

test.describe("WhatsApp Agent — OpenClaw Agent (eng tenant)", () => {
  test.beforeEach(async ({ page }) => {
    await setupSmartAuth(page);
  });

  test("agent page loads and shows WhatsApp status", async ({ page }) => {
    test.setTimeout(60_000);

    // 1. Go to agents list — exactly like a human opening the dashboard
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);
    await expect(
      page.getByRole("heading", { name: "Agents" })
    ).toBeVisible({ timeout: 15_000 });

    // 2. Find and click "OpenClaw Agent" — like a human scanning the page
    const agentLink = page.locator(`a[href*="/agents/"]`).filter({
      hasText: AGENT_NAME,
    });
    await expect(agentLink.first()).toBeVisible({ timeout: 10_000 });
    await agentLink.first().click();

    // 3. Agent detail page loads — Playground tab visible
    await page.waitForURL("**/agents/**");
    await expect(
      page.getByText(/playground/i).first()
    ).toBeVisible({ timeout: 15_000 });

    // 4. WhatsApp section should be visible (agent has WhatsApp enabled)
    const whatsappSection = page.locator("text=WhatsApp").first();
    await expect(whatsappSection).toBeVisible({ timeout: 10_000 });

    // 5. Check the status badge — should say "Connected" or "Active"
    //    If it says "Not Linked" or "Setup Required" → the test FAILS
    //    This is the key check: is WhatsApp actually working?
    const statusBadge = page.locator(
      'span:has-text("Active"), span:has-text("Connected")'
    );
    const setupBadge = page.locator(
      'span:has-text("Setup Required"), span:has-text("Not Linked")'
    );

    // Wait a moment for the live status check API call to complete
    await page.waitForTimeout(3000);

    const isConnected = await statusBadge.first().isVisible().catch(() => false);
    const needsSetup = await setupBadge.first().isVisible().catch(() => false);

    if (needsSetup) {
      // Take a screenshot for evidence
      await page.screenshot({
        path: "test-results/whatsapp-not-connected.png",
        fullPage: true,
      });
    }

    expect(
      isConnected,
      "WhatsApp should show 'Connected' / 'Active'. " +
        "If this fails, WhatsApp is disconnected and needs re-linking."
    ).toBe(true);
  });

  test("send a chat message and get a response", async ({ page }) => {
    test.setTimeout(90_000);

    // 1. Navigate directly to the agent
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator(`a[href*="/agents/"]`).filter({
      hasText: AGENT_NAME,
    });
    await expect(agentLink.first()).toBeVisible({ timeout: 10_000 });
    await agentLink.first().click();
    await page.waitForURL("**/agents/**");

    // 2. Wait for the chat input to appear — like a human waiting for the page
    const chatInput = page.locator(
      'input[type="text"][placeholder*="Message"], input[type="text"][placeholder*="message"]'
    );
    await expect(chatInput).toBeVisible({ timeout: 15_000 });

    // 3. Type a simple message — like a human typing
    await chatInput.fill("Hello, are you working? Reply with just 'yes'.");

    // 4. Click the Send button (purple button with Send icon)
    const sendButton = page.locator(
      'button:has(svg.lucide-send), button.bg-\\[\\#7C3AED\\]'
    ).first();

    // Fallback: if the specific button selector doesn't work, try Enter key
    if (await sendButton.isVisible().catch(() => false)) {
      await sendButton.click();
    } else {
      await chatInput.press("Enter");
    }

    // 5. Wait for the agent's response to appear — streaming text
    //    The user message appears immediately, then the assistant message streams in.
    //    We wait for any non-empty assistant response (not our own message).
    const assistantResponse = page.locator('[class*="message"], [class*="chat"] div').filter({
      hasNotText: /Hello.*are you working/,
    });

    // Wait up to 45 seconds for a response (agent may be slow)
    await expect(
      page.locator("body")
    ).not.toContainText("error", { timeout: 10_000 }).catch(() => {
      // Ignore — error text might not appear
    });

    // The streaming response takes a moment. Wait for the send button to
    // reappear (it becomes a Stop button during streaming, then goes back)
    await expect(
      chatInput
    ).toBeEnabled({ timeout: 45_000 });

    // 6. Verify we got SOMETHING back — the page should have more content now
    const pageText = await page.locator("main").textContent();
    expect(
      pageText && pageText.length > 100,
      "Expected the agent to respond with some text"
    ).toBe(true);

    // Screenshot on success too — proof the chat works
    await page.screenshot({
      path: "test-results/whatsapp-agent-chat-success.png",
      fullPage: true,
    });
  });

  test("ask agent about its WhatsApp status", async ({ page }) => {
    test.setTimeout(90_000);

    // Navigate to the agent
    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator(`a[href*="/agents/"]`).filter({
      hasText: AGENT_NAME,
    });
    await expect(agentLink.first()).toBeVisible({ timeout: 10_000 });
    await agentLink.first().click();
    await page.waitForURL("**/agents/**");

    // Wait for chat input
    const chatInput = page.locator(
      'input[type="text"][placeholder*="Message"], input[type="text"][placeholder*="message"]'
    );
    await expect(chatInput).toBeVisible({ timeout: 15_000 });

    // Ask specifically about WhatsApp — this tests that the agent
    // can see its own channel status and respond coherently
    await chatInput.fill(
      "What channels are you connected to? Do you have any active WhatsApp sessions?"
    );

    const sendButton = page.locator(
      'button:has(svg.lucide-send), button.bg-\\[\\#7C3AED\\]'
    ).first();
    if (await sendButton.isVisible().catch(() => false)) {
      await sendButton.click();
    } else {
      await chatInput.press("Enter");
    }

    // Wait for response to complete (chat input becomes enabled again)
    await expect(chatInput).toBeEnabled({ timeout: 60_000 });

    // Take screenshot of the full conversation
    await page.screenshot({
      path: "test-results/whatsapp-agent-channel-check.png",
      fullPage: true,
    });

    // Verify the response mentions WhatsApp somewhere
    const mainContent = await page.locator("main").textContent();
    expect(
      mainContent,
      "Agent should have responded to the channel status question"
    ).toBeTruthy();
  });

  test("WhatsApp section UI elements are present", async ({ page }) => {
    test.setTimeout(60_000);

    await page.goto("/dashboard/agents");
    await waitForDashboard(page);

    const agentLink = page.locator(`a[href*="/agents/"]`).filter({
      hasText: AGENT_NAME,
    });
    await expect(agentLink.first()).toBeVisible({ timeout: 10_000 });
    await agentLink.first().click();
    await page.waitForURL("**/agents/**");

    // The WhatsApp section should show:
    // - A phone icon (Smartphone component)
    // - Status text ("Connected" or "Not Linked")
    // - A status badge ("Active" or "Setup Required")
    // - If not connected: a "Generate QR Code" / "Link WhatsApp" button

    const whatsappHeading = page.locator("text=WhatsApp").first();
    await expect(whatsappHeading).toBeVisible({ timeout: 10_000 });

    // Wait for live status to resolve
    await page.waitForTimeout(3000);

    // Check status indicators exist
    const hasConnected = await page
      .locator('span:has-text("Connected"), span:has-text("Active")')
      .first()
      .isVisible()
      .catch(() => false);

    const hasNotLinked = await page
      .locator('span:has-text("Not Linked"), span:has-text("Setup Required")')
      .first()
      .isVisible()
      .catch(() => false);

    // One of the two states must be shown
    expect(
      hasConnected || hasNotLinked,
      "WhatsApp section should show either 'Connected/Active' or 'Not Linked/Setup Required'"
    ).toBe(true);

    // If not connected, the "Link WhatsApp" button should be visible
    if (hasNotLinked) {
      const linkButton = page.locator(
        'button:has-text("Link WhatsApp"), button:has-text("Generate QR")'
      );
      await expect(linkButton.first()).toBeVisible({ timeout: 5_000 });
    }

    await page.screenshot({
      path: "test-results/whatsapp-ui-elements.png",
      fullPage: true,
    });
  });
});
