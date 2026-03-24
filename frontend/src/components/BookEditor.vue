<template>
  <div class="editor-component">
    <!-- 上下文菜单 -->
    <div
      v-show="showContextMenu"
      class="context-menu"
      :style="{ left: contextMenuX + 'px', top: contextMenuY + 'px' }"
    >
      <div class="context-menu-item" @click="handlePaste">
        <van-icon name="records-o" />
        <span>粘贴</span>
      </div>
      <div class="context-menu-item" @click="handleInsertImage">
        <van-icon name="photo-o" />
        <span>插入图片</span>
      </div>
      <div class="context-menu-item" @click="insertPageBreak">
        <van-icon name="bookmark-o" />
        <span>插入换页符</span>
      </div>
    </div>
    <!-- 隐藏的文件输入框 -->
    <input
      ref="imageInputRef"
      type="file"
      accept="image/*"
      style="display: none"
      @change="onImageFileSelected"
    />
    <!-- 查找替换浮动面板 -->
    <div
      v-if="showFindReplace"
      ref="findReplacePanelRef"
      class="find-replace-panel"
      :style="findReplacePanelStyle"
    >
      <div class="find-replace-header" @mousedown="startDragPanel">
        <span>查找和替换</span>
        <van-icon name="cross" class="close-btn" @click.stop="closeFindReplace" />
      </div>
      <div class="find-replace-content">
        <div class="find-row">
          <van-field
            ref="findInputRef"
            v-model="findText"
            placeholder="查找内容"
            @update:model-value="onFindTextChange"
            @keydown.enter="doFindNext"
          >
            <template #button>
              <div class="nav-buttons">
                <van-button size="small" type="default" @click="doFindPrev">上一个</van-button>
                <van-button size="small" type="default" @click="doFindNext">下一个</van-button>
              </div>
            </template>
          </van-field>
        </div>
        <div class="replace-row">
          <van-field
            ref="replaceInputRef"
            v-model="replaceText"
            placeholder="替换为（为空则删除）"
            @keydown.enter="doReplace"
          >
            <template #button>
              <van-button size="small" type="default" @click="doReplace">替换</van-button>
            </template>
          </van-field>
        </div>
        <div class="replace-actions">
          <van-button size="small" type="default" @click="doReplaceAll">全部替换</van-button>
          <span class="find-count">{{ findCount > 0 ? `${currentFindIndex + 1}/${findCount} 处匹配` : findCount === 0 && findText ? '无匹配' : '' }}</span>
        </div>
      </div>
    </div>
    <!-- 图片预览弹窗（非模态，无遮罩）- 使用纯 div 避免 teleport 导致的定位问题 -->
    <div
      v-if="showImagePreview"
      class="image-preview-popup-wrapper"
      :style="imagePreviewStyle"
    >
      <div class="image-preview-header" @mousedown="startDragImagePreview">
        <span>图片预览</span>
        <van-icon name="cross" class="close-btn" @click="showImagePreview = false" />
      </div>
      <div class="image-preview-content">
        <img v-if="previewImageUrl" :src="previewImageUrl" class="preview-image" alt="预览" />
        <div v-else class="loading-placeholder">加载中...</div>
      </div>
    </div>
    <div ref="editorRef" class="codemirror-editor"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { EditorView, keymap, Decoration } from '@codemirror/view'
import { EditorState, StateField, StateEffect } from '@codemirror/state'
import { markdown } from '@codemirror/lang-markdown'
import { indentWithTab } from '@codemirror/commands'
import { syntaxHighlighting, HighlightStyle } from '@codemirror/language'
import { tags } from '@lezer/highlight'
import { showToast, showNotify } from 'vant'

interface Props {
  modelValue: string
  bookId?: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'save': []
}>()

const editorRef = ref<HTMLDivElement | null>(null)
let editorView: EditorView | null = null

// 查找替换相关状态
const findText = ref('')
const replaceText = ref('')
const findCount = ref(0)
const currentFindIndex = ref(-1)
const showFindReplace = ref(false)

// 面板拖动相关状态
const findReplacePanelStyle = ref<Record<string, string>>({})
let isDraggingPanel = false
let panelStartX = 0
let panelStartY = 0
let panelLeft = 0
let panelTop = 0

// 上下文菜单相关状态
const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
let longPressTimer: number | null = null

// 图片预览相关
const showImagePreview = ref(false)
const previewImageUrl = ref('')

// 插入图片相关
const imageInputRef = ref<HTMLInputElement | null>(null)
let imageInsertPosition = 0 // 记录插入图片的位置

