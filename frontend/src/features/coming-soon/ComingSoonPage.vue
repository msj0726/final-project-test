<script setup lang="ts">
import { useRouter } from 'vue-router'
import { IC } from '@/shared/lib/icons'
import EmptyState from '@/shared/ui/EmptyState.vue'

const router = useRouter()
</script>

<template>
  <div class="wrap" style="max-width: 720px">
    <EmptyState :icon="IC.shield" title="질의응답은 준비 중이에요" desc="분석한 발표 영상을 바탕으로 한 실시간 질의응답은 다음 단계에서 제공돼요.">
      <button class="btn btn-p" @click="router.push('/me')">내 발표로 돌아가기</button>
    </EmptyState>
  </div>
</template>
