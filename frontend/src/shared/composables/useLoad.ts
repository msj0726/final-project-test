import { ref, type Ref } from 'vue'
import { ApiError } from '@/shared/api'

/** 비동기 로딩 상태 도우미: data / loading / error 를 한 번에 관리 */
export function useLoad<T>(fn: () => Promise<T>) {
  const data = ref<T | null>(null) as Ref<T | null>
  const loading = ref(true)
  const error = ref('')
  async function reload() {
    loading.value = true
    error.value = ''
    try {
      data.value = await fn()
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '불러오지 못했어요. 잠시 후 다시 시도해 주세요.'
    } finally {
      loading.value = false
    }
  }
  reload()
  return { data, loading, error, reload }
}
