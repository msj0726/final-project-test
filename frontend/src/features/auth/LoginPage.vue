<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, usesMock } from '@/shared/api'
import { useAuth } from '@/shared/state/auth'

const MOCK_AUTH = usesMock('POST', '/auth/login')
const route = useRoute()
const router = useRouter()
const auth = useAuth()
const form = reactive({ email: MOCK_AUTH ? 'jiyoung@example.com' : '', password: MOCK_AUTH ? 'password123' : '' })
const err = ref('')
const busy = ref(false)

async function submit() {
  err.value = ''
  if (!form.email || !form.password) {
    err.value = '이메일과 비밀번호를 입력해 주세요.'
    return
  }
  busy.value = true
  try {
    await auth.login(form.email, form.password)
    if (auth.user?.role === 'ADMIN') {
      err.value = '관리자 화면은 아직 준비 중이에요.'
      await auth.logout()
      return
    }
    const next = typeof route.query.next === 'string' && route.query.next.startsWith('/') ? route.query.next : '/me'
    router.replace(next)
  } catch (e) {
    err.value = e instanceof ApiError ? e.message : '로그인하지 못했어요. 잠시 후 다시 시도해 주세요.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth">
    <div class="authc">
      <h1>다시 만나서 반가워요</h1>
      <p class="sub">로그인하고 이어서 이용해 보세요.</p>
      <form style="margin-top: 18px; display: flex; flex-direction: column; gap: 16px" novalidate @submit.prevent="submit">
        <div>
          <label class="f" for="lid">이메일</label>
          <input id="lid" v-model="form.email" class="in" type="email" autocomplete="username" />
        </div>
        <div>
          <label class="f" for="lpw">비밀번호</label>
          <input id="lpw" v-model="form.password" class="in" type="password" autocomplete="current-password" />
        </div>
        <div style="display: flex; justify-content: flex-end">
          <button type="button" class="link" disabled aria-disabled="true" title="곧 제공될 예정이에요" style="font-size: 14px">비밀번호 찾기</button>
        </div>
        <div v-if="err" class="err" role="alert">{{ err }}</div>
        <button class="btn btn-p btn-l" type="submit" style="width: 100%" :disabled="busy">{{ busy ? '로그인 중…' : '로그인' }}</button>
      </form>
      <p style="margin-top: 20px; text-align: center; font-size: 14px; color: var(--mute)">
        아직 계정이 없나요? <button class="link" @click="router.push('/signup')">회원가입</button>
      </p>
      <div v-if="MOCK_AUTH" class="note" style="margin-top: 18px; font-size: 13px">목업 모드라 계정이 미리 입력돼 있어요. 가입한 계정도 이 브라우저에서 그대로 쓸 수 있어요.</div>
    </div>
  </div>
</template>