// 弹窗拖动相关
let isDraggingImagePreview = false
let imageDragStartX = 0
let imageDragStartY = 0
let imageDragStartLeft = 0
let imageDragStartTop = 0

// 计算弹窗样式 (按屏幕比例)
const imagePreviewStyle = ref<Record<string, string>>({})

const updateImagePreviewStyle = () => {
  // 弹窗更小一点，放在右侧中央
  const width = Math.min(window.innerWidth * 0.35, 300)
  const height = Math.min(window.innerHeight * 0.45, 350)
  // 右侧中央（使用 fixed 定位，相对于视口）
  const left = window.innerWidth - width - 20
  const top = (window.innerHeight - height) / 2

  imagePreviewStyle.value = {
    width: `${width}px`,
    height: `${height}px`,
    left: `${left}px`,
    top: `${top}px`,
    position: 'fixed',  // 相对于视口定位
    transform: 'none',
    zIndex: '9999'  // 确保在最顶层
  }
}

// 拖动图片预览弹窗（完全模仿查找面板的实现）
const startDragImagePreview = (e: MouseEvent) => {
  // 排除点击关闭按钮的情况
  const target = e.target as HTMLElement
  if (target.closest('.close-btn')) return

  isDraggingImagePreview = true
  imageDragStartX = e.clientX
  imageDragStartY = e.clientY

  // 获取弹窗当前位置
  const popup = document.querySelector('.image-preview-popup-wrapper') as HTMLElement
  if (popup) {
    const rect = popup.getBoundingClientRect()
    imageDragStartLeft = rect.left
    imageDragStartTop = rect.top
  }

  e.preventDefault()
}

const onDragImagePreviewMove = (e: MouseEvent) => {
  if (!isDraggingImagePreview) return

  const dx = e.clientX - imageDragStartX
  const dy = e.clientY - imageDragStartY

  imagePreviewStyle.value = {
    ...imagePreviewStyle.value,
    left: `${imageDragStartLeft + dx}px`,
    top: `${imageDragStartTop + dy}px`,
    transform: 'none'
  }
}

const onDragImagePreviewUp = (e: MouseEvent) => {
  if (isDraggingImagePreview) {
    const dx = e.clientX - imageDragStartX
    const dy = e.clientY - imageDragStartY
    imageDragStartLeft = imageDragStartLeft + dx
    imageDragStartTop = imageDragStartTop + dy
  }
  isDraggingImagePreview = false
}

// 从文本中提取图片链接
const extractImageLink = (content: string, pos: number): string | null => {
  // 匹配 Markdown 图片语法: ![alt](path)
  const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g
  let match
  while ((match = imageRegex.exec(content)) !== null) {
    const start = match.index
    const end = start + match[0].length
    // 检查点击位置是否在图片语法范围内
    if (pos >= start && pos <= end) {
      return match[2] // 返回图片路径
    }
  }
  return null
}

// 预览图片
const previewImage = async (imagePath: string) => {
  if (!props.bookId) {
    showToast('无法获取书籍信息')
    return
  }

  try {
    // 先显示弹窗，然后加载图片
    previewImageUrl.value = ''
    showImagePreview.value = true

    // 调用后端 API 获取图片
    const token = localStorage.getItem('token')
    const response = await fetch(
      `/api/v1/books/${props.bookId}/preview-image?filename=${encodeURIComponent(imagePath)}`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      }
    )

    if (!response.ok) {
      showImagePreview.value = false
      throw new Error('图片加载失败')
    }

    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    previewImageUrl.value = url
  } catch (error) {
    console.error('预览图片失败:', error)
    showToast('无法预览图片')
    showImagePreview.value = false
  }
}

// 搜索高亮相关
const searchHighlightMark = Decoration.mark({ class: 'cm-searchMatch' })
const searchHighlightSelectedMark = Decoration.mark({ class: 'cm-searchMatch cm-searchMatch-selected' })

// 定义设置搜索高亮的效果
const setSearchHighlightEffect = StateEffect.define<{ matches: { pos: number; length: number }[]; currentIndex: number }>()

// 搜索高亮 StateField
const searchHighlightField = StateField.define<any>({
  create() {
    return Decoration.none
  },
  update(decorations, tr) {
    for (const e of tr.effects) {
      if (e.is(setSearchHighlightEffect)) {
        const { matches, currentIndex } = e.value
        const deco: any[] = []
        for (let i = 0; i < matches.length; i++) {
          const match = matches[i]
          const isSelected = i === currentIndex
          deco.push(
            isSelected
              ? searchHighlightSelectedMark.range(match.pos, match.pos + match.length)
              : searchHighlightMark.range(match.pos, match.pos + match.length)
          )
        }
        return Decoration.set(deco, true)
      }
    }
    return decorations.map(tr.changes)
  },
  provide: (f) => EditorView.decorations.from(f)
})

