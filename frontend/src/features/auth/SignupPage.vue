<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError } from '@/shared/api'
import { useAuth } from '@/shared/state/auth'
import { useUi } from '@/shared/state/ui'

const router = useRouter()
const auth = useAuth()
const ui = useUi()
const v = reactive({ name: '', email: '', pw: '', pw2: '', terms: false, privacy: false, aiAnalysis: false })
const err = ref<Record<string, string>>({})
const busy = ref(false)

const all = computed({
  get: () => v.terms && v.privacy && v.aiAnalysis,
  set: (x: boolean) => (v.terms = v.privacy = v.aiAnalysis = x),
})

async function submit() {
  const e: Record<string, string> = {}
  if (!v.name.trim()) e.name = '이름을 입력해 주세요.'
  if (!/^\S+@\S+\.\S+$/.test(v.email)) e.email = '이메일 형식을 확인해 주세요.'
  if (v.pw.length < 8) e.pw = '비밀번호는 8자 이상이어야 해요.'
  if (v.pw2 !== v.pw) e.pw2 = '비밀번호가 서로 달라요.'
  if (!all.value) e.ag = '필수 항목에 모두 동의해 주세요.'
  err.value = e
  if (Object.keys(e).length) return
  busy.value = true
  try {
    await auth.signup({ name: v.name, email: v.email, password: v.pw, agreements: { terms: v.terms, privacy: v.privacy, aiAnalysis: v.aiAnalysis } })
    ui.toast('가입을 환영해요!')
    router.replace('/me')
  } catch (x) {
    if (x instanceof ApiError && x.fields) {
      // 서버 필드명(password, agreements)을 화면 필드명에 맞춤
      err.value = { name: x.fields.name, email: x.fields.email, pw: x.fields.password, ag: x.fields.agreements } as Record<string, string>
    } else err.value = { ag: x instanceof ApiError ? x.message : '가입하지 못했어요. 잠시 후 다시 시도해 주세요.' }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="auth">
    <div class="authc" style="max-width: 480px">
      <h1>회원가입</h1>
      <p class="sub">1분이면 끝나요. 가입하면 바로 첫 프로젝트를 만들 수 있어요.</p>
      <form style="margin-top: 22px; display: flex; flex-direction: column; gap: 16px" novalidate @submit.prevent="submit">
        <div>
          <label class="f" for="name">이름 <em>*</em></label>
          <input id="name" v-model="v.name" class="in" :class="{ bad: err.name }" autocomplete="name" placeholder="홍길동" />
          <div v-if="err.name" class="err" role="alert">{{ err.name }}</div>
        </div>
        <div>
          <label class="f" for="email">이메일 (아이디) <em>*</em></label>
          <input id="email" v-model="v.email" class="in" :class="{ bad: err.email }" type="email" autocomplete="email" placeholder="you@example.com" />
          <div v-if="err.email" class="err" role="alert">{{ err.email }}</div>
        </div>
        <div>
          <label class="f" for="pw">비밀번호 <em>*</em></label>
          <input id="pw" v-model="v.pw" class="in" :class="{ bad: err.pw }" type="password" autocomplete="new-password" placeholder="8자 이상" />
          <div v-if="err.pw" class="err" role="alert">{{ err.pw }}</div>
        </div>
        <div>
          <label class="f" for="pw2">비밀번호 확인 <em>*</em></label>
          <input id="pw2" v-model="v.pw2" class="in" :class="{ bad: err.pw2 }" type="password" autocomplete="new-password" placeholder="한 번 더 입력" />
          <div v-if="err.pw2" class="err" role="alert">{{ err.pw2 }}</div>
        </div>
        <div style="display: flex; flex-direction: column; gap: 10px; padding: 14px 16px; border-radius: 14px; background: var(--soft2); border: 1px solid var(--soft)">
          <label class="chk"><input v-model="all" type="checkbox" /> <b>전체 동의</b></label>
          <label class="chk"><input v-model="v.terms" type="checkbox" /> <span>(필수) 이용약관에 동의해요</span></label>
          <label class="chk"><input v-model="v.privacy" type="checkbox" /> <span>(필수) 개인정보 수집·이용에 동의해요</span></label>
          <label class="chk"><input v-model="v.aiAnalysis" type="checkbox" /> <span>(필수) 올린 영상을 AI로 분석하는 데 동의해요</span></label>
          <div v-if="err.ag" class="err" role="alert">{{ err.ag }}</div>
        </div>
        <button class="btn btn-p btn-l" type="submit" style="width: 100%" :disabled="busy">{{ busy ? '가입 중…' : '가입하고 시작하기' }}</button>
      </form>
      <p style="margin-top: 18px; text-align: center; font-size: 14px; color: var(--mute)">
        이미 계정이 있나요? <button class="link" @click="router.push('/login')">로그인</button>
      </p>
    </div>
  </div>
</template>
