import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发：vite 5173，/api 代理到 FastAPI 8600
// 生产：npm run build → dist/，由 FastAPI StaticFiles 单端口托管
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8600',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1200,
  },
})