// 转义正则表达式特殊字符
const escapeRegex = (str: string): string => {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 自定义滚动到目标位置（将目标放到屏幕上 1/3 处）
const scrollToPosition = (targetPos: number) => {
  if (!editorView) return

  // 计算滚动位置：将目标放到屏幕上 1/3 处
  const editorRect = editorView.scrollDOM.getBoundingClientRect()
  const targetOffset = editorRect.height / 3

  // 获取目标位置的 DOM 坐标
  const coords = editorView.coordsAtPos(targetPos)
  if (!coords) {
    // 如果无法获取坐标，使用默认滚动
    editorView.dispatch({ scrollIntoView: true })
    return
  }

  // 计算需要滚动的距离
  const scrollTop = editorView.scrollDOM.scrollTop
  const newScrollTop = coords.top - editorRect.top + scrollTop - targetOffset

  // 如果已经到底部，无法达到 1/3 位置，则滚动到底部
  const maxScroll = editorView.scrollDOM.scrollHeight - editorRect.height
  if (newScrollTop > maxScroll) {
    editorView.scrollDOM.scrollTop = maxScroll
  } else {
    editorView.scrollDOM.scrollTop = newScrollTop
  }
}

// 获取所有匹配位置（不区分大小写）
const getMatchPositions = (): { pos: number; length: number }[] => {
  if (!findText.value || !editorView) return []
  const content = editorView.state.doc.toString()
  const matches: { pos: number; length: number }[] = []
  const regex = new RegExp(escapeRegex(findText.value), 'gi')
  let match
  while ((match = regex.exec(content)) !== null) {
    matches.push({ pos: match.index, length: match[0].length })
  }
  return matches
}

// 计算匹配数量（不区分大小写）
const updateFindCount = () => {
  if (!findText.value) {
    findCount.value = 0
    // 清除高亮
    if (editorView) {
      editorView.dispatch({
        effects: setSearchHighlightEffect.of({ matches: [], currentIndex: -1 })
      })
    }
    return
  }
  try {
    const content = editorView?.state.doc.toString() || ''
    const regex = new RegExp(escapeRegex(findText.value), 'gi')
    const matches = content.match(regex)
    findCount.value = matches ? matches.length : 0
  } catch {
    findCount.value = 0
  }
}

// 更新搜索高亮
const updateSearchHighlight = () => {
  if (!editorView || !findText.value) {
    return
  }
  const matches = getMatchPositions()
  if (matches.length > 0) {
    editorView.dispatch({
      effects: setSearchHighlightEffect.of({
        matches,
        currentIndex: currentFindIndex.value
      })
    })
  }
}

// 查找文本变化时更新计数
const onFindTextChange = () => {
  updateFindCount()
  if (findCount.value > 0) {
    // 有匹配，自动定位到第一个
    currentFindIndex.value = 0
    const matches = getMatchPositions()
    if (editorView && matches.length > 0) {
      const match = matches[0]
      editorView.dispatch({
        selection: { anchor: match.pos, head: match.pos + match.length }
      })
      // 使用自定义滚动
      scrollToPosition(match.pos)
    }
    // 更新高亮
    updateSearchHighlight()
  } else {
    currentFindIndex.value = -1
  }
}

// 查找上一个 - 使用手动定位
const doFindPrev = () => {
  if (!findText.value) {
    showToast('请输入要查找的内容')
    return
  }
  updateFindCount()
  if (findCount.value === 0) {
    showToast('未找到匹配内容')
    return
  }
  // 获取所有匹配位置
  const matches = getMatchPositions()
  if (matches.length === 0) return

  // 向前导航：索引减1
  const newIndex = (currentFindIndex.value - 1 + matches.length) % matches.length
  currentFindIndex.value = newIndex

  // 跳转到对应位置
  if (editorView) {
    const match = matches[newIndex]
    editorView.dispatch({
      selection: { anchor: match.pos, head: match.pos + match.length }
    })
    // 使用自定义滚动
    scrollToPosition(match.pos)
  }
  // 更新高亮
  updateSearchHighlight()
}

// 查找下一个 - 使用手动定位
const doFindNext = () => {
  if (!findText.value) {
    showToast('请输入要查找的内容')
    return
  }
  updateFindCount()
  if (findCount.value === 0) {
    showToast('未找到匹配内容')
    return
  }
  // 获取所有匹配位置
  const matches = getMatchPositions()
  if (matches.length === 0) return

  // 向后导航：索引加1
  const newIndex = (currentFindIndex.value + 1) % matches.length
  currentFindIndex.value = newIndex

  // 跳转到对应位置
  if (editorView) {
    const match = matches[newIndex]
    editorView.dispatch({
      selection: { anchor: match.pos, head: match.pos + match.length }
    })
    // 使用自定义滚动
    scrollToPosition(match.pos)
  }
  // 更新高亮
  updateSearchHighlight()
}

// 执行替换（替换当前选中的匹配）
const doReplace = () => {
  if (!findText.value) {
    showToast('请输入要查找的内容')
    return
  }

  updateFindCount()
  if (findCount.value === 0) {
    showToast('未找到匹配内容')
    return
  }

  try {
    if (!editorView) return
    
    const matches = getMatchPositions()
    if (matches.length === 0) {
      showToast('未找到匹配内容')
      return
    }

    // 只替换当前索引位置的匹配
    const currentMatch = matches[currentFindIndex.value]

    // 使用 CodeMirror 的变更API
    editorView.dispatch({
      changes: {
        from: currentMatch.pos,
        to: currentMatch.pos + currentMatch.length,
        insert: replaceText.value
      }
    })

    // 更新匹配位置（因为内容变了）
    updateFindCount()

    // 更新当前索引
    if (findCount.value > 0) {
      // 如果还有匹配，保持在当前位置（如果已到末尾则跳到开头）
      if (currentFindIndex.value >= findCount.value) {
        currentFindIndex.value = 0
      }
      showNotify({ type: 'success', message: '已替换1处', duration: 1500 })
    } else {
      currentFindIndex.value = 0
      showNotify({ type: 'success', message: '已替换（已删除）', duration: 1500 })
    }
  } catch {
    showToast('替换失败')
  }
}

// 全部替换
const doReplaceAll = () => {
  if (!findText.value) {
    showToast('请输入要查找的内容')
    return
  }

  try {
    if (!editorView) return
    
    const content = editorView.state.doc.toString()
    const regex = new RegExp(escapeRegex(findText.value), 'gi')
    const matches = content.match(regex)
    const count = matches ? matches.length : 0

    if (count === 0) {
      showToast('未找到匹配内容')
      return
    }

    // 获取新内容
    const newContent = content.replace(regex, replaceText.value)
    
    // 使用 CodeMirror 替换全部内容
    editorView.dispatch({
      changes: {
        from: 0,
        to: content.length,
        insert: newContent
      }
    })
    
    findCount.value = 0
    currentFindIndex.value = 0

    const action = replaceText.value === '' ? '已删除' : `已替换 ${count} 处`
    showNotify({ type: 'success', message: action, duration: 1500 })
  } catch {
    showToast('替换失败')
  }
}

// 打开查找替换面板（使用自定义面板）
const openFindReplace = () => {
  if (!editorView) return

  // 获取选中文本
  const selection = editorView.state.selection.main
  const selectedText = selection.from !== selection.to
    ? editorView.state.sliceDoc(selection.from, selection.to)
    : ''

  // 显示自定义面板
  showFindReplace.value = true

  // 如果有选中文本，填充到搜索框
  if (selectedText) {
    findText.value = selectedText
    updateFindCount()
    if (findCount.value > 0) {
      // 有匹配，自动定位到第一个
      currentFindIndex.value = 0
      const matches = getMatchPositions()
      if (matches.length > 0) {
        const match = matches[0]
        editorView.dispatch({
          selection: { anchor: match.pos, head: match.pos + match.length }
        })
        // 使用自定义滚动
        scrollToPosition(match.pos)
      }
      // 更新高亮
      updateSearchHighlight()
    } else {
      currentFindIndex.value = -1
    }
  }
}

// 关闭查找替换面板
const closeFindReplace = () => {
  showFindReplace.value = false
  findText.value = ''
  replaceText.value = ''
  findCount.value = 0
  currentFindIndex.value = 0
  // 清除高亮
  if (editorView) {
    editorView.dispatch({
      effects: setSearchHighlightEffect.of({ matches: [], currentIndex: -1 })
    })
  }
  // 重置面板位置
  panelLeft = 0
  panelTop = 0
  findReplacePanelStyle.value = {}
}

// 面板拖动功能
const startDragPanel = (e: MouseEvent) => {
  // 排除点击关闭按钮的情况
  const target = e.target as HTMLElement
  if (target.closest('.close-btn')) return

  isDraggingPanel = true
  panelStartX = e.clientX
  panelStartY = e.clientY

  // 获取面板当前位置
  const panel = document.querySelector('.find-replace-panel') as HTMLElement
  if (panel) {
    const rect = panel.getBoundingClientRect()
    panelLeft = rect.left
    panelTop = rect.top
  }

  e.preventDefault()
}

const onDragPanelMove = (e: MouseEvent) => {
  if (!isDraggingPanel) return

  const dx = e.clientX - panelStartX
  const dy = e.clientY - panelStartY
  findReplacePanelStyle.value = {
    left: `${panelLeft + dx}px`,
    top: `${panelTop + dy}px`,
    transform: 'none'
  }
}

const onDragPanelUp = (e: MouseEvent) => {
  if (isDraggingPanel) {
    const dx = e.clientX - panelStartX
    const dy = e.clientY - panelStartY
    panelLeft = panelLeft + dx
    panelTop = panelTop + dy
  }
  isDraggingPanel = false
}

// 关闭上下文菜单
const closeContextMenu = () => {
  showContextMenu.value = false
}

// 处理粘贴
const handlePaste = async () => {
  closeContextMenu()
  try {
    const text = await navigator.clipboard.readText()
    if (text && editorView) {
      const selection = editorView.state.selection.main
      editorView.dispatch({
        changes: {
          from: selection.from,
          to: selection.to,
          insert: text
        }
      })
      showNotify({ type: 'success', message: '已粘贴', duration: 1500 })
    }
  } catch {
    showToast('粘贴失败，请检查剪贴板权限')
  }
}

// 插入分页符
const insertPageBreak = () => {
  closeContextMenu()
  if (!editorView) return

  const selection = editorView.state.selection.main
  const pageBreak = '\n---\n'

  editorView.dispatch({
    changes: {
      from: selection.from,
      to: selection.to,
      insert: pageBreak
    }
  })
  showNotify({ type: 'success', message: '已插入换页符', duration: 1500 })
}

// 处理插入图片（打开文件选择器）
const handleInsertImage = () => {
  closeContextMenu()
  if (!editorView) return

  // 记录当前光标位置
  const selection = editorView.state.selection.main
  imageInsertPosition = selection.from

  // 打开文件选择器
  if (imageInputRef.value) {
    imageInputRef.value.click()
  }
}

// 图片文件选择后的处理
const onImageFileSelected = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file || !editorView || !props.bookId) {
    // 清理 input
    if (target) target.value = ''
    return
  }

  // 显示上传中提示
  const uploadingToast = showToast({
    message: '正在上传图片...',
    forbidClick: true,
    duration: 0 // 不会自动关闭
  })

  try {
    // 获取 token
    const token = localStorage.getItem('token')

    // 创建 FormData
    const formData = new FormData()
    formData.append('file', file)

    // 调用后端 API 上传图片
    const response = await fetch(
      `/api/v1/books/${props.bookId}/upload-image`,
      {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData
      }
    )

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.detail || '上传失败')
    }

    const data = await response.json()
    const imagePath = data.path // 返回的是 ./assets/filename 格式

    // 在光标位置插入图片 Markdown
    const imageMarkdown = `\n![image](${imagePath})\n`
    editorView.dispatch({
      changes: {
        from: imageInsertPosition,
        to: imageInsertPosition,
        insert: imageMarkdown
      }
    })

    uploadingToast.close()
    showNotify({ type: 'success', message: '图片已插入', duration: 1500 })
  } catch (error) {
    console.error('上传图片失败:', error)
    uploadingToast.close()
    showToast('上传图片失败，请重试')
  } finally {
    // 清理 input 以便重复选择同一文件
    if (target) target.value = ''
  }
}

// 显示上下文菜单
const showContextMenuAt = (x: number, y: number) => {
  // 确保菜单位于视口内
  const menuWidth = 140
  const menuHeight = 120 // 3个菜单项，每个约40px高
  const viewportWidth = window.innerWidth
  const viewportHeight = window.innerHeight

  let finalX = x
  let finalY = y

  if (x + menuWidth > viewportWidth) {
    finalX = viewportWidth - menuWidth - 10
  }
  if (y + menuHeight > viewportHeight) {
    finalY = viewportHeight - menuHeight - 10
  }

  contextMenuX.value = finalX
  contextMenuY.value = finalY
  showContextMenu.value = true
}

// 处理右键点击
const handleContextMenu = (e: MouseEvent) => {
  // 检查点击是否在编辑器区域内
  const target = e.target as HTMLElement
  const editorElement = editorRef.value
  if (!editorElement || !editorElement.contains(target)) return

  e.preventDefault()
  showContextMenuAt(e.clientX, e.clientY)
}

// 处理触摸开始（长按检测）
const handleTouchStart = (e: TouchEvent) => {
  const target = e.target as HTMLElement
  const editorElement = editorRef.value
  if (!editorElement || !editorElement.contains(target)) return

  const touch = e.touches[0]

  longPressTimer = window.setTimeout(() => {
    showContextMenuAt(touch.clientX, touch.clientY)
  }, 600) // 600ms 长按触发
}

// 处理触摸结束
const handleTouchEnd = () => {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
}

// 处理触摸移动（取消长按）
const handleTouchMove = () => {
  if (longPressTimer) {
    clearTimeout(longPressTimer)
    longPressTimer = null
  }
}

// 处理点击其他地方关闭菜单
const handleClickOutside = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  const menuElement = document.querySelector('.context-menu')
  if (menuElement && !menuElement.contains(target)) {
    closeContextMenu()
  }
}

// 处理编辑器点击事件
const handleEditorClick = (e: MouseEvent) => {
  if (!editorView) return

  // 获取点击位置
  const pos = editorView.posAtCoords({ x: e.clientX, y: e.clientY })
  if (pos === null) return

  // 获取编辑器内容
  const content = editorView.state.doc.toString()

  // 检查点击位置是否在图片链接上
  const imagePath = extractImageLink(content, pos)
  if (imagePath) {
    // 如果点击的是图片链接，阻止默认行为并预览图片
    e.preventDefault()
    e.stopPropagation()
    previewImage(imagePath)
  }
}

// 处理键盘快捷键
const handleKeyDown = (e: KeyboardEvent) => {
  // Ctrl+F: 查找
  if (e.ctrlKey && e.key === 'f') {
    e.preventDefault()
    openFindReplace()
    return
  }

  // Ctrl+H: 替换
  if (e.ctrlKey && e.key === 'h') {
    e.preventDefault()
    openFindReplace()
    return
  }

  // Escape: 关闭查找替换面板
  if (e.key === 'Escape' && showFindReplace.value) {
    closeFindReplace()
    return
  }
}

