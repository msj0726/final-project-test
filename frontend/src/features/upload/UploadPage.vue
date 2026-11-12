<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, projects, rounds, uploads, usesMock } from '@/shared/api'
import { sha256File } from '@/shared/lib/sha256'
import type { ProjectDetail } from '@/shared/api/types'
import { fmt, fsz } from '@/shared/lib/format'
import { IC } from '@/shared/lib/icons'
import { useLoad } from '@/shared/composables/useLoad'

const MAX_BYTES = 524_288_000 // 500 MiB
const MAX_SEC = 30 * 60

const route = useRoute()
const router = useRouter()
const pid = String(route.query.p ?? '')
const { data, loading, error } = useLoad<{ detail: ProjectDetail; goal: string | null }>(async () => {
  const detail = await projects.get(pid)
  // 지난 회차 리포트의 첫 실천 조언을 이번 연습 목표로 보여줌
  const last = detail.rounds.filter((r) => r.status === 'DONE').at(-1)
  const goal = last ? (await rounds.cachedReport(pid, last.roundNo).catch(() => null))?.coaching.actions[0] ?? null : null
  return { detail, goal }
})
const nextNo = computed(() => (data.value ? data.value.detail.rounds.length + 1 : 1))

const file = ref<File | null>(null)
const dur = ref(0)
const fileErr = ref('')
const consent = ref(false)
const err = ref('')
const drag = ref(false)
const phase = ref<'idle' | 'hash' | 'upload' | 'finish'>('idle')
const ratio = ref(0)
const MOCK_UPLOAD = usesMock('POST', '/projects/x/uploads')
let objectUrl = ''

const extType = (f: File) => {
  if (f.type) return f.type
  const n = f.name.toLowerCase()
  return n.endsWith('.mp4') ? 'video/mp4' : n.endsWith('.mov') ? 'video/quicktime' : ''
}

async function pick(f: File | undefined) {
  if (!f) return
  fileErr.value = ''
  file.value = null
  dur.value = 0
  if (!['video/mp4', 'video/quicktime'].includes(extType(f))) {
    fileErr.value = 'MP4 또는 MOV 영상만 올릴 수 있어요.'
    return
  }
  if (f.size > MAX_BYTES) {
    fileErr.value = `영상은 500MB 이하만 올릴 수 있어요. (선택한 파일 ${fsz(f.size)})`
    return
  }
  // 재생 가능 여부와 길이를 브라우저에서 먼저 확인 (서버가 최종 검증)
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = URL.createObjectURL(f)
  const length = await new Promise<number>((resolve) => {
    const v = document.createElement('video')
    v.preload = 'metadata'
    v.onloadedmetadata = () => resolve(v.duration)
    v.onerror = () => resolve(-1)
    v.src = objectUrl
  })
  if (length < 0 || !isFinite(length)) {
    fileErr.value = '이 영상은 재생할 수 없어요. 다른 파일을 골라 주세요.'
    return
  }
  if (length > MAX_SEC) {
    fileErr.value = `영상은 30분 이하만 올릴 수 있어요. (선택한 영상 ${fmt(length)})`
    return
  }
  file.value = f
  dur.value = length
}
const onDrop = (e: DragEvent) => {
  drag.value = false
  pick(e.dataTransfer?.files?.[0])
}
onBeforeUnmount(() => objectUrl && URL.revokeObjectURL(objectUrl))

const ready = computed(() => !!file.value && consent.value && phase.value === 'idle')
const label = computed(() => ({ idle: '이 영상으로 분석하기', hash: `영상 확인 중… ${Math.round(ratio.value * 100)}%`, upload: `올리는 중… ${Math.round(ratio.value * 100)}%`, finish: '분석 접수 중…' })[phase.value])

async function start() {
  err.value = ''
  if (!file.value) {
    err.value = '영상을 먼저 선택해 주세요.'
    return
  }
  if (!consent.value) {
    err.value = '분석 동의에 체크해 주세요.'
    return
  }
  const f = file.value
  let uploadId = ''
  try {
    phase.value = 'hash'
    ratio.value = 0
    const checksum = await sha256File(f, (r) => (ratio.value = r)) // 영상 전체의 SHA-256 (조각 단위로 읽어 메모리 절약)
    const ticket = await uploads.create(pid, { fileName: f.name, sizeBytes: f.size, contentType: extType(f) as 'video/mp4' | 'video/quicktime', checksum })
    uploadId = ticket.uploadId
    phase.value = 'upload'
    ratio.value = 0
    await uploads.putContent(ticket, f, checksum, (r) => (ratio.value = r))
    phase.value = 'finish'
    const done = await uploads.complete(ticket.uploadId)
    router.replace(`/analysis?p=${pid}&n=${done.analysisRef.roundNo}`)
  } catch (e) {
    phase.value = 'idle'
    ratio.value = 0
    err.value = e instanceof ApiError ? e.message : (e as Error).message || '업로드하지 못했어요. 잠시 후 다시 시도해 주세요.'
    if (uploadId) uploads.cancel(uploadId).catch(() => {})
  }
}
</script>

<template>
  <div class="wrap" style="max-width: 820px">
    <div v-if="loading" class="loading"><span class="spin" /> 불러오는 중…</div>
    <div v-else-if="error || !data" class="card"><p class="err" role="alert">{{ error || '프로젝트를 찾을 수 없어요.' }}</p><button class="btn" style="margin-top: 10px" @click="router.push('/new')">새 연습으로</button></div>
    <template v-else>
      <div class="crumb">새 연습 › <b>영상 올리기</b></div>
      <h1 class="h1" style="margin-top: 6px">{{ data.detail.project.name }} · {{ nextNo }}회차 영상 올리기</h1>
      <p class="sub">리허설 영상 1개를 올려 주세요. MP4·MOV 형식, 최대 30분(500MB)까지 올릴 수 있어요.</p>
      <div v-if="data.goal" class="goalbox"><b>이번 연습 목표</b><span>{{ data.goal }}</span></div>

      <div v-if="file" class="fcard">
        <span class="fi" v-html="IC.cam" />
        <div style="flex: 1; min-width: 0"><b>{{ file.name }}</b><small>{{ fsz(file.size) }} · {{ fmt(dur) }}</small></div>
        <button class="btn btn-s" :disabled="phase !== 'idle'" @click="file = null">바꾸기</button>
      </div>
      <div v-else class="drop" :class="{ on: drag }" style="margin-top: 22px" @dragover.prevent="drag = true" @dragleave="drag = false" @drop.prevent="onDrop">
        <div class="empty" style="padding: 0"><span class="ic" v-html="IC.cam" /></div>
        <b style="font-size: 18px; color: var(--pri-d)">여기로 영상을 끌어다 놓거나</b>
        <div style="margin-top: 12px; display: flex; gap: 10px; justify-content: center; flex-wrap: wrap">
          <label class="btn btn-p" style="cursor: pointer">파일 고르기<input type="file" accept="video/mp4,video/quicktime,.mp4,.mov" class="sr" @change="pick(($event.target as HTMLInputElement).files?.[0])" /></label>
        </div>
        <div v-if="MOCK_UPLOAD" class="hint" style="margin-top: 12px">목업 모드라 영상은 서버로 전송되지 않아요. 아무 MP4·MOV 파일이나 골라 흐름을 확인할 수 있어요. 파일 이름에 “fail”을 넣으면 분석 실패 화면도 볼 수 있어요.</div>
      </div>
      <div v-if="fileErr" class="err" role="alert" style="margin-top: 8px">{{ fileErr }}</div>

      <label class="chk" style="margin-top: 18px"><input v-model="consent" type="checkbox" aria-describedby="reqs" /> <span>올린 영상을 AI로 분석하는 데 동의해요. 삭제하면 바로 접근이 차단돼요.</span></label>
      <div v-if="err" class="err" role="alert">{{ err }}</div>

      <div class="ctabar">
        <div class="reqs" id="reqs">
          <span :class="{ ok: file }">{{ file ? '✓' : '○' }} 영상 선택</span>
          <span :class="{ ok: consent }">{{ consent ? '✓' : '○' }} 분석 동의</span>
        </div>
        <div v-if="phase === 'upload' || phase === 'hash'" class="prog" style="margin-top: 12px" role="progressbar" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="Math.round(ratio * 100)"><i :style="{ width: ratio * 100 + '%' }" /></div>
        <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; flex-wrap: wrap">
          <button class="btn btn-g" :disabled="phase !== 'idle'" @click="router.push('/me')">취소</button>
          <button class="btn btn-p btn-l" style="min-height: 56px; font-size: 17px; padding: 0 28px" :disabled="!ready" @click="start">{{ label }}</button>
        </div>
      </div>
    </template>
  </div>
</template>
