import type { ApiErrorBody, Tokens } from './types'
import { mockRequest, type Res } from './mock/server'
import { newKey } from '../lib/format'
import { reportError } from '../monitoring'

/**
 * API 연결 방식 (VITE_API_MODE)
 *  - hybrid(기본): 백엔드에 구현된 경로(IMPLEMENTED)는 실제 서버로, 아직 없는 경로는 목업으로
 *  - real: 모든 요청을 실제 서버로
 *  - mock: 모든 요청을 목업으로 (백엔드 없이 실행)
 */
export type ApiMode = 'hybrid' | 'real' | 'mock'
const rawMode = import.meta.env.VITE_API_MODE as string | undefined
export const API_MODE: ApiMode = rawMode === 'real' || rawMode === 'mock' ? rawMode : 'hybrid'
const API_BASE = '/api/v1'

/**
 * 백엔드에 실제로 구현된 경로. backend/contracts/endpoint-catalog.json 에서 status 가 implemented 인 것만 적는다.
 * 백엔드가 경로를 구현할 때마다 여기에 추가하면 그 경로부터 목업 대신 실제 서버를 호출한다.
 */
const IMPLEMENTED: { method: string; test: RegExp }[] = [{ method: 'GET', test: /^\/healthz$/ }]
const isImplemented = (method: string, path: string) => IMPLEMENTED.some((e) => e.method === method && e.test.test(path))

/** 이 요청을 목업이 처리하는지 */
export const usesMock = (method: string, path: string) => API_MODE === 'mock' || (API_MODE === 'hybrid' && !isImplemented(method, path))

export class ApiError extends Error {
  status: number
  code: string
  fields: Record<string, string>
  retryable: boolean
  requestId?: string
  constructor(status: number, body?: ApiErrorBody | null) {
    super(body?.error?.message || '요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.')
    this.status = status
    this.code = body?.error?.code || 'UNKNOWN'
    this.fields = body?.error?.fields || {}
    this.retryable = !!body?.error?.retryable
    this.requestId = body?.error?.requestId
  }
}

// ----- 토큰 보관 (인증 백엔드 확정 전: sessionStorage)
const TK = 'propitch-tokens'
export const tokenStore = {
  get(): Tokens | null {
    try {
      return JSON.parse(sessionStorage.getItem(TK) || 'null')
    } catch {
      return null
    }
  },
  set(t: Tokens | null) {
    try {
      if (t) sessionStorage.setItem(TK, JSON.stringify(t))
      else sessionStorage.removeItem(TK)
    } catch {
      /* 저장 불가 환경 */
    }
  },
}

let onUnauthorized: () => void = () => {}
export const setUnauthorizedHandler = (fn: () => void) => (onUnauthorized = fn)

export interface ReqOpts {
  query?: Record<string, string | number | undefined>
  body?: unknown
  /** 업무 POST 는 Idempotency-Key 필수 (login/refresh/logout/WS ticket 제외) */
  idempotent?: boolean
  auth?: boolean
  headers?: Record<string, string>
}

async function send(method: string, path: string, o: ReqOpts, token?: string | null): Promise<Res> {
  const headers: Record<string, string> = { ...o.headers }
  if (o.body !== undefined) headers['Content-Type'] = 'application/json'
  if (o.auth !== false && token) headers.Authorization = `Bearer ${token}`
  if (o.idempotent) headers['Idempotency-Key'] = newKey()
  if (usesMock(method, path)) return mockRequest(method, path, { query: o.query, body: o.body, headers })
  const qs = o.query ? '?' + new URLSearchParams(Object.entries(o.query).filter(([, v]) => v !== undefined).map(([k, v]) => [k, String(v)])) : ''
  const url = (path === '/healthz' || path === '/readyz' ? '' : API_BASE) + path + qs
  const res = await fetch(url, { method, headers, body: o.body !== undefined ? JSON.stringify(o.body) : undefined })
  const text = res.status === 204 ? '' : await res.text()
  let body: unknown = null
  try {
    body = text ? (JSON.parse(text) as unknown) : null
  } catch {
    /* JSON 이 아닌 응답(프록시 오류 등) */
  }
  return { status: res.status, body }
}

let refreshing: Promise<boolean> | null = null
async function refresh(): Promise<boolean> {
  const t = tokenStore.get()
  if (!t) return false
  refreshing ??= (async () => {
    const r = await send('POST', '/auth/refresh', { body: { refreshToken: t.refreshToken }, auth: false })
    if (r.status === 200) {
      const b = r.body as { data?: Tokens } | Tokens
      tokenStore.set('data' in b && b.data ? b.data : (b as Tokens))
      return true
    }
    return false
  })().finally(() => (refreshing = null))
  return refreshing
}

/** 응답 본문 전체({data, page?})를 반환. 204 는 null */
export async function request<T = unknown>(method: string, path: string, o: ReqOpts = {}): Promise<T> {
  let r = await send(method, path, o, tokenStore.get()?.accessToken)
  if (r.status === 401 && o.auth !== false && !path.startsWith('/auth/')) {
    if (await refresh()) r = await send(method, path, o, tokenStore.get()?.accessToken)
    if (r.status === 401) {
      tokenStore.set(null)
      onUnauthorized()
    }
  }
  if (r.status >= 400) {
    const err = new ApiError(r.status, r.body as ApiErrorBody | null)
    // 사용자 입력 오류(4xx)는 제외하고 서버·네트워크 문제(5xx)만 기록. 본문·헤더는 보내지 않는다
    if (r.status >= 500) reportError(err, { status: r.status, code: err.code, method, path: path.replace(/[0-9a-f-]{36}/g, ':id') })
    throw err
  }
  return r.body as T
}

/** 본문 { data } 만 꺼내기 */
export const one = async <T>(method: string, path: string, o?: ReqOpts) => (await request<{ data: T }>(method, path, o)).data
