import type { App } from 'vue'
import type { Router } from 'vue-router'
import * as Sentry from '@sentry/vue'
import type { ErrorEvent } from '@sentry/vue'

/**
 * Sentry 오류 수집. VITE_SENTRY_DSN 이 없으면 아무것도 하지 않는다(개발·테스트 기본값).
 * 영상·전사문·토큰·비밀번호가 Sentry 로 나가지 않도록 데이터 수집 옵션을 모두 끄고, 전송 직전에 요청 헤더·본문·쿠키·사용자 정보를 지운다.
 */
let enabled = false

/** 보내기 전에 민감할 수 있는 값을 제거 */
export function scrubEvent(event: ErrorEvent): ErrorEvent {
  if (event.request) {
    delete event.request.headers
    delete event.request.data
    delete event.request.cookies
    if (event.request.url) event.request.url = event.request.url.split('?')[0]
    delete event.request.query_string
  }
  delete event.user
  return event
}

export function initMonitoring(app: App, router: Router): boolean {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined
  if (!dsn) return false
  Sentry.init({
    app,
    dsn,
    environment: import.meta.env.MODE,
    release: import.meta.env.VITE_APP_RELEASE as string | undefined,
    // Sentry v11 의 기본값은 사용자 정보·쿠키·헤더·본문·쿼리를 모두 수집하므로 명시적으로 모두 끈다
    dataCollection: { userInfo: false, cookies: false, httpHeaders: false, httpBodies: [], urlQueryParams: false },
    integrations: [Sentry.browserTracingIntegration({ router })],
    // 성능 추적은 기본으로 끈다. 필요하면 0~1 사이 값으로 켠다.
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0),
    beforeSend: scrubEvent,
  })
  enabled = true
  return true
}

/** 화면이 잡아서 처리하는 서버·네트워크 오류도 기록하고 싶을 때 사용. 모니터링이 꺼져 있으면 무시 */
export function reportError(error: unknown, context?: Record<string, string | number>) {
  if (enabled) Sentry.captureException(error, { extra: context })
}
