import { test, expect, layoutScreenshot } from "./fixtures";
import baseline from "../src/__fixtures__/collaboration/baseline.json" with { type: "json" };
import verified from "../src/__fixtures__/collaboration/verified.json" with { type: "json" };

for (const { mode, endpoint, payload } of [
  { mode: "standard", endpoint: "/api/v1/chat", payload: { answer: "Synthetic retry answer", mode: "extractive", sources: [] } },
  { mode: "collaboration", endpoint: "/api/v1/collaborate", payload: baseline },
  { mode: "verified", endpoint: "/api/v1/collaborate", payload: verified },
]) {
  test(`${mode} can be cancelled by keyboard and retried`, async ({ page }, info) => {
    let calls = 0;
    let release!: () => void;
    const held = new Promise<void>(resolve => { release = resolve; });
    await page.route(`**${endpoint}`, async route => {
      calls += 1;
      if (calls === 1) await held;
      await route.fulfill({ json: payload });
    });
    try {
      await page.goto(`/?workflow=${mode}`);
      const input = page.getByLabel("Ask the example knowledge base", { exact: true });
      await input.fill("Synthetic cancellation question");
      const requested = page.waitForRequest(request => request.url().endsWith(endpoint));
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      const request = await requested;
      await expect(page.getByRole("button", { name: "Searching…", exact: true })).toBeDisabled();
      await expect(page.getByRole("button", { name: "Compare workflows", exact: true })).toBeDisabled();
      const cancel = page.getByRole("button", { name: "Cancel request", exact: true });
      await input.focus();
      await page.keyboard.press("Tab");
      await expect(cancel).toBeFocused();
      await layoutScreenshot(page, info, `${mode}-cancel-control`);
      const aborted = page.waitForEvent("requestfailed", failed => failed === request);
      await page.keyboard.press("Enter");
      await aborted;
      release();
      await expect(page.getByRole("status")).toHaveText("Request cancelled. You can edit your question and try again.");
      await expect(page.getByRole("alert")).toHaveCount(0);
      await expect(cancel).toHaveCount(0);
      await expect(input).toBeFocused();
      await expect(input).toHaveValue("Synthetic cancellation question");
      await layoutScreenshot(page, info, `${mode}-cancelled`);
      await page.getByRole("button", { name: "Ask", exact: true }).click();
      await expect(page.locator(".answer > p").first()).toHaveText(payload.answer);
      await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeEnabled();
      await expect(page.getByRole("status")).toHaveCount(0);
      expect(calls).toBe(2);
    } finally {
      release();
    }
  });
}
