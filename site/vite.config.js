import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { zanim } from '@zanim/web/vite'

export default defineConfig({
  base: '/zanim/',
  plugins: [zanim(), vue()],
  build: { target: 'es2022' },
})
