// 사용자 API v3.5 · backend/contracts(models.py, analysis.py) 기준 타입.
// 계약에 필드 구성이 없어 프론트가 임시로 정한 부분은 [가정]으로 표시한다. 확정되면 backend/contracts 와 맞춰 수정한다.

// ----- 공통 envelope
export interface DataResponse<T> {
  data: T
}
/** 목록 응답. 계약의 Page.number 는 0부터 시작한다. */
export interface PageResponse<T> {
  data: T[]
  page: { number: number; size: number; total: number }
}
export interface ApiErrorBody {
  error: {
    code: string
    message: string
    fields?: Record<string, string>
    details?: Record<string, unknown>
    retryable?: boolean
    requestId: string
  }
}

// ----- 인증·계정 (백엔드 미구현, 경로·필드는 사용자 API v3.5 표 기준)
export type Role = 'USER' | 'ADMIN'
export interface User {
  id: string
  name: string
  email: string
  role: Role
}
export interface Agreements {
  terms: boolean
  privacy: boolean
  aiAnalysis: boolean
}
export interface AgreementVersions {
  terms: string
  privacy: string
  aiAnalysis: string
}
export interface Tokens {
  accessToken: string
  refreshToken: string
}

// ----- 프로젝트 (ProjectCreate / ProjectPatch 는 계약 모델 그대로)
export interface ProjectCreate {
  name: string
  topic: string
  finalDate?: string | null
  /** 생략 시 30, 0 이면 목표 시간 없음 */
  targetMinutes?: number
}
export type ProjectPatch = Partial<ProjectCreate & { done: boolean }>
/** [가정] 프로젝트 응답 필드 (ERD v10 projects 기준) */
export interface Project {
  id: string
  name: string
  topic: string
  finalDate: string | null
  targetMinutes: number
  done: boolean
  createdAt: string
}

/** GET /projects/{id}: project, rounds, materials, qaEligible (사용자 API v3.5) */
export interface ProjectDetail {
  project: Project
  rounds: RoundSummary[]
  materials: unknown[]
  qaEligible: boolean
}

// ----- 회차·상태
export type JobStatus = 'QUEUED' | 'EXTRACTING' | 'ANALYZING' | 'SCORING' | 'DONE' | 'FAILED'
/** [가정] 회차 목록 원소: 명세는 "회차·상태·총점"만 정의. durationSec/createdAt 은 화면 표시용으로 가정 */
export interface RoundSummary {
  analysisId: string
  roundNo: number
  status: JobStatus
  totalScore: number | null
  durationSec: number | null
  createdAt: string
}
export interface RoundStatusInfo {
  status: JobStatus
  progress: number
  stage: string
  etaSec?: number | null
  failure?: { code: string; retryable: boolean } | null
}

// ----- 업로드 (UploadCreate: 계약 모델 그대로)
export interface UploadCreate {
  fileName: string
  sizeBytes: number
  contentType: 'video/mp4' | 'video/quicktime'
  /** 영상 전체의 SHA-256 소문자 hex 64자 */
  checksum: string
}
export interface UploadTicket {
  uploadId: string
  roundNo: number
  status: 'CREATED'
  expiresAt: string
  uploadPath: string
}
export interface UploadCompleteResult {
  analysisRef: { projectId: string; roundNo: number; analysisId: string }
  status: 'QUEUED'
}

// ----- 리포트 (contracts/analysis.py Report)
export interface Evidence {
  fromSec: number
  toSec: number
  signal: string
  /** 관찰 불가면 null + reason */
  value: number | null
  reason: string | null
}
export interface ReportItemScore {
  rubricItemId: string
  itemKey: 'SPEECH_RATE' | 'FLUENCY' | 'GESTURE' | 'GAZE' | string
  score: number
  weight: number
  evidence: Evidence[]
}
export interface ReportSegment {
  fromSec: number
  toSec: number
  /** [가정] 계약은 문자열만 정의. 화면은 STRENGTH(잘한 점)/IMPROVEMENT(고칠 점)로 해석 */
  kind: string
  feedback: string
}
export interface Report {
  analysisId: string
  projectId: string
  roundNo: number
  status: 'DONE'
  totalScore: number
  scores: ReportItemScore[]
  versions: { model: string; rubric: string }
  segments: ReportSegment[]
  /** 신호 이름 → 시간 구간 배열. 신호 이름 집합은 [가정] (shared/lib/signals.ts) */
  timeline: Record<string, Evidence[]>
  coaching: { strengths: string[]; improvements: string[]; actions: string[] }
  targetMinutes: number
  timeCheck: { actualMinutes: number; deltaMinutes: number | null }
  contentCheck: null
  expectedQuestions: { kind: string; text: string }[]
  quality: 'NORMAL' | 'DEGRADED'
  limitations: string[]
}
export interface Utterance {
  seq: number
  startSec: number
  endSec: number
  text: string
}
export interface Transcript {
  utterances: Utterance[]
}

/** [가정] GET /schedule 응답 원소 */
export interface ScheduleItem {
  projectId: string
  projectName: string
  date: string
  done: boolean
}
