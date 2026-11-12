<script setup lang="ts">
import { fmt } from '@/shared/lib/format'
import { IC } from '@/shared/lib/icons'

defineProps<{ a: number; b: number; label?: string }>()
defineEmits<{ go: [a: number, b: number] }>()
</script>

<template>
  <button class="evb" type="button" @click="$emit('go', a, b)">
    <span style="display: inline-flex" v-html="IC.playMini" />{{ fmt(a) }}<template v-if="b - a > 4">–{{ fmt(b) }}</template>
    <template v-if="label"> {{ label }}</template>
  </button>
</template>
