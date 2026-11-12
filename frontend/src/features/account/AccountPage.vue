<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, auth as authApi } from '@/shared/api'
import { useAuth } from '@/shared/state/auth'
import { useUi } from '@/shared/state/ui'
import MyPageShell from '@/shared/ui/MyPageShell.vue'

const auth = useAuth()
const ui = useUi()
const router = useRouter()
const name = ref(auth.user?.name ?? '')
const nameErr = ref('')
const busy = ref(false)

async function saveName() {
  nameErr.value = ''
  if (!name.value.trim()) {
    nameErr.value = '이름을 입력해 주세요.'
    return
  }
  busy.value = true
  try {
    await auth.rename(name.value)
    ui.toast('이름을 저장했어요')
  } catch (e) {
    nameErr.value = e instanceof ApiError ? e.message : '저장하지 못했어요.'
  } finally {
    busy.value = false
  }
}
async function logout() {
  await auth.logout()
  router.push('/')
}
async function deleteAccount() {
  const r = await ui.confirm({
    title: '계정을 삭제할까요?',
    body: '모든 프로젝트와 영상, 리포트가 삭제 예약되고 바로 접근할 수 없게 돼요. 되돌릴 수 없어요.',
    okLabel: '계정 삭제',
    danger: true,
    input: { label: '비밀번호 확인', type: 'password' },
  })
  if (!r.ok) return
  try {
    await authApi.deleteMe(r.value)
    auth.clear()
    ui.toast('계정을 삭제했어요')
    router.push('/')
  } catch (e) {
    ui.toast(e instanceof ApiError ? e.fields?.password || e.message : '삭제하지 못했어요.')
  }
}
</script>

<template>
  <MyPageShell>
    <h1 class="h1">계정 설정</h1>
    <p class="sub">기본 정보와 영상 보관 방식을 확인해요.</p>
    <div class="card" style="margin-top: 20px; max-width: 640px">
      <h2>기본 정보</h2>
      <div style="margin-top: 14px; display: flex; flex-direction: column; gap: 14px">
        <div>
          <label class="f" for="an">이름</label>
          <input id="an" v-model="name" class="in" :class="{ bad: nameErr }" />
          <div v-if="nameErr" class="err" role="alert">{{ nameErr }}</div>
        </div>
        <div>
          <label class="f" for="ae">이메일</label>
          <input id="ae" class="in" :value="auth.user?.email" disabled />
        </div>
        <div><button class="btn btn-p" :disabled="busy" @click="saveName">저장</button></div>
      </div>
    </div>
    <div class="card" style="margin-top: 16px; max-width: 640px">
      <h2>영상 보관</h2>
      <p style="margin-top: 8px; color: #334155; font-size: 15px">
        회차나 프로젝트를 삭제하면 영상·전사문·리포트에 바로 접근할 수 없게 되고, 삭제가 예약돼요. 자동 삭제 기한은 확정되면 이곳에 안내해 드릴게요.
      </p>
    </div>
    <div class="card" style="margin-top: 16px; max-width: 640px">
      <h2>계정</h2>
      <div style="margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap">
        <button class="btn" @click="logout">로그아웃</button>
        <button class="btn btn-danger" @click="deleteAccount">계정 삭제</button>
      </div>
    </div>
  </MyPageShell>
</template>
