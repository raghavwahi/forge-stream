import { test, expect } from "@playwright/test";

const SAMPLE_ITEMS = [
  {
    id: "epic-user-authentication",
    type: "epic",
    title: "User Authentication",
    description: "Allow users to sign up and log in.",
  },
  {
    id: "story-sign-up-flow",
    type: "story",
    title: "Sign up flow",
    description: "Registration with email + password.",
  },
  {
    id: "task-set-up-ci",
    type: "task",
    title: "Set up CI",
    description: "Configure GitHub Actions.",
  },
];

test.describe("Review page", () => {
  test.beforeEach(async ({ page }) => {
    // Pre-seed sessionStorage so the page has items to render
    await page.goto("/");
    await page.evaluate((items) => {
      sessionStorage.setItem("forgestream_items", JSON.stringify(items));
    }, SAMPLE_ITEMS);
    await page.goto("/review");
  });

  test("renders work items from session storage", async ({ page }) => {
    await expect(page.getByText("User Authentication")).toBeVisible();
    await expect(page.getByText("Sign up flow")).toBeVisible();
    await expect(page.getByText("Set up CI")).toBeVisible();
  });

  test("shows selected item count", async ({ page }) => {
    // All items pre-selected; text rendered as "{n} of {total} selected"
    await expect(page.getByText(/\d+\s+of\s+\d+\s+selected/i)).toBeVisible();
  });

  test("deselect all removes selection", async ({ page }) => {
    await page.getByRole("button", { name: /deselect all/i }).click();
    await expect(page.getByText(/0 of \d+ selected/i)).toBeVisible();
  });

  test("create repository button is visible with items selected", async ({
    page,
  }) => {
    const createBtn = page.getByRole("button", { name: /create repository/i });
    await expect(createBtn).toBeVisible();
    await expect(createBtn).toBeEnabled();
  });

  test("create repository shows toast when nothing is selected", async ({
    page,
  }) => {
    await page.getByRole("button", { name: /deselect all/i }).click();
    await page.getByRole("button", { name: /create repository/i }).click();
    await expect(page.getByText(/select at least one item/i)).toBeVisible();
  });

  test("back button navigates to home", async ({ page }) => {
    await page.getByRole("button", { name: /back to dashboard/i }).click();
    await expect(page).toHaveURL("/");
  });

  test("empty session storage shows empty state", async ({ page }) => {
    await page.evaluate(() => sessionStorage.removeItem("forgestream_items"));
    await page.goto("/review");
    await expect(page.getByText(/no items to review/i)).toBeVisible();
  });
});
