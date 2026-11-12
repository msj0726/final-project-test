<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/shared/ui/AppHeader.vue'
import AppFooter from '@/shared/ui/AppFooter.vue'
import ConfirmModal from '@/shared/ui/ConfirmModal.vue'
import { ui } from '@/shared/state/ui'
import { API_MODE, health } from '@/shared/api'

const route = useRoute()
const variant = computed(() => (route.meta.auth ? 'app' : 'public'))

// 백엔드에 실제로 구현된 /healthz 호출 결과를 하단에 표시
const backend = ref<{ ok: boolean; source: 'backend' | 'mock' } | null>(null)
onMounted(async () => (backend.value = await health.check()))
const label = computed(() => {
  if (!backend.value) return ''
  const b = backend.value
  if (b.source === 'mock') return '목업 데이터로 동작 중 · 로그인 jiyoung@example.com / password123'
  return b.ok
    ? '백엔드 연결됨(/healthz) · 아직 없는 API는 목업 · 로그인 jiyoung@example.com / password123'
    : '백엔드에 연결하지 못했어요(/healthz) · 아직 없는 API는 목업 · 로그인 jiyoung@example.com / password123'
})
</script>

<template>
  <AppHeader :variant="variant" :landing="route.path === '/'" />
  <main id="main">
    <router-view />
  </main>
  <AppFooter v-if="route.path === '/'" />
  <div v-if="API_MODE !== 'real' && label" class="mockbar" :class="{ bad: backend && !backend.ok }" role="note">{{ label }}</div>
  <div class="toast" :class="{ show: !!ui.toastMsg }" role="status" aria-live="polite">{{ ui.toastMsg }}</div>
  <ConfirmModal />
</template>

<style>
.mockbar{position:fixed;left:12px;bottom:12px;z-index:50;background:#0F172A;color:#fff;font-size:12px;padding:6px 12px;border-radius:999px;opacity:.85}
.mockbar.bad{background:#991b1b}
@media(max-width:640px){.mockbar{display:none}}
</style>
