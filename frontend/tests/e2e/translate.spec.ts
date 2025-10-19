import { test, expect } from "@playwright/test";

test.describe("Translation flow", () => {
  test("translates text with mocked backend", async ({ page }) => {
    await page.route("http://localhost:8000/auth/token?*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ access_token: "mock-token" }),
      });
    });

    await page.route("http://localhost:8000/translate/stream", async (route) => {
      await route.fulfill({
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
        body: "event: translation_start\n\ndata: Hallo Welt\n\n",
      });
    });

    await page.goto("/");

    await page.getByRole("button", { name: "Get Auth Token" }).click();
    await expect(page.getByText("✓ Authenticated")).toBeVisible();

    await page
      .getByPlaceholder("Enter text in Russian, English, or German...")
      .fill("Hello");

    await page.getByRole("button", { name: "Translate" }).click();

    await expect(page.getByText("Hallo Welt")).toBeVisible();
  });
});
