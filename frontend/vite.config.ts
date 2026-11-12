import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  // 백엔드(FastAPI)는 기본 8000. 브라우저는 같은 출처(5173)로 호출하고 Vite 가 /api·/healthz 를 넘겨 준다.
  const target = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: { proxy: { '/api': { target, changeOrigin: true }, '/healthz': { target, changeOrigin: true }, '/readyz': { target, changeOrigin: true } } },
  }
})
