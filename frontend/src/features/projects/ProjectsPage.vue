<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { projects } from '@/shared/api'
import { loadOverviews, type ProjectOverview } from './projectOverview'
import { ITEMS } from '@/shared/lib/rubric'
import { dday, doneRounds, gainItem, isPending, mmdd, pstat, scoreOf, worstItem } from '@/shared/lib/format'
import { IC } from '@/shared/lib/icons'
import { useLoad } from '@/shared/composables/useLoad'
import { useUi } from '@/shared/state/ui'
import MyPageShell from '@/shared/ui/MyPageShell.vue'
import EmptyState from '@/shared/ui/EmptyState.vue'
import SparkChart from '@/shared/ui/SparkChart.vue'
import ScoreBar from '@/shared/ui/ScoreBar.vue'

const router = useRouter()
const ui = useUi()
const { data, loading, error, reload } = useLoad(() => loadOverviews())
const tab = ref<'all' | 'ing' | 'done'>('all')
const menuFor = ref<string | null>(null)

const all = computed(() => data.value ?? [])
const ing = computed(() => all.value.filter((p) => !p.done))
const dn = computed(() => all.value.filter((p) => p.done))
const list = computed(() => (tab.value === 'ing' ? ing.value : tab.value === 'done' ? dn.value : all.value))

const view = (p: ProjectOverview) => {
  const st = pstat(p.rounds)
  const pts = doneRounds(p.rounds).map((r) => ({ v: r.totalScore as number, l: r.roundNo + '회' }))
  const pend = p.rounds.find(isPending)
  const g = gainItem(p.rounds)
  const w = st.cnt ? worstItem(st.last as NonNullable<typeof st.last>) : null
  return { st, pts, pend, g, w }
}

async function toggleDone(p: ProjectOverview) {
  menuFor.value = null
  await projects.update(p.id, { done: !p.done })
  ui.toast(p.done ? '진행 중으로 되돌렸어요' : '발표 완료로 표시했어요')
  reload()
}
async function remove(p: ProjectOverview) {
  menuFor.value = null
  const r = await ui.confirm({ title: `‘${p.name}’을(를) 삭제할까요?`, body: '프로젝트와 모든 회차의 영상·리포트가 삭제돼요. 되돌릴 수 없어요.', okLabel: '삭제', danger: true })
  if (!r.ok) return
  await projects.remove(p.id)
  ui.toast('프로젝트를 삭제했어요')
  reload()
}
</script>

