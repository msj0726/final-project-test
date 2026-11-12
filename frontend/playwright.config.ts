import { defineConfig, devices } from '@playwright/test'

// 개발 서버(5173)와 겹치지 않게 테스트 전용 포트를 쓴다.
//  - 5174: 일반 서버. VITE_API_MODE=hybrid → /healthz 는 실제 백엔드(8000), 나머지는 목업
//  - 5175: Sentry 테스트 전용 서버. 가짜 DSN 을 주입하고 전송 요청은 테스트에서 가로챈다(실제 Sentry 로 나가지 않음)
const base = { reuseExistingServer: false, timeout: 60_000 }
export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['list']],
  use: { trace: 'retain-on-failure', channel: 'chrome' }, // 설치된 Chrome 사용 (브라우저 다운로드 없음)
  projects: [
    { name: 'app', testIgnore: /sentry/, use: { ...devices['Desktop Chrome'], channel: 'chrome', baseURL: 'http://localhost:5174' } },
    { name: 'sentry', testMatch: /sentry/, use: { ...devices['Desktop Chrome'], channel: 'chrome', baseURL: 'http://localhost:5175' } },
  ],
  webServer: [
    { command: 'npx vite --host localhost --port 5174 --strictPort', url: 'http://localhost:5174', env: { VITE_API_MODE: 'hybrid' }, ...base },
    {
      command: 'npx vite --host localhost --port 5175 --strictPort',
      url: 'http://localhost:5175',
      env: { VITE_API_MODE: 'mock', VITE_SENTRY_DSN: 'https://publickey@o0.ingest.sentry.io/0' },
      ...base,
    },
  ],
})
