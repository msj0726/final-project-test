import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { setUnauthorizedHandler } from '@/shared/api'
import { auth } from '@/shared/state/auth'
import { initMonitoring } from '@/shared/monitoring'
import '@/shared/styles/prototype.css'
import '@/shared/styles/app.css'

// 테마: 기본은 빨간 테마(skt). ?ui=blue 로 파란 테마를 볼 수 있고 선택은 localStorage 에 기억
const THEME_KEY = 'propitch-ui'
const q = new URLSearchParams(location.search).get('ui')
try {
  if (q === 'blue' || q === 'skt') localStorage.setItem(THEME_KEY, q)
} catch {
  /* 저장 불가 환경 */
}
let theme = 'skt'
try {
  theme = localStorage.getItem(THEME_KEY) || 'skt'
} catch {
  /* ignore */
}
document.documentElement.dataset.ui = theme

// 토큰 갱신까지 실패하면 로그인 화면으로
setUnauthorizedHandler(() => {
  auth.clear()
  if (router.currentRoute.value.meta.auth) router.push({ path: '/login', query: { next: router.currentRoute.value.fullPath } })
})

const app = createApp(App)
app.use(router)
initMonitoring(app, router) // VITE_SENTRY_DSN 이 있을 때만 동작
app.mount('#app')
