import { test, expect } from '@playwright/test'

const SAMPLE_ITEMS = [
  {
    type: 'epic',
    title: 'User Authentication',
    description: 'Allow users to sign up and log in.',
    labels: ['auth'],
    children: [
      {
        type: 'story',
        title: 'Sign up flow',
        description: 'Registration with email + password.',
        labels: [],
        children: [],
      },
    ],
  },
  {
    type: 'task',
    title: 'Set up CI',
    description: 'Configure GitHub Actions.',
    labels: [],
    children: [],
  },
]

test.describe('Review page', () => {
  test.beforeEach(async ({ page }) => {
    // Pre-seed sessionStorage so the page has items to render
    await page.goto('/')
    await page.evaluate((items) => {
      sessionStorage.setItem('forgestream_items', JSON.stringify(items))
    }, SAMPLE_ITEMS)
    await page.goto('/review')
  })

  test('renders work items from session storage', async ({ page }) => {
    await expect(page.getByText('User Authentication')).toBeVisible()
    await expect(page.getByText('Sign up flow')).toBeVisible()
    await expect(page.getByText('Set up CI')).toBeVisible()
  })

  test('shows selected item count', async ({ page }) => {
    // All items pre-selected
    await expect(page.getByText(/of \d+ items selected/i)).toBeVisible()
  })

  test('deselect all removes selection', async ({ page }) => {
    await page.getByRole('button', { name: /deselect all/i }).click()
    await expect(page.getByText(/0 of/i)).toBeVisible()
  })

  test('continue to github button disabled when nothing selected', async ({
    page,
  }) => {
    await page.getByRole('button', { name: /deselect all/i }).click()
    const continueBtn = page.getByRole('button', { name: /continue to github/i })
    await expect(continueBtn).toBeDisabled()
  })

  test('continue to github button enabled when items selected', async ({
    page,
  }) => {
    const continueBtn = page.getByRole('button', { name: /continue to github/i })
    await expect(continueBtn).toBeEnabled()
  })

  test('navigates to github config step on continue', async ({ page }) => {
    await page.getByRole('button', { name: /continue to github/i }).click()
    await expect(page.getByText(/github configuration/i)).toBeVisible()
  })

  test('github config step shows token and repo fields', async ({ page }) => {
    await page.getByRole('button', { name: /continue to github/i }).click()
    await expect(page.getByLabel(/personal access token/i)).toBeVisible()
    await expect(page.getByLabel(/repository owner/i)).toBeVisible()
    await expect(page.getByLabel(/repository name/i)).toBeVisible()
  })

  test('back button on github config returns to review step', async ({
    page,
  }) => {
    await page.getByRole('button', { name: /continue to github/i }).click()
    await page.getByRole('button', { name: /back/i }).first().click()
    await expect(page.getByText('User Authentication')).toBeVisible()
  })

  test('submitting empty github config shows toast error', async ({ page }) => {
    await page.getByRole('button', { name: /continue to github/i }).click()
    await page.getByRole('button', { name: /create issues/i }).click()
    await expect(page.getByText(/fill in all github/i)).toBeVisible()
  })

  test('empty session storage shows empty state', async ({ page }) => {
    await page.evaluate(() => sessionStorage.removeItem('forgestream_items'))
    await page.goto('/review')
    await expect(
      page.getByText(/no items to review/i),
    ).toBeVisible()
  })
})
