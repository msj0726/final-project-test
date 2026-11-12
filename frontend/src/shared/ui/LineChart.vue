<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{ pts: { v: number; l: string }[]; w?: number; h?: number; pending?: boolean; label?: string; color?: string }>(),
  { w: 640, h: 240, color: 'var(--pri)', label: '점수 추이 그래프' },
)
const L = 52, R = 24, T = 28, B = 38

const geo = computed(() => {
  const { pts, w: W, h: H } = props
  const vals = pts.map((p) => p.v)
  let lo = Math.floor((Math.min(...vals) - 4) / 10) * 10
  let hi = Math.ceil((Math.max(...vals) + 4) / 10) * 10
  if (hi - lo < 20) hi = lo + 20
  const X = (i: number) => (pts.length === 1 ? (L + W - R) / 2 : L + ((W - L - R) * i) / (pts.length - 1))
  const Y = (v: number) => T + (H - T - B) * (1 - (v - lo) / (hi - lo))
  const grid: number[] = []
  for (let v = lo; v <= hi; v += 10) grid.push(v)
  const last = pts.length - 1
  const px = pts.length === 1 ? X(0) + 80 : X(last) + ((W - L - R) / Math.max(1, last)) * 0.5 + 20
  return { X, Y, grid, last, px }
})
</script>

<template>
  <svg v-if="pts.length" :viewBox="`0 0 ${w} ${h}`" style="width: 100%; height: auto; display: block" role="img"
    :aria-label="`${label}: ${pts.map((p) => p.l + ' ' + p.v + '점').join(', ')}`">
    <g v-for="v in geo.grid" :key="v">
      <line :x1="L" :x2="w - R" :y1="geo.Y(v)" :y2="geo.Y(v)" stroke="var(--soft)" />
      <text :x="L - 10" :y="geo.Y(v) + 4" text-anchor="end" font-size="12" fill="#475569">{{ v }}</text>
    </g>
    <polyline v-if="pts.length > 1" fill="none" :stroke="color" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"
      :points="pts.map((p, i) => geo.X(i) + ',' + geo.Y(p.v)).join(' ')" />
    <g v-if="pending">
      <line :x1="geo.X(geo.last)" :y1="geo.Y(pts[geo.last].v)" :x2="geo.px" :y2="geo.Y(pts[geo.last].v) - 10" :stroke="color" stroke-width="3" stroke-dasharray="5 5" />
      <circle :cx="geo.px" :cy="geo.Y(pts[geo.last].v) - 10" r="7" fill="var(--soft2)" :stroke="color" stroke-width="3" stroke-dasharray="3 3" />
      <text :x="geo.px" :y="geo.Y(pts[geo.last].v) - 28" text-anchor="middle" font-size="12" font-weight="700" :fill="color">분석 중</text>
    </g>
    <g v-for="(p, i) in pts" :key="i">
      <circle :cx="geo.X(i)" :cy="geo.Y(p.v)" r="7" :fill="i === geo.last ? color : '#fff'" :stroke="color" stroke-width="3" />
      <text :x="geo.X(i)" :y="geo.Y(p.v) - 14" text-anchor="middle" font-size="14" font-weight="700" fill="var(--pri-d)">{{ p.v }}</text>
      <text :x="geo.X(i)" :y="h - 12" text-anchor="middle" font-size="13" fill="#475569">{{ p.l }}</text>
    </g>
  </svg>
</template>
