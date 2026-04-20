/**
 * VirtualContent.vue - 虚拟内容渲染组件
 *
 * 功能：渲染 HTML 内容并提供交互支持
 * - 图片懒加载（IntersectionObserver）
 * - 事件代理（contextmenu、click、mousedown）
 * - 内容更新监听
 */
<template>
  <div 
    ref="containerRef"
    class="virtual-content"
  >
    <div class="content-wrapper" v-html="content"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'

const props = defineProps<{
  content: string
  visibleThreshold?: number  // 元素可见多少比例时加载
}>()

const emit = defineEmits<{
  (e: 'contextmenu', event: MouseEvent): void
  (e: 'click', event: MouseEvent): void
  (e: 'mousedown', event: MouseEvent): void
}>()

const containerRef = ref<HTMLElement | null>(null)
const visibleThreshold = props.visibleThreshold ?? 0.1  // 10% 可见时触发

// 懒加载图片：只有图片进入视口才加载真实 src
const lazyLoadImages = (): IntersectionObserver | null => {
  if (!containerRef.value) return null
  
  const images = containerRef.value.querySelectorAll('img[data-src]')
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target as HTMLImageElement
        const src = img.getAttribute('data-src')
        if (src) {
          img.src = src
          img.removeAttribute('data-src')
          img.classList.remove('lazy-loading')
        }
        observer.unobserve(img)
      }
    })
  }, {
    root: containerRef.value,
    rootMargin: '100px',  // 提前 100px 开始加载
    threshold: visibleThreshold
  })
  
  images.forEach(img => {
    img.classList.add('lazy-loading')
    observer.observe(img)
  })
  
  return observer
}

let imageObserver: IntersectionObserver | null = null

// 初始化时预处理图片（将 src 移到 data-src）
watch(() => props.content, async (newContent) => {
  // 等待 DOM 更新
  await nextTick()
  
  if (containerRef.value) {
    // 将所有图片的 src 替换为 data-src，延迟加载
    const wrapper = containerRef.value.querySelector('.content-wrapper')
    if (wrapper) {
      wrapper.innerHTML = newContent.replace(
        /src="([^"]*)"/g,
        'data-src="$1" class="lazy-loading"'
      )
    }
    
    // 停止旧的 observer
    if (imageObserver) {
      imageObserver.disconnect()
    }
    
    // 启动新的懒加载 observer
    imageObserver = lazyLoadImages()
  }
}, { immediate: true })

onMounted(() => {
  imageObserver = lazyLoadImages()
  
  // 添加原生事件监听，处理动态内容的点击和右键菜单
  if (containerRef.value) {
    containerRef.value.addEventListener('contextmenu', handleContextMenu as EventListener)
    containerRef.value.addEventListener('click', handleClick as EventListener)
    containerRef.value.addEventListener('mousedown', handleMouseDown as EventListener)
  }
})

onUnmounted(() => {
  if (imageObserver) {
    imageObserver.disconnect()
    imageObserver = null
  }
  // 移除事件监听
  if (containerRef.value) {
    containerRef.value.removeEventListener('contextmenu', handleContextMenu as EventListener)
    containerRef.value.removeEventListener('click', handleClick as EventListener)
    containerRef.value.removeEventListener('mousedown', handleMouseDown as EventListener)
  }
})

// 处理右键菜单事件
const handleContextMenu = (e: Event) => {
  emit('contextmenu', e as MouseEvent)
}

// 处理点击事件
const handleClick = (e: Event) => {
  emit('click', e as MouseEvent)
}

// 处理鼠标按下事件
const handleMouseDown = (e: Event) => {
  emit('mousedown', e as MouseEvent)
}
</script>

<style scoped>
.virtual-content {
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
  height: 100%;
  width: 100%;
}

.content-wrapper {
  width: 100%;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

/* 图片懒加载样式 */
:deep(.lazy-loading) {
  opacity: 0;
  transition: opacity 0.3s ease-in-out;
}

:deep(img:not(.lazy-loading)) {
  opacity: 1;
}
</style>
