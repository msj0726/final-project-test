<script setup lang="ts">
defineProps<{ icon: string; title: string; desc: string }>()
</script>

<template>
  <div class="card empty">
    <span class="ic" v-html="icon" />
    <h2>{{ title }}</h2>
    <p>{{ desc }}</p>
    <div class="acts"><slot /></div>
  </div>
</template>
