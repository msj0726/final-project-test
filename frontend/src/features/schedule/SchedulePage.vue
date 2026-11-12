<script setup lang="ts">
import { computed, ref } from 'vue'
import { schedule } from '@/shared/api'
import { dday, mmdd } from '@/shared/lib/format'
import { useLoad } from '@/shared/composables/useLoad'
import MyPageShell from '@/shared/ui/MyPageShell.vue'

const today = new Date()
const ym = ref(new Date(today.getFullYear(), today.getMonth(), 1))
const monthKey = computed(() => `${ym.value.getFullYear()}-${String(ym.value.getMonth() + 1).padStart(2, '0')}`)
const { data, loading, error, reload } = useLoad(() => schedule.list())

const events = computed(() => (data.value ?? []).filter((e) => !e.done))
const byDay = computed(() => {
  const m: Record<number, typeof events.value> = {}
  for (const e of events.value) if (e.date.startsWith(monthKey.value)) (m[+e.date.slice(8, 10)] ||= []).push(e)
  return m
})
const days = computed(() => new Date(ym.value.getFullYear(), ym.value.getMonth() + 1, 0).getDate())
const lead = computed(() => ym.value.getDay())
const upcoming = computed(() => [...events.value].sort((a, b) => a.date.localeCompare(b.date)))
const isToday = (d: number) => ym.value.getFullYear() === today.getFullYear() && ym.value.getMonth() === today.getMonth() && d === today.getDate()
const move = (n: number) => (ym.value = new Date(ym.value.getFullYear(), ym.value.getMonth() + n, 1))
</script>

<template>
  <MyPageShell>
    <h1 class="h1">발표 일정</h1>
    <p class="sub">최종 발표일까지 남은 날을 확인해요.</p>
    <div v-if="loading" class="loading"><span class="spin" /> 불러오는 중…</div>
    <div v-else-if="error" class="card" style="margin-top: 18px"><p class="err" role="alert">{{ error }}</p><button class="btn" style="margin-top: 10px" @click="reload">다시 시도</button></div>
    <div v-else class="row" style="margin-top: 20px">
      <div class="card" style="flex: 1 1 360px">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
          <div style="display: flex; align-items: center; gap: 8px">
            <button class="btn btn-s btn-g" aria-label="이전 달" @click="move(-1)">‹</button>
            <h2>{{ ym.getFullYear() }}년 {{ ym.getMonth() + 1 }}월</h2>
            <button class="btn btn-s btn-g" aria-label="다음 달" @click="move(1)">›</button>
          </div>
          <span class="tag">오늘 {{ String(today.getMonth() + 1).padStart(2, '0') }}.{{ String(today.getDate()).padStart(2, '0') }}</span>
        </div>
        <div class="cal">
          <div v-for="w in ['일', '월', '화', '수', '목', '금', '토']" :key="w" class="dw">{{ w }}</div>
          <div v-for="i in lead" :key="'b' + i" />
          <div v-for="d in days" :key="d" class="d" :class="{ ev: byDay[d], today: isToday(d) }">
            {{ d }}<small v-for="e in byDay[d] || []" :key="e.projectId">{{ e.projectName }}</small>
          </div>
        </div>
      </div>
      <div class="card" style="flex: 1 1 300px">
        <h2>다가오는 일정</h2>
        <template v-if="upcoming.length">
          <div v-for="e in upcoming" :key="e.projectId" style="display: flex; justify-content: space-between; gap: 8px; padding: 12px 14px; border-radius: 12px; background: var(--soft2); margin-top: 10px">
            <span>{{ e.projectName }}</span><b style="color: var(--ok)">{{ mmdd(e.date) }} · {{ dday(e.date) }}</b>
          </div>
        </template>
        <p v-else style="margin-top: 12px; color: var(--mute); font-size: 15px">등록된 발표 일정이 없어요. 프로젝트를 만들 때 최종 발표일을 입력하면 여기에 표시돼요.</p>
      </div>
    </div>
  </MyPageShell>
</template>