// 创建编辑器
const createEditor = () => {
  if (!editorRef.value) return

  const customKeymap = keymap.of([
    {
      key: 'Ctrl-s',
      run: () => {
        emit('save')
        return true
      }
    },
    indentWithTab
  ])

  const updateListener = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      emit('update:modelValue', update.state.doc.toString())
    }
  })



  // 自定义 Markdown 语法高亮样式
  const markdownHighlightStyle = HighlightStyle.define([
    // 标题 - 蓝色加粗
    { tag: tags.heading1, color: '#1890ff', fontWeight: 'bold', fontSize: '1.4em' },
    { tag: tags.heading2, color: '#1890ff', fontWeight: 'bold', fontSize: '1.3em' },
    { tag: tags.heading3, color: '#1890ff', fontWeight: 'bold', fontSize: '1.2em' },
    { tag: tags.heading4, color: '#1890ff', fontWeight: 'bold', fontSize: '1.1em' },
    { tag: tags.heading5, color: '#1890ff', fontWeight: 'bold' },
    { tag: tags.heading6, color: '#1890ff', fontWeight: 'bold' },
    // 强调文字
    { tag: tags.strong, color: '#fa541c', fontWeight: 'bold' },
    { tag: tags.emphasis, color: '#722ed1', fontStyle: 'italic' },
    // 代码
    { tag: tags.monospace, color: '#13c2c2', backgroundColor: '#f6ffed', borderRadius: '3px', padding: '0 4px' },
    // 链接和图片
    { tag: tags.link, color: '#52c41a', textDecoration: 'underline' },
    { tag: tags.url, color: '#52c41a' },
    // 引用
    { tag: tags.quote, color: '#666', borderLeft: '3px solid #ddd', paddingLeft: '8px' },
    // 列表标记
    { tag: tags.list, color: '#1890ff' },
    // 注释/元数据
    { tag: tags.comment, color: '#999', fontStyle: 'italic' },
    // 水平线（分页符）- 使用醒目的橙色高亮
    { tag: tags.contentSeparator, color: '#ff6b35', fontWeight: 'bold', backgroundColor: '#fff2e8', padding: '2px 8px', borderRadius: '4px' }
  ])

  const startState = EditorState.create({
    doc: props.modelValue,
    extensions: [
      searchHighlightField,
      // 移除 highlightSelectionMatches 以避免干扰双击选词
      markdown(),
      syntaxHighlighting(markdownHighlightStyle),
      customKeymap,
      updateListener,
      EditorView.lineWrapping,
      EditorView.theme({
        '&': {
          fontSize: '14px',
          height: '100%',
          backgroundColor: '#fff',
          userSelect: 'text',
          WebkitUserSelect: 'text',
          MozUserSelect: 'text',
          msUserSelect: 'text',
          '&::selection': {
            backgroundColor: '#b3d7ff'
          }
        },
        '.cm-scroller': {
          fontFamily: "'Consolas', 'Monaco', 'Courier New', monospace",
          lineHeight: '1.6',
          backgroundColor: '#fff',
          userSelect: 'text',
          WebkitUserSelect: 'text'
        },
        '.cm-content': {
          padding: '16px',
          backgroundColor: '#fff',
          color: '#333',
          userSelect: 'text',
          WebkitUserSelect: 'text',
          MozUserSelect: 'text'
        },
        '.cm-line': {
          userSelect: 'text',
          WebkitUserSelect: 'text',
          MozUserSelect: 'text'
        },
        '.cm-gutters': {
          backgroundColor: '#f5f5f5',
          borderRight: '1px solid #ddd',
          color: '#666'
        },
        '.cm-activeLineGutter': {
          backgroundColor: '#e8e8e8'
        },
        '.cm-activeLine': {
          backgroundColor: '#f0f7ff'
        },
        '.cm-cursor': {
          borderLeftColor: '#333'
        },
        '.cm-selectionBackground': {
          backgroundColor: '#b3d7ff'
        },
        // 分页符高亮样式
        '.cm-line:has(.cm-contentSeparator)': {
          backgroundColor: '#fff7e6',
          borderTop: '2px dashed #ff6b35',
          borderBottom: '2px dashed #ff6b35',
          margin: '8px 0',
          padding: '4px 0'
        },
        '.cm-contentSeparator': {
          color: '#ff6b35 !important',
          fontWeight: 'bold',
          fontSize: '1.1em'
        }
      })
    ]
  })

  editorView = new EditorView({
    state: startState,
    parent: editorRef.value
  })
}