<template>
  <MyPageShell>
    <div style="display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: flex-end">
      <div>
        <h1 class="h1">내 발표 프로젝트</h1>
        <p class="sub">발표마다 추이와 개선 상태를 따로 모아 보여드려요.</p>
      </div>
      <button class="btn btn-p" @click="router.push('/new')">+ 새 프로젝트</button>
    </div>

    <div v-if="loading" class="loading"><span class="spin" /> 불러오는 중…</div>
    <div v-else-if="error" class="card" style="margin-top: 18px">
      <p class="err" role="alert">{{ error }}</p>
      <button class="btn" style="margin-top: 10px" @click="reload">다시 시도</button>
    </div>
    <template v-else>
      <div v-if="all.length" class="tabs" role="tablist" style="margin-top: 18px">
        <button role="tab" :aria-selected="tab === 'all'" @click="tab = 'all'">전체 {{ all.length }}</button>
        <button role="tab" :aria-selected="tab === 'ing'" @click="tab = 'ing'">진행 중 {{ ing.length }}</button>
        <button role="tab" :aria-selected="tab === 'done'" @click="tab = 'done'">발표 끝남 {{ dn.length }}</button>
      </div>

      <EmptyState v-if="!all.length" :icon="IC.folder" title="아직 발표 프로젝트가 없어요" desc="발표 하나를 프로젝트로 만들면, 연습할 때마다 점수와 추이가 한곳에 쌓여요.">
        <button class="btn btn-p btn-l" @click="router.push('/new')">첫 프로젝트 만들기</button>
      </EmptyState>
      <EmptyState v-else-if="!list.length" :icon="IC.folder" :title="tab === 'done' ? '끝난 발표가 아직 없어요' : '진행 중인 발표가 없어요'"
        :desc="tab === 'done' ? '프로젝트 ⋯ 메뉴에서 “발표 완료로 표시”를 누르면 여기로 옮겨져요.' : '새 프로젝트를 만들어 연습을 시작해 보세요.'">
        <button class="btn btn-p" @click="router.push('/new')">새 프로젝트 만들기</button>
      </EmptyState>

      <div v-else class="pcards">
        <article v-for="p in list" :key="p.id" class="card pc" :style="p.done ? 'opacity:.85' : ''">
          <div class="top">
            <div>
              <div class="nm">{{ p.name }}</div>
              <div class="tp">{{ p.topic }}</div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center">
              <span v-if="view(p).pend" class="pill pill-a">분석 중</span>
              <span class="pill pill-d">{{ p.done ? '발표 끝남' : p.finalDate ? dday(p.finalDate) + ' · ' + mmdd(p.finalDate) : '일정 없음' }}</span>
              <div class="rel">
                <button class="btn btn-g btn-s" :aria-label="`${p.name} 관리`" @click="menuFor = menuFor === p.id ? null : p.id">⋯</button>
                <div v-if="menuFor === p.id" class="menu" role="menu">
                  <button role="menuitem" @click="toggleDone(p)">{{ p.done ? '진행 중으로 되돌리기' : '발표 완료로 표시' }}</button>
                  <hr />
                  <button role="menuitem" style="color: #b91c1c" @click="remove(p)">프로젝트 삭제</button>
                </div>
              </div>
            </div>
          </div>

          <template v-if="!view(p).st.cnt">
            <div class="note">{{ view(p).pend ? '분석 중인 회차가 있어요. 화면을 나가도 분석은 계속돼요.' : '아직 연습 기록이 없어요. 첫 회차를 연습하면 점수와 추이가 여기에 쌓여요.' }}</div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: auto">
              <button class="btn btn-p" @click="router.push(`/new?p=${p.id}`)">{{ view(p).pend ? '새 회차 연습하기' : '첫 회차 연습하기' }}</button>
              <button v-if="view(p).pend" class="btn" @click="router.push(`/analysis?p=${p.id}&n=${view(p).pend!.roundNo}`)">분석 상태 보기</button>
            </div>
          </template>

          <template v-else>
            <template v-for="(v, i) in [view(p)]" :key="i">
              <div class="stat">
                <span class="tag">{{ v.st.cnt }}회차</span><span class="tag">영상 평가 {{ v.st.cnt }}</span>
              </div>
              <div class="stat">
                <template v-if="v.st.cnt! > 1">
                  <span :class="v.st.up ? 'st-up' : 'st-flat'">{{ v.st.up ? '개선 중' : '정체' }}</span>
                  <span>{{ v.st.up ? '첫 회차 대비' : '직전 회차 대비' }} {{ (v.st.delta ?? 0) >= 0 ? '+' : '' }}{{ v.st.delta }}점</span>
                </template>
                <template v-else>
                  <span class="st-up">첫 회차 완료</span><span>종합 {{ v.st.last!.totalScore }}점</span>
                </template>
              </div>
              <div><SparkChart :pts="v.pts" :color="v.st.up || v.st.cnt === 1 ? 'var(--pri)' : '#B45309'" /></div>
              <div class="mini"><ScoreBar v-for="it in ITEMS" :key="it[0]" :label="it[1]" :value="scoreOf(v.st.last!, it[0])" /></div>
              <div v-if="v.st.up && v.g" class="note">
                가장 많이 나아진 항목은 <b>{{ v.g.l }}({{ v.g.d >= 0 ? '+' : '' }}{{ v.g.d }})</b>예요. <b>{{ v.w![1] }}({{ scoreOf(v.st.last!, v.w![0]) }}점)</b>이 아직 남았어요.
              </div>
              <div v-else class="warn">
                <template v-if="v.st.cnt! > 1">점수가 제자리예요. </template><b>{{ v.w![1] }}({{ scoreOf(v.st.last!, v.w![0]) }}점)</b>를 먼저 고쳐 보세요.
              </div>
              <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: auto">
                <button class="btn btn-p" @click="router.push(`/new?p=${p.id}`)">새 회차 연습하기</button>
                <button class="btn" @click="router.push(`/report/${p.id}/${v.st.last!.roundNo}`)">최근 리포트</button>
                <button class="btn" @click="router.push(`/me/history?p=${p.id}`)">이력 · 추이 보기</button>
              </div>
            </template>
          </template>
        </article>
      </div>

      <div v-if="all.length" class="note" style="margin-top: 20px"><b>같은 프로젝트 안에서만 비교해요.</b> 서로 다른 발표의 점수는 섞이지 않아요.</div>
    </template>
  </MyPageShell>
</template>
