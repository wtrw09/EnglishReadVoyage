<template>
  <!-- 导入对话框 -->
  <van-dialog
    v-model:show="showImportDialog"
    title="导入书籍"
    :show-confirm-button="false"
    :show-cancel-button="false"
    :close-on-click-overlay="true"
    width="320px"
    @closed="onImportDialogClosed"
  >
    <div class="import-dialog-content">
      <div
        class="drop-zone"
        :class="{ 'drag-over': isDragOver, 'has-file': selectedFile || selectedFiles.length > 0 }"
        @dragenter.prevent="isDragOver = true"
        @dragover.prevent="isDragOver = true"
        @dragleave.prevent="isDragOver = false"
        @drop.prevent="onFileDrop"
        @click="triggerFileInput"
      >
        <template v-if="selectedFile || selectedFiles.length > 0">
          <i class="fas fa-file-lines" style="font-size: 40px; color: #1989fa;"></i>
          <p class="file-name">
            {{ selectedFiles.length > 0 ? `已选择 ${selectedFiles.length} 个文件` : selectedFile?.name }}
          </p>
          <p class="file-hint">点击更换文件</p>
        </template>
        <template v-else>
          <i class="fas fa-plus" style="font-size: 40px; color: #969799;"></i>
          <p>拖拽MD或ZIP文件到这里，或点击选择</p>
          <p class="hint">支持 .md 和 .zip 格式，支持多选MD文件批量导入</p>
        </template>
      </div>

      <input
        ref="fileInput"
        type="file"
        accept=".md,.zip"
        hidden
        multiple
        @change="onFileSelected"
      />

      <!-- 导入进度 -->
      <div v-if="uploading || importing || importProgress === 100" class="import-progress">
        <van-progress
          :percentage="uploading ? uploadProgress : importProgress"
          :stroke-width="8"
          :show-pivot="true"
        />
        <p class="import-status">{{ uploading ? uploadStatus : importStatus }}</p>
      </div>

      <!-- 操作按钮 -->
      <div class="import-actions">
        <van-button
          type="primary"
          size="large"
          :disabled="(!selectedFile && selectedFiles.length === 0) || importing || uploading"
          :loading="importing || uploading"
          @click="importCompleted ? closeImportDialog() : handleImportConfirm()"
        >
          {{ uploading ? '上传中...' : (importing ? '导入中...' : (importCompleted ? '关闭' : '开始导入')) }}
        </van-button>
      </div>
    </div>
  </van-dialog>

  <!-- 重复书籍检测对话框 -->
  <van-dialog
    :show="showDuplicateDialog"
    title="发现重复书籍"
    :show-confirm-button="false"
    :show-cancel-button="false"
    :close-on-click-overlay="false"
  >
    <div class="duplicate-dialog-content">
      <p class="duplicate-hint">
        ZIP文件中共 {{ duplicateCheckResult.total_books }} 本书籍，
        其中 {{ duplicateCheckResult.duplicate_books?.length || 0 }} 本已存在，
        {{ duplicateCheckResult.new_books?.length || 0 }} 本为新书籍
      </p>

      <!-- 重复书籍列表 -->
      <div class="duplicate-section" v-if="duplicateCheckResult.duplicate_books?.length > 0">
        <p class="duplicate-section-title">已存在书籍（请选择要覆盖的）：</p>
        <div class="duplicate-list">
          <div
            v-for="book in duplicateCheckResult.duplicate_books"
            :key="book.book_id"
            class="duplicate-item selectable"
            @click="toggleDuplicateSelect(book.book_id)"
          >
            <div class="duplicate-checkbox">
              <input
                type="checkbox"
                :checked="selectedDuplicateBooks.includes(book.book_id)"
                @click.stop
                @change="toggleDuplicateSelect(book.book_id)"
              />
            </div>
            <span class="duplicate-title">《{{ book.title }}》</span>
            <span class="duplicate-status">已存在</span>
          </div>
        </div>
        <div class="duplicate-select-all">
          <van-button type="primary" size="mini" plain @click="selectAllDuplicates">
            全选
          </van-button>
          <van-button type="default" size="mini" plain @click="clearAllDuplicates">
            清空
          </van-button>
        </div>
      </div>

      <!-- 新书籍列表 -->
      <div class="duplicate-section" v-if="duplicateCheckResult.new_books?.length > 0">
        <p class="duplicate-section-title">新书籍（将被导入）：</p>
        <div class="duplicate-list new-books">
          <div
            v-for="book in duplicateCheckResult.new_books"
            :key="book.book_id"
            class="duplicate-item"
          >
            <span class="duplicate-title">《{{ book.title }}》</span>
            <span class="duplicate-status new">新书籍</span>
          </div>
        </div>
      </div>

      <div class="duplicate-actions">
        <van-button
          v-if="selectedDuplicateBooks.length > 0"
          type="primary"
          size="small"
          @click="handleImportSelected"
        >
          覆盖选中 ({{ selectedDuplicateBooks.length }})
        </van-button>
        <template v-else>
          <van-button type="primary" size="small" @click="handleImportWithOverwrite">
            覆盖全部
          </van-button>
          <van-button type="default" size="small" @click="handleImportSkipDuplicates">
            跳过全部
          </van-button>
        </template>
        <van-button size="small" @click="cancelImport">
          取消
        </van-button>
      </div>
    </div>
  </van-dialog>

  <!-- 合并检查结果对话框 -->
  <van-dialog
    :show="showImportCheckDialog"
    title="导入检查结果"
    :show-confirm-button="true"
    :show-cancel-button="true"
    confirm-button-text="确定导入"
    cancel-button-text="取消"
    :close-on-click-overlay="false"
    @confirm="handleImportCheckConfirm"
    @cancel="handleImportCheckCancel"
  >
    <div class="duplicate-dialog-content">
      <!-- 不完整的书籍（自动跳过） -->
      <div v-if="importCheckResult.invalid_books.length > 0">
        <p class="duplicate-hint skip">以下书籍信息不全，将自动跳过：</p>
        <div class="duplicate-list">
          <div
            v-for="book in importCheckResult.invalid_books"
            :key="book.title"
            class="duplicate-item"
          >
            <span class="duplicate-title">《{{ book.title }}》</span>
            <span class="duplicate-status error">{{ book.reason }}</span>
          </div>
        </div>
      </div>
      <!-- 已存在的书籍 -->
      <div v-if="importCheckResult.duplicate_books.length > 0">
        <p class="duplicate-hint">以下书籍已存在，请选择要覆盖的书籍：</p>
        <van-checkbox
          v-model="isSelectAllDuplicatesForMerge"
          shape="square"
          icon-size="18px"
          class="select-all-checkbox"
          @change="handleSelectAllToggle"
        >
          全选
        </van-checkbox>
        <div class="duplicate-list duplicate-check-list">
          <div
            v-for="book in importCheckResult.duplicate_books"
            :key="book.title"
            class="duplicate-item"
            @click="toggleDuplicateBookForMerge(book.title)"
          >
            <van-checkbox
              :model-value="selectedDuplicateBooksForMerge.includes(book.title)"
              shape="square"
              icon-size="18px"
            />
            <span class="duplicate-title">《{{ book.title }}》</span>
          </div>
        </div>
      </div>
      <!-- 可以导入的书籍 -->
      <div class="import-valid-summary">
        <p class="import-valid-count">
          共 {{ importCheckResult.valid_books.length }} 本新书籍 + {{ selectedDuplicateBooksForMerge.length }} 本覆盖，共 {{ importCheckResult.valid_books.length + selectedDuplicateBooksForMerge.length }} 本
        </p>
        <p v-if="importCheckResult.invalid_books.length > 0" class="import-valid-hint">
          信息不全的书籍将自动跳过
        </p>
      </div>
    </div>
  </van-dialog>

  <!-- 完整性错误对话框 -->
  <van-dialog
    :show="showIntegrityErrorDialog"
    title="部分书籍无法导入"
    :show-confirm-button="true"
    :show-cancel-button="true"
    cancel-button-text="取消导入"
    confirm-button-text="跳过并继续"
    :close-on-click-overlay="false"
    @confirm="handleIntegrityErrorContinue"
    @cancel="handleIntegrityErrorCancel"
  >
    <div class="duplicate-dialog-content">
      <p class="duplicate-hint">以下书籍信息不全，已跳过：</p>
      <div class="duplicate-list">
        <div
          v-for="book in integrityErrorBooks"
          :key="book.name"
          class="duplicate-item"
        >
          <span class="duplicate-title">《{{ book.name }}》</span>
          <span class="duplicate-status error">{{ book.reason }}</span>
        </div>
      </div>
    </div>
  </van-dialog>

  <!-- 导入完成后选择对话框 -->
  <van-dialog
    :show="showChoiceDialog"
    title="导入完成"
    :show-confirm-button="false"
    :show-cancel-button="false"
    close-on-click-overlay
  >
    <div class="choice-dialog-content">
      <p class="choice-hint">请选择下一步操作：</p>
      <van-button type="primary" size="large" @click="handleEditAndGenerate">
        编辑文件并生成语音
      </van-button>
    </div>
  </van-dialog>
