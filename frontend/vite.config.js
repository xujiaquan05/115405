import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  // Vitest 設定：用 jsdom 模擬瀏覽器環境（localStorage、DOM），
  // globals 讓 describe/it/expect 免匯入。
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
