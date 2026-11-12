import { expect, test } from '@playwright/test'
import { login, sampleFile } from './helpers'

test.describe('인증', () => {
  test('로그인하지 않고 보호된 화면에 가면 로그인으로 보내고, 로그인 뒤 원래 화면으로 돌아온다', async ({ page }) => {
    await page.goto('/me/history')
    await expect(page).toHaveURL(/\/login\?next=(%2F|\/)me(%2F|\/)history/)
    await page.locator('#main').getByRole('button', { name: '로그인', exact: true }).click()
    await expect(page).toHaveURL(/\/me\/history$/)
  })

  test('비밀번호가 틀리면 오류를 보여 주고 이동하지 않는다', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('비밀번호').fill('wrong-password')
    await page.locator('#main').getByRole('button', { name: '로그인', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText('맞지 않아요')
    await expect(page).toHaveURL(/\/login/)
  })

  test('회원가입은 필수 동의와 비밀번호 확인을 검사한다', async ({ page }) => {
    await page.goto('/signup')
    await page.getByRole('button', { name: '가입하고 시작하기' }).click()
    await expect(page.getByRole('alert').first()).toBeVisible()
    await page.getByLabel(/^이름/).fill('테스트')
    await page.getByLabel(/^이메일/).fill('e2e@example.com')
    await page.getByLabel(/^비밀번호 \*/).fill('password123')
    await page.getByLabel(/^비밀번호 확인/).fill('password123')
    await page.getByLabel('전체 동의').check()
    await page.getByRole('button', { name: '가입하고 시작하기' }).click()
    await expect(page).toHaveURL(/\/me$/)
    await expect(page.getByText('아직 발표 프로젝트가 없어요')).toBeVisible()
  })

  test('메인 화면에서도 로그아웃할 수 있고 로그아웃하면 세션이 지워진다', async ({ page }) => {
    await login(page)
    await page.goto('/')
    await page.getByRole('button', { name: /이지영/ }).click()
    await page.getByRole('menuitem', { name: '로그아웃' }).click()
    await expect(page.getByRole('banner').getByRole('button', { name: '로그인' })).toBeVisible()
    expect(await page.evaluate(() => sessionStorage.getItem('propitch-tokens'))).toBeNull()
    await page.goto('/me')
    await expect(page).toHaveURL(/\/login/)
  })
})

test.describe('프로젝트·이력', () => {
  test('프로젝트 카드와 이력·추이가 계약 형식 데이터로 그려진다', async ({ page }) => {
    await login(page)
    await expect(page.locator('.pc')).toHaveCount(2)
    await expect(page.getByText('최종발표 리허설')).toBeVisible()
    await page.getByRole('button', { name: '이력 · 추이', exact: true }).first().click()
    await expect(page.getByRole('heading', { name: /이력/ })).toBeVisible()
    await expect(page.locator('tbody tr')).toHaveCount(3)
  })

  test('새 프로젝트: 필수값을 검사하고 만들면 영상 올리기로 이동한다', async ({ page }) => {
    await login(page)
    await page.goto('/new')
    await expect(page.getByRole('button', { name: /질의응답 연습/ })).toBeDisabled()
    await page.getByRole('button', { name: /발표 평가/ }).click()
    await page.getByRole('button', { name: '프로젝트 만들고 영상 올리기' }).click()
    await expect(page.getByText('발표 제목을 입력해 주세요.')).toBeVisible()
    await page.getByLabel(/^발표 제목/).fill('E2E 발표')
    await page.getByLabel(/^발표 주제/).fill('테스트 주제')
    await page.getByRole('button', { name: '프로젝트 만들고 영상 올리기' }).click()
    await expect(page).toHaveURL(/\/upload\?p=/)
    await expect(page.getByRole('heading', { name: /E2E 발표 · 1회차/ })).toBeVisible()
  })
})

test.describe('업로드 → 분석 → 리포트', () => {
  test('영상을 올리면 분석이 진행되고 끝나면 리포트가 열린다', async ({ page }) => {
    await login(page)
    await page.getByRole('button', { name: '새 회차 연습하기' }).first().click()
    await page.getByRole('button', { name: /회차 영상 올리기/ }).click()
    await page.locator('input[type=file]').setInputFiles(sampleFile())
    await expect(page.locator('.fcard')).toContainText('rehearsal.mp4')
    const start = page.getByRole('button', { name: '이 영상으로 분석하기' })
    await expect(start).toBeDisabled() // 동의 전에는 비활성
    await page.getByLabel(/분석하는 데 동의/).check()
    await start.click()
    await expect(page).toHaveURL(/\/analysis\?p=.*&n=4/, { timeout: 30_000 })
    await expect(page.getByRole('progressbar')).toBeVisible()
    await expect(page).toHaveURL(/\/report\/.*\/4/, { timeout: 40_000 })
    await expect(page.getByRole('heading', { name: '4회차 분석 리포트' })).toBeVisible()
  })

  test('MP4/MOV가 아닌 파일은 올리기 전에 거절한다', async ({ page }) => {
    await login(page)
    await page.goto('/new')
    await page.getByRole('button', { name: /발표 평가/ }).click()
    await page.getByRole('tab', { name: '기존 프로젝트에 회차 추가' }).click()
    await page.getByRole('button', { name: /회차 영상 올리기/ }).click()
    await page.locator('input[type=file]').setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('hello') })
    await expect(page.getByRole('alert')).toContainText('MP4 또는 MOV')
  })

  test('분석이 실패하면 안내하고 다시 시도하면 끝까지 진행된다', async ({ page }) => {
    await login(page)
    await page.goto('/new')
    await page.getByRole('button', { name: /발표 평가/ }).click()
    await page.getByRole('tab', { name: '기존 프로젝트에 회차 추가' }).click()
    await page.getByRole('button', { name: /회차 영상 올리기/ }).click()
    await page.locator('input[type=file]').setInputFiles(sampleFile('fail-demo.mp4'))
    await page.getByLabel(/분석하는 데 동의/).check()
    await page.getByRole('button', { name: '이 영상으로 분석하기' }).click()
    await expect(page.getByRole('heading', { name: '분석하지 못했어요' })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText('STT_TEMPORARY_ERROR')).toBeVisible()
    await page.getByRole('button', { name: '다시 분석하기' }).click()
    await expect(page).toHaveURL(/\/report\//, { timeout: 40_000 })
  })
})

