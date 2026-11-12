import type { RoundSummary } from '../api/types'
import { ITEMS } from './rubric'

/** 한 회차의 항목별 점수(리포트에서 가져옴). 총점은 RoundSummary.totalScore */
export type ItemScores = Record<string, number>
export interface RoundView extends RoundSummary {
  /** DONE 회차만 채워짐 */
  items: ItemScores
}

export const fmt = (sec: number) => {
  const t = Math.max(0, Math.round(sec))
  return Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0')
}

export const fsz = (b: number) =>
  b >= 1048576 ? (b / 1048576).toFixed(b >= 1.05e8 ? 0 : 1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB'

export const grade = (v: number): [string, 'ok' | 'obs' | 'fix'] =>
  v >= 80 ? ['좋아요', 'ok'] : v >= 70 ? ['보통', 'obs'] : ['보완 필요', 'fix']

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
export const dday = (dateStr: string | null) => {
  if (!dateStr) return ''
  const [y, m, d] = dateStr.split('-').map(Number)
  const n = Math.round((new Date(y, m - 1, d).getTime() - startOfDay(new Date()).getTime()) / 864e5)
  return n >= 0 ? (n === 0 ? 'D-day' : 'D-' + n) : 'D+' + -n
}
export const mmdd = (iso: string | null) => {
  if (!iso) return ''
  const a = iso.slice(0, 10).split('-')
  return a[1] + '.' + a[2]
}

export const scoreOf = (r: RoundView, key: string) => r.items[key] ?? 0

export const doneRounds = (rs: RoundView[]) => rs.filter((r) => r.status === 'DONE' && r.totalScore != null)
export const isPending = (r: { status: string }) => r.status !== 'DONE' && r.status !== 'FAILED'

export function worstItem(r: RoundView): [string, string] {
  return ITEMS.reduce((a, b) => ((r.items[b[0]] ?? 0) < (r.items[a[0]] ?? 0) ? b : a))
}
export function gainItem(rs: RoundView[]) {
  const d = doneRounds(rs)
  if (d.length < 2) return null
  const a = d[0]
  const b = d[d.length - 1]
  return ITEMS.map(([k, l]) => ({ k, l, d: (b.items[k] ?? 0) - (a.items[k] ?? 0) })).sort((x, y) => y.d - x.d)[0]
}
export function pstat(rs: RoundView[]) {
  const d = doneRounds(rs)
  if (!d.length) return { cnt: 0 as const }
  const last = d[d.length - 1]
  const first = d[0]
  const prev = d[d.length - 2]
  const lt = last.totalScore as number
  const up = d.length > 1 && lt - (first.totalScore as number) >= 5
  return {
    cnt: d.length,
    last,
    first,
    prev,
    up,
    delta: d.length > 1 ? (up ? lt - (first.totalScore as number) : lt - (prev.totalScore as number)) : null,
  }
}

export const newKey = () => globalThis.crypto?.randomUUID?.() ?? String(Date.now()) + Math.random().toString(16).slice(2)
