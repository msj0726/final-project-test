<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, projects } from '@/shared/api'
import { loadOverviews } from './projectOverview'
import { dday, doneRounds, mmdd } from '@/shared/lib/format'
import { IC } from '@/shared/lib/icons'
import { useLoad } from '@/shared/composables/useLoad'
import EmptyState from '@/shared/ui/EmptyState.vue'
import SparkChart from '@/shared/ui/SparkChart.vue'

const route = useRoute()
const router = useRouter()
const { data, loading } = useLoad(() => loadOverviews('ONGOING'))
const list = computed(() => data.value ?? [])

const qp = typeof route.query.p === 'string' ? route.query.p : ''
const chosen = ref(!!(route.query.mode || qp))
const tab = ref<'new' | 'old'>(qp ? 'old' : 'new')
const pid = ref(qp)
const sel = computed(() => list.value.find((p) => p.id === pid.value) ?? list.value[0])

const v = reactive({ name: '', topic: '', finalDate: '', target: '30' })
const err = ref<Record<string, string>>({})
const busy = ref(false)

const stepper = computed(() => {
  const n = chosen.value ? 2 : 1
  return ['연습 방식', '저장할 곳', '발표 정보'].map((t, i) => ({ t, i: i + 1, cls: i + 1 === n ? 'on' : i + 1 < n ? 'done' : '' }))
})

