import { expect, test } from '@playwright/test'

test('renders dark shell outside Telegram', async ({ page }) => {
  await page.goto('/app', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Откройте сервис через Telegram-бота')).toBeVisible()
  const backgroundColor = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
  expect(backgroundColor).toBe('rgb(11, 15, 20)')
})
