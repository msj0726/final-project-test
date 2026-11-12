<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, projects, rounds, videoSrc } from '@/shared/api'
import type { Project, Report, RoundSummary, Utterance } from '@/shared/api/types'
import { fmt, grade } from '@/shared/lib/format'
import { HOW_MEASURED, itemLabel } from '@/shared/lib/rubric'
import { SIGNAL, describeEvidence, rangesOf, type Range } from '@/shared/lib/signals'
import { IC } from '@/shared/lib/icons'
import { usePlayer } from '@/features/video-player/usePlayer'
import EvBtn from './EvidenceButton.vue'
import '@/features/video-player/player.css'
import TranscriptPanel from '@/features/transcript/TranscriptPanel.vue'

const route = useRoute()
const router = useRouter()
const pid = String(route.params.pid)
const n = Number(route.params.n)

const report = ref<Report | null>(null)
const project = ref<Project | null>(null)
const round = ref<RoundSummary | null>(null)
const utterances = ref<Utterance[] | null>(null)
const error = ref('')
const loading = ref(true)
const showTranscript = ref(false)
const lv = ref<'all' | 'fix' | 'obs' | 'ok'>('all')

// 영상 길이: 회차 목록의 durationSec(없으면 리포트 timeCheck.actualMinutes)
const D = computed(() => round.value?.durationSec ?? Math.round((report.value?.timeCheck.actualMinutes ?? 1 / 60) * 60))
const src = videoSrc(pid, n)
const videoEl = ref<HTMLVideoElement | null>(null)
const player = usePlayer(D, videoEl)
const { t, playing, speed } = player
const pc = (s: number) => ((s / D.value) * 100).toFixed(2) + '%'

onMounted(async () => {
  try {
    const [r, d] = await Promise.all([rounds.cachedReport(pid, n), projects.get(pid)])
    report.value = r
    project.value = d.project
    round.value = d.rounds.find((x) => x.roundNo === n) ?? null
    await nextTick()
    watchPlayer()
  } catch (e) {
    if (e instanceof ApiError && e.code === 'REPORT_NOT_READY') return router.replace(`/analysis?p=${pid}&n=${n}`)
    error.value = e instanceof ApiError && e.status === 404 ? '리포트를 찾을 수 없어요.' : '리포트를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.'
  } finally {
    loading.value = false
  }
})

// 전사문은 펼칠 때 불러옴 (분석 완료 후에만 공개)
watch(showTranscript, async (v) => {
  if (v && !utterances.value) {
    try {
      utterances.value = (await rounds.transcript(pid, n)).utterances
    } catch {
      utterances.value = []
    }
  }
})

// ----- 파생 데이터
const total = computed(() => report.value?.totalScore ?? 0)
const subs = computed(() =>
  (report.value?.scores ?? []).map((s) => ({ ...s, label: itemLabel(s.itemKey), note: s.evidence[0] ? describeEvidence(s.evidence[0]) : '' })),
)
// Report.timeline(신호 이름 → 구간 배열)을 화면 트랙별 목록으로 변환. 모르는 신호는 무시한다.
const tl = computed(() => {
  const t = report.value!.timeline
  const sec = (s: string) => (t[s] ?? []).map((e) => e.fromSec)
  return {
    fast: rangesOf(t, SIGNAL.fastSpeech),
    fillers: sec(SIGNAL.fillerWord),
    pauses: sec(SIGNAL.longPause),
    lowConfidence: rangesOf(t, SIGNAL.lowSttConfidence),
    handMotion: rangesOf(t, SIGNAL.handMotion),
    handMotionHigh: rangesOf(t, SIGNAL.handMotionHigh),
    gazeOff: rangesOf(t, SIGNAL.gazeOffFront),
    gazeOffShort: rangesOf(t, SIGNAL.gazeOffShort),
    noFace: rangesOf(t, SIGNAL.faceNotVisible),
    speechRate: { windowSec: 10, values: (t[SIGNAL.speechRateWindow] ?? []).map((e) => e.value ?? 0) },
  }
})
const LIMIT_TEXT: Record<string, [string, string, () => Range[]]> = {
  FACE_NOT_VISIBLE_EXCLUDED: ['영상 상태', '얼굴이 보이지 않은 구간은 시선·제스처 분석에서 제외했어요.', () => tl.value.noFace],
  LOW_STT_CONFIDENCE: ['음성 인식', '음성 인식이 어려웠던 구간은 말버릇·말 속도 측정이 부정확할 수 있어요.', () => tl.value.lowConfidence],
}
const limits = computed(() =>
  (report.value?.limitations ?? []).map((code) => {
    const m = LIMIT_TEXT[code]
    return { code, title: m?.[0] ?? '참고', message: m?.[1] ?? code, ranges: m?.[2]() ?? [] }
  }),
)
const SLICES = 5
const slices = computed(() =>
  Array.from({ length: SLICES }, (_, i) => {
    const a = Math.round((D.value * i) / SLICES)
    const b = Math.round((D.value * (i + 1)) / SLICES)
    const inR = (x: number) => x >= a && x < b
    const cnt = (rs: Range[]) => rs.filter(([x]) => inR(x)).length
    return {
      i, a, b,
      stats: [
        ['말버릇', tl.value.fillers.filter(inR).length + '회'],
        ['빠른 말', cnt(tl.value.fast) + '곳'],
        ['정면 이탈', cnt(tl.value.gazeOff) + '회'],
        ['손 움직임 많음', cnt(tl.value.handMotionHigh) + '곳'],
      ] as [string, string][],
      good: (report.value?.segments ?? []).filter((s) => s.kind === 'STRENGTH' && inR(s.fromSec)),
      fix: (report.value?.segments ?? []).filter((s) => s.kind !== 'STRENGTH' && inR(s.fromSec)),
    }
  }),
)
const sliceOf = (sec: number) => Math.min(SLICES - 1, Math.floor((sec / D.value) * SLICES))

const todo = computed(() => {
  const r = report.value!
  return [...subs.value]
    .sort((a, b) => a.score - b.score)
    .slice(0, 2)
    .map((s, i) => ({ tag: s.label, title: s.note || `${s.label} 점수가 낮았어요.`, action: r.coaching.actions[i] ?? '', evs: s.evidence.map((e) => [e.fromSec, e.toSec] as Range) }))
})

const spd = computed(() => {
  const v = tl.value.speechRate.values
  const mn = Math.min(...v) - 10
  const mx = Math.max(...v) + 10
  const y = (x: number) => 56 - ((x - mn) / (mx - mn)) * 52 - 2
  const w = tl.value.speechRate.windowSec
  return { pts: v.map((x, i) => (((i * w + w / 2) / D.value) * 1000).toFixed(1) + ',' + y(x).toFixed(1)).join(' ') }
})

function active(sec: number) {
  const x = tl.value
  const inAny = (rs: Range[]) => rs.some(([a, b]) => sec >= a && sec <= b)
  const out: string[] = []
  if (inAny(x.fast)) out.push('빠른 말 속도')
  if (inAny(x.gazeOff)) out.push('고개가 정면을 벗어남')
  if (inAny(x.noFace)) out.push('얼굴이 안 보임')
  if (inAny(x.lowConfidence)) out.push('발음 확인 구간')
  if (inAny(x.handMotionHigh)) out.push('손 움직임 많음')
  return out
}
const curSeg = computed(() => sliceOf(t.value))
const live = computed(() => active(t.value))

// 지표 카드의 보조 수치: 타임라인에서 계산
const stat = (key: string): [string, string][] => {
  const x = tl.value
  const longest = x.gazeOff.reduce((m, [a, b]) => Math.max(m, b - a), 0)
  const fastSec = x.fast.reduce((m, [a, b]) => m + (b - a), 0)
  const avg = Math.round(x.speechRate.values.reduce((a, b) => a + b, 0) / x.speechRate.values.length)
  switch (key) {
    case 'SPEECH_RATE': return [['빠르게 말한 구간', x.fast.length + '곳'], ['전체 중 비율', Math.round((fastSec / D.value) * 100) + '%'], ['평균 속도', `분당 ${avg}음절`]]
    case 'FLUENCY': return [['말버릇', x.fillers.length + '회'], ['문장 중간 긴 쉼', x.pauses.length + '회'], ['발음 다시 듣기', x.lowConfidence.length + '곳']]
    case 'GESTURE': return [['손 움직임 있음', x.handMotion.length + '곳'], ['크게 움직인 구간', x.handMotionHigh.length + '곳'], ['얼굴 안 보임', x.noFace.length + '곳']]
    case 'GAZE': return [['10초 넘게 벗어남', x.gazeOff.length + '번'], ['짧게 벗어남', x.gazeOffShort.length + '번'], ['가장 길었던 이탈', longest + '초']]
    default: return []
  }
}
const cards = computed(() => subs.value.filter((s) => lv.value === 'all' || grade(s.score)[1] === lv.value))

