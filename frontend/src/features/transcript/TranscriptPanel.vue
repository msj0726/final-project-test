<script setup lang="ts">
import { fmt } from '@/shared/lib/format'
import type { Utterance } from '@/shared/api/types'

/** 전사문(발화 목록). null 이면 불러오는 중. 문장을 누르면 그 시각으로 이동 */
defineProps<{ utterances: Utterance[] | null; currentSeq?: number }>()
defineEmits<{ seek: [sec: number] }>()
</script>

<template>
  <div v-if="!utterances" class="loading"><span class="spin" /> 불러오는 중…</div>
  <p v-else-if="!utterances.length" style="color: var(--mute)">전사문이 없어요.</p>
  <ol v-else class="trl">
    <li v-for="u in utterances" :key="u.seq" :class="{ on: u.seq === currentSeq }">
      <button @click="$emit('seek', u.startSec)"><time>{{ fmt(u.startSec) }}</time><span>{{ u.text }}</span></button>
    </li>
  </ol>
</template>

<style>
.trl{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:2px;max-height:420px;overflow:auto}
.trl li button{display:flex;gap:14px;width:100%;text-align:left;background:none;border:0;border-radius:10px;padding:8px 10px;color:inherit;font-size:15px}
.trl li button:hover{background:var(--soft2)}
.trl li.on button{background:var(--soft)}
.trl time{flex:none;width:44px;color:var(--mute);font-variant-numeric:tabular-nums}
</style>
