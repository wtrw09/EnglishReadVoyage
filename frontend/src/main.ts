import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

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
    
    // 获取精确状态栏高度设置到CSS变量
    const info = await StatusBar.getInfo()
    if (info && info.height && info.height > 0) {
      document.documentElement.style.setProperty(
        '--safe-area-top',
        `${info.height}px`
      )
      // 同时设置到body padding作为兜底
      document.body.style.paddingTop = `${info.height}px`
    }
  } catch {
    // StatusBar插件不可用（如在浏览器中），使用CSS默认值
    // CSS中已有 .is-native-shell .van-nav-bar--fixed { padding-top: var(--safe-area-top, 24px) !important; }
  }
}

const app = createApp(App)

app.use(createPinia())
app.use(router)

// DOM准备好后初始化安全区域
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(initSafeArea, 100) // 延迟100ms确保CSS变量已设置
  })
} else {
  setTimeout(initSafeArea, 100)
}

app.mount('#app')
