import { expect, test } from '@playwright/test'
import { login } from './helpers'

// 가짜 DSN(o0.ingest.sentry.io)으로 설정된 서버(5175)에서 실행한다. 전송 요청은 가로채서 실제 Sentry 로 나가지 않는다.
const envelopes: string[] = []
test.beforeEach(async ({ page }) => {
  envelopes.length = 0
  await page.route(/ingest\.sentry\.io/, async (route) => {
    envelopes.push(route.request().postData() ?? '')
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })
})

test('처리되지 않은 오류가 Sentry 로 전송된다', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => setTimeout(() => { throw new Error('e2e-sentry-unhandled') }, 0))
  await expect.poll(() => envelopes.some((e) => e.includes('e2e-sentry-unhandled'))).toBe(true)
})

test('전송되는 이벤트에는 토큰·비밀번호·사용자 정보·헤더가 없다', async ({ page }) => {
  await login(page)
  await page.evaluate(() => setTimeout(() => { throw new Error('e2e-sentry-scrub') }, 0))
  await expect.poll(() => envelopes.some((e) => e.includes('e2e-sentry-scrub'))).toBe(true)
  const body = envelopes.find((e) => e.includes('e2e-sentry-scrub')) ?? ''
  expect(body).not.toMatch(/Bearer/i)
  expect(body).not.toContain('password123')
  expect(body).not.toContain('jiyoung@example.com')
  expect(body).not.toMatch(/"user":\{[^}]*"(email|username|ip_address)"/)
  expect(body).not.toMatch(/"headers"/)
})
