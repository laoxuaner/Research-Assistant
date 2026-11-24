import { defineConfig } from "@playwright/test";

// Intentionally has no webServer: this suite must reach the real public service.
export default defineConfig({
  testDir: "./tests",
  testMatch: "public-demo.spec.ts",
  timeout: 120000,
  expect: { timeout: 20000 },
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.PUBLIC_DEMO_URL || "http://127.0.0.1",
    browserName: "chromium",
    channel: process.env.PW_BROWSER_CHANNEL || undefined,
    headless: true,
    viewport: { width: 1440, height: 1000 },
    actionTimeout: 20000,
    navigationTimeout: 45000,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
