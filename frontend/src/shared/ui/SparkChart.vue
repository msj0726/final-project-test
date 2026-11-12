<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{ pts: { v: number; l: string }[]; color?: string }>(), { color: 'var(--pri)' })
const W = 300, H = 70, L = 14, R = 14, T = 22, B = 18

const geo = computed(() => {
  const vals = props.pts.map((p) => p.v)
  const lo = Math.min(...vals) - 4
  let hi = Math.max(...vals) + 4
  if (hi - lo < 10) hi = lo + 10
  const X = (i: number) => (props.pts.length === 1 ? W / 2 : L + ((W - L - R) * i) / (props.pts.length - 1))
  const Y = (v: number) => T + (H - T - B) * (1 - (v - lo) / (hi - lo))
  return { X, Y }
})
</script>

<template>
  <svg v-if="pts.length" :viewBox="`0 0 ${W} ${H}`" style="width: 100%; height: auto; display: block" role="img"
    :aria-label="`점수 추이: ${pts.map((p) => p.l + ' ' + p.v + '점').join(', ')}`">
    <polyline v-if="pts.length > 1" fill="none" :stroke="color" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
      :points="pts.map((p, i) => geo.X(i) + ',' + geo.Y(p.v)).join(' ')" />
    <g v-for="(p, i) in pts" :key="i">
      <circle :cx="geo.X(i)" :cy="geo.Y(p.v)" r="5.5" :fill="i === pts.length - 1 ? color : '#fff'" :stroke="color" stroke-width="2.5" />
      <text :x="geo.X(i)" :y="geo.Y(p.v) - 10" text-anchor="middle" font-size="12" font-weight="700" fill="var(--pri-d)">{{ p.v }}</text>
      <text :x="geo.X(i)" :y="H - 3" text-anchor="middle" font-size="11" fill="#475569">{{ p.l }}</text>
    </g>
  </svg>
</template>
