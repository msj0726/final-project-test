import { reactive } from 'vue'

export interface ConfirmOpts {
  title: string
  body?: string
  okLabel?: string
  danger?: boolean
  /** 입력 필드(비밀번호 확인 등) */
  input?: { label: string; type?: string }
}

let toastTimer: ReturnType<typeof setTimeout> | undefined
let resolver: ((v: { ok: boolean; value: string }) => void) | null = null

export const ui = reactive({
  toastMsg: '',
  confirmOpts: null as ConfirmOpts | null,
  toast(msg: string) {
    this.toastMsg = msg
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => (this.toastMsg = ''), 2400)
  },
  confirm(opts: ConfirmOpts) {
    this.confirmOpts = opts
    return new Promise<{ ok: boolean; value: string }>((res) => (resolver = res))
  },
  answer(ok: boolean, value = '') {
    resolver?.({ ok, value })
    resolver = null
    this.confirmOpts = null
  },
})
export const useUi = () => ui
