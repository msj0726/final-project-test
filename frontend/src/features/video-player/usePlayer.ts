import { onBeforeUnmount, ref, type Ref } from 'vue'

/**
 * 리포트 플레이어 엔진.
 * - video 요소가 있으면 그 재생 시각(currentTime)을 기준으로 동작한다.
 * - 없으면(실제 영상 인증 방식이 정해지기 전) 시계만 흘리는 시안용 엔진으로 동작한다.
 */
export function usePlayer(duration: Ref<number>, video: Ref<HTMLVideoElement | null>) {
  const t = ref(0)
  const playing = ref(false)
  const speed = ref(1)
  let stopAt: number | null = null
  let timer: ReturnType<typeof setInterval> | null = null

  const clear = () => {
    if (timer) clearInterval(timer)
    timer = null
  }
  const maxT = () => Math.min(duration.value, video.value?.duration || duration.value)

  function pause() {
    playing.value = false
    clear()
    video.value?.pause()
  }
  function tick() {
    const v = video.value
    if (v) t.value = v.currentTime
    else t.value += 0.1 * speed.value
    if (stopAt != null && t.value >= stopAt) {
      stopAt = null
      pause()
    } else if (t.value >= maxT() - 0.05 || (v && v.ended)) {
      t.value = maxT()
      pause()
    }
  }
  function play() {
    if (t.value >= maxT() - 0.05) seek(0)
    playing.value = true
    clear()
    const v = video.value
    if (v) {
      v.playbackRate = speed.value
      v.play().catch(() => pause()) // 자동재생 차단 등
    }
    timer = setInterval(tick, 100)
  }
  function seek(s: number) {
    t.value = Math.min(maxT(), Math.max(0, s))
    if (video.value) video.value.currentTime = t.value
  }
  function playRange(a: number, b: number) {
    seek(a)
    stopAt = b
    play()
  }
  function toggle() {
    if (playing.value) pause()
    else {
      stopAt = null
      play()
    }
  }
  function cycleSpeed() {
    speed.value = speed.value === 1 ? 2 : speed.value === 2 ? 4 : 1
    if (video.value) video.value.playbackRate = speed.value
  }
  onBeforeUnmount(clear)
  return { t, playing, speed, seek, playRange, toggle, pause, cycleSpeed }
}
