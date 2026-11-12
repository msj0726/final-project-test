// 목업 리포트·전사 생성기. backend/contracts 의 Report 형식을 따르는 합성 데이터이며 실제 분석 결과가 아니다.
// 프로토타입(app5)의 18분 42초 예시 발표를 영상 길이에 맞춰 비율로 늘이고 줄인다.
import type { Evidence, Report, ReportItemScore, ReportSegment, Utterance } from '../types'
import { SIGNAL } from '../../lib/signals'

const BASE_D = 1122
export const RUBRIC_ITEMS: { id: string; key: string; weight: number }[] = [
  { id: '11111111-1111-4111-8111-000000000001', key: 'SPEECH_RATE', weight: 0.25 },
  { id: '11111111-1111-4111-8111-000000000002', key: 'FLUENCY', weight: 0.25 },
  { id: '11111111-1111-4111-8111-000000000003', key: 'GESTURE', weight: 0.25 },
  { id: '11111111-1111-4111-8111-000000000004', key: 'GAZE', weight: 0.25 },
]

function rng(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function buildReport(a: {
  projectId: string
  analysisId: string
  roundNo: number
  durationSec: number
  targetMinutes: number
  scores: Record<string, number>
  total: number
}): Report {
  const D = a.durationSec
  const k = D / BASE_D
  const R = rng(a.roundNo * 31 + 7)
  const clampT = (x: number) => Math.min(D, Math.max(0, x))
  const iv = (signal: string, from: number, to: number, value: number | null, reason: string | null = null): Evidence => {
    const f = clampT(Math.round(from * k))
    return { fromSec: f, toSec: Math.min(D, Math.max(f + 1, Math.round(to * k))), signal, value, reason }
  }
  const many = (signal: string, rs: [number, number][], value: number | null, reason: string | null = null) => rs.map(([x, y]) => iv(signal, x, y, value, reason))

  const fast = many(SIGNAL.fastSpeech, [[432, 500]], 410)
  const gazeOff = [[130, 144], [530, 544], [750, 766]].map(([x, y]) => iv(SIGNAL.gazeOffFront, x, y, y - x))
  const lowConf = many(SIGNAL.lowSttConfidence, [[485, 505], [860, 880]], 0.42)
  const handHigh = many(SIGNAL.handMotionHigh, [[545, 600]], 0.8)
  const noFace = many(SIGNAL.faceNotVisible, [[860, 872]], null, '얼굴이 화면에 보이지 않음')

  // 10초 창 발화 속도(분당 음절)
  const windows: Evidence[] = []
  for (let from = 0, i = 0; from < D; from += 10, i++) {
    const mid = from + 5
    const isFast = fast.some((f) => mid >= f.fromSec && mid <= f.toSec)
    windows.push({
      fromSec: from, toSec: Math.min(D, from + 10), signal: SIGNAL.speechRateWindow,
      value: Math.round(isFast ? 398 + R() * 28 : 298 + 22 * Math.sin(i / 5) + R() * 16 - 6), reason: null,
    })
  }
  const hand: Evidence[] = []
  for (let t = 20; t < D - 20; ) {
    const len = 6 + Math.floor(R() * 14)
    const from = t
    const to = Math.min(D, t + len)
    const clash = [...noFace, ...handHigh].some((e) => from < e.toSec && to > e.fromSec)
    if (!clash && to > from) hand.push({ fromSec: from, toSec: to, signal: SIGNAL.handMotion, value: 0.3, reason: null })
    t += len + 6 + Math.floor(R() * 40)
  }
  const fillers: Evidence[] = []
  ;[[9, 5, 95], [6, 105, 325], [14, 335, 675], [17, 685, 965], [7, 975, 1115]].forEach(([c, x, y]) => {
    for (let i = 0; i < c; i++) {
      const t = clampT(Math.round((x + R() * (y - x)) * k))
      fillers.push({ fromSec: Math.min(t, D - 1), toSec: Math.min(D, Math.min(t, D - 1) + 1), signal: SIGNAL.fillerWord, value: 1, reason: null })
    }
  })
  fillers.sort((p, q) => p.fromSec - q.fromSec)

  const timeline: Report['timeline'] = {
    [SIGNAL.speechRateWindow]: windows,
    [SIGNAL.fastSpeech]: fast,
    [SIGNAL.fillerWord]: fillers,
    [SIGNAL.longPause]: many(SIGNAL.longPause, [[185, 187], [408, 410], [570, 572], [782, 784]], 2),
    [SIGNAL.lowSttConfidence]: lowConf,
    [SIGNAL.handMotion]: hand,
    [SIGNAL.handMotionHigh]: handHigh,
    [SIGNAL.gazeOffFront]: gazeOff,
    [SIGNAL.gazeOffShort]: many(SIGNAL.gazeOffShort, [[60, 66], [300, 307], [640, 648], [1010, 1016]], 6),
    [SIGNAL.faceNotVisible]: noFace,
  }

  const evidenceOf: Record<string, Evidence[]> = {
    SPEECH_RATE: fast,
    FLUENCY: [iv(SIGNAL.fillerWord, 5, 95, 9), ...lowConf],
    GESTURE: handHigh,
    GAZE: gazeOff,
  }
  const scores: ReportItemScore[] = RUBRIC_ITEMS.map((it) => ({
    rubricItemId: it.id, itemKey: it.key, score: a.scores[it.key], weight: it.weight, evidence: evidenceOf[it.key],
  }))

  const seg = (kind: 'STRENGTH' | 'IMPROVEMENT', from: number, to: number, feedback: string): ReportSegment => {
    const e = iv('SEGMENT', from, to, null, 'segment')
    return { fromSec: e.fromSec, toSec: e.toSec, kind, feedback }
  }
  const segments: ReportSegment[] = [
    seg('STRENGTH', 6, 20, '첫 문장에서 발표 목적을 바로 말했어요.'),
    seg('IMPROVEMENT', 5, 95, '「음, 어」가 도입에 몰려 있어요. 첫 문장 앞의 말버릇부터 줄여 보세요.'),
    seg('STRENGTH', 160, 200, '문제 상황을 수치와 함께 설명해서 이해하기 쉬웠어요.'),
    seg('IMPROVEMENT', 130, 144, '고개가 정면을 14초 동안 벗어나 있었어요. 슬라이드를 볼 때도 중간에 한 번씩 청중 쪽으로 돌아오세요.'),
    seg('STRENGTH', 370, 372, '핵심 수치를 말하기 직전에 잠깐 멈춰서 강조가 잘 됐어요.'),
    seg('IMPROVEMENT', 432, 500, '약 68초 동안 말이 많이 빨랐어요. 문장 사이에 한 박자씩 쉬어 보세요.'),
    seg('IMPROVEMENT', 530, 544, '고개가 14초 동안 정면을 벗어나 있었어요.'),
    seg('STRENGTH', 735, 760, '기대 효과를 구체 사례로 설명했어요.'),
    seg('IMPROVEMENT', 750, 766, '고개가 16초 동안 정면을 벗어나 있었어요.'),
    seg('STRENGTH', 1040, 1060, '결론에서 핵심 요지를 한 번 더 짚고 마무리했어요.'),
  ].sort((p, q) => p.fromSec - q.fromSec)

  const actualMinutes = D / 60 // 계약: actualMinutes × 60 == 영상 길이(초)
  return {
    analysisId: a.analysisId, projectId: a.projectId, roundNo: a.roundNo, status: 'DONE', totalScore: a.total,
    scores, versions: { model: 'mock-model-v1', rubric: 'mock-rubric-v1' }, segments, timeline,
    coaching: {
      strengths: ['말버릇이 많지 않고 쉬어가는 타이밍이 자연스러워 듣기 편안했어요.', '손동작이 과하지 않아 내용에 집중하기 좋았어요.'],
      improvements: ['중반에 말이 크게 빨라져 핵심 내용이 묻힐 수 있었어요.', '고개가 정면에서 10초 넘게 벗어난 구간이 세 번 있었어요.'],
      actions: ['핵심 내용은 한 문장씩 끊고 한 박자 쉬어 보세요.', '슬라이드를 본 뒤에는 청중 쪽으로 고개를 돌려 보세요.'],
    },
    targetMinutes: a.targetMinutes,
    timeCheck: { actualMinutes, deltaMinutes: a.targetMinutes === 0 ? null : actualMinutes - a.targetMinutes },
    contentCheck: null,
    expectedQuestions: [
      { kind: 'TECH', text: '점수는 어떤 기준으로 산출되나요?' },
      { kind: 'BUSINESS', text: '경쟁 서비스와 무엇이 다른가요?' },
      { kind: 'TECH', text: '영상 길이가 길어져도 분석 시간이 크게 늘지 않나요?' },
    ],
    quality: 'NORMAL',
    limitations: ['FACE_NOT_VISIBLE_EXCLUDED', 'LOW_STT_CONFIDENCE'],
  }
}

const SENT = [
  '안녕하세요, 오늘 발표를 맡은 이지영입니다.',
  '오늘은 AI로 발표를 연습하는 서비스를 소개해 드리려고 합니다.',
  '먼저 발표 연습에서 가장 어려운 점부터 말씀드리겠습니다.',
  '혼자 연습하면 내 발표가 어떻게 들리는지 알기가 어렵습니다.',
  '그래서 영상을 올리면 말의 속도와 시선, 손동작을 함께 분석해 드립니다.',
  '결과는 구간별 피드백과 네 가지 지표 점수로 정리됩니다.',
  '같은 발표를 반복하면 회차별로 점수가 어떻게 달라졌는지 볼 수 있습니다.',
  '특히 말이 빨라진 구간은 시간축에서 바로 확인할 수 있습니다.',
  '고개가 정면을 벗어난 구간도 같은 방식으로 표시됩니다.',
  '점수는 정해진 규칙으로 계산하고, 코칭 문장은 그 결과를 설명합니다.',
  '이렇게 하면 다음 연습에서 무엇을 고칠지 분명해집니다.',
  '마지막으로 정리하면, 데이터로 연습하고 질문까지 대비할 수 있습니다.',
  '이상으로 발표를 마치겠습니다. 감사합니다.',
]
/** 전사 계약: seq 1부터 연속, startSec < endSec ≤ 영상 길이 */
export function buildTranscript(durationSec: number, seed: number): Utterance[] {
  const R = rng(seed)
  const out: Utterance[] = []
  let t = 1
  let i = 0
  while (t < durationSec - 3) {
    const len = 3 + Math.floor(R() * 4)
    out.push({ seq: out.length + 1, startSec: t, endSec: Math.min(t + len, durationSec), text: SENT[i % SENT.length] })
    t += len + 1 + Math.floor(R() * 3)
    i++
  }
  return out
}
