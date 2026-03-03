<template>
  <div class="vocabulary-page">
    <!-- 顶部导航栏 -->
    <van-nav-bar
      title="生词本"
      left-text="返回"
      left-arrow
      fixed
      placeholder
      @click-left="goBack"
    />

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <van-loading type="spinner" size="24px" />
      <span>加载中...</span>
    </div>

    <!-- 空状态 -->
    <div v-else-if="vocabularyList.length === 0" class="empty-container">
      <van-icon name="records-o" size="48" color="#ccc" />
      <p>暂无生词</p>
      <p class="empty-tip">在阅读时长按单词查词，点击"加入生词本"即可添加</p>
    </div>

    <!-- 生词列表 -->
    <div v-else class="vocabulary-list">
      <van-swipe-cell
        v-for="item in vocabularyList"
        :key="item.id"
        class="vocabulary-item"
      >
        <div class="word-card" @click="showWordDetail(item)">
          <div class="word-header">
            <span class="word-text">{{ item.word }}</span>
            <span v-if="item.phonetic" class="word-phonetic">{{ item.phonetic }}</span>
          </div>
          <div class="word-book" v-if="item.book_name">
            <van-icon name="bookmark-o" size="12" />
            <span>{{ item.book_name }}</span>
          </div>
          <div class="word-date">{{ formatDate(item.created_at) }}</div>
        </div>

        <!-- 左滑删除 -->
        <template #right>
          <van-button
            square
            type="danger"
            text="删除"
            class="delete-btn"
            @click="confirmDelete(item)"
          />
        </template>
      </van-swipe-cell>
    </div>

    <!-- 生词详情弹窗 -->
    <van-popup
      v-model:show="showDetailDialog"
      position="bottom"
      round
      :style="{ maxHeight: '70%' }"
    >
      <div class="detail-popup-header">
        <span class="detail-popup-title">{{ selectedWord?.word }}</span>
        <van-icon name="cross" class="detail-popup-close" @click="showDetailDialog = false" />
      </div>
      <div class="word-detail" v-if="selectedWord">
        <div class="detail-section" v-if="selectedWord.phonetic">
          <div class="detail-label">音标</div>
          <div class="detail-phonetic">{{ selectedWord.phonetic }}</div>
        </div>

        <div class="detail-section" v-if="selectedWord.translation">
          <div class="detail-label">中文释义</div>
          <div class="detail-translation">{{ selectedWord.translation }}</div>
        </div>

        <div class="detail-section" v-if="selectedWord.sentence">
          <div class="detail-label">所在句子</div>
          <div class="detail-sentence">{{ selectedWord.sentence }}</div>
        </div>

        <div class="detail-section" v-if="selectedWord.book_name">
          <div class="detail-label">来源书籍</div>
          <div class="detail-book">
            <van-icon name="bookmark-o" />
            <span>{{ selectedWord.book_name }}</span>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-label">添加时间</div>
          <div class="detail-date">{{ formatDateTime(selectedWord.created_at) }}</div>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { api } from '@/store/auth'

interface VocabularyItem {
  id: number
  word: string
  phonetic?: string
  translation?: string
  sentence?: string
  book_name?: string
  created_at: string
}

const router = useRouter()
const loading = ref(true)
const vocabularyList = ref<VocabularyItem[]>([])
const showDetailDialog = ref(false)
const selectedWord = ref<VocabularyItem | null>(null)

// 返回上一页
const goBack = () => {
  router.back()
}

// 加载生词列表
const loadVocabulary = async () => {
  loading.value = true
  try {
    const res = await api.get('/vocabulary/')
    vocabularyList.value = res.data.items || []
  } catch (error) {
    showToast('加载失败')
  } finally {
    loading.value = false
  }
}

// 显示生词详情
const showWordDetail = (item: VocabularyItem) => {
  selectedWord.value = item
  showDetailDialog.value = true
}

// 确认删除
const confirmDelete = (item: VocabularyItem) => {
  showConfirmDialog({
    title: '确认删除',
    message: `确定要删除 "${item.word}" 吗？`
  }).then(() => {
    deleteVocabulary(item.id)
  }).catch(() => {
    // 取消删除
  })
}

// 删除生词
const deleteVocabulary = async (id: number) => {
  try {
    await api.delete(`/vocabulary/${id}`)
    showToast('已删除')
    // 重新加载列表
    loadVocabulary()
  } catch (error) {
    showToast('删除失败')
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()}`
}

// 格式化日期时间
const formatDateTime = (dateStr: string) => {
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

// 页面加载时获取数据
onMounted(() => {
  loadVocabulary()
})
</script>

<style scoped>
.vocabulary-page {
  min-height: 100vh;
  background: #f7f8fa;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: #999;
  gap: 12px;
}

.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  color: #999;
}

.empty-container p {
  margin: 8px 0 0;
  font-size: 16px;
}

.empty-tip {
  font-size: 14px !important;
  color: #bbb;
  text-align: center;
  padding: 0 40px;
  margin-top: 12px !important;
}

.vocabulary-list {
  padding: 12px;
}

.vocabulary-item {
  margin-bottom: 8px;
}

.word-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.word-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.word-text {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.word-phonetic {
  font-size: 14px;
  color: #666;
  font-family: 'Times New Roman', serif;
}

.word-book {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.word-date {
  font-size: 12px;
  color: #bbb;
}

.delete-btn {
  height: 100%;
}

/* 详情弹窗样式 */
.word-detail {
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

/* 详情弹窗头部样式 */
.detail-popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #eee;
}

.detail-popup-title {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}

.detail-popup-close {
  font-size: 20px;
  color: #999;
  cursor: pointer;
  padding: 4px;
}

.detail-popup-close:hover {
  color: #666;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 6px;
}

.detail-phonetic {
  font-size: 16px;
  color: #666;
  font-family: 'Times New Roman', serif;
}

.detail-translation {
  font-size: 15px;
  color: #333;
  line-height: 1.6;
}

.detail-sentence {
  font-size: 14px;
  color: #555;
  line-height: 1.6;
  padding: 10px;
  background: #f7f8fa;
  border-radius: 6px;
}

.detail-book {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #666;
}

.detail-date {
  font-size: 13px;
  color: #999;
}
</style>