test.describe('리포트', () => {
  test('영상이 재생되고 근거 버튼이 해당 시각으로 이동하며 전사문을 볼 수 있다', async ({ page }) => {
    await login(page)
    await page.getByRole('button', { name: '최근 리포트' }).first().click()
    await expect(page.getByRole('heading', { name: /회차 분석 리포트/ })).toBeVisible()
    const video = page.locator('.pv video')
    await expect(video).toBeVisible()
    await page.locator('.pv .big').click()
    await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(0.5)
    await page.locator('.pv .big').click() // 일시정지
    const ev = page.locator('.evb').first()
    const label = (await ev.innerText()).trim()
    await ev.click()
    const t = await video.evaluate((v: HTMLVideoElement) => v.currentTime)
    const [m, s] = label.split('–')[0].split(':').map(Number)
    expect(Math.abs(t - (m * 60 + s))).toBeLessThan(3)
    await expect(page.locator('.sgc')).toHaveCount(5)
    await expect(page.locator('.mc')).toHaveCount(4)
    await page.getByRole('button', { name: '전사문 펼치기' }).click()
    await expect(page.locator('.trl li').first()).toBeVisible()
  })

  test('질의응답은 준비 중으로 막혀 있다', async ({ page }) => {
    await login(page)
    await page.getByRole('button', { name: '최근 리포트' }).first().click()
    await expect(page.getByRole('button', { name: '질의응답 준비 중' })).toBeDisabled()
  })

  test('모바일 폭에서 가로 스크롤이 생기지 않는다', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await login(page)
    await page.getByRole('button', { name: '최근 리포트' }).first().click()
    await expect(page.getByRole('heading', { name: /회차 분석 리포트/ })).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    expect(overflow).toBeLessThanOrEqual(1)
  })
})

test.describe('테마·백엔드', () => {
  test('기본은 빨간 테마이고 ?ui=blue 로 파란 테마가 된다', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('html')).toHaveAttribute('data-ui', 'skt')
    await page.goto('/?ui=blue')
    await expect(page.locator('html')).toHaveAttribute('data-ui', 'blue')
  })

  test('백엔드 /healthz 를 프록시로 실제 호출한다 (백엔드가 꺼져 있으면 건너뜀)', async ({ request }) => {
    const res = await request.get('/healthz')
    test.skip(!res.ok(), '백엔드(8000)가 실행 중이 아님')
    expect(await res.json()).toEqual({ status: 'ok' })
  })
})
