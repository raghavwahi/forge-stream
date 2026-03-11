import { test, expect } from "@playwright/test";

test.describe("Home page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders title and description", async ({ page }) => {
    await expect(page.getByText("ForgeStream")).toBeVisible();
    await expect(
      page.getByText(/Describe what you want to build/i),
    ).toBeVisible();
  });

  test("has a prompt input field", async ({ page }) => {
    const input = page.getByRole("textbox", { name: /describe/i });
    await expect(input).toBeVisible();
    await expect(input).toBeEnabled();
  });

  test("has a generate button", async ({ page }) => {
    const btn = page.getByRole("button", { name: /generate/i });
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });

  test("shows error toast when submitting empty prompt", async ({ page }) => {
    await page.getByRole("button", { name: /generate/i }).click();
    await expect(page.getByText(/enter a prompt/i)).toBeVisible();
  });

  test("disables generate button while generating", async ({ page }) => {
    // Intercept API call to keep it pending — use glob to match any host
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    await page.route("**/api/generate", async (_route) => {
      // never resolve — simulates a slow response
      await new Promise(() => {});
    });

    await page.getByRole("textbox").fill("Build a todo app");
    await page.getByRole("button", { name: /generate/i }).click();

    const btn = page.getByRole("button", { name: /generating/i });
    await expect(btn).toBeDisabled();
  });

  test("redirects to /review on successful generation", async ({ page }) => {
    await page.route("**/api/generate", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: "epic-test",
              type: "epic",
              title: "Test Epic",
              description: "A test epic",
            },
          ],
        }),
      });
    });

    await page.getByRole("textbox").fill("Build a todo app");
    await page.getByRole("button", { name: /generate/i }).click();

    await expect(page).toHaveURL("/review");
  });
});
