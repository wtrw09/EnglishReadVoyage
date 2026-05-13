import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import AudiobookPlayer from '@/views/AudiobookPlayer.vue'

// 导入Vant样式
import 'vant/lib/index.css'
// 导入Vant图标样式
import 'vant/es/icon/style/index'
// 导入Font Awesome样式
import '@fortawesome/fontawesome-free/css/all.min.css'
// 导入自定义样式（覆盖Vant默认样式）
import './style.css'
// 导入Vant触摸模拟器（支持PC端鼠标事件）
import '@vant/touch-emulator'

// 初始化安全区域和状态栏高度
async function initSafeArea() {
  // 尝试通过Capacitor StatusBar插件防止WebView重叠状态栏
  try {
    const { StatusBar, Style } = await import('@capacitor/status-bar')
    
    // 核心：阻止状态栏覆盖WebView内容（Capacitor原生处理，比WindowCompat更可靠）
    await StatusBar.setOverlaysWebView({ overlay: false })
    
    // 设置白色背景状态栏 + 深色文字图标
    await StatusBar.setBackgroundColor({ color: '#ffffff' })
    await StatusBar.setStyle({ style: Style.Dark })
  } catch {
    // StatusBar插件不可用（如在浏览器中），无需手动设置padding
    // setOverlaysWebView({ overlay: false }) 已原生处理好状态栏避让
  }
}

const app = createApp(App)

app.use(createPinia())
app.use(router)
// 强制注册 AudiobookPlayer 组件，防止 Rollup 树摇优化移除
app.component('AudiobookPlayer', AudiobookPlayer)

// DOM准备好后初始化安全区域
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(initSafeArea, 100) // 延迟确保 StatusBar 插件初始化
  })
} else {
  setTimeout(initSafeArea, 100)
}

app.mount('#app')
