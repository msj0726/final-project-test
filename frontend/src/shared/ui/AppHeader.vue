<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/shared/state/auth'
import { IC } from '@/shared/lib/icons'

defineProps<{ variant: 'public' | 'app'; landing?: boolean }>()
const auth = useAuth()
const router = useRouter()
const open = ref(false)

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
}
async function logout() {
  open.value = false
  await auth.logout()
  router.push('/')
}
const go = (p: string) => {
  open.value = false
  router.push(p)
}
</script>

<template>
  <header class="hd">
    <div class="hd-in">
      <button class="logo" :aria-label="'ProPitch 처음으로'" @click="go(variant === 'app' ? '/me' : '/')">
        <i v-html="IC.logo" />ProPitch
      </button>

      <template v-if="variant === 'public'">
        <nav v-if="landing" class="hnav" aria-label="주요 메뉴">
          <button @click="scrollTo('features')">기능</button>
          <button @click="scrollTo('how')">이용 방법</button>
          <button @click="scrollTo('privacy')">개인정보</button>
        </nav>
        <div v-if="!auth.loggedIn" class="hr">
          <button class="btn btn-g" style="border-color: transparent" @click="go('/login')">로그인</button>
          <button class="btn btn-p" @click="go('/signup')">시작하기</button>
        </div>
      </template>

      <div v-if="variant === 'app' || auth.loggedIn" class="hr">
        <button class="btn btn-p" @click="go('/new')">새 연습</button>
        <div class="rel">
          <button class="userbtn" aria-haspopup="true" :aria-expanded="open" @click="open = !open">
            <span class="av">{{ auth.user?.name.slice(0, 1) }}</span>{{ auth.user?.name }} ▾
          </button>
          <div v-if="open" class="menu" role="menu">
            <small>마이페이지</small>
            <button role="menuitem" @click="go('/me')">내 발표 프로젝트</button>
            <button role="menuitem" @click="go('/me/history')">이력 · 추이</button>
            <button role="menuitem" @click="go('/me/calendar')">발표 일정</button>
            <button role="menuitem" @click="go('/me/account')">계정 설정</button>
            <hr />
            <button role="menuitem" @click="logout">로그아웃</button>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>
