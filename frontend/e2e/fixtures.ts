import { test as base, expect, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";

export const PREFIX = "/api/v1/personal";
export const FIXTURE_TOKEN = "e2e-fixture-only-token-00000000000000000000";

export const test = base.extend<{ ownerApi: APIRequestContext; pageFence: void; expectedHttpErrors: Set<string> }>({
  expectedHttpErrors: async ({ baseURL }, runFixture) => {
    if (!baseURL) throw new Error("Fixture base URL is required");
    await runFixture(new Set());
  },
  ownerApi: async ({ playwright, baseURL }, runFixture) => {
    if (!baseURL) throw new Error("Fixture base URL is required");
    const api = await playwright.request.newContext({ baseURL, extraHTTPHeaders: { Authorization: `Bearer ${FIXTURE_TOKEN}` } });
    const health = await api.get("/__e2e_health");
    expect(await health.json()).toEqual({ fixture: "agent-me-e2e-v1" });
    const profile = await api.get("/api/v1/profile");
    expect(await profile.json()).toMatchObject({ name: "Agent-Me E2E fixture", external_provider_enabled: false, personal_enabled: true });
    const owner = await api.get(`${PREFIX}/identity/owner`);
    const { owner_id } = await owner.json();
    const purged = await api.post(`${PREFIX}/workspace/purge`, { data: { expected_owner_id: owner_id, confirmation: "erase-personal-workspace" } });
    expect(purged.ok()).toBe(true);
    try { await runFixture(api); } finally { await api.dispose(); }
  },
  pageFence: [async ({ context, page, baseURL, expectedHttpErrors }, runFixture) => {
    const unexpected: string[] = [];
    const errors: string[] = [];
    await context.route("**/*", async route => {
      const url = new URL(route.request().url());
      if (url.origin !== baseURL && url.protocol !== "data:" && url.protocol !== "blob:") {
        unexpected.push(url.origin); await route.abort(); return;
      }
      await route.continue();
    });
    page.on("pageerror", error => errors.push(error.message));
    page.on("response", response => {
      const key = `${response.status()}:${new URL(response.url()).pathname}`;
      if (response.status() >= 400 && !expectedHttpErrors.has(key)) errors.push(key);
    });
    page.on("console", message => {
      if (message.type() !== "error") return;
      const status = /Failed to load resource: the server responded with a status of (\d+)/.exec(message.text());
      const location = message.location().url;
      const known = status && location && expectedHttpErrors.has(`${status[1]}:${new URL(location).pathname}`);
      if (!known) errors.push(message.text());
    });
    await runFixture();
    expect(unexpected, "Page requests must stay on the isolated fixture origin").toEqual([]);
    expect(errors, "Browser JavaScript/console errors").toEqual([]);
  }, { auto: true }],
});
export { expect };

export async function post(api: APIRequestContext, path: string, data: unknown) {
  const response = await api.post(PREFIX + path, { data });
  expect(response.ok(), `${path}: ${await response.text()}`).toBe(true);
  expect(response.headers()["cache-control"]).toBe("no-store");
  return response.json();
}
export async function get(api: APIRequestContext, path: string) {
  const response = await api.get(PREFIX + path);
  expect(response.ok()).toBe(true);
  return response.json();
}
export async function unlock(page: Page) {
  await page.goto("/");
  await page.getByRole("combobox", { name: "Language", exact: true }).selectOption("en");
  await page.getByLabel("Workspace token", { exact: true }).fill(FIXTURE_TOKEN);
  await page.getByRole("button", { name: "Unlock", exact: true }).click();
  await page.getByRole("button", { name: "Open review workbench", exact: true }).click();
  await expect(page.getByRole("button", { name: "Refresh workbench", exact: true })).toBeEnabled();
}
export async function openIdentity(page: Page) {
  await page.getByRole("button", { name: "Manage identities & relationships", exact: true }).click();
  await expect(page.getByRole("button", { name: "Close identity review", exact: true })).toBeEnabled();
  return page.getByRole("region", { name: "Identity & relationship review", exact: true });
}
export async function layoutScreenshot(page: Page, info: TestInfo, name: string) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  const image = await page.screenshot({ path: info.outputPath(`${name}.png`) });
  await info.attach(name, { body: image, contentType: "image/png" });
}
