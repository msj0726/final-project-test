<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '@/shared/state/auth'

const auth = useAuth()
const route = useRoute()
const router = useRouter()
const items: [string, string][] = [
  ['/me', '내 발표 프로젝트'],
  ['/me/history', '이력 · 추이'],
  ['/me/calendar', '발표 일정'],
  ['/me/account', '계정 설정'],
]
</script>

<template>
  <div class="wrap">
    <div class="mp">
      <nav class="side" aria-label="마이페이지 메뉴">
        <div class="who">
          <span class="av" style="width: 40px; height: 40px; font-size: 17px">{{ auth.user?.name.slice(0, 1) }}</span>
          <div>
            <b>{{ auth.user?.name }}</b><small>마이페이지</small>
          </div>
        </div>
        <button v-for="it in items" :key="it[0]" :aria-current="route.path === it[0] ? 'page' : undefined" @click="router.push(it[0])">
          {{ it[1] }}
        </button>
      </nav>
      <div class="mpmain"><slot /></div>
    </div>
  </div>
</template>
