import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("..", import.meta.url));
const python = path.join(root, ".venv", "Scripts", "python.exe");
export default defineConfig({
  testDir: "./tests",
  timeout: 90000,
  expect: { timeout: 15000 },
  workers: 1,
  fullyParallel: false,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    actionTimeout: 15000,
    browserName: "chromium",
    channel: process.env.PW_BROWSER_CHANNEL || undefined,
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        '"' +
        python +
        '" -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 8001',
      url: "http://127.0.0.1:8001/api/health",
      timeout: 40000,
      reuseExistingServer: false,
      env: {
        DATA_DIR: path.join(root, "tmp", "e2e-" + Date.now()),
        AI_CHAT_MODEL: "",
        AI_API_KEY: "",
        EMBEDDING_MODEL: "",
        EMBEDDING_API_KEY: "",
      },
    },
    {
      command: "npm.cmd run dev -- --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      timeout: 40000,
      reuseExistingServer: false,
      env: { WORKBENCH_API_URL: "http://127.0.0.1:8001" },
    },
  ],
});
