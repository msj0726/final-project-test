import { projects, rounds } from '@/shared/api'
import type { Project, RoundSummary } from '@/shared/api/types'
import type { RoundView } from '@/shared/lib/format'

/** 프로젝트 + 회차(DONE 회차는 항목별 점수 포함). 화면의 카드·이력이 함께 쓴다. */
export interface ProjectOverview extends Project {
  rounds: RoundView[]
}

/**
 * 회차 목록(상태·총점)에 DONE 회차의 항목별 점수를 리포트에서 붙인다.
 * [가정] 사용자 API 에 "프로젝트 카드/회차별 항목 점수" 요약이 없어 리포트를 읽어 만든다. 요약 필드가 생기면 이 함수만 바꾼다.
 */
export async function toRoundViews(pid: string, rs: RoundSummary[]): Promise<RoundView[]> {
  return Promise.all(
    rs.map(async (r): Promise<RoundView> => {
      if (r.status !== 'DONE') return { ...r, items: {} }
      const rep = await rounds.cachedReport(pid, r.roundNo)
      return { ...r, items: Object.fromEntries(rep.scores.map((s) => [s.itemKey, s.score])) }
    }),
  )
}

export async function loadOverviews(status?: 'ONGOING' | 'DONE'): Promise<ProjectOverview[]> {
  const ps = await projects.listAll(status)
  return Promise.all(ps.map(async (p) => ({ ...p, rounds: await toRoundViews(p.id, await rounds.list(p.id)) })))
}
