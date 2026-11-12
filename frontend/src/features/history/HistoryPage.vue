<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { loadOverviews } from '@/features/projects/projectOverview'
import { ITEMS, itemLabel } from '@/shared/lib/rubric'
import { doneRounds, isPending, pstat, scoreOf, worstItem } from '@/shared/lib/format'
import { IC } from '@/shared/lib/icons'
import { useLoad } from '@/shared/composables/useLoad'
import MyPageShell from '@/shared/ui/MyPageShell.vue'
import EmptyState from '@/shared/ui/EmptyState.vue'
import LineChart from '@/shared/ui/LineChart.vue'

const route = useRoute()
const router = useRouter()
const { data, loading, error, reload } = useLoad(() => loadOverviews())
const item = ref('total')
const pid = ref('')

const list = computed(() => data.value ?? [])
watch([list, () => route.query.p], () => {
  const q = typeof route.query.p === 'string' ? route.query.p : ''
  pid.value = list.value.find((p) => p.id === q)?.id ?? list.value.find((p) => p.id === pid.value)?.id ?? list.value[0]?.id ?? ''
}, { immediate: true })

const proj = computed(() => list.value.find((p) => p.id === pid.value))
const rs = computed(() => proj.value?.rounds ?? [])
const done = computed(() => doneRounds(rs.value))
const st = computed(() => pstat(rs.value))
const lab = computed(() => (item.value === 'total' ? '종합' : itemLabel(item.value)))
const val = (r: (typeof rs.value)[number], k: string) => (k === 'total' ? (r.totalScore as number) : scoreOf(r, k))
const pts = computed(() => done.value.map((r) => ({ v: val(r, item.value), l: r.roundNo + '회차' })))
const worst = computed(() => (st.value.cnt ? worstItem(st.value.last!) : null))
const ranked = computed(() => {
  if (!st.value.prev) return null
  const last = st.value.last!
  const prev = st.value.prev
  return ITEMS.map(([k, l]) => ({ k, l, a: scoreOf(prev, k), b: scoreOf(last, k), d: scoreOf(last, k) - scoreOf(prev, k) }))
})
const bestDelta = computed(() => (ranked.value ? [...ranked.value].sort((x, y) => y.d - x.d) : []))

const comment = computed(() => {
  if (!done.value.length) return null
  const f = done.value[0]
  const l = done.value[done.value.length - 1]
  if (done.value.length < 2) return { p: `첫 회차 ${lab.value} 점수는 ${val(l, item.value)}점이에요. 두 번째 연습부터 변화가 그래프에 이어서 그려져요.`, next: '' }
  const d = val(l, item.value) - val(f, item.value)
  const ds = ITEMS.map(([k, n]) => ({ n, d: scoreOf(l, k) - scoreOf(f, k), v: scoreOf(l, k) })).sort((a, b) => b.d - a.d)
  const low = [...ds].sort((a, b) => a.v - b.v)[0]
  return {
    p: `${done.value.length}번 연습하는 동안 ${lab.value} 점수는 ${val(f, item.value)}점에서 ${val(l, item.value)}점으로 ${d >= 0 ? '+' : ''}${d}점 ${d >= 0 ? '올랐어요' : '내려갔어요'}. 항목 중에는 처음 대비 ${ds[0].n}이 ${ds[0].d >= 0 ? '+' : ''}${ds[0].d}점으로 가장 많이 올랐고, 지금 점수가 가장 낮은 항목은 ${low.n}(${low.v}점)이에요.`,
    next: `다음 연습에서는 ${low.n}에 집중해 보세요.`,
  }
})
const prevOf = (i: number) => done.value[i - 1]
</script>

