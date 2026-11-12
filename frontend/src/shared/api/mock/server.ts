/* eslint-disable @typescript-eslint/no-explicit-any -- 목업 서버는 임의의 요청 JSON 을 손으로 검증한다 */
// 백엔드에 아직 없는 경로를 대신하는 목업 서버. 사용자 API v3.5 와 backend/contracts 의 응답 형식을 따른다.
// 상태는 localStorage(propitch-mock-db-v3)에 저장되어 새로고침해도 유지된다.
// 초기화: 개발자도구에서 localStorage.removeItem('propitch-mock-db-v3')
import type { ApiErrorBody, JobStatus, Project, RoundSummary, User } from '../types'
import { RUBRIC_ITEMS, buildReport, buildTranscript } from './report'
import { SAMPLE_SEC } from './sample'

interface MUser extends User {
  password: string
  agreements: { terms: boolean; privacy: boolean; aiAnalysis: boolean }
  agreementVersions: { terms: string; privacy: string; aiAnalysis: string }
}
interface MProject extends Project {
  userId: string
}
interface MRound {
  id: string
  projectId: string
  roundNo: number
  uploadId: string
  durationSec: number
  createdAt: string
  scores: Record<string, number>
  total: number
  /** null 이면 시드(이미 완료), 숫자면 분석 시작 시각(ms) */
  startedAt: number | null
  willFail: boolean
}
interface MUpload {
  id: string
  projectId: string
  roundNo: number
  fileName: string
  sizeBytes: number
  contentType: string
  checksum: string
  expiresAt: string
  received: boolean
  roundId?: string
}
interface DB {
  users: MUser[]
  projects: MProject[]
  rounds: MRound[]
  uploads: MUpload[]
  idem: Record<string, Res>
}

const KEY = 'propitch-mock-db-v3'
const uid = () => crypto.randomUUID()
const iso = (offsetDays = 0, hour = 10) => {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  d.setHours(hour, 0, 0, 0)
  return d.toISOString()
}
const dateStr = (offsetDays: number) => iso(offsetDays).slice(0, 10)

function seed(): DB {
  const u: MUser = {
    id: uid(), name: '이지영', email: 'jiyoung@example.com', password: 'password123', role: 'USER',
    agreements: { terms: true, privacy: true, aiAnalysis: true },
    agreementVersions: { terms: '2026-11-01', privacy: '2026-11-01', aiAnalysis: '2026-11-01' },
  }
  const mkP = (name: string, topic: string, final: number, target: number, created: number): MProject => ({
    id: uid(), userId: u.id, name, topic, finalDate: dateStr(final), targetMinutes: target, done: false, createdAt: iso(created),
  })
  const pA = mkP('최종발표 리허설', 'AI 기반 발표 코칭 서비스 소개', 10, 30, -14)
  const pB = mkP('동아리 정기 발표', '2학기 활동 결과 공유', 21, 20, -20)
  const mk = (p: MProject, n: number, daysAgo: number, s: [number, number, number, number]): MRound => ({
    id: uid(), projectId: p.id, roundNo: n, uploadId: uid(), durationSec: SAMPLE_SEC, createdAt: iso(-daysAgo, 14),
    scores: { SPEECH_RATE: s[0], FLUENCY: s[1], GESTURE: s[2], GAZE: s[3] },
    total: Math.round((s[0] + s[1] + s[2] + s[3]) / 4), startedAt: null, willFail: false,
  })
  const rounds = [
    mk(pA, 1, 9, [50, 60, 52, 54]), mk(pA, 2, 7, [58, 69, 60, 63]), mk(pA, 3, 5, [66, 84, 85, 62]),
    mk(pB, 1, 14, [44, 56, 46, 48]), mk(pB, 2, 11, [54, 64, 56, 54]), mk(pB, 3, 8, [51, 62, 52, 55]), mk(pB, 4, 5, [52, 63, 58, 60]),
  ]
  return { users: [u], projects: [pA, pB], rounds, uploads: [], idem: {} }
}

let db: DB
function load() {
  if (db) return
  try {
    const raw = localStorage.getItem(KEY)
    if (raw) {
      db = JSON.parse(raw)
      return
    }
  } catch {
    /* 저장소 사용 불가 */
  }
  db = seed()
  save()
}
function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(db))
  } catch {
    /* ignore */
  }
}

