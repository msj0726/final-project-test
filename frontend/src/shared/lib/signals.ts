// Report.timeline 은 "신호 이름 → Evidence[]" 이다(계약). 신호 이름은 STT/Vision 담당과 확정 전이라 아래 이름을 임시로 쓴다.
// 화면은 알려진 신호만 시간축 트랙에 그리고, 모르는 신호는 무시한다.
import type { Evidence } from '../api/types'

export const SIGNAL = {
  speechRateWindow: 'SPEECH_RATE_WINDOW', // value = 분당 음절, 10초 창
  fastSpeech: 'FAST_SPEECH',
  fillerWord: 'FILLER_WORD',
  longPause: 'LONG_PAUSE',
  lowSttConfidence: 'LOW_STT_CONFIDENCE',
  handMotion: 'HAND_MOTION',
  handMotionHigh: 'HAND_MOTION_HIGH',
  gazeOffFront: 'GAZE_OFF_FRONT', // value = 벗어난 시간(초), 10초 이상
  gazeOffShort: 'GAZE_OFF_SHORT',
  faceNotVisible: 'FACE_NOT_VISIBLE',
} as const

export type Range = [number, number]
export const rangesOf = (tl: Record<string, Evidence[]>, signal: string): Range[] =>
  (tl[signal] ?? []).map((e) => [e.fromSec, e.toSec] as Range)

/** 근거(evidence) 한 줄 설명. 모르는 신호는 reason 또는 신호 이름으로 대체 */
export function describeEvidence(e: Evidence): string {
  const len = Math.round(e.toSec - e.fromSec)
  switch (e.signal) {
    case SIGNAL.fastSpeech: return '평소보다 빠르게 말한 구간이에요.'
    case SIGNAL.fillerWord: return '「음, 어」 같은 말버릇이 몰려 있어요.'
    case SIGNAL.lowSttConfidence: return '음성 인식이 어려워 다시 들어볼 구간이에요.'
    case SIGNAL.handMotionHigh: return '손을 크게 움직인 구간이에요.'
    case SIGNAL.gazeOffFront: return `고개가 정면을 ${e.value ?? len}초 동안 벗어났어요.`
    case SIGNAL.longPause: return '문장 중간에 쉼이 길었어요.'
    default: return e.reason ?? e.signal
  }
}