// ----- 시간축 클릭 / 이동
const phw = ref<HTMLElement | null>(null)
function seekByClick(e: MouseEvent) {
  const el = phw.value
  if (!el) return
  const r = el.getBoundingClientRect()
  player.seek(((e.clientX - r.left) / r.width) * D.value)
}
const go = (a: number, b: number) => player.playRange(a, b)
const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

// 플레이어가 화면에서 벗어나면 미니 플레이어 표시
const playerEl = ref<HTMLElement | null>(null)
const pvis = ref(true)
let io: IntersectionObserver | null = null
function watchPlayer() {
  if (!playerEl.value) return
  io = new IntersectionObserver((e) => (pvis.value = e[0].isIntersecting), { threshold: 0 })
  io.observe(playerEl.value)
}
onBeforeUnmount(() => io?.disconnect())
const showMini = computed(() => !pvis.value && (playing.value || t.value > 0))

const curUtt = computed(() => utterances.value?.find((u) => t.value >= u.startSec && t.value < u.endSec)?.seq)
const LV: Record<string, string> = { fix: '보완 필요', ok: '좋아요', obs: '보통' }
</script>

<template>
  <div v-if="loading" class="wrap loading"><span class="spin" /> 리포트를 불러오는 중…</div>
  <div v-else-if="error || !report" class="wrap">
    <div class="card"><p class="err" role="alert">{{ error }}</p><button class="btn" style="margin-top: 10px" @click="router.push('/me')">내 발표로</button></div>
  </div>

  <div v-else class="rpt">
    <nav class="subnav" aria-label="리포트 바로가기">
      <div class="subnav-in">
        <a href="#" @click.prevent="jump('s-sum')">종합</a><a href="#" @click.prevent="jump('s-todo')">핵심 개선점</a>
        <a href="#" @click.prevent="jump('s-tl')">시간축</a><a href="#" @click.prevent="jump('s-seg')">구간별 피드백</a>
        <a href="#" @click.prevent="jump('s-met')">지표별 결과</a><a href="#" @click.prevent="jump('s-tr')">전사문</a><a href="#" @click.prevent="jump('s-lim')">참고 사항</a>
      </div>
    </nav>

    <div class="wrap" style="padding-top: 0">
      <!-- 종합 -->
      <section id="s-sum" class="sec2" style="margin-top: 0">
        <div class="crumb" style="margin-top: 6px">
          <button class="link" style="font-weight: 500; text-decoration: none; color: inherit; padding: 0" @click="router.push('/me')">내 발표</button> ›
          <button class="link" style="font-weight: 500; text-decoration: none; color: inherit; padding: 0" @click="router.push(`/me/history?p=${pid}`)">{{ project?.name }}</button> › {{ n }}회차 리포트
        </div>
        <div style="margin-top: 10px; display: flex; flex-wrap: wrap; gap: 12px 24px; align-items: flex-end; justify-content: space-between">
          <div>
            <h1 class="h1">{{ n }}회차 분석 리포트</h1>
            <p class="sub">{{ (round?.createdAt ?? '').slice(0, 10).replace(/-/g, '.') }} · 영상 {{ fmt(D) }} · 모델 {{ report.versions.model }} · 루브릭 {{ report.versions.rubric }}</p>
          </div>
          <div class="rtop-cta"><button class="btn btn-p" @click="router.push(`/new?p=${pid}`)">다시 연습하기</button></div>
        </div>

        <div class="top">
          <div class="tsc">
            <span class="tag">종합 점수</span>
            <div class="gw">{{ grade(total)[0] }}</div>
            <div class="gs">{{ total }}<small>점 / 100</small></div>
            <ul class="tmeta">
              <li>발표 시간 <b>{{ fmt(D) }}</b></li>
              <li v-if="report.targetMinutes">목표 <b>{{ report.targetMinutes }}분</b> · <b>{{ (report.timeCheck.deltaMinutes ?? 0) > 0 ? '+' : '' }}{{ report.timeCheck.deltaMinutes }}분</b></li>
              <li v-else>목표 시간 <b>제한 없음</b></li>
              <li v-if="report.quality === 'DEGRADED'">분석 품질 <b>일부 제한</b> · <a href="#" @click.prevent="jump('s-lim')">자세히</a></li>
            </ul>
          </div>
          <div class="subs">
            <div v-for="x in subs" :key="x.itemKey" class="sb">
              <div class="sbh"><span class="nm">{{ x.label }}</span><span class="lv" :class="grade(x.score)[1]">{{ grade(x.score)[0] }}</span></div>
              <div class="sv">{{ x.score }}<small>점</small></div>
              <div class="bar"><i :class="grade(x.score)[1]" :style="{ width: x.score + '%' }" /></div>
              <p>{{ x.note }}</p>
            </div>
          </div>
        </div>

        <div class="fb">
          <h2>종합 피드백</h2>
          <p class="fb1">{{ report.coaching.strengths[0] }} {{ report.coaching.improvements[0] }}</p>
          <p class="fb2">
            <template v-for="s in report.coaching.strengths.slice(1)" :key="s">{{ s }} </template>
            <template v-for="s in report.coaching.improvements.slice(1)" :key="s">{{ s }} </template>
            다음 연습에서는 {{ report.coaching.actions.join(' ') }}
          </p>
        </div>

        <section id="s-todo" class="kf">
          <div class="kfh"><h2>오늘의 핵심 개선점</h2><span>눌러서 해당 장면을 바로 확인하세요</span></div>
          <div class="kfg">
            <article v-for="(x, i) in todo" :key="i" class="kfc">
              <div class="kft"><span class="n">{{ i + 1 }}</span><em>{{ x.tag }}</em></div>
              <h3>{{ x.title }}</h3>
              <p v-if="x.action">→ {{ x.action }}</p>
              <div class="kfa">
                <button v-if="x.evs.length" class="btn btn-s btn-p" @click="go(x.evs[0][0], x.evs[0][1] + 8)"><span style="display: inline-flex" v-html="IC.playMini" /> 이 구간 다시 보기</button>
                <span v-if="x.evs.length > 1" class="kfm">총 {{ x.evs.length }}곳 · {{ x.evs.map((e) => fmt(e[0])).join(' · ') }}</span>
              </div>
            </article>
          </div>
          <div class="kfn">
            <div><b>다음 연습 목표</b><span>{{ todo[0]?.tag }} 개선</span></div>
            <button class="btn btn-p" @click="router.push(`/new?p=${pid}`)">이 목표로 다시 연습하기</button>
          </div>
        </section>
      </section>

      <!-- 영상과 시간축 -->
      <section id="s-tl" class="sec2">
        <h2>영상과 시간축</h2>
        <p class="lead">트랙을 누르면 그 시점으로 이동해요. 노란색은 ‘보완 필요’ 근거 구간이에요.</p>
        <div class="pl">
          <div>
            <div id="player" ref="playerEl" class="pv" :class="{ vid: !!src, paused: !playing }">
              <video v-if="src" ref="videoEl" :src="src" preload="metadata" playsinline aria-label="발표 영상" @click="player.toggle()" />
              <svg v-else viewBox="0 0 120 120" width="84" height="84" aria-hidden="true"><circle cx="60" cy="42" r="20" fill="#475569" /><path d="M20 120c0-30 18-50 40-50s40 20 40 50z" fill="#475569" /></svg>
              <button class="big" aria-label="재생 또는 일시정지" @click="player.toggle()"><span style="display: inline-flex" v-html="playing ? IC.pauseMini : IC.playMini" /></button>
              <span class="sg">구간 {{ curSeg + 1 }}</span>
              <span class="tm">{{ fmt(t) }} / {{ fmt(D) }}</span>
              <span class="note2">{{ src ? '샘플 영상 (목업)' : '시안 · 실제 영상 자리' }}</span>
            </div>
            <div class="pctl">
              <input type="range" min="0" :max="D" step="1" :value="Math.round(t)" aria-label="재생 위치" @input="player.seek(+($event.target as HTMLInputElement).value)" />
              <button class="spd" @click="player.cycleSpeed()">{{ speed }}×</button>
            </div>
            <div class="live" aria-live="polite">
              <b>지금 장면 · 구간 {{ curSeg + 1 }}</b>
              <div v-if="live.length" class="chs"><span v-for="x in live" :key="x">{{ x }}</span></div>
              <div v-else style="color: var(--mute); margin-top: 4px">이 장면에서 표시할 사항이 없어요.</div>
            </div>
          </div>

          <div class="tl">
            <div ref="phw" class="phw"><div class="ph" :style="{ left: pc(t) }" /></div>
            <div class="tr">
              <span class="l">발화 속도<small>{{ tl.speechRate.windowSec }}초 창</small></span>
              <div class="pt tall" @click="seekByClick">
                <svg viewBox="0 0 1000 56" preserveAspectRatio="none" aria-hidden="true">
                  <rect v-for="(f, i) in tl.fast" :key="i" :x="(f[0] / D) * 1000" :width="((f[1] - f[0]) / D) * 1000" height="56" fill="#FCD34D" opacity=".55" />
                  <polyline fill="none" stroke="var(--d1)" stroke-width="2" vector-effect="non-scaling-stroke" :points="spd.pts" />
                </svg>
              </div>
            </div>
            <div class="tr"><span class="l">말버릇<small>유창성</small></span><div class="pt" @click="seekByClick"><i v-for="(f, i) in tl.fillers" :key="i" class="tk" :style="{ left: pc(f) }" /></div></div>
            <div class="tr"><span class="l">쉬어가기<small>유창성</small></span><div class="pt" @click="seekByClick"><i v-for="(p, i) in tl.pauses" :key="i" class="bk pz" :style="{ left: pc(p), width: pc(2) }" /></div></div>
            <div class="tr"><span class="l">발음<small>유창성</small></span><div class="pt" @click="seekByClick"><i v-for="(r, i) in tl.lowConfidence" :key="i" class="bk info" :style="{ left: pc(r[0]), width: pc(r[1] - r[0]) }" /></div></div>
            <div class="tr">
              <span class="l">제스처<small>손 움직임</small></span>
              <div class="pt" @click="seekByClick">
                <i v-for="(r, i) in tl.noFace" :key="'n' + i" class="bk none" :style="{ left: pc(r[0]), width: pc(r[1] - r[0]) }" />
                <i v-for="(r, i) in tl.handMotion" :key="'h' + i" class="bk" :style="{ left: pc(r[0]), width: pc(r[1] - r[0]) }" />
                <i v-for="(r, i) in tl.handMotionHigh" :key="'g' + i" class="bk hi" :style="{ left: pc(r[0]), width: pc(r[1] - r[0]) }" />
              </div>
            </div>
            <div class="tr">
              <span class="l">시선<small>고개 방향</small></span>
              <div class="pt" @click="seekByClick">
                <i v-for="(r, i) in tl.noFace" :key="'n' + i" class="bk none" :style="{ left: pc(r[0]), width: pc(r[1] - r[0]) }" />
                <i v-for="(r, i) in tl.gazeOffShort" :key="'s' + i" class="bk" :style="{ left: pc(r[0]), width: pc(r[1] - r[0]) }" />
                <i v-for="(r, i) in tl.gazeOff" :key="'w' + i" class="bk warn" :style="{ left: pc(r[0]), width: pc(r[1] - r[0]) }" />
              </div>
            </div>
            <div class="tr">
              <span class="l">구간</span>
              <div class="pt" style="height: 34px">
                <div class="sgs"><button v-for="s in slices" :key="s.i" :class="{ on: s.i === curSeg }" :style="{ flex: s.b - s.a }" @click="player.seek(s.a)">{{ s.i + 1 }} 구간</button></div>
              </div>
            </div>
            <div class="axis"><span>0:00</span><span>{{ fmt(D / 3) }}</span><span>{{ fmt((D * 2) / 3) }}</span><span>{{ fmt(D) }}</span></div>
            <div class="lg">
              <span><i style="background: #fcd34d" />보완 필요 근거</span>
              <span><i style="background: var(--d2)" />손 움직임 · 정면에서 벗어난 짧은 구간</span>
              <span><i style="background: var(--d1)" />손 움직임 많음</span>
              <span><i style="background: #f59e0b" />문장 중간 긴 쉼</span>
              <span><i style="background: #93c5fd; outline: 1px dashed var(--pri)" />발음 다시 듣기</span>
              <span><i style="background: repeating-linear-gradient(45deg, #cbd5e1 0 3px, #e2e8f0 3px 6px)" />얼굴 안 보임(제외)</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 구간별 피드백 -->
      <section id="s-seg" class="sec2">
        <h2>구간별 피드백</h2>
        <p class="lead">영상을 5개 구간으로 나눠 잘한 점과 고칠 점을 정리했어요. ‘이 구간 재생’을 누르면 그 구간이 재생돼요.</p>
        <div class="segs">
          <article v-for="s in slices" :key="s.i" class="sgc" :class="{ on: s.i === curSeg, playing: s.i === curSeg && playing }">
            <div class="sgh">
              <h3>구간 {{ s.i + 1 }}<span>{{ fmt(s.a) }} – {{ fmt(s.b) }}</span></h3>
              <button class="btn btn-s btn-p" @click="go(s.a, s.b)"><span style="display: inline-flex" v-html="IC.playMini" /> 이 구간 재생</button>
            </div>
            <div class="sgm"><span v-for="x in s.stats" :key="x[0]">{{ x[0] }} <b>{{ x[1] }}</b></span></div>
            <div class="gf">
              <div class="g">
                <h4>잘한 점</h4>
                <ul v-if="s.good.length"><li v-for="g in s.good" :key="g.fromSec">{{ g.feedback }}<div class="evw"><EvBtn :a="g.fromSec" :b="g.toSec" @go="go" /></div></li></ul>
                <div v-else class="none">두드러진 잘한 점이 없었어요.</div>
              </div>
              <div class="f">
                <h4>고칠 점</h4>
                <ul v-if="s.fix.length"><li v-for="g in s.fix" :key="g.fromSec">{{ g.feedback }}<div class="evw"><EvBtn :a="g.fromSec" :b="g.toSec" @go="go" /></div></li></ul>
                <div v-else class="none">두드러진 고칠 점이 없었어요.</div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <!-- 지표별 결과 -->
      <section id="s-met" class="sec2">
        <h2>지표별 결과</h2>
        <p class="lead">네 가지 지표를 따로 살펴봤어요. 다시 보기를 누르면 그 장면이 재생돼요.</p>
        <div class="tabs" role="tablist" style="margin-bottom: 14px">
          <button v-for="o in [['all', '전체'], ['fix', '보완 필요'], ['obs', '보통'], ['ok', '좋아요']]" :key="o[0]" role="tab" :aria-selected="lv === o[0]" @click="lv = o[0] as typeof lv">{{ o[1] }}</button>
        </div>
        <div class="mcs">
          <article v-for="s in cards" :key="s.itemKey" class="mc" :data-lv="grade(s.score)[1]">
            <div class="mh"><h3>{{ s.label }}</h3><span class="mhr"><b>{{ s.score }}점</b><span class="lv" :class="grade(s.score)[1]">{{ grade(s.score)[0] }}</span></span></div>
            <p class="mhead">{{ s.note }}</p>
            <div class="mst"><div v-for="x in stat(s.itemKey)" :key="x[0]"><b>{{ x[1] }}</b><span>{{ x[0] }}</span></div></div>
            <div class="evs"><small>다시 보기</small><EvBtn v-for="(e, i) in s.evidence" :key="i" :a="e.fromSec" :b="e.toSec" @go="go" /></div>
            <p class="tip" :class="{ none: grade(s.score)[1] === 'ok' }"><b>이렇게 해보세요</b>{{ grade(s.score)[1] === 'ok' ? '지금처럼 이어가면 좋아요.' : report.coaching.actions[subs.findIndex((z) => z.itemKey === s.itemKey) % report.coaching.actions.length] }}</p>
            <details class="how"><summary>어떻게 쟀나요?</summary><p>{{ HOW_MEASURED[s.itemKey] }}</p></details>
          </article>
          <p v-if="!cards.length" style="color: var(--mute)">{{ LV[lv] }} 항목이 없어요.</p>
        </div>
      </section>

      <!-- 전사문 -->
      <section id="s-tr" class="sec2">
        <h2>전사문</h2>
        <p class="lead">내가 한 말을 시간순으로 확인해요. 문장을 누르면 그 장면으로 이동해요.</p>
        <button class="btn" @click="showTranscript = !showTranscript">{{ showTranscript ? '전사문 접기' : '전사문 펼치기' }}</button>
        <div v-if="showTranscript" class="card" style="margin-top: 14px">
          <TranscriptPanel :utterances="utterances" :current-seq="curUtt" @seek="player.seek" />
        </div>
      </section>

      <!-- 참고 사항 -->
      <section id="s-lim" class="sec2">
        <h2>분석할 때 참고하세요</h2>
        <p class="lead">영상과 음성 상태에 따라 결과가 달라질 수 있어요. 아래 내용을 함께 봐 주세요.</p>
        <div class="lim">
          <div v-for="l in limits" :key="l.code" class="card">
            <h3>{{ l.title }}</h3>
            <ul><li>{{ l.message }}</li></ul>
            <p v-if="l.ranges.length" style="margin-top: 8px"><EvBtn v-for="(r, i) in l.ranges" :key="i" :a="r[0]" :b="r[1]" @go="go" /></p>
          </div>
          <div class="card"><h3>결과를 읽는 방법</h3><ul><li>점수는 정해진 규칙으로 계산했고, 코칭 문장은 그 결과를 설명해요.</li><li>발표 내용의 좋고 나쁨은 평가하지 않아요.</li><li>기준은 앞으로 더 많은 발표 데이터로 계속 다듬어 갈 예정이에요.</li></ul></div>
        </div>
        <div class="cta3">
          <div>
            <h2>이 발표로 질의응답 연습하기</h2>
            <p>예상 질문을 바탕으로 심사위원 질문에 답해 보세요. (준비 중)</p>
            <div class="qs" style="margin-top: 12px">
              <div v-for="(q, i) in report.expectedQuestions" :key="i"><em :class="q.kind === 'TECH' ? 't' : 'b'">{{ q.kind === 'TECH' ? '기술' : '사업' }}</em><span>{{ q.text }}</span></div>
            </div>
          </div>
          <button class="btn" style="background: #fff; border-color: #fff" disabled aria-disabled="true" title="다음 단계에서 제공돼요">질의응답 준비 중</button>
        </div>
        <p class="foot">목업 데이터이며 실제 분석 결과가 아니에요</p>
      </section>
    </div>

    <div class="rmini" :class="{ show: showMini }">
      <div class="rmini-in">
        <button aria-label="재생 또는 일시정지" @click="player.toggle()"><span style="display: inline-flex" v-html="playing ? IC.pauseMini : IC.playMini" /></button>
        <div class="tx"><b>{{ fmt(t) }}</b> · 구간 {{ curSeg + 1 }}<template v-if="live.length"> · {{ live[0] }}</template></div>
        <button class="up2" style="border-radius: 8px" @click="playerEl?.scrollIntoView({ behavior: 'smooth', block: 'center' })">플레이어 보기</button>
      </div>
      <div class="mbar"><i :style="{ width: (t / D) * 100 + '%' }" /></div>
    </div>
    <div class="rcta"><button class="btn btn-p btn-l" @click="router.push(`/new?p=${pid}`)">다시 연습하기</button></div>
  </div>
</template>
