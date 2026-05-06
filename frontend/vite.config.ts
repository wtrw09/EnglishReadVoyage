import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from 'unplugin-vue-components/resolvers'
import { resolve } from 'path'

// HarmonyOS $rawfile 协议兼容插件
function harmonyCompat(): Plugin {
  return {
    name: 'harmony-compat',
    enforce: 'post',
    transformIndexHtml(html: string) {
      return html
        .replace(/\scrossorigin(="[^"]*")?/g, '')
        .replace(/\stype="module"/g, '')
    }
  }
}

// https://vitejs.dev/config/
export default defineConfig({
  base: './',
  plugins: [
    vue(),
    Components({
      resolvers: [VantResolver()],
    }),
    // HarmonyOS $rawfile 协议兼容：移除 crossorigin + type=module
    harmonyCompat(),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    // 默认输出到 frontend/dist；可通过 VITE_OUT_DIR 环境变量覆盖
    outDir: process.env.VITE_OUT_DIR || 'dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
        format: 'iife',
        name: 'app',
        entryFileNames: 'assets/app.js',
        assetFileNames: 'assets/[name].[ext]'
      }
    }
  },
  // HarmonyOS $rawfile 兼容补丁：输出为 IIFE（非 ES Module），
  // 因为 $rawfile:// 协议下 ES Module 会被 CORS 阻止
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
        ws: true,
      },
      // 使用正则，必须带尾斜杠才代理，避免误伤前端路由 /audiobook
      '^/books/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
      '^/audio/': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
