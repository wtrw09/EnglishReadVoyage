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

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
