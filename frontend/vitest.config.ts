import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const ROOT_DIR = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./setupTests.ts"],
    globals: true,
    include: ["app/**/*.test.tsx", "lib/**/*.test.ts", "tests/unit/**/*.test.ts?(x)"],
    exclude: ["tests/e2e/**", "playwright.config.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["app/**/*.{ts,tsx}", "lib/**/*.{ts,tsx}"],
      exclude: ["app/layout.tsx"],
      thresholds: {
        branches: 70,
        functions: 80,
        lines: 80,
        statements: 80,
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(ROOT_DIR, "."),
    },
  },
});
