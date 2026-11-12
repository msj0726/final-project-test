import { readFileSync } from 'node:fs'
import { expect, type Page } from '@playwright/test'

export const SAMPLE_VIDEO = new URL('../public/sample/sample-pitch.mp4', import.meta.url).pathname
export const sampleFile = (name = 'rehearsal.mp4') => ({ name, mimeType: 'video/mp4', buffer: readFileSync(SAMPLE_VIDEO) })

/** 목업 계정으로 로그인. 매 테스트는 새 브라우저 컨텍스트라 목업 DB 도 처음 상태다. */
export async function login(page: Page) {
  await page.goto('/login')
  await page.locator('#main').getByRole('button', { name: '로그인', exact: true }).click()
  await expect(page).toHaveURL(/\/me$/)
}
