import type { PlaywrightTestConfig } from "@playwright/test";

const config: PlaywrightTestConfig = {
  testDir: "tests/e2e",
  timeout: 30 * 1000,
  expect: {
    timeout: 5000,
  },
  use: {
    headless: true,
    baseURL: "http://localhost:3000",
  },
  webServer: {
    command: "npm run dev -- --port 3000",
    port: 3000,
    reuseExistingServer: !process.env.CI,
    stdout: "pipe",
    stderr: "pipe",
  },
};

export default config;
