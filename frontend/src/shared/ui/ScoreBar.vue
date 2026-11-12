<script setup lang="ts">
defineProps<{ label: string; value: number }>()
const cls = (v: number) => (v >= 80 ? 'g' : v >= 70 ? 'm' : 'a')
</script>

<template>
  <div class="mini">
    <div class="l"><span>{{ label }}</span><span>{{ value }}</span></div>
    <div class="bar" style="margin-top: -4px"><i :class="cls(value)" :style="{ width: value + '%' }" /></div>
  </div>
</template>