async function create() {
  const e: Record<string, string> = {}
  if (!v.name.trim()) e.name = '발표 제목을 입력해 주세요.'
  if (!v.topic.trim()) e.topic = '발표 주제를 입력해 주세요.'
  err.value = e
  if (Object.keys(e).length) return
  busy.value = true
  try {
    const p = await projects.create({ name: v.name.trim(), topic: v.topic.trim(), finalDate: v.finalDate || undefined, targetMinutes: Number(v.target) })
    router.push(`/upload?p=${p.id}`)
  } catch (x) {
    if (x instanceof ApiError && x.fields) err.value = { name: x.fields.name, topic: x.fields.topic } as Record<string, string>
    else err.value = { name: x instanceof ApiError ? x.message : '프로젝트를 만들지 못했어요.' }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="wrap" :style="chosen ? '' : 'max-width:860px'">
    <div v-if="loading" class="loading"><span class="spin" /> 불러오는 중…</div>

    <!-- 1단계: 연습 방식 -->
    <template v-else-if="!chosen">
      <div class="crumb">새 연습</div>
      <h1 class="h1" style="margin-top: 6px">무엇을 연습할까요?</h1>
      <p class="sub">먼저 연습 방식을 고르세요. 다음 단계에서 저장할 프로젝트를 정해요.</p>
      <ol class="steps3" aria-label="진행 단계">
        <li v-for="s in stepper" :key="s.i" :class="s.cls" :aria-current="s.cls === 'on' ? 'step' : undefined"><i>{{ s.i }}</i>{{ s.t }}</li>
      </ol>
      <div class="row" style="margin-top: 22px; gap: 16px; align-items: stretch">
        <div style="flex: 1 1 320px">
          <button type="button" class="pickc" @click="chosen = true">
            <b>발표 평가 · 영상 올리기</b>
            <span>녹화한 발표 영상을 올리면 음성과 영상을 분석한 리포트를 받아요. 영상은 MP4·MOV, 최대 30분(500MB)까지 올릴 수 있어요.</span>
            <em>분석이 끝나면 바로 리포트를 열 수 있어요</em>
          </button>
        </div>
        <div style="flex: 1 1 320px">
          <button type="button" class="pickc" disabled aria-disabled="true">
            <b>질의응답 연습 (실시간) <span class="pill pill-g">준비 중</span></b>
            <span>분석한 발표 영상을 바탕으로 심사위원이 질문하는 실시간 질의응답은 다음 단계에서 제공돼요.</span>
            <em>곧 만나요</em>
          </button>
        </div>
      </div>
    </template>

    <!-- 2단계: 저장할 곳 / 발표 정보 -->
    <template v-else>
      <div class="crumb">새 연습 › <b>{{ tab === 'new' ? '프로젝트 만들기' : '기존 프로젝트에 회차 추가' }}</b></div>
      <h1 class="h1" style="margin-top: 6px">{{ tab === 'new' ? '어떤 발표를 준비하나요?' : '어떤 발표를 이어서 연습할까요?' }}</h1>
      <ol class="steps3" aria-label="진행 단계">
        <li v-for="s in stepper" :key="s.i" :class="s.cls" :aria-current="s.cls === 'on' ? 'step' : undefined"><i>{{ s.i }}</i>{{ s.t }}</li>
      </ol>
      <p class="sub" style="margin-top: 12px">
        {{ tab === 'new' ? '같은 발표를 반복 연습하면 회차별 점수와 추이가 이 프로젝트 안에 모여요. 발표가 다르면 프로젝트를 나눠 주세요.' : '고른 프로젝트의 다음 회차로 기록되고, 같은 추이 안에서 점수를 비교해요.' }}
      </p>

      <div class="row" style="margin-top: 24px; align-items: flex-start">
        <div class="card" style="flex: 2 1 560px; min-width: 0; padding: 28px">
          <div class="tabs" role="tablist" aria-label="어디에 저장할까요?">
            <button role="tab" :aria-selected="tab === 'new'" @click="tab = 'new'">새 프로젝트 만들기</button>
            <button role="tab" :aria-selected="tab === 'old'" @click="tab = 'old'">기존 프로젝트에 회차 추가</button>
          </div>

          <form v-if="tab === 'new'" style="display: flex; flex-direction: column; gap: 20px; margin-top: 22px" novalidate @submit.prevent="create">
            <div>
              <label class="f" for="title">발표 제목 <em>*</em></label>
              <input id="title" v-model="v.name" class="in" :class="{ bad: err.name }" placeholder="예: 최종발표 리허설" />
              <div v-if="err.name" class="err" role="alert">{{ err.name }}</div>
              <div v-else class="hint">프로젝트 목록과 이력에 이 이름으로 표시돼요.</div>
            </div>
            <div>
              <label class="f" for="topic">발표 주제 <em>*</em></label>
              <input id="topic" v-model="v.topic" class="in" :class="{ bad: err.topic }" placeholder="한 줄로 적어 주세요" />
              <div v-if="err.topic" class="err" role="alert">{{ err.topic }}</div>
              <div v-else class="hint">무엇에 대한 발표인지 한 줄 적어 주세요.</div>
            </div>
            <div class="row" style="gap: 20px">
              <div style="flex: 1 1 220px">
                <label class="f" for="date">최종 발표일</label>
                <input id="date" v-model="v.finalDate" class="in" type="date" />
                <div class="hint">남은 날짜를 프로젝트 카드에 보여드려요. (선택)</div>
              </div>
              <div style="flex: 1 1 220px">
                <label class="f" for="target">목표 발표 시간</label>
                <select id="target" v-model="v.target" class="in">
                  <option value="0">제한 없음</option><option value="10">10분</option><option value="20">20분</option><option value="30">30분 (최대)</option>
                </select>
                <div class="hint">딱 맞출 필요는 없어요. 목표 시간을 넘겨도 자동으로 끝나지 않아요.</div>
              </div>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 10px; flex-wrap: wrap">
              <button type="button" class="btn btn-g" @click="router.push('/me')">취소</button>
              <button class="btn btn-p btn-l" type="submit" style="min-height: 50px; font-size: 16px" :disabled="busy">{{ busy ? '만드는 중…' : '프로젝트 만들고 영상 올리기' }}</button>
            </div>
          </form>

          <template v-else>
            <EmptyState v-if="!list.length" :icon="IC.folder" title="이어서 연습할 프로젝트가 아직 없어요" desc="먼저 새 프로젝트를 만들면 다음부터 여기서 회차를 추가할 수 있어요.">
              <button class="btn btn-p" @click="tab = 'new'">새 프로젝트 만들기</button>
            </EmptyState>
            <div v-else style="margin-top: 22px">
              <div class="f" style="font-weight: 800; color: var(--pri-d)">프로젝트 고르기</div>
              <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 10px" role="radiogroup">
                <button v-for="p in list" :key="p.id" type="button" class="opt" role="radio" :aria-checked="p.id === sel?.id" @click="pid = p.id">
                  <span class="rd" />
                  <div style="flex: 1">
                    <b>{{ p.name }}</b>
                    <span>{{ p.topic }} · {{ doneRounds(p.rounds).length }}회 연습</span>
                  </div>
                  <div style="text-align: right">
                    <b v-if="doneRounds(p.rounds).length" style="font-size: 24px">{{ doneRounds(p.rounds).at(-1)!.totalScore }}</b>
                    <b v-else style="font-size: 16px; color: var(--mute)">—</b>
                    <span v-if="p.finalDate" style="font-size: 12px">{{ dday(p.finalDate) }} · {{ mmdd(p.finalDate) }}</span>
                  </div>
                </button>
              </div>
              <div class="hint" style="margin-top: 10px; display: flex; justify-content: space-between; gap: 8px; padding: 12px 16px; border: 1.5px dashed var(--line); border-radius: 14px; align-items: center">
                <span>찾는 발표가 없나요?</span><button class="link" @click="tab = 'new'">+ 새 프로젝트 만들기</button>
              </div>
              <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 22px; flex-wrap: wrap">
                <button class="btn btn-g" @click="router.push('/me')">취소</button>
                <button class="btn btn-p btn-l" style="min-height: 50px; font-size: 16px" @click="router.push(`/upload?p=${sel!.id}`)">
                  {{ (sel?.rounds.length ?? 0) + 1 }}회차 영상 올리기
                </button>
              </div>
            </div>
          </template>
        </div>

        <div v-if="tab === 'new' || sel" style="flex: 1 1 300px; display: flex; flex-direction: column; gap: 16px; min-width: 0">
          <template v-if="tab === 'new'">
            <div class="card">
              <h2>프로젝트로 묶으면</h2>
              <ul style="margin-top: 12px; display: flex; flex-direction: column; gap: 10px; font-size: 15px">
                <li style="display: flex; gap: 10px"><span class="av" style="flex: none; width: 24px; height: 24px; font-size: 12px">1</span><span>발표마다 <b>점수 추이와 개선 상태</b>를 따로 봐요.</span></li>
                <li style="display: flex; gap: 10px"><span class="av" style="flex: none; width: 24px; height: 24px; font-size: 12px">2</span><span>회차마다 <b>리포트와 영상</b>이 한 프로젝트에 쌓여요.</span></li>
                <li style="display: flex; gap: 10px"><span class="av" style="flex: none; width: 24px; height: 24px; font-size: 12px">3</span><span>최종 발표일까지 <b>D-day</b>와 남은 연습을 확인해요.</span></li>
              </ul>
            </div>
            <div class="note">
              <b>이렇게 나뉘어요</b>
              <div v-for="p in list" :key="p.id" style="display: flex; justify-content: space-between; background: #fff; border-radius: 10px; padding: 10px 14px; margin-top: 8px"><b>{{ p.name }}</b><span>{{ p.rounds.length }}회차</span></div>
              <div v-if="!list.length" style="background: #fff; border-radius: 10px; padding: 10px 14px; margin-top: 8px; color: var(--mute)">아직 프로젝트가 없어요.</div>
              <div style="margin-top: 8px; font-size: 13px">서로 다른 발표의 점수는 섞이지 않아요.</div>
            </div>
          </template>
          <template v-else-if="sel">
            <div class="card">
              <h2>{{ sel.name }} · 지금까지</h2>
              <div v-if="doneRounds(sel.rounds).length" style="margin-top: 8px"><SparkChart :pts="doneRounds(sel.rounds).map((r) => ({ v: r.totalScore!, l: r.roundNo + '회' }))" /></div>
              <p v-else class="hint" style="margin-top: 10px">아직 점수가 없어요. 첫 회차가 기준이 돼요.</p>
            </div>
            <div class="note"><b>목표 {{ sel.targetMinutes ? sel.targetMinutes + '분' : '시간 제한 없음' }}</b><br /><span style="font-size: 13px">영상은 최대 30분, 500MB까지 올릴 수 있어요.</span></div>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>
