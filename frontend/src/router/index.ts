import { createRouter, createWebHistory } from 'vue-router'
import { auth } from '@/shared/state/auth'

declare module 'vue-router' {
  interface RouteMeta {
    auth?: boolean
    title?: string
  }
}

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: (_to, _from, saved) => saved ?? { top: 0 },
  routes: [
    { path: '/', component: () => import('@/features/landing/LandingPage.vue'), meta: { title: 'ProPitch AI 발표 코칭' } },
    { path: '/login', component: () => import('@/features/auth/LoginPage.vue'), meta: { title: '로그인' } },
    { path: '/signup', component: () => import('@/features/auth/SignupPage.vue'), meta: { title: '회원가입' } },
    { path: '/me', component: () => import('@/features/projects/ProjectsPage.vue'), meta: { auth: true, title: '내 발표 프로젝트' } },
    { path: '/me/history', component: () => import('@/features/history/HistoryPage.vue'), meta: { auth: true, title: '이력 · 추이' } },
    { path: '/me/calendar', component: () => import('@/features/schedule/SchedulePage.vue'), meta: { auth: true, title: '발표 일정' } },
    { path: '/me/account', component: () => import('@/features/account/AccountPage.vue'), meta: { auth: true, title: '계정 설정' } },
    { path: '/new', component: () => import('@/features/projects/NewPracticePage.vue'), meta: { auth: true, title: '새 연습' } },
    { path: '/upload', component: () => import('@/features/upload/UploadPage.vue'), meta: { auth: true, title: '영상 올리기' } },
    { path: '/analysis', component: () => import('@/features/analysis-status/AnalysisStatusPage.vue'), meta: { auth: true, title: '분석 중' } },
    { path: '/report/:pid/:n', component: () => import('@/features/report/ReportPage.vue'), meta: { auth: true, title: '분석 리포트' } },
    // 질의응답은 다음 단계 범위
    { path: '/qa', component: () => import('@/features/coming-soon/ComingSoonPage.vue'), meta: { auth: true, title: '질의응답 (준비 중)' } },
    { path: '/:rest(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  if (!auth.ready) await auth.restore()
  if (to.meta.auth && !auth.loggedIn) return { path: '/login', query: { next: to.fullPath } }
  if ((to.path === '/login' || to.path === '/signup') && auth.loggedIn) return '/me'
  return true
})
router.afterEach((to) => {
  document.title = (to.meta.title as string) || 'ProPitch'
})