</template>

<script setup lang="ts">
import { useImport } from '../composables/useImport'

// 接收从父组件传入的 useImport 状态
const props = defineProps<{
  importState?: ReturnType<typeof useImport>
}>()

// 如果有传入状态则使用，否则自己调用
const state = props.importState || useImport()

const {
  // 状态
  showImportDialog,
  fileInput,
  importing,
  importCompleted,
  selectedFile,
  selectedFiles,
  isDragOver,
  importProgress,
  importStatus,
  uploading,
  uploadProgress,
  uploadStatus,
  showChoiceDialog,
  showDuplicateDialog,
  duplicateCheckResult,
  selectedDuplicateBooks,
  showIntegrityErrorDialog,
  integrityErrorBooks,
  handleIntegrityErrorContinue,
  handleIntegrityErrorCancel,
  showImportCheckDialog,
  importCheckResult,
  selectedDuplicateBooksForMerge,
  isSelectAllDuplicatesForMerge,
  handleImportCheckConfirm,
  handleImportCheckCancel,
  toggleDuplicateBookForMerge,
  handleSelectAllToggle,

  // 方法
  triggerFileInput,
  onFileDrop,
  onFileSelected,
  handleImportConfirm,
  closeImportDialog,
  onImportDialogClosed,
  toggleDuplicateSelect,
  selectAllDuplicates,
  clearAllDuplicates,
  handleImportWithOverwrite,
  handleImportSkipDuplicates,
  handleImportSelected,
  cancelImport,
} = state

// 编辑文件并生成语音
const handleEditAndGenerate = () => {
  showChoiceDialog.value = false
  // 通过 emit 通知父组件处理
}
</script>

<style scoped>
.import-dialog-content {
  padding: 16px;
  max-height: 70vh;
  overflow-y: auto;
}

.drop-zone {
  border: 2px dashed #dcdee0;
  border-radius: 8px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: #f7f8fa;
}

.drop-zone:hover {
  border-color: #1989fa;
  background: #f0f8ff;
}

.drop-zone.drag-over {
  border-color: #1989fa;
  background: #e6f7ff;
}

.drop-zone.has-file {
  border-style: solid;
  border-color: #1989fa;
  background: #e6f7ff;
}

.drop-zone p {
  margin: 10px 0 0;
  color: #646566;
  font-size: 14px;
}

.drop-zone .hint {
  font-size: 12px;
  color: #969799;
}

.drop-zone .file-name {
  color: #1989fa;
  font-weight: 500;
  word-break: break-all;
}

.drop-zone .file-hint {
  font-size: 12px;
  color: #969799;
}

.import-progress {
  margin-top: 20px;
}

.import-status {
  margin-top: 8px;
  text-align: center;
  font-size: 12px;
  color: #969799;
}

.import-actions {
  margin-top: 20px;
}

/* 重复书籍对话框样式 */
.duplicate-dialog-content {
  padding: 16px;
  max-height: 70vh;
  overflow-y: auto;
}

.duplicate-hint {
  margin-bottom: 12px;
  color: #646566;
  font-size: 14px;
}

.duplicate-hint.skip {
  color: #ee0a24;
  margin-top: 12px;
}

.duplicate-check-list .duplicate-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  cursor: pointer;
}

.duplicate-check-list .duplicate-title {
  flex: 1;
}

.select-all-checkbox {
  margin-bottom: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #ebedf0;
}

.import-valid-summary {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #ebedf0;
  text-align: center;
}

.import-valid-count {
  font-size: 16px;
  font-weight: 500;
  color: #1989fa;
}

.import-valid-hint {
  font-size: 12px;
  color: #969799;
  margin-top: 4px;
}

.duplicate-section {
  margin-bottom: 16px;
}

.duplicate-section-title {
  font-size: 13px;
  color: #969799;
  margin-bottom: 8px;
  font-weight: 500;
}

.duplicate-list {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 8px;
}

.duplicate-list.new-books {
  background: #f7f8fa;
}

.duplicate-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
}

.duplicate-item:last-child {
  border-bottom: none;
}

.duplicate-item.selectable {
  cursor: pointer;
}

.duplicate-item.selectable:hover {
  background: #f7f8fa;
}

.duplicate-checkbox {
  margin-right: 8px;
  display: flex;
  align-items: center;
}

.duplicate-checkbox input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.duplicate-title {
  font-size: 14px;
  color: #333;
  flex: 1;
}

.duplicate-status {
  font-size: 12px;
  color: #ff976a;
  background: #fff5f0;
  padding: 2px 8px;
  border-radius: 4px;
  margin-left: 8px;
}

.duplicate-status.new {
  color: #07c160;
  background: #e8f5e9;
}

.duplicate-status.error {
  color: #ee0a24;
  background: #fff0f0;
}

.duplicate-select-all {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  justify-content: flex-end;
}

.duplicate-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;
}

/* 选择对话框样式 */
.choice-dialog-content {
  padding: 20px;
  text-align: center;
}

.choice-hint {
  margin-bottom: 20px;
  color: #646566;
}
</style>
