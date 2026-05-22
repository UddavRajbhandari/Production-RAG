import { test, expect } from '@playwright/test';

test.describe('Streaming UX', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('query page loads with input field', async ({ page }) => {
    const input = page.locator('textarea[placeholder*="Ask about your documents"]');
    await expect(input).toBeVisible({ timeout: 10000 });
  });

  test('sends query and receives streaming response', async ({ page }) => {
    const input = page.locator('textarea[placeholder*="Ask about your documents"]');
    const sendButton = page.locator('button[aria-label="Send message"]');

    await expect(input).toBeVisible({ timeout: 10000 });
    await input.fill('What is the World Bank fiscal year?');
    await sendButton.click();

    // Wait for the assistant message to appear with streaming content
    const assistantMessage = page.locator('text=World Bank').first();
    await expect(assistantMessage).toBeVisible({ timeout: 120000 });

    // Verify sources panel appears
    const sourcesButton = page.locator('button:has-text("source")');
    await expect(sourcesButton).toBeVisible({ timeout: 120000 });
  });

  test('shows thinking indicator while streaming', async ({ page }) => {
    const input = page.locator('textarea[placeholder*="Ask about your documents"]');
    const sendButton = page.locator('button[aria-label="Send message"]');

    await input.fill('What is Python?');
    await sendButton.click();

    // Thinking indicator appears
    const thinking = page.locator('text=Thinking');
    await expect(thinking).toBeVisible({ timeout: 5000 });
  });

  test('displays sources after streaming completes', async ({ page }) => {
    const input = page.locator('textarea[placeholder*="Ask about your documents"]');
    const sendButton = page.locator('button[aria-label="Send message"]');

    await input.fill('What is the IMF GDP projection?');
    await sendButton.click();

    // Wait for sources button
    const sourcesButton = page.locator('button:has-text("source")');
    await expect(sourcesButton).toBeVisible({ timeout: 120000 });

    // Click to expand sources
    await sourcesButton.click();
    const sourcePanel = page.locator('text=source').first();
    await expect(sourcePanel).toBeVisible();
  });

  test('no console errors during query', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    const input = page.locator('textarea[placeholder*="Ask about your documents"]');
    const sendButton = page.locator('button[aria-label="Send message"]');

    await input.fill('What is the project about?');
    await sendButton.click();

    // Wait for response
    await page.locator('button:has-text("source")').waitFor({ timeout: 120000 });

    expect(consoleErrors).toHaveLength(0);
  });
});
