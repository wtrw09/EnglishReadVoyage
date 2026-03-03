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
      <div class="context-menu-item" @click="insertPageBreak">
        <van-icon name="bookmark-o" />
        <span>插入换页符</span>
      </div>
    </div>
    <!-- 查找替换浮动面板 -->
    <div v-show="showFindReplace" class="find-replace-panel">
      <div class="find-replace-header">
        <span>查找和替换</span>
        <van-icon name="cross" class="close-btn" @click="closeFindReplace" />
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
    <div ref="editorRef" class="codemirror-editor"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { EditorView, keymap } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { markdown } from '@codemirror/lang-markdown'
import { indentWithTab } from '@codemirror/commands'
import { syntaxHighlighting, HighlightStyle } from '@codemirror/language'
import { tags } from '@lezer/highlight'
import { showToast, showNotify } from 'vant'

interface Props {
  modelValue: string
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
const currentFindIndex = ref(0)
const showFindReplace = ref(false)
const findInputRef = ref<any>(null)

// 上下文菜单相关状态
const showContextMenu = ref(false)
const contextMenuX = ref(0)
const contextMenuY = ref(0)
let longPressTimer: number | null = null

// 转义正则表达式特殊字符
const escapeRegex = (str: string): string => {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// 获取所有匹配位置
const getMatchPositions = (): number[] => {
  if (!findText.value || !editorView) return []
  const content = editorView.state.doc.toString()
  const positions: number[] = []
  const regex = new RegExp(escapeRegex(findText.value), 'g')
  let match
  while ((match = regex.exec(content)) !== null) {
    positions.push(match.index)
  }
  return positions
}

// 计算匹配数量
const updateFindCount = () => {
  if (!findText.value) {
    findCount.value = 0
    return
  }
  try {
    const content = editorView?.state.doc.toString() || ''
    const regex = new RegExp(escapeRegex(findText.value), 'g')
    const matches = content.match(regex)
    findCount.value = matches ? matches.length : 0
  } catch {
    findCount.value = 0
  }
}

// 查找文本变化时更新计数
const onFindTextChange = () => {
  updateFindCount()
  currentFindIndex.value = 0
}

// 滚动到当前匹配位置
const scrollToCurrentMatch = async () => {
  await nextTick()
  const positions = getMatchPositions()
  if (positions.length === 0 || !editorView) return

  const currentPos = positions[currentFindIndex.value]
  const line = editorView.state.doc.lineAt(currentPos)
  
  // 使用 CodeMirror 的滚动API
  editorView.dispatch({
    effects: EditorView.scrollIntoView(line.from, { y: 'center' })
  })
}

// 查找上一个
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
  // 向前移动，如果已经是第一个则跳到最后一个
  currentFindIndex.value = currentFindIndex.value > 0
    ? currentFindIndex.value - 1
    : findCount.value - 1
  scrollToCurrentMatch()
}

// 查找下一个
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
  // 向后移动，如果已经是最后一个则跳到第一个
  currentFindIndex.value = currentFindIndex.value < findCount.value - 1
    ? currentFindIndex.value + 1
    : 0
  scrollToCurrentMatch()
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
    
    const positions = getMatchPositions()
    if (positions.length === 0) {
      showToast('未找到匹配内容')
      return
    }

    // 只替换当前索引位置的匹配
    const currentPos = positions[currentFindIndex.value]
    const searchTerm = findText.value
    
    // 使用 CodeMirror 的变更API
    editorView.dispatch({
      changes: {
        from: currentPos,
        to: currentPos + searchTerm.length,
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
    const regex = new RegExp(escapeRegex(findText.value), 'g')
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

// 打开查找替换面板
const openFindReplace = () => {
  showFindReplace.value = true
  // 聚焦到查找输入框
  setTimeout(() => {
    findInputRef.value?.focus()
  }, 100)
}

// 关闭查找替换面板
const closeFindReplace = () => {
  showFindReplace.value = false
  findText.value = ''
  replaceText.value = ''
  findCount.value = 0
  currentFindIndex.value = 0
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

// 显示上下文菜单
const showContextMenuAt = (x: number, y: number) => {
  // 确保菜单位于视口内
  const menuWidth = 140
  const menuHeight = 80
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
      markdown(),
      syntaxHighlighting(markdownHighlightStyle),
      customKeymap,
      updateListener,
      EditorView.lineWrapping,
      EditorView.theme({
        '&': {
          fontSize: '14px',
          height: '100%',
          backgroundColor: '#fff'
        },
        '.cm-scroller': {
          fontFamily: "'Consolas', 'Monaco', 'Courier New', monospace",
          lineHeight: '1.6',
          backgroundColor: '#fff'
        },
        '.cm-content': {
          padding: '16px',
          backgroundColor: '#fff',
          color: '#333'
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

defineExpose({
  focus
})

onMounted(() => {
  createEditor()
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('contextmenu', handleContextMenu)
  window.addEventListener('touchstart', handleTouchStart, { passive: true })
  window.addEventListener('touchend', handleTouchEnd)
  window.addEventListener('touchmove', handleTouchMove, { passive: true })
  window.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('contextmenu', handleContextMenu)
  window.removeEventListener('touchstart', handleTouchStart)
  window.removeEventListener('touchend', handleTouchEnd)
  window.removeEventListener('touchmove', handleTouchMove)
  window.removeEventListener('click', handleClickOutside)
  if (longPressTimer) {
    clearTimeout(longPressTimer)
  }
  editorView?.destroy()
  editorView = null
})
</script>

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
</style>
