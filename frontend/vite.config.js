import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],

  server: {
    host: '0.0.0.0',
    allowedHosts: ['mebod.clouda.dpdns.org'],

    // 把 /api 與 /ws 轉發到本機後端。
    // 這樣前端一律用「同一個網域」的相對路徑呼叫 API，
    // 不論從 localhost 或對外網域（隧道）開啟都能運作
    // —— 若寫死 localhost:8000，遠端訪客會連到「自己的電腦」而失敗。
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },

  // Vitest 設定：用 jsdom 模擬瀏覽器環境（localStorage、DOM），
  // globals 讓 describe/it/expect 免匯入。
  test: {
    environment: 'jsdom',
    globals: true,
  },
})