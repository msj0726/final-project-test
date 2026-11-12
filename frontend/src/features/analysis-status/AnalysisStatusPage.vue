<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, projects, rounds } from '@/shared/api'
import type { ProjectDetail, RoundStatusInfo } from '@/shared/api/types'
import { fmt } from '@/shared/lib/format'
import { IC } from '@/shared/lib/icons'
import { useUi } from '@/shared/state/ui'
import LineChart from '@/shared/ui/LineChart.vue'

const route = useRoute()
const router = useRouter()
const ui = useUi()
const pid = String(route.query.p ?? '')
const n = Number(route.query.n)

const detail = ref<ProjectDetail | null>(null)
const info = ref<RoundStatusInfo | null>(null)
const err = ref('')
const retrying = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined
let dead = false

async function poll() {
  try {
    const s = await rounds.status(pid, n)
    info.value = s
    if (s.status === 'DONE') return router.replace(`/report/${pid}/${n}`)
    if (s.status === 'FAILED') return
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return router.replace('/me')
    err.value = e instanceof ApiError ? e.message : ''
  }
  if (!dead) timer = setTimeout(poll, 1500)
}
async function retry() {
  retrying.value = true
  try {
    await rounds.retry(pid, n)
    info.value = null
    poll()
  } catch (e) {
    ui.toast(e instanceof ApiError ? e.message : '다시 시도하지 못했어요.')
  } finally {
    retrying.value = false
  }
}

onMounted(async () => {
  try {
    detail.value = await projects.get(pid)
  } catch {
    return router.replace('/me')
  }
  poll()
})
onBeforeUnmount(() => {
  dead = true
  clearTimeout(timer)
})

const round = computed(() => detail.value?.rounds.find((r) => r.roundNo === n))
const pts = computed(() => (detail.value?.rounds ?? []).filter((r) => r.status === 'DONE' && r.totalScore != null).map((r) => ({ v: r.totalScore as number, l: r.roundNo + '회' })))
const failed = computed(() => info.value?.status === 'FAILED')
const idx = computed(() => ({ QUEUED: 0, EXTRACTING: 1, ANALYZING: 2, SCORING: 3, DONE: 4, FAILED: 2 })[info.value?.status ?? 'QUEUED'])
const stepsDef = computed(() => [
  ['영상 저장', `${round.value?.durationSec ? fmt(round.value.durationSec) + ' · ' : ''}프로젝트 ‘${detail.value?.project.name ?? ''}’에 연결`],
  ['음성 분석', '발화 속도 · 쉼 · 음성 인식(전사)'],
  ['표정 · 시선 · 제스처 분석', '자세와 얼굴 방향을 시간축으로 정렬'],
  ['리포트 정리', '항목별 점수와 코칭 문장 만들기'],
])
function stepCls(i: number) {
  if (failed.value) return i < 2 ? 'done' : i === 2 ? 'now' : 'wait'
  // QUEUED/EXTRACTING → 1단계(영상 저장) 완료 후 음성 분석 시작 …
  const cur = idx.value === 0 ? 0 : idx.value
  return i < cur ? 'done' : i === cur ? 'now' : 'wait'
}
</script>

<template>
  <div class="wrap">
    <div v-if="!detail" class="loading"><span class="spin" /> 불러오는 중…</div>
    <div v-else class="row" style="align-items: flex-start; gap: 24px">
      <div class="card" style="flex: 1 1 440px; padding: 30px; min-width: 0">
        <span class="pill">업로드 영상 분석</span>
        <h1 style="margin-top: 12px; font-size: 32px; line-height: 1.3; color: var(--pri-d); font-weight: 800">
          {{ failed ? '분석하지 못했어요' : `${n}회차 영상을 분석하고 있어요` }}
        </h1>
        <p class="sub" style="margin-top: 6px">{{ failed ? '일시적인 문제일 수 있어요. 다시 시도하면 처음부터 다시 분석해요.' : '영상은 안전하게 저장됐어요. 길이에 따라 몇 분 걸릴 수 있어요.' }}</p>
        <div v-if="!failed" class="stay"><b>화면을 나가도 분석은 계속돼요.</b> 내 발표 목록에서 ‘분석 중’으로 보이고, 끝나면 바로 리포트를 열 수 있어요.</div>
        <div v-else class="warn" style="margin-top: 14px"><b>실패 코드</b> · {{ info?.failure?.code }}<span v-if="info?.failure && !info.failure.retryable"> (다시 시도해도 같은 결과일 수 있어요)</span></div>

        <div class="prog" style="margin-top: 22px" role="progressbar" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="info?.progress ?? 0"><i :style="{ width: (info?.progress ?? 0) + '%' }" /></div>
        <div style="margin-top: 6px; font-weight: 700; color: var(--ok); font-size: 14px">
          {{ info?.progress ?? 0 }}%<template v-if="!failed && info?.etaSec"> · 약 {{ Math.max(1, Math.ceil(info.etaSec / 60)) }}분 이내</template>
        </div>
        <ul class="stepl">
          <li v-for="(s, i) in stepsDef" :key="i" :class="stepCls(i)">
            <span class="dot" v-html="stepCls(i) === 'done' ? IC.check : ''" />
            <div><b>{{ s[0] }}</b><small>{{ s[1] }}</small></div>
          </li>
        </ul>
        <div style="margin-top: 26px; display: flex; gap: 10px; flex-wrap: wrap">
          <button v-if="failed" class="btn btn-p" :disabled="retrying" @click="retry">{{ retrying ? '접수 중…' : '다시 분석하기' }}</button>
          <button class="btn" @click="router.push('/me')">{{ failed ? '목록으로' : '나가서 기다리기' }}</button>
        </div>
      </div>

      <div style="flex: 1 1 380px; min-width: 0">
        <h2 style="font-size: 18px; font-weight: 800; color: var(--pri-d); margin: 6px 0 12px">분석이 끝나면 여기에 들어가요</h2>
        <div class="card" style="padding: 20px">
          <div style="display: flex; justify-content: space-between; align-items: center"><h3>① {{ n }}회차 분석 리포트</h3><span class="pill">업로드 분석</span></div>
          <div style="display: flex; gap: 14px; margin-top: 14px; align-items: center">
            <div style="flex: none; width: 96px; height: 64px; border-radius: 10px; background: #0f172a" />
            <p style="font-size: 14px; color: #334155">저장한 영상으로 구간별 피드백과 종합 점수를 받아요.</p>
          </div>
        </div>
        <div class="card" style="padding: 20px; margin-top: 14px">
          <div style="display: flex; justify-content: space-between"><h3>② 이력 · 추이</h3><span style="font-size: 13px; color: var(--mute)">{{ detail.project.name }}</span></div>
          <div v-if="pts.length" style="margin-top: 8px"><LineChart :pts="pts" :w="560" :h="200" pending /></div>
          <p v-else class="hint" style="margin-top: 12px">첫 회차예요. 분석이 끝나면 첫 점수가 여기에 표시돼요.</p>
        </div>
      </div>
    </div>
  </div>
</template>
