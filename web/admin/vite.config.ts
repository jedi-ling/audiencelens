import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// 独立的端口(5200)——与用户产品前端(5199)分开，可以单独部署到内网/VPN 域名，
// 不共享同一个构建产物、不共享同一个访问入口。仍然只是同一个后端(8000)的另一个消费者。
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5200,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
})