// ----- 응답 헬퍼 (계약: 단건 {data}, 목록 {data,page}, 204 무본문, 오류 {error:{...}})
export type Res = { status: number; body: any }
const ok = (data: unknown, status = 200): Res => ({ status, body: { data } })
const none = (): Res => ({ status: 204, body: null })
const fail = (status: number, code: string, message: string, extra: Partial<ApiErrorBody['error']> = {}): Res => ({
  status,
  body: { error: { code, message, fields: {}, details: {}, retryable: false, requestId: 'mock-' + uid().slice(0, 8), ...extra } },
})
const invalid = (fields: Record<string, string>) => fail(400, 'VALIDATION_FAILED', '입력값을 확인해 주세요.', { fields })
const notFound = () => fail(404, 'NOT_FOUND', '찾을 수 없어요.')

// ----- 분석 진행: 시작 후 경과 시간으로 상태를 계산 (약 13초 뒤 DONE)
const STAGES: { until: number; status: JobStatus; stage: string; from: number; to: number }[] = [
  { until: 1.5, status: 'QUEUED', stage: 'QUEUED', from: 0, to: 5 },
  { until: 4, status: 'EXTRACTING', stage: 'PREPROCESS', from: 5, to: 30 },
  { until: 9, status: 'ANALYZING', stage: 'AUDIO', from: 30, to: 80 },
  { until: 13, status: 'SCORING', stage: 'RUBRIC_RULE', from: 80, to: 99 },
]
function statusOf(r: MRound) {
  if (r.startedAt == null) return { status: 'DONE' as JobStatus, progress: 100, stage: 'DONE', etaSec: 0, failure: null }
  const el = (Date.now() - r.startedAt) / 1000
  if (r.willFail && el > 6) return { status: 'FAILED' as JobStatus, progress: 40, stage: 'AUDIO', etaSec: null, failure: { code: 'STT_TEMPORARY_ERROR', retryable: true } }
  let prev = 0
  for (const s of STAGES) {
    if (el < s.until) {
      const f = (el - prev) / (s.until - prev)
      return { status: s.status, progress: Math.round(s.from + (s.to - s.from) * f), stage: s.stage, etaSec: Math.max(1, Math.round((13 - el) * 10)), failure: null }
    }
    prev = s.until
  }
  return { status: 'DONE' as JobStatus, progress: 100, stage: 'DONE', etaSec: 0, failure: null }
}
function summary(r: MRound): RoundSummary {
  const st = statusOf(r)
  return { analysisId: r.id, roundNo: r.roundNo, status: st.status, totalScore: st.status === 'DONE' ? r.total : null, durationSec: r.durationSec, createdAt: r.createdAt }
}
const roundsOf = (pid: string) => db.rounds.filter((r) => r.projectId === pid).sort((a, b) => a.roundNo - b.roundNo)
const strip = ({ userId: _u, ...p }: MProject): Project => p

// ----- 라우터
interface Ctx {
  query?: Record<string, string | number | undefined>
  body?: any
  headers: Record<string, string>
}
type Handler = (m: string[], c: Ctx, user: MUser | null) => Res | Promise<Res>
const routes: { method: string; re: RegExp; auth: boolean; h: Handler }[] = []
const route = (method: string, path: string, auth: boolean, h: Handler) =>
  routes.push({ method, re: new RegExp('^' + path.replace(/:[a-zA-Z]+/g, '([^/]+)') + '$'), auth, h })

const tokenFor = (u: MUser) => ({ accessToken: 'mock.' + u.id, refreshToken: 'mockr.' + u.id })
const pub = (u: MUser): User => ({ id: u.id, name: u.name, email: u.email, role: u.role })
const ownProject = (id: string, u: MUser) => db.projects.find((p) => p.id === id && p.userId === u.id)

// 상태 확인 (실제 백엔드가 꺼져 있을 때 전체 목업 모드용)
route('GET', '/healthz', false, () => ({ status: 200, body: { status: 'ok' } }))

