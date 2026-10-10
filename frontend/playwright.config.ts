import { defineConfig } from "@playwright/test";

const port = Number(process.env.AGENT_ME_E2E_PORT ?? "4193");
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Invalid E2E gateway port");
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  timeout: 60000,
  expect: { timeout: 10000 },
  fullyParallel: false,
  workers: 1, // The temporary API workspace is reset before each test, never concurrently.
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: { baseURL: `http://127.0.0.1:${port}`, browserName: "chromium", locale: "en-US",
    headless: true, trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: { command: "node e2e/server.mjs", url: `http://127.0.0.1:${port}/__e2e_health`,
    reuseExistingServer: false, timeout: 60000, gracefulShutdown: { signal: "SIGTERM", timeout: 12000 } },
});