// 监听外部值变化
watch(() => props.modelValue, (newValue) => {
  if (editorView && newValue !== editorView.state.doc.toString()) {
    editorView.dispatch({
      changes: {
        from: 0,
        to: editorView.state.doc.length,
        insert: newValue
      }
    })
  }
})

// 聚焦编辑器
const focus = () => {
  editorView?.focus()
}

// 关闭图片预览
const closeImagePreview = () => {
  showImagePreview.value = false
  if (previewImageUrl.value) {
    URL.revokeObjectURL(previewImageUrl.value)
    previewImageUrl.value = ''
  }
}

defineExpose({
  focus,
  closeImagePreview
})

onMounted(() => {
  createEditor()
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('contextmenu', handleContextMenu)
  window.addEventListener('touchstart', handleTouchStart, { passive: true })
  window.addEventListener('touchend', handleTouchEnd)
  window.addEventListener('touchmove', handleTouchMove, { passive: true })
  window.addEventListener('click', handleClickOutside)
  window.addEventListener('mousemove', onDragPanelMove)
  window.addEventListener('mouseup', onDragPanelUp)

  // 添加编辑器点击事件监听
  const editorElement = editorRef.value
  if (editorElement) {
    editorElement.addEventListener('click', handleEditorClick)
  }

  // 初始化图片预览弹窗样式
  updateImagePreviewStyle()
  window.addEventListener('mousemove', onDragImagePreviewMove)
  window.addEventListener('mouseup', onDragImagePreviewUp)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('contextmenu', handleContextMenu)
  window.removeEventListener('touchstart', handleTouchStart)
  window.removeEventListener('touchend', handleTouchEnd)
  window.removeEventListener('touchmove', handleTouchMove)
  window.removeEventListener('click', handleClickOutside)
  window.removeEventListener('mousemove', onDragPanelMove)
  window.removeEventListener('mouseup', onDragPanelUp)

  // 移除编辑器点击事件监听
  const editorElement = editorRef.value
  if (editorElement) {
    editorElement.removeEventListener('click', handleEditorClick)
  }

  // 移除图片预览拖动事件监听
  window.removeEventListener('mousemove', onDragImagePreviewMove)
  window.removeEventListener('mouseup', onDragImagePreviewUp)

  // 清理预览图片的 Blob URL
  if (previewImageUrl.value) {
    URL.revokeObjectURL(previewImageUrl.value)
  }

  if (longPressTimer) {
    clearTimeout(longPressTimer)
  }
  editorView?.destroy()
  editorView = null
})
</script>