// 인증
route('POST', '/auth/signup', false, (_, { body: b }) => {
  const f: Record<string, string> = {}
  if (!b?.name?.trim()) f.name = '이름을 입력해 주세요.'
  if (!/^\S+@\S+\.\S+$/.test(b?.email || '')) f.email = '이메일 형식을 확인해 주세요.'
  if ((b?.password || '').length < 8) f.password = '비밀번호는 8자 이상이어야 해요.'
  if (!b?.agreements?.terms || !b?.agreements?.privacy || !b?.agreements?.aiAnalysis) f.agreements = '필수 항목에 모두 동의해 주세요.'
  if (Object.keys(f).length) return invalid(f)
  if (db.users.some((u) => u.email === b.email)) return invalid({ email: '이미 가입된 이메일이에요.' })
  const u: MUser = { id: uid(), name: b.name.trim(), email: b.email, password: b.password, role: 'USER', agreements: b.agreements, agreementVersions: b.agreementVersions }
  db.users.push(u)
  save()
  return ok(pub(u), 201)
})
route('POST', '/auth/login', false, (_, { body: b }) => {
  const u = db.users.find((x) => x.email === b?.email && x.password === b?.password)
  return u ? ok({ user: pub(u), tokens: tokenFor(u) }) : fail(401, 'UNAUTHENTICATED', '이메일 또는 비밀번호가 맞지 않아요.')
})
route('POST', '/auth/refresh', false, (_, { body: b }) => {
  const u = db.users.find((x) => x.id === String(b?.refreshToken || '').replace('mockr.', ''))
  return u ? ok(tokenFor(u)) : fail(401, 'UNAUTHENTICATED', '다시 로그인해 주세요.')
})
route('POST', '/auth/logout', false, () => none())

// 내 정보
route('GET', '/me', true, (_, __, u) => ok({ user: pub(u!), agreements: u!.agreements, agreementVersions: u!.agreementVersions }))
route('PATCH', '/me', true, (_, { body: b }, u) => {
  if (b?.name !== undefined) {
    if (!String(b.name).trim()) return invalid({ name: '이름을 입력해 주세요.' })
    u!.name = String(b.name).trim()
  }
  save()
  return ok(pub(u!))
})
route('DELETE', '/me', true, (_, { body: b }, u) => {
  if (b?.password !== u!.password) return invalid({ password: '비밀번호가 맞지 않아요.' })
  const pids = db.projects.filter((p) => p.userId === u!.id).map((p) => p.id)
  db.rounds = db.rounds.filter((r) => !pids.includes(r.projectId))
  db.projects = db.projects.filter((p) => p.userId !== u!.id)
  db.users = db.users.filter((x) => x.id !== u!.id)
  save()
  return none()
})

// 프로젝트 (ProjectCreate/ProjectPatch 계약: name, topic, finalDate, targetMinutes, done)
route('GET', '/projects', true, (_, { query: q }, u) => {
  let list = db.projects.filter((p) => p.userId === u!.id)
  if (q?.status === 'ONGOING') list = list.filter((p) => !p.done)
  if (q?.status === 'DONE') list = list.filter((p) => p.done)
  list.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  const size = Math.min(100, Math.max(1, Number(q?.size) || 20))
  const number = Math.max(0, Number(q?.page) || 0)
  return { status: 200, body: { data: list.slice(number * size, number * size + size).map(strip), page: { number, size, total: list.length } } }
})
route('POST', '/projects', true, (_, { body: b }, u) => {
  const f: Record<string, string> = {}
  if (typeof b?.name !== 'string' || !b.name.trim()) f.name = '발표 제목을 입력해 주세요.'
  if (typeof b?.topic !== 'string' || !b.topic.trim()) f.topic = '발표 주제를 입력해 주세요.'
  if (b?.finalDate != null && !/^\d{4}-\d{2}-\d{2}$/.test(b.finalDate)) f.finalDate = '날짜는 YYYY-MM-DD 형식이어야 해요.'
  if (b?.targetMinutes != null && (!Number.isInteger(b.targetMinutes) || b.targetMinutes < 0)) f.targetMinutes = '0 이상의 정수여야 해요.'
  if (Object.keys(f).length) return invalid(f)
  const p: MProject = { id: uid(), userId: u!.id, name: b.name.trim(), topic: b.topic.trim(), finalDate: b.finalDate ?? null, targetMinutes: b.targetMinutes ?? 30, done: false, createdAt: new Date().toISOString() }
  db.projects.push(p)
  save()
  return ok(strip(p), 201)
})
route('GET', '/projects/:id', true, ([id], _, u) => {
  const p = ownProject(id, u!)
  if (!p) return notFound()
  const rs = roundsOf(p.id).map(summary)
  return ok({ project: strip(p), rounds: rs, materials: [], qaEligible: rs.some((r) => r.status === 'DONE') })
})
route('PATCH', '/projects/:id', true, ([id], { body: b }, u) => {
  const p = ownProject(id, u!)
  if (!p) return notFound()
  if (!b || !Object.keys(b).length) return invalid({ body: '최소 한 필드가 필요해요.' })
  for (const k of ['name', 'topic', 'finalDate', 'targetMinutes', 'done'] as const) if (b[k] !== undefined) (p as any)[k] = b[k]
  save()
  return ok(strip(p))
})
route('DELETE', '/projects/:id', true, ([id], _, u) => {
  if (!ownProject(id, u!)) return notFound()
  db.projects = db.projects.filter((x) => x.id !== id)
  db.rounds = db.rounds.filter((r) => r.projectId !== id)
  save()
  return none()
})