<template>
  <MyPageShell>
    <div v-if="loading" class="loading"><span class="spin" /> 불러오는 중…</div>
    <div v-else-if="error" class="card"><p class="err" role="alert">{{ error }}</p><button class="btn" style="margin-top: 10px" @click="reload">다시 시도</button></div>

    <template v-else-if="!list.length">
      <h1 class="h1">이력 · 추이</h1>
      <EmptyState :icon="IC.chart" title="아직 쌓인 이력이 없어요" desc="첫 연습을 마치면 회차별 점수와 나아진 항목이 여기에 그려져요.">
        <button class="btn btn-p btn-l" @click="router.push('/new')">첫 연습 시작하기</button>
      </EmptyState>
    </template>

    <template v-else-if="proj">
      <div style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: flex-end">
        <div><h1 class="h1">{{ proj.name }} · 이력</h1><p class="sub">같은 발표를 반복한 기록이에요.</p></div>
        <button class="btn btn-p" @click="router.push(`/new?p=${proj.id}`)">새 회차 연습하기</button>
      </div>
      <div v-if="list.length > 1" class="tabs" role="tablist" style="margin-top: 16px">
        <button v-for="p in list" :key="p.id" role="tab" :aria-selected="p.id === pid" @click="pid = p.id">{{ p.name }}</button>
      </div>

      <EmptyState v-if="!done.length" :icon="IC.chart" title="이 프로젝트의 연습 기록이 아직 없어요" desc="첫 회차를 연습하면 점수 변화가 그려져요.">
        <button class="btn btn-p btn-l" @click="router.push(`/new?p=${proj.id}`)">첫 회차 연습하기</button>
      </EmptyState>

      <template v-else>
        <div class="row" style="margin-top: 20px">
          <div class="card" style="flex: 2 1 520px; min-width: 0">
            <div style="display: flex; flex-wrap: wrap; gap: 10px; justify-content: space-between; align-items: center">
              <h2>회차별 {{ lab }} 점수</h2>
              <div style="display: flex; gap: 6px; flex-wrap: wrap">
                <button v-for="c in [['total', '종합'], ...ITEMS]" :key="c[0]" class="btn btn-s" :class="{ 'btn-p': item === c[0] }" style="border-radius: 999px" :aria-pressed="item === c[0]" @click="item = c[0]">{{ c[1] }}</button>
              </div>
            </div>
            <div style="margin-top: 10px"><LineChart :pts="pts" :pending="rs.some(isPending)" :label="lab + ' 점수 추이'" /></div>
            <div v-if="comment" class="tcm"><h3>종합 코멘트</h3><p>{{ comment.p }}</p><p v-if="comment.next" class="tnx">{{ comment.next }}</p></div>
          </div>

          <div style="flex: 1 1 260px; display: flex; flex-direction: column; gap: 14px">
            <div class="score-big" style="flex: none">
              <div style="font-size: 14px; color: var(--line); font-weight: 600">{{ done.length > 1 ? '종합 점수 변화' : '지금까지' }}</div>
              <div style="font-size: 34px; line-height: 1.25; font-weight: 800">{{ done.length > 1 ? `${st.first!.totalScore}점 → ${st.last!.totalScore}점` : `${st.last!.totalScore}점` }}</div>
              <div v-if="done.length > 1" style="font-size: 44px; line-height: 1.2; font-weight: 800">{{ st.last!.totalScore! - st.first!.totalScore! >= 0 ? '+' : '' }}{{ st.last!.totalScore! - st.first!.totalScore! }}</div>
              <div style="font-size: 14px; color: var(--soft)">{{ done.length > 1 ? `${done.length}번 연습하는 동안 ${st.last!.totalScore! >= st.first!.totalScore! ? '올랐어요' : '내려갔어요'}` : '첫 회차를 마쳤어요' }}</div>
            </div>
            <div class="card" style="padding: 18px">
              <h3>{{ st.prev ? '지난 회차 대비' : '지난 회차 대비' }}</h3>
              <template v-if="ranked">
                <div class="chgl">
                  <div v-for="r in ranked" :key="r.k"><span>{{ r.l }}</span><b class="dlt" :class="r.d >= 0 ? 'up' : 'dn'" style="font-size: 15px">{{ r.a }} → {{ r.b }} ({{ r.d >= 0 ? '+' : '' }}{{ r.d }})</b></div>
                </div>
                <div style="margin-top: 10px; font-size: 13.5px; color: #334155">
                  <template v-if="bestDelta[0].d > 0">가장 크게 나아진 부분은 <b>{{ bestDelta[0].l }}</b> (+{{ bestDelta[0].d }})예요.<template v-if="bestDelta[bestDelta.length - 1].d < 0"> <b>{{ bestDelta[bestDelta.length - 1].l }}</b>은 {{ bestDelta[bestDelta.length - 1].d }}이라 한 번 더 살펴보세요.</template></template>
                  <template v-else>이번에는 점수가 크게 오른 항목이 없어요.</template>
                </div>
              </template>
              <div v-else style="margin-top: 6px; font-size: 15px; color: var(--mute)">2회차부터 보여드려요</div>
            </div>
            <div v-if="worst" class="warn"><b style="font-size: 16px">아직 남은 항목</b><div style="margin-top: 6px; font-size: 22px; font-weight: 800">{{ worst[1] }} <span style="font-size: 15px">{{ scoreOf(st.last!, worst[0]) }}점</span></div></div>
          </div>
        </div>

        <div class="card" style="margin-top: 20px">
          <h2>회차 목록</h2>
          <div class="tw" style="margin-top: 12px">
            <table>
              <thead><tr><th>회차</th><th>날짜</th><th>종합</th><th v-for="x in ITEMS" :key="x[0]">{{ x[1] }}</th><th><span class="sr">리포트</span></th></tr></thead>
              <tbody>
                <tr v-for="r in [...rs].reverse()" :key="r.analysisId">
                  <td><b>{{ r.roundNo }}회차</b></td>
                  <td>{{ r.createdAt.slice(5, 10).replace('-', '.') }}</td>
                  <template v-if="isPending(r)">
                    <td colspan="5"><span class="pill pill-a">분석 중</span></td>
                    <td><button class="btn btn-s" @click="router.push(`/analysis?p=${proj.id}&n=${r.roundNo}`)">진행 보기</button></td>
                  </template>
                  <template v-else-if="r.status === 'FAILED'">
                    <td colspan="5"><span class="pill pill-a">분석 실패</span></td>
                    <td><button class="btn btn-s" @click="router.push(`/analysis?p=${proj.id}&n=${r.roundNo}`)">자세히</button></td>
                  </template>
                  <template v-else>
                    <td><b style="color: var(--pri-d)">{{ r.totalScore }}</b></td>
                    <td v-for="x in ITEMS" :key="x[0]">
                      {{ scoreOf(r, x[0]) }}
                      <span v-if="prevOf(done.indexOf(r))" class="dlt" :class="scoreOf(r, x[0]) - scoreOf(prevOf(done.indexOf(r)), x[0]) >= 0 ? 'up' : 'dn'">{{ scoreOf(r, x[0]) - scoreOf(prevOf(done.indexOf(r)), x[0]) >= 0 ? '▲' : '▼' }}{{ Math.abs(scoreOf(r, x[0]) - scoreOf(prevOf(done.indexOf(r)), x[0])) }}</span>
                    </td>
                    <td><button class="btn btn-s" :class="{ 'btn-p': r === st.last }" @click="router.push(`/report/${proj.id}/${r.roundNo}`)">리포트 보기</button></td>
                  </template>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </template>
  </MyPageShell>
</template>
