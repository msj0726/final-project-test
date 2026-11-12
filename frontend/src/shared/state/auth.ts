import { reactive } from 'vue'
import { auth as authApi, clearApiCache, tokenStore } from '../api'
import type { Agreements, User } from '../api/types'

// 라우터·상태 라이브러리를 늘리지 않으려고 Pinia 대신 모듈 단위 reactive 객체를 쓴다.
export const auth = reactive({
  user: null as User | null,
  ready: false,
  get loggedIn() {
    return !!this.user
  },
  /** 앱 시작 시 저장된 토큰으로 내 정보 복원 */
  async restore() {
    if (tokenStore.get()) {
      try {
        this.user = (await authApi.me()).user
      } catch {
        tokenStore.set(null)
      }
    }
    this.ready = true
  },
  async login(email: string, password: string) {
    const r = await authApi.login(email, password)
    tokenStore.set(r.tokens)
    this.user = r.user
  },
  async signup(b: { name: string; email: string; password: string; agreements: Agreements }) {
    await authApi.signup(b)
    await this.login(b.email, b.password)
  },
  async logout() {
    await authApi.logout()
    this.clear()
  },
  async rename(name: string) {
    this.user = await authApi.updateMe({ name })
  },
  clear() {
    tokenStore.set(null)
    clearApiCache()
    this.user = null
  },
})
export const useAuth = () => auth