// 영상 업로드 (UploadCreate 계약: fileName, sizeBytes ≤ 500MiB, contentType mp4|quicktime, checksum sha256 hex 64자). 영상 바이트는 저장하지 않는다.
route('POST', '/projects/:id/uploads', true, ([id], { body: b }, u) => {
  if (!ownProject(id, u!)) return notFound()
  if (!['video/mp4', 'video/quicktime'].includes(b?.contentType)) return fail(415, 'UNSUPPORTED_MEDIA', 'MP4 또는 MOV 영상만 올릴 수 있어요.')
  if (!Number.isInteger(b?.sizeBytes) || b.sizeBytes < 1) return invalid({ sizeBytes: '파일 크기를 확인해 주세요.' })
  if (b.sizeBytes > 524288000) return fail(413, 'UPLOAD_TOO_LARGE', '영상은 500MB 이하만 올릴 수 있어요.')
  if (!/^[a-fA-F0-9]{64}$/.test(b?.checksum || '')) return invalid({ checksum: 'SHA-256 64자리 값이 필요해요.' })
  const roundNo = Math.max(0, ...db.rounds.filter((r) => r.projectId === id).map((r) => r.roundNo), ...db.uploads.filter((x) => x.projectId === id && !x.roundId).map((x) => x.roundNo)) + 1
  const up: MUpload = { id: uid(), projectId: id, roundNo, fileName: b.fileName, sizeBytes: b.sizeBytes, contentType: b.contentType, checksum: b.checksum.toLowerCase(), expiresAt: new Date(Date.now() + 3600e3).toISOString(), received: false }
  db.uploads.push(up)
  save()
  return ok({ uploadId: up.id, roundNo, status: 'CREATED', expiresAt: up.expiresAt, uploadPath: `/uploads/${up.id}/content` }, 201)
})
route('PUT', '/uploads/:id/content', true, ([id], { headers }, u) => {
  const up = db.uploads.find((x) => x.id === id)
  if (!up || !ownProject(up.projectId, u!)) return notFound()
  if (new Date(up.expiresAt) < new Date()) return fail(410, 'UPLOAD_EXPIRED', '업로드 시간이 지났어요. 다시 시작해 주세요.')
  const sum = (headers['X-Checksum-Sha256'] || '').toLowerCase()
  if (sum !== up.checksum) return fail(409, 'INVALID_STATE', '업로드한 내용이 처음 알린 것과 달라요.')
  up.received = true
  save()
  return none()
})
route('POST', '/uploads/:id/complete', true, ([id], _, u) => {
  const up = db.uploads.find((x) => x.id === id)
  if (!up || !ownProject(up.projectId, u!)) return notFound()
  if (!up.received) return fail(409, 'UPLOAD_INCOMPLETE', '영상 전송이 끝나지 않았어요.')
  const done = (rid: string) => ok({ analysisRef: { projectId: up.projectId, roundNo: up.roundNo, analysisId: rid }, status: 'QUEUED' }, 202)
  if (up.roundId) return done(up.roundId)
  const prev = roundsOf(up.projectId).at(-1)
  const base = prev?.scores ?? { SPEECH_RATE: 50, FLUENCY: 58, GESTURE: 50, GAZE: 54 }
  const scores: Record<string, number> = {}
  RUBRIC_ITEMS.forEach((it, i) => (scores[it.key] = Math.max(30, Math.min(95, Math.round(base[it.key] + ((up.roundNo * 13 + i * 7) % 11) - 2)))))
  const total = Math.round(Object.values(scores).reduce((a, b) => a + b, 0) / 4)
  const r: MRound = { id: uid(), projectId: up.projectId, roundNo: up.roundNo, uploadId: up.id, durationSec: SAMPLE_SEC, createdAt: new Date().toISOString(), scores, total, startedAt: Date.now(), willFail: /fail|실패/i.test(up.fileName) }
  db.rounds.push(r)
  up.roundId = r.id
  save()
  return done(r.id)
})
route('DELETE', '/uploads/:id', true, ([id], _, u) => {
  const up = db.uploads.find((x) => x.id === id)
  if (!up || !ownProject(up.projectId, u!)) return notFound()
  db.uploads = db.uploads.filter((x) => x.id !== id)
  save()
  return none()
})

