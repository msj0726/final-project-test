import { one, request, tokenStore, usesMock } from './client'
import { SAMPLE_SRC } from './mock/sample'
import type {
  AgreementVersions, Agreements, Project, ProjectCreate, ProjectDetail, ProjectPatch, Report, RoundStatusInfo,
  RoundSummary, ScheduleItem, Tokens, Transcript, UploadCompleteResult, UploadCreate, UploadTicket, User,
  PageResponse,
} from './types'

export { ApiError, API_MODE, setUnauthorizedHandler, tokenStore, usesMock } from './client'

/** 현재 약관 문서 버전. [가정] 서버가 내려주기 전까지 프론트 상수로 전송 */
export const AGREEMENT_VERSIONS: AgreementVersions = { terms: '2026-11-01', privacy: '2026-11-01', aiAnalysis: '2026-11-01' }

export const health = {
  /** 백엔드 /healthz. 실제 서버(hybrid·real)면 실제 호출, mock 모드면 목업 응답 */
  async check(): Promise<{ ok: boolean; source: 'backend' | 'mock' }> {
    const source = usesMock('GET', '/healthz') ? 'mock' : 'backend'
    try {
      const r = await request<{ status: string }>('GET', '/healthz', { auth: false })
      return { ok: r?.status === 'ok', source }
    } catch {
      return { ok: false, source }
    }
  },
}

export const auth = {
  signup: (b: { name: string; email: string; password: string; agreements: Agreements }) =>
    one<User>('POST', '/auth/signup', { body: { ...b, agreementVersions: AGREEMENT_VERSIONS }, auth: false }),
  login: (email: string, password: string) =>
    one<{ user: User; tokens: Tokens }>('POST', '/auth/login', { body: { email, password }, auth: false }),
  logout: async () => {
    const t = tokenStore.get()
    if (t) await request('POST', '/auth/logout', { body: { refreshToken: t.refreshToken }, auth: false }).catch(() => {})
  },
  me: () => one<{ user: User; agreements: Agreements; agreementVersions: AgreementVersions }>('GET', '/me'),
  updateMe: (b: { name?: string; currentPassword?: string; newPassword?: string }) => one<User>('PATCH', '/me', { body: b }),
  deleteMe: (password: string) => request('DELETE', '/me', { body: { password } }),
}

export const projects = {
  list: (q: { status?: 'ONGOING' | 'DONE'; page?: number; size?: number } = {}) =>
    request<PageResponse<Project>>('GET', '/projects', { query: q }),
  /** 모든 쪽을 모아서 반환 (page.number 는 0부터) */
  async listAll(status?: 'ONGOING' | 'DONE'): Promise<Project[]> {
    const out: Project[] = []
    for (let page = 0; ; page++) {
      const r = await projects.list({ status, page, size: 100 })
      out.push(...r.data)
      if (out.length >= r.page.total || !r.data.length) return out
    }
  },
  create: (b: ProjectCreate) => one<Project>('POST', '/projects', { body: b, idempotent: true }),
  get: (id: string) => one<ProjectDetail>('GET', `/projects/${id}`),
  update: (id: string, b: ProjectPatch) => one<Project>('PATCH', `/projects/${id}`, { body: b }),
  remove: (id: string) => request('DELETE', `/projects/${id}`),
}

const reportCache = new Map<string, Report>()
export const clearApiCache = () => reportCache.clear()

export const rounds = {
  list: (pid: string) => one<RoundSummary[]>('GET', `/projects/${pid}/rounds`),
  status: (pid: string, n: number) => one<RoundStatusInfo>('GET', `/projects/${pid}/rounds/${n}/status`),
  retry: (pid: string, n: number) => one('POST', `/projects/${pid}/rounds/${n}/retry`, { idempotent: true }),
  report: (pid: string, n: number) => one<Report>('GET', `/projects/${pid}/rounds/${n}/report`),
  /** DONE 리포트는 바뀌지 않으므로 세션 동안 캐시 (이력·카드에서 여러 번 읽음) */
  async cachedReport(pid: string, n: number): Promise<Report> {
    const k = `${pid}:${n}`
    const hit = reportCache.get(k)
    if (hit) return hit
    const r = await rounds.report(pid, n)
    reportCache.set(k, r)
    return r
  },
  transcript: (pid: string, n: number) => one<Transcript>('GET', `/projects/${pid}/rounds/${n}/transcript`),
  remove: async (pid: string, n: number) => {
    await request('DELETE', `/projects/${pid}/rounds/${n}`)
    reportCache.delete(`${pid}:${n}`)
  },
}

export const schedule = {
  list: (month?: string) => one<ScheduleItem[]>('GET', '/schedule', { query: { month } }),
}

export const uploads = {
  create: (pid: string, b: UploadCreate) => one<UploadTicket>('POST', `/projects/${pid}/uploads`, { body: b, idempotent: true }),
  /** 영상 바이너리 전송(PUT, Content-Type + X-Checksum-Sha256). 진행률(0~1) 콜백 */
  async putContent(ticket: UploadTicket, file: File, checksum: string, onProgress: (ratio: number) => void) {
    if (usesMock('PUT', ticket.uploadPath)) {
      for (let i = 1; i <= 10; i++) {
        await new Promise((r) => setTimeout(r, 120))
        onProgress(i / 10)
      }
      await request('PUT', ticket.uploadPath, { headers: { 'X-Checksum-Sha256': checksum } })
      return
    }
    await new Promise<void>((resolve, reject) => {
      const x = new XMLHttpRequest()
      x.open('PUT', '/api/v1' + ticket.uploadPath)
      x.setRequestHeader('Authorization', `Bearer ${tokenStore.get()?.accessToken}`)
      x.setRequestHeader('Content-Type', file.type)
      x.setRequestHeader('X-Checksum-Sha256', checksum)
      x.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total)
      x.onload = () => (x.status === 204 ? resolve() : reject(Object.assign(new Error('업로드에 실패했어요.'), { status: x.status })))
      x.onerror = () => reject(new Error('네트워크 오류로 업로드에 실패했어요.'))
      x.send(file)
    })
  },
  complete: (uploadId: string) => one<UploadCompleteResult>('POST', `/uploads/${uploadId}/complete`, { idempotent: true }),
  cancel: (uploadId: string) => request('DELETE', `/uploads/${uploadId}`),
}

/**
 * 리포트 플레이어가 쓸 영상 주소. 목업이면 내장 샘플 영상.
 * 실제 GET /projects/{id}/rounds/{n}/video 는 Bearer 인증이라 <video src> 로 바로 쓸 수 없어 null (인증 방식 합의 후 연결).
 */
export const videoSrc = (pid: string, n: number): string | null => (usesMock('GET', `/projects/${pid}/rounds/${n}/video`) ? SAMPLE_SRC : null)
