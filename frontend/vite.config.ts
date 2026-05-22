import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from 'unplugin-vue-components/resolvers'
import { resolve } from 'path'

// HarmonyOS $rawfile 协议兼容插件：只在构建时生效
// 开发模式下必须保留 type="module" 供浏览器正确加载 ES Module
function harmonyCompat(): Plugin {
  return {
    name: 'harmony-compat',
    enforce: 'post',
    transformIndexHtml(html: string, ctx) {
      // ctx.server 存在时说明是 dev server，跳过兼容转换
      if (ctx?.server) return html
      return html
        .replace(/\scrossorigin(="[^"]*")?/g, '')
        .replace(/\stype="module"/g, '')
        .replace(/(<script)(\s+src=)/g, '$1 defer$2')
        .replace(/href="\.\/logo\.svg"/g, 'href="/logo.svg"')
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
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            // 禁用 SSE 响应缓冲，确保 progress 事件实时触发
            proxyRes.headers['x-accel-buffering'] = 'no'
            proxyRes.headers['cache-control'] = 'no-cache'
          })
        }
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