// 회차·상태·리포트·전사
const roundOf = (pid: string, n: string, u: MUser) => (ownProject(pid, u) ? db.rounds.find((r) => r.projectId === pid && r.roundNo === Number(n)) : undefined)
route('GET', '/projects/:id/rounds', true, ([id], _, u) => (ownProject(id, u!) ? ok(roundsOf(id).map(summary)) : notFound()))
route('GET', '/projects/:id/rounds/:n/status', true, ([id, n], _, u) => {
  const r = roundOf(id, n, u!)
  return r ? ok(statusOf(r)) : notFound()
})
route('POST', '/projects/:id/rounds/:n/retry', true, ([id, n], _, u) => {
  const r = roundOf(id, n, u!)
  if (!r) return notFound()
  if (statusOf(r).status !== 'FAILED') return fail(409, 'INVALID_STATE', '실패한 분석만 다시 시도할 수 있어요.')
  r.startedAt = Date.now()
  r.willFail = false
  save()
  return ok({ analysisRef: { projectId: id, roundNo: r.roundNo, analysisId: r.id }, status: 'QUEUED' }, 202)
})
route('GET', '/projects/:id/rounds/:n/report', true, ([id, n], _, u) => {
  const r = roundOf(id, n, u!)
  if (!r) return notFound()
  if (statusOf(r).status !== 'DONE') return fail(409, 'REPORT_NOT_READY', '아직 분석 중이에요.')
  const p = ownProject(id, u!)!
  return ok(buildReport({ projectId: id, analysisId: r.id, roundNo: r.roundNo, durationSec: r.durationSec, targetMinutes: p.targetMinutes, scores: r.scores, total: r.total }))
})
route('GET', '/projects/:id/rounds/:n/transcript', true, ([id, n], _, u) => {
  const r = roundOf(id, n, u!)
  if (!r) return notFound()
  if (statusOf(r).status !== 'DONE') return fail(409, 'REPORT_NOT_READY', '아직 분석 중이에요.')
  return ok({ utterances: buildTranscript(r.durationSec, r.roundNo * 17 + 3) })
})
route('DELETE', '/projects/:id/rounds/:n', true, ([id, n], _, u) => {
  const r = roundOf(id, n, u!)
  if (!r) return notFound()
  db.rounds = db.rounds.filter((x) => x.id !== r.id)
  save()
  return none()
})
route('GET', '/schedule', true, (_, { query: q }, u) => {
  const month = q?.month as string | undefined
  return ok(
    db.projects
      .filter((p) => p.userId === u!.id && p.finalDate && (!month || p.finalDate.startsWith(month)))
      .map((p) => ({ projectId: p.id, projectName: p.name, date: p.finalDate as string, done: p.done })),
  )
})

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** path 는 /api/v1 뒤의 경로(/projects 등). 헬스체크만 /healthz */
export async function mockRequest(method: string, path: string, ctx: Ctx): Promise<Res> {
  load()
  await sleep(120 + Math.random() * 180)
  const r = routes.find((x) => x.method === method && x.re.test(path))
  if (!r) return fail(404, 'NOT_FOUND', '지원하지 않는 요청이에요. (목업)')
  let user: MUser | null = null
  if (r.auth) {
    const tk = (ctx.headers.Authorization || '').replace('Bearer ', '')
    user = db.users.find((u) => 'mock.' + u.id === tk) ?? null
    if (!user) return fail(401, 'UNAUTHENTICATED', '로그인이 필요해요.')
  }
  // 멱등성: 같은 Idempotency-Key 의 같은 요청은 최초 결과를 반환
  const ik = ctx.headers['Idempotency-Key']
  const ikey = ik ? `${user?.id}|${method} ${path}|${ik}` : null
  if (ikey && db.idem[ikey]) return db.idem[ikey]
  const res = await r.h(path.match(r.re)!.slice(1), ctx, user)
  if (ikey && res.status < 400) {
    db.idem[ikey] = res
    save()
  }
  return res
}