<style>
/* 全局样式：强制 CodeMirror 文本可选择 */
.cm-editor {
  user-select: text !important;
  -webkit-user-select: text !important;
  -moz-user-select: text !important;
}
.cm-editor .cm-content {
  user-select: text !important;
  -webkit-user-select: text !important;
  -moz-user-select: text !important;
}
.cm-editor .cm-line {
  user-select: text !important;
  -webkit-user-select: text !important;
  -moz-user-select: text !important;
}
.cm-editor .cm-scroller {
  user-select: text !important;
  -webkit-user-select: text !important;
  -moz-user-select: text !important;
}
</style>

<style scoped>
.editor-component {
  height: 100%;
}

.edit-area {
  height: 100%;
  overflow: hidden;
}

.editor-container {
  height: 100%;
  padding: 0;
}

.editor-wrapper {
  position: relative;
  height: 100%;
  overflow: hidden;
}

.highlight-layer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-y: scroll;
  overflow-x: hidden;
  color: transparent;
  pointer-events: none;
  background: #fafafa;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  z-index: 0;
  box-sizing: border-box;
  scrollbar-width: thin;
  scrollbar-color: transparent transparent;
}

.highlight-layer::-webkit-scrollbar {
  width: 8px;
}

.highlight-layer::-webkit-scrollbar-track {
  background: transparent;
}

.highlight-layer::-webkit-scrollbar-thumb {
  background: transparent;
}

.editor-textarea {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  padding: 16px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  resize: none;
  background: transparent;
  color: transparent;
  caret-color: #1890ff;
  z-index: 1;
  text-shadow: 0 0 0 #333;
  box-sizing: border-box;
  overflow-y: scroll;
  overflow-x: hidden;
  scrollbar-width: thin;
  tab-size: 2;
}

.editor-textarea:focus {
  outline: none;
  border-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

/* 高亮样式 */
:deep(.highlight-heading) {
  color: #1890ff;
  font-weight: bold;
}

:deep(.highlight-bold) {
  color: #fa541c;
  font-weight: bold;
}

:deep(.highlight-italic) {
  color: #722ed1;
  font-style: italic;
}

:deep(.highlight-code-block) {
  color: #13c2c2;
  background: #f0f0f0;
}

:deep(.highlight-code) {
  color: #eb2f96;
  background: #fff0f6;
}

:deep(.highlight-link) {
  color: #52c41a;
}

:deep(.highlight-image) {
  color: #faad14;
}

:deep(.highlight-list) {
  color: #1890ff;
}

/* 查找替换浮动面板 */
.find-replace-panel {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  width: 90%;
  max-width: 500px;
  z-index: 100;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.find-replace-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #f5f5f5;
  border-bottom: 1px solid #eee;
  font-weight: 500;
  font-size: 14px;
  cursor: move;
  user-select: none;
}

.find-replace-header .close-btn {
  cursor: pointer;
  color: #999;
}

.find-replace-header .close-btn:hover {
  color: #333;
}

.find-replace-content {
  padding: 12px;
}

.find-row,
.replace-row {
  margin-bottom: 10px;
}

.find-row .van-field,
.replace-row .van-field {
  padding: 0;
}

.nav-buttons {
  display: flex;
  gap: 4px;
}

.replace-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.find-count {
  font-size: 12px;
  color: #666;
}

.codemirror-editor {
  height: 100%;
  user-select: text;
  -webkit-user-select: text;
}

/* 上下文菜单 */
.context-menu {
  position: fixed;
  z-index: 200;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  min-width: 140px;
  padding: 4px 0;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background-color 0.2s;
  font-size: 14px;
  color: #333;
}

.context-menu-item:hover {
  background-color: #f5f5f5;
}

.context-menu-item:active {
  background-color: #e8e8e8;
}

.context-menu-item .van-icon {
  font-size: 18px;
  color: #666;
}

/* 隐藏 CodeMirror 搜索面板 */
:deep(.cm-panels) {
  display: none !important;
}

/* 搜索高亮样式 */
:deep(.cm-searchMatch) {
  background-color: #ffe58f !important;
  border-radius: 2px;
}

:deep(.cm-searchMatch.cm-searchMatch-selected) {
  background-color: #faad14 !important;
}

/* 图片预览弹窗 */
.image-preview-popup-wrapper {
  display: flex;
  flex-direction: column;
  position: fixed;
  z-index: 9999;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  overflow: hidden;
}

.image-preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f5f5f5;
  border-bottom: 1px solid #eee;
  cursor: move;
  user-select: none;
  border-radius: 12px 12px 0 0;
}

.image-preview-header span {
  font-weight: 500;
  font-size: 14px;
}

.image-preview-header .close-btn {
  cursor: pointer;
  color: #999;
}

.image-preview-header .close-btn:hover {
  color: #333;
}

.image-preview-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  overflow: hidden;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
}

.loading-placeholder {
  color: #999;
}
</style>
