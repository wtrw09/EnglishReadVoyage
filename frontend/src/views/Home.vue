<template>
  <div class="home">
    <!-- 顶部导航栏 -->
    <van-nav-bar fixed placeholder>
      <!-- 左侧：搜索框 + 添加按钮 -->
      <template #left>
        <div class="nav-left">
          <div class="nav-search">
            <van-icon name="search" class="search-icon" />
            <input
              v-model="searchText"
              type="text"
              placeholder="搜索书籍..."
              class="search-input"
              @input="handleSearch"
            />
          </div>
          <van-icon name="plus" class="nav-icon" @click="openImportDialog(0)" v-if="authStore.isAdmin" />
        </div>
      </template>
      <template #right>
        <div class="nav-actions">
          <!-- 书籍管理下拉菜单 -->
          <van-popover
            v-model:show="showBookPopover"
            placement="bottom-end"
            :actions="bookActions"
            close-on-click-outside
            teleport="body"
            @update:show="(show: boolean) => handlePopoverShow(show, 'book')"
            @select="onBookActionSelect"
          >
            <template #reference>
              <div class="nav-icon-btn">
                <van-icon name="bars" class="nav-icon" />
              </div>
            </template>
          </van-popover>
          <!-- 用户名下拉菜单 -->
          <van-popover
            v-model:show="showUserPopover"
            placement="bottom-end"
            :actions="userActions"
            close-on-click-outside
            teleport="body"
            @update:show="(show: boolean) => handlePopoverShow(show, 'user')"
            @select="onUserSelect"
          >
            <template #reference>
              <span class="username-link">{{ authStore.user?.username || '用户' }}</span>
            </template>
          </van-popover>
          <!-- 设置下拉菜单 -->
          <van-popover
            v-model:show="showSettingsPopover"
            placement="bottom-end"
            :actions="settingsActions"
            close-on-click-outside
            teleport="body"
            @update:show="(show: boolean) => handlePopoverShow(show, 'settings')"
            @select="onSettingsSelect"
          >
            <template #reference>
              <div class="nav-icon-btn">
                <van-icon name="setting-o" class="nav-icon" />
              </div>
            </template>
          </van-popover>
        </div>
      </template>
    </van-nav-bar>

    <!-- 内容区域 -->
    <div class="content">
      <!-- 使用van-collapse实现可折叠分组 -->
      <van-collapse v-model="activeNames" accordion>
        <van-collapse-item
          v-for="group in filteredGroups"
          :key="group.id"
          :name="group.id"
          class="group-item"
          v-show="group.name !== '未分组' || group.books.length > 0"
        >
          <!-- 分组标题 -->
          <template #title>
            <div
              class="group-title"
              @contextmenu.prevent="showGroupContextMenu($event, group)"
              @longpress="showGroupContextMenu($event, group)"
            >
              <!-- 分组选择框（仅在多选模式下显示） -->
              <div v-if="isMultiSelect" class="group-checkbox">
                <input
                  type="checkbox"
                  :checked="isGroupAllSelected(group.id)"
                  @change.stop="toggleGroupSelect(group.id)"
                />
              </div>
              <span class="group-name">{{ group.name }}</span>
              <span class="book-count">({{ group.books.length }})</span>
            </div>
          </template>
          <!-- 分组右侧操作 -->
          <template #right-icon>
            <div class="group-actions" @click.stop>
              <!-- 该分组下的导入按钮（仅管理员可见） -->
              <van-button
                type="primary"
                size="small"
                icon="plus"
                @click="openImportDialog(group.id)"
                class="group-import-btn"
                v-if="authStore.isAdmin"
              />
            </div>
          </template>

          <!-- 书籍列表 -->
          <div class="book-list">
            <van-swipe-cell
              v-for="book in getVisibleBooks(group)"
              :key="book.id"
              :ref="(el) => { if (el) swipeCellRefs[book.id] = el }"
              :disabled="isMultiSelect"
              :stop-propagation="true"
              @open="handleSwipeOpen($event, book)"
            >
              <div
                class="book-item"
                :class="{ 'selected': selectedBooks.includes(book.id), 'is-read': book.is_read }"
                @click="handleBookClick(book.id, group.id)"
                @contextmenu.prevent="showContextMenu($event, book, group.id)"
                @longpress="showContextMenu($event, book, group.id)"
              >
                <!-- 多选复选框 -->
                <div v-if="isMultiSelect" class="book-checkbox" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedBooks.includes(book.id)"
                    @change="toggleBookSelect(book.id)"
                  />
                </div>
                <!-- 封面图片 -->
                <div class="book-cover" :class="{ 'landscape': isLandscape }" @click.stop="handleCoverClick(book)">
                  <template v-if="getBookCover(book)">
                    <img
                      :src="getBookCover(book)"
                      :alt="book.title"
                      loading="lazy"
                      decoding="async"
                      @error="(e) => handleCoverError(e, book)"
                    />
                  </template>
                  <template v-else>
                    <van-icon name="book" size="32" color="#dcdee0" />
                  </template>
                  <!-- 已读标记 -->
                  <div v-if="book.is_read" class="read-badge">
                    <van-icon name="success" size="12" color="#fff" />
                  </div>
                </div>
                <!-- 书籍名称 -->
                <div class="book-info">
                  <span class="book-title">{{ book.title }}</span>
                  <span class="book-meta">Level: {{ book.level }} | {{ book.page_count }} 页</span>
                </div>
              </div>

              <!-- 左侧滑动：标记为未读 -->
              <template #left>
                <div class="swipe-action unread" @click="markBookAsRead(book.id, 0)">
                  <van-icon name="cross" size="24" color="#fff" />
                  <span>未读</span>
                </div>
              </template>

              <!-- 右侧滑动：标记为已读 -->
              <template #right>
                <div class="swipe-action read" @click="markBookAsRead(book.id, 1)">
                  <van-icon name="success" size="24" color="#fff" />
                  <span>已读</span>
                </div>
              </template>
            </van-swipe-cell>
            <div v-if="getVisibleBooks(group).length === 0" class="empty-tip">
              {{ hideReadBooksMap[group.id] ? '该分组下暂无未读书籍' : '该分组下暂无书籍' }}
            </div>
          </div>
        </van-collapse-item>
      </van-collapse>

      <!-- 批量操作栏 -->
      <div v-if="isMultiSelect" class="batch-actions">
        <van-button type="primary" size="small" plain @click="selectAllBooks">
          {{ isAllSelected ? '取消全选' : '全选' }}
        </van-button>
        <van-button type="primary" size="small" plain @click="selectAllBooksInCurrentGroup">
          全选当前分组
        </van-button>
        <van-button type="primary" size="small" icon="down" @click="exportSelectedBooks" :disabled="selectedBooks.length === 0">
          导出 ({{ selectedBooks.length }})
        </van-button>
        <van-button type="primary" size="small" @click="batchMoveBooks" :disabled="selectedBooks.length === 0">
          移动到 ({{ selectedBooks.length }})
        </van-button>
        <van-button type="danger" size="small" v-if="authStore.isAdmin" @click="batchDeleteBooks" :disabled="selectedBooks.length === 0">
          删除 ({{ selectedBooks.length }})
        </van-button>
        <van-button size="small" @click="cancelMultiSelect">
          取消
        </van-button>
      </div>

      <!-- 空状态 -->
      <van-empty
        v-if="filteredGroups.length === 0 && !loading"
        description="暂无书籍"
      />
    </div>

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
          :class="{ 'drag-over': isDragOver, 'has-file': selectedFile }"
          @dragenter.prevent="isDragOver = true"
          @dragover.prevent="isDragOver = true"
          @dragleave.prevent="isDragOver = false"
          @drop.prevent="onFileDrop"
          @click="triggerFileInput"
        >
          <template v-if="selectedFile || selectedFiles.length > 0">
            <van-icon name="description" size="40" color="#1989fa" />
            <p class="file-name">
              {{ selectedFiles.length > 0 ? `已选择 ${selectedFiles.length} 个文件` : selectedFile?.name }}
            </p>
            <p class="file-hint">点击更换文件</p>
          </template>
          <template v-else>
            <van-icon name="plus" size="40" color="#969799" />
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

        <!-- 导入进度（合并上传和导入） -->
        <div v-if="uploading || importing || importProgress === 100" class="import-progress">
          <van-progress
            :percentage="uploading ? uploadProgress : importProgress"
            :stroke-width="8"
            :show-pivot="true" />
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

    <!-- 导出进度对话框 -->
    <van-dialog
      v-model:show="showExportProgressDialog"
      title="导出书籍"
      :show-confirm-button="false"
      :show-cancel-button="false"
      :close-on-click-overlay="false"
    >
      <div class="export-progress-content">
        <van-progress
          :percentage="exportProgress"
          :stroke-width="10"
          :show-pivot="true"
        />
        <p class="export-status">{{ exportStatus }}</p>
        <p v-if="exportCurrentBook" class="export-current-book">
          正在处理: {{ exportCurrentBook }}
        </p>
      </div>
    </van-dialog>

    <!-- 添加分组对话框 -->
    <van-dialog
      v-model:show="showAddGroupDialog"
      title="添加分组"
      show-cancel-button
      @confirm="handleAddGroup"
    >
      <van-field
        v-model="newGroupName"
        placeholder="请输入分组名称"
        label="分组名称"
      />
    </van-dialog>

    <!-- 导入完成后选择对话框 -->
    <van-dialog
      v-model:show="showChoiceDialog"
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

    <!-- 重复书籍检测对话框 -->
    <van-dialog
      v-model:show="showDuplicateDialog"
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

        <!-- 重复书籍列表（带选择） -->
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
          <!-- 有选中书籍时显示覆盖选中按钮 -->
          <van-button
            v-if="selectedDuplicateBooks.length > 0"
            type="primary"
            size="small"
            @click="handleImportSelected"
          >
            覆盖选中 ({{ selectedDuplicateBooks.length }})
          </van-button>
          <!-- 无选中时显示覆盖全部和跳过全部 -->
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

    <!-- 独立编辑对话框 -->
    <BookEditDialog
      ref="bookEditDialogRef"
      v-model="showEditDialog"
      :book-id="currentBookId"
      :title="currentBookTitle"
      :initial-content="editContent"
      @saved="onEditSavedHandler"
      @closed="onEditClosedHandler"
    />

    <!-- 书籍右键菜单 -->
    <van-popup
      v-model:show="showContextMenuPopup"
      :style="{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }"
      round
      class="context-menu"
    >
      <van-cell-group>
        <van-cell
          :title="contextMenuBook?.is_read ? '标记为未读' : '标记为已读'"
          clickable
          @click="toggleBookReadStatus"
        />
        <van-cell title="重命名" clickable @click="openRenameBookDialog" />
        <van-cell title="选择更多" clickable @click="enableMultiSelect" v-if="!isMultiSelect" />
        <van-cell title="导出书籍" clickable @click="exportSingleBook" />
        <van-cell title="移动到其他分组" clickable @click="openMoveDialog" />
        <van-cell title="修改封面" clickable @click="openCoverDialog" />
        <van-cell title="删除" clickable @click="confirmDeleteBook" v-if="authStore.isAdmin" />
      </van-cell-group>
    </van-popup>

    <!-- 分组右键菜单 -->
    <van-popup
      v-model:show="showGroupContextMenuPopup"
      :style="{ top: groupContextMenuPos.y + 'px', left: groupContextMenuPos.x + 'px' }"
      round
      class="context-menu"
    >
      <van-cell-group>
        <van-cell
          :title="hideReadBooksMap[contextMenuGroup?.id || 0] ? '显示已读书籍' : '隐藏已读书籍'"
          clickable
          @click="toggleHideReadBooks"
        />
        <van-cell title="修改名称" clickable @click="openRenameGroupDialog" v-if="contextMenuGroup?.id !== 0 && contextMenuGroup?.name !== '未分组'" />
        <van-cell title="删除分组" clickable @click="confirmDeleteGroup" v-if="contextMenuGroup?.id !== 0 && contextMenuGroup?.name !== '未分组'" />
      </van-cell-group>
    </van-popup>

    <!-- 修改分组名称对话框 -->
    <van-dialog
      v-model:show="showRenameGroupDialog"
      title="修改分组名称"
      show-cancel-button
      @confirm="handleRenameGroup"
    >
      <van-field
        v-model="renameGroupName"
        placeholder="请输入分组名称"
        label="分组名称"
      />
    </van-dialog>

    <!-- 重命名书籍对话框 -->
    <van-dialog
      v-model:show="showRenameBookDialog"
      title="重命名书籍"
      show-cancel-button
      @confirm="handleRenameBook"
    >
      <van-field
        v-model="renameBookName"
        placeholder="请输入新名称"
        label="书籍名称"
      />
    </van-dialog>

    <!-- 移动到分组对话框 -->
    <van-popup v-model:show="showMoveDialog" position="bottom" round>
      <div class="move-dialog">
        <div class="move-dialog-header">
          <span>移动到分组</span>
          <van-icon name="cross" @click="showMoveDialog = false" />
        </div>
        <div class="move-dialog-content">
          <van-radio-group v-model="selectedMoveCategory">
            <van-cell-group>
              <van-cell
                v-for="cat in categoriesForMove"
                :key="cat.id"
                clickable
                @click="selectedMoveCategory = cat.id"
              >
                <template #title>
                  <span>{{ cat.name }}</span>
                </template>
                <template #right-icon>
                  <van-radio :name="cat.id" />
                </template>
              </van-cell>
            </van-cell-group>
          </van-radio-group>
        </div>
        <div class="move-dialog-footer">
          <van-button size="small" type="primary" plain @click="showAddGroupInMove = true">
            创建新分组
          </van-button>
          <van-button size="small" type="primary" :loading="movingBooks" loading-text="移动中..." @click="confirmMoveBooks">
            确定
          </van-button>
        </div>
        <van-field
          v-if="showAddGroupInMove"
          v-model="newGroupInMove"
          placeholder="输入新分组名称"
          @keyup.enter="createGroupInMove"
        >
          <template #button>
            <van-button size="small" type="primary" @click="createGroupInMove">创建</van-button>
          </template>
        </van-field>
      </div>
    </van-popup>

    <!-- 修改封面对话框 -->
    <van-dialog
      v-model:show="showCoverDialog"
      title="修改封面"
      show-cancel-button
      @confirm="saveCover"
    >
      <div class="cover-dialog-content">
        <!-- 预览 -->
        <div class="cover-preview">
          <img v-if="previewCover" :src="previewCover" alt="封面预览" />
          <van-icon v-else name="book" size="60" color="#dcdee0" />
        </div>

        <!-- 操作按钮 -->
        <div class="cover-actions">
          <van-button type="primary" size="small" @click="triggerCoverUpload">
            上传封面
          </van-button>
          <van-button size="small" @click="openCoverPicker">
            从书籍中选择
          </van-button>
          <van-button size="small" @click="useDefaultCover">
            默认封面
          </van-button>
        </div>

        <input
          ref="coverInput"
          type="file"
          accept="image/*"
          hidden
          @change="onCoverSelected"
        />
      </div>
    </van-dialog>

    <!-- 从md资源选择 -->
    <van-popup v-model:show="showCoverPicker" position="bottom" round>
      <div class="cover-picker">
        <div class="cover-picker-title">选择图片作为封面</div>
        <div class="cover-picker-content">
          <div v-if="mdImages.length > 0" class="cover-picker-grid">
            <div
              v-for="img in mdImages"
              :key="img"
              class="cover-picker-item"
              :class="{ selected: selectedMdImage === img }"
              @click="selectMdImage(img)"
            >
              <img :src="img" />
            </div>
          </div>
          <van-empty v-else description="该书籍没有可用的图片资源" />
        </div>
        <div class="cover-picker-footer">
          <van-button type="primary" block @click="confirmMdImage" :disabled="mdImages.length === 0">确定</van-button>
        </div>
      </div>
    </van-popup>

    <!-- 朗读设置弹窗 -->
    <van-dialog
      v-model:show="showTtsSettingsDialog"
      title="朗读设置"
      show-cancel-button
      confirm-button-text="保存"
      cancel-button-text="取消"
      @confirm="saveTtsSettings"
      @closed="stopTtsTest"
    >
      <div class="settings-dialog-content">
        <!-- 服务名称 -->
        <van-field label="服务名称">
          <template #input>
            <select v-model="ttsServiceName" class="tts-voice-select">
              <option value="kokoro-tts">Kokoro TTS (本地)</option>
              <option value="doubao-tts">豆包 TTS (在线)</option>
              <option value="siliconflow-tts">硅基流动 TTS (在线)</option>
              <option value="edge-tts">Edge-TTS (微软在线)</option>
              <option value="minimax-tts">MiniMax TTS (speech-2.8-hd)</option>
            </select>
          </template>
        </van-field>

        <!-- 语音选择 -->
        <van-field
          label="语音类型"
        >
          <template #input>
            <select v-model="ttsVoice" class="tts-voice-select">
              <option value="" disabled>请选择语音类型</option>
              <option v-for="voice in availableVoices" :key="voice.id" :value="voice.id">
                {{ voice.name }}
              </option>
            </select>
          </template>
        </van-field>

        <!-- 朗读速度 (硅基流动和MiniMax不支持) -->
        <template v-if="ttsServiceName !== 'siliconflow-tts'">
          <van-field
            label="朗读速度"
            placeholder="1.0"
          >
            <template #input>
              <input
                :value="ttsSpeed.toFixed(1)"
                type="number"
                step="0.1"
                min="0.25"
                max="4.0"
                class="tts-speed-input"
                @input="ttsSpeed = Math.round(parseFloat(($event.target as HTMLInputElement).value) * 10) / 10"
              />
              <span class="speed-unit">x</span>
            </template>
          </van-field>
          <div class="field-hint">
            范围: {{ ttsServiceName === 'kokoro-tts' || ttsServiceName === 'minimax-tts' ? '0.25 - 4.0' : '0.5 - 2.0' }} (默认 1.0)
          </div>
        </template>

        <!-- 豆包TTS配置 (仅在使用豆包时显示) -->
        <template v-if="ttsServiceName === 'doubao-tts'">
          <van-field
            v-model="ttsAppId"
            label="APP ID"
            placeholder="豆包APP ID"
          />
          <van-field
            v-model="ttsAccessKey"
            label="Access Key"
            placeholder="豆包Access Key"
            type="password"
          />
          <van-field
            v-model="ttsResourceId"
            label="Resource ID"
            placeholder="seed-tts-1.0"
          />
        </template>

        <!-- 硅基流动TTS配置 (仅在使用硅基流动时显示) -->
        <template v-if="ttsServiceName === 'siliconflow-tts'">
          <van-field
            v-model="ttsSiliconFlowApiKey"
            label="API Key"
            placeholder="硅基流动API Key"
            type="password"
          />
          <van-field label="模型选择">
            <template #input>
              <select v-model="ttsSiliconFlowModel" class="tts-voice-select">
                <option value="" disabled>请选择模型</option>
                <option v-for="model in siliconflowModels" :key="model.id" :value="model.id">
                  {{ model.name }}
                </option>
              </select>
            </template>
          </van-field>
        </template>

        <!-- MiniMax TTS配置 (仅在使用MiniMax时显示) -->
        <template v-if="ttsServiceName === 'minimax-tts'">
          <van-field
            v-model="ttsMinimaxApiKey"
            label="API Key"
            placeholder="留空使用系统默认"
            type="password"
          />
          <van-field
            v-model="ttsMinimaxModel"
            label="模型"
            placeholder="speech-2.8-hd"
          />
          <div class="field-hint">
            Token Plan Plus用户每日4000字符限额
          </div>
          <van-button
            type="default"
            size="small"
            plain
            class="usage-check-btn"
            :loading="minimaxUsageChecking"
            :disabled="minimaxUsageChecking"
            @click="handleCheckMinimaxUsage"
          >
            {{ minimaxUsageChecking ? '查询中...' : '查询剩余配额' }}
          </van-button>
        </template>

        <!-- 服务地址 (仅在使用Kokoro时显示) -->
        <van-field
          v-if="ttsServiceName === 'kokoro-tts'"
          v-model="ttsApiUrl"
          label="服务地址"
          placeholder="留空使用系统默认"
          :rules="[{ validator: validateTtsUrl, message: '地址必须以 http:// 或 https:// 开头' }]"
        >
          <template #label>
            <span>服务地址</span>
            <van-icon name="info-o" class="field-info-icon" @click="showTtsUrlHelp" />
          </template>
        </van-field>
        <div v-if="ttsServiceName === 'kokoro-tts'" class="field-hint">
          当前默认: {{ defaultTtsConfig.api_url }}
        </div>

        <!-- 测试按钮 -->
        <div class="tts-test-section">
          <van-button
            type="primary"
            size="small"
            icon="play-circle-o"
            :loading="ttsTesting"
            @click="testTts"
          >
            测试朗读
          </van-button>
          <p class="test-text">{{ ttsTestText }}</p>
        </div>
      </div>
    </van-dialog>

    <!-- 词典设置弹窗 -->
    <van-dialog
      v-model:show="showDictionarySettingsDialog"
      title="词典设置"
      show-cancel-button
      confirm-button-text="保存"
      cancel-button-text="取消"
      @confirm="saveDictionarySettings"
    >
      <div class="settings-dialog-content">
        <van-radio-group v-model="dictionarySource">
          <van-cell-group>
            <van-cell title="FreeDictionaryAPI (在线)" clickable @click="dictionarySource = 'api'">
              <template #right-icon>
                <van-radio name="api" />
              </template>
              <template #label>
                <span class="dict-label">使用在线词典API，需要网络连接</span>
              </template>
            </van-cell>
            <van-cell
              title="本地ECDICT"
              clickable
              @click="dictionarySource = 'local'"
              :class="{ 'disabled-cell': !ecdictAvailable }"
            >
              <template #right-icon>
                <van-radio name="local" :disabled="!ecdictAvailable" />
              </template>
              <template #label>
                <span class="dict-label">
                  {{ ecdictAvailable ? '使用本地词典，无需网络' : '本地词典未安装' }}
                </span>
              </template>
            </van-cell>
          </van-cell-group>
        </van-radio-group>

        <!-- 百度翻译API设置（仅管理员可见） -->
        <div class="baidu-settings" v-if="authStore.isAdmin" style="margin-top: 16px;">
          <div class="baidu-settings-header">百度翻译API（用于句子翻译）</div>
          <div v-if="translationApis.length === 0" class="baidu-add-api">
            <van-field
              v-model="newBaiduAppId"
              label="APP ID"
              placeholder="百度翻译APP ID"
            />
            <van-field
              v-model="newBaiduAppKey"
              label="APP Key"
              placeholder="百度翻译APP Key"
              type="password"
            />
            <div class="baidu-add-btn">
              <van-button type="primary" block @click="addBaiduApi">添加百度翻译API</van-button>
            </div>
          </div>
          <div v-else class="baidu-api-config">
            <van-cell-group>
              <van-cell title="APP ID">
                <template #value>
                  <span class="app-id-display">{{ translationApis[0]?.app_id }}</span>
                </template>
              </van-cell>
              <van-cell title="状态">
                <template #value>
                  <van-switch v-model="translationApis[0].is_active" size="small" @change="saveTranslationApi" />
                </template>
              </van-cell>
            </van-cell-group>
            <div class="baidu-api-actions">
              <van-button size="small" type="danger" plain @click="deleteTranslationApi(translationApis[0].id)">删除</van-button>
            </div>
            <div class="translation-hint">
              已配置百度翻译API（用于句子翻译）
            </div>
          </div>
        </div>
      </div>
    </van-dialog>


    <!-- 音标设置弹窗 -->
    <van-dialog
      v-model:show="showPhoneticSettingsDialog"
      title="音标设置"
      show-cancel-button
      confirm-button-text="保存"
      cancel-button-text="取消"
      @confirm="savePhoneticSettings"
    >
      <div class="settings-dialog-content">
        <van-radio-group v-model="phoneticAccent">
          <van-cell-group>
            <van-cell title="英式音标 (UK)" clickable @click="phoneticAccent = 'uk'">
              <template #right-icon>
                <van-radio name="uk" />
              </template>
              <template #label>
                <span class="dict-label">使用英式发音音标，如 /həˈləʊ/</span>
              </template>
            </van-cell>
            <van-cell title="美式音标 (US)" clickable @click="phoneticAccent = 'us'">
              <template #right-icon>
                <van-radio name="us" />
              </template>
              <template #label>
                <span class="dict-label">使用美式发音音标，如 /həˈloʊ/</span>
              </template>
            </van-cell>
          </van-cell-group>
        </van-radio-group>
      </div>
    </van-dialog>

    <!-- 语音配置错误清单弹窗 -->
    <!-- 音频检查修复弹窗 -->
    <AudioFixDialog
      v-model:show="showAudioErrorDialog"
      :fixed-list="audioFixedList"
      :error-list="audioErrorList"
      @edit-book="handleEditBookFromAudioFix"
    />

    <!-- 补充翻译+中文语音进度弹窗 -->
    <van-dialog
      v-model:show="showSupplementProgress"
      title="补充翻译+中文语音"
      :close-on-click-overlay="false"
      :show-cancel-button="supplementLoading"
      :show-confirm-button="!supplementLoading"
      confirm-button-text="关闭"
      cancel-button-text="取消"
      @cancel="handleCancelSupplement"
    >
      <div class="supplement-progress-content">
        <van-progress
          :percentage="supplementProgress"
          :stroke-width="8"
          :show-pivot="true"
        />
        <div class="progress-message">
          {{ supplementMessage }}
        </div>
      </div>
    </van-dialog>

    <!-- 预编译缓存进度弹窗 -->
    <van-dialog
      v-model:show="showPrecompileProgress"
      title="预编译缓存"
      :close-on-click-overlay="false"
      :show-cancel-button="false"
      :show-confirm-button="!precompileLoading"
      confirm-button-text="关闭"
    >
      <div class="supplement-progress-content">
        <van-progress
          :percentage="precompileProgress"
          :stroke-width="8"
          :show-pivot="true"
        />
        <div class="progress-message">
          {{ precompileMessage }}
        </div>
      </div>
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showNotify, showToast, showLoadingToast, closeToast } from 'vant'
import { useAuthStore, api } from '@/store/auth'
import BookEditDialog from '@/components/BookEditDialog.vue'
import AudioFixDialog from '@/components/AudioFixDialog.vue'

// 定义组件名称，用于 keep-alive 匹配
defineOptions({
  name: 'Home'
})

interface Book {
  id: string
  title: string
  level: string
  file_path: string
  page_count: number
  cover_path?: string
  is_read?: number
}

interface BookGroup {
  id: number
  name: string
  type: string
  books: Book[]
}

interface PopoverAction {
  text: string
  icon: string
  key: string
}

const router = useRouter()
const authStore = useAuthStore()

// 数据
const bookGroups = ref<BookGroup[]>([])
const loading = ref(false)
const searchText = ref('')
const activeNames = ref<number>(0)

// 导航栏状态
const showBookPopover = ref(false)
const showSettingsPopover = ref(false)
const showUserPopover = ref(false)

// 导入相关
const showImportDialog = ref(false)
const importCategoryId = ref(0) // 导入到的分类ID
const fileInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const importCompleted = ref(false)
const selectedFile = ref<File | null>(null)
const selectedFiles = ref<File[]>([]) // 多选文件列表
const isBatchImport = ref(false) // 标记是否是批量导入（多本书）
const isDragOver = ref(false)
const importProgress = ref(0)
const importStatus = ref('')
// 上传进度相关
const uploading = ref(false)
const uploadProgress = ref(0)
const uploadStatus = ref('')
const currentBookId = ref('')
const showChoiceDialog = ref(false)
const overwriteMode = ref('')
const isZipImport = ref(false) // 标记是否是ZIP导入
const isBatchMdImport = ref(false) // 标记是否是批量MD导入
const showDuplicateDialog = ref(false) // 重复书籍检测对话框

// 导出进度相关
const showExportProgressDialog = ref(false)
const exportProgress = ref(0)
const exportStatus = ref('')
const exportCurrentBook = ref('')
const duplicateCheckResult = ref<any>({
  has_duplicates: false,
  duplicate_books: [],
  new_books: [],
  total_books: 0
})
const importAction = ref<'skip' | 'overwrite' | 'selected' | null>(null) // 导入操作类型
const selectedDuplicateBooks = ref<string[]>([]) // 用户选中的重复书籍ID列表

// 分组相关
const showAddGroupDialog = ref(false)
const newGroupName = ref('')

// 编辑相关状态
const showEditDialog = ref(false)
const editContent = ref('')
const currentBookTitle = ref('')

// 多选模式
const isMultiSelect = ref(false)
const selectedBooks = ref<string[]>([])

// 书籍右键菜单
const showContextMenuPopup = ref(false)
const contextMenuPos = ref({ x: 0, y: 0 })
const contextMenuBook = ref<Book | null>(null)
const contextMenuGroupId = ref(0)

// 分组右键菜单
const showGroupContextMenuPopup = ref(false)
const groupContextMenuPos = ref({ x: 0, y: 0 })
const contextMenuGroup = ref<BookGroup | null>(null)

// 隐藏已读书籍状态（按分组存储）
const hideReadBooksMap = ref<Record<number, boolean>>({})

// swipe-cell 组件引用
const swipeCellRefs = ref<Record<string, any>>({})

// 修改分组名称
const showRenameGroupDialog = ref(false)
const renameGroupName = ref('')

// 重命名书籍
const showRenameBookDialog = ref(false)
const renameBookName = ref('')

// 移动到分组对话框
const showMoveDialog = ref(false)
const selectedMoveCategory = ref(0)
const categoriesForMove = ref<{ id: number; name: string }[]>([])
const showAddGroupInMove = ref(false)
const newGroupInMove = ref('')
const currentGroupId = ref(0)
const movingBooks = ref(false)

// 修改封面对话框
const showCoverDialog = ref(false)
const coverInput = ref<HTMLInputElement | null>(null)
const previewCover = ref('')
const showCoverPicker = ref(false)
const mdImages = ref<string[]>([])
const selectedMdImage = ref('')

// 朗读设置弹窗
const showTtsSettingsDialog = ref(false)
const ttsServiceName = ref('edge-tts')
const ttsVoice = ref('')
const ttsSpeed = ref(1.0)
const ttsApiUrl = ref('')
// 豆包TTS配置
const ttsAppId = ref('')
const ttsAccessKey = ref('')
const ttsResourceId = ref('')
// 硅基流动TTS配置
const ttsSiliconFlowApiKey = ref('')
const ttsSiliconFlowModel = ref('')
// Edge-TTS配置
const ttsEdgeTtsVoice = ref('')
const defaultTtsConfig = ref({
  service_name: 'edge-tts',
  voice: 'en-US-AriaNeural',
  speed: 1.0,
  api_url: 'http://localhost:8880/v1/audio/speech',
  app_id: '',
  access_key: '',
  resource_id: '',
  siliconflow_api_key: '',
  siliconflow_model: 'fnlp/MOSS-TTSD-v0.5',
  siliconflow_voice: 'anna',
  edge_tts_voice: 'en-US-AriaNeural',
  edge_tts_speed: 1.0,
  minimax_api_key: '',
  minimax_model: 'speech-2.8-hd',
  minimax_voice: 'male-qn-qingse',
  minimax_speed: 1.0
})
const ttsVoices = ref<{id: string, name: string}[]>([])
// 硅基流动固定模型和语音列表
const siliconflowModels = [
  { id: 'fnlp/MOSS-TTSD-v0.5', name: 'MOSS TTSD v0.5' },
  { id: 'FunAudioLLM/CosyVoice2-0.5B', name: 'CosyVoice2 0.5B' },
  { id: 'IndexTeam/IndexTTS-2', name: 'IndexTTS 2' }
]
const siliconflowVoices = [
  { id: 'anna', name: 'Anna' },
  { id: 'alex', name: 'Alex' },
  { id: 'bella', name: 'Bella' },
  { id: 'benjamin', name: 'Benjamin' },
  { id: 'charles', name: 'Charles' },
  { id: 'claire', name: 'Claire' },
  { id: 'david', name: 'David' },
  { id: 'diana', name: 'Diana' }
]
// Edge-TTS语音列表（从后端动态获取）
const edgeTtsVoices = ref<{id: string, name: string}[]>([])
// MiniMax TTS配置
const ttsMinimaxApiKey = ref('')
const ttsMinimaxModel = ref('')
const ttsMinimaxVoice = ref('')
const ttsMinimaxSpeed = ref(1.0)
// MiniMax TTS语音列表（从后端动态获取）
const minimaxVoices = ref<{id: string, name: string}[]>([])
const minimaxUsageChecking = ref(false)
const ttsTesting = ref(false)
const ttsTestText = "She meticulously practiced the intricate piano sonata, her fingers dancing across the ivory keys with a grace that belied the immense concentration required."
let currentTestAudio: HTMLAudioElement | null = null

// 词典设置弹窗
const showDictionarySettingsDialog = ref(false)
const dictionarySource = ref('local')
const ecdictAvailable = ref(false)

// 音标设置弹窗
const showPhoneticSettingsDialog = ref(false)
const phoneticAccent = ref('uk')

// 翻译API相关状态
const translationApis = ref<{id: number, app_id: string, is_active: boolean}[]>([])
const selectedTranslationApiId = ref<number | null>(null)
const newBaiduAppId = ref('')
const newBaiduAppKey = ref('')

// 加载用户设置
const loadUserSettings = async () => {
  try {
    const res = await api.get('/settings/')
    dictionarySource.value = res.data.dictionary.dictionary_source
    phoneticAccent.value = res.data.phonetic?.accent || 'uk'

    // 获取服务名称
    const serviceName = res.data.tts?.service_name || 'edge-tts'

    // 根据服务类型选择对应的语音和语速配置
    const isKokoro = serviceName === 'kokoro-tts'
    const voice = isKokoro
      ? (res.data.tts?.kokoro_voice || 'bf_v0isabella')
      : (res.data.tts?.doubao_voice || 'en_male_corey_emo_v2_mars_bigtts')
    const speed = isKokoro
      ? (res.data.tts?.kokoro_speed ?? 1.0)
      : (res.data.tts?.doubao_speed ?? 1.0)

    // 保存默认配置（后端已处理默认值逻辑，直接使用）
    defaultTtsConfig.value = {
      service_name: serviceName,
      voice: voice,
      speed: speed,
      api_url: res.data.tts?.kokoro_api_url || '',
      app_id: res.data.tts?.doubao_app_id || '',
      access_key: res.data.tts?.doubao_access_key || '',
      resource_id: res.data.tts?.doubao_resource_id || '',
      siliconflow_api_key: res.data.tts?.siliconflow_api_key || '',
      siliconflow_model: res.data.tts?.siliconflow_model || 'fnlp/MOSS-TTSD-v0.5',
      siliconflow_voice: res.data.tts?.siliconflow_voice || 'anna',
      edge_tts_voice: res.data.tts?.edge_tts_voice || 'en-US-AriaNeural',
      edge_tts_speed: res.data.tts?.edge_tts_speed ?? 1.0,
      minimax_api_key: res.data.tts?.minimax_api_key || '',
      minimax_model: res.data.tts?.minimax_model || 'speech-2.8-hd',
      minimax_voice: res.data.tts?.minimax_voice || 'male-qn-qingse',
      minimax_speed: res.data.tts?.minimax_speed ?? 1.0
    }
    // 使用后端返回的值（已包含.env默认值）
    ttsServiceName.value = defaultTtsConfig.value.service_name
    ttsVoice.value = defaultTtsConfig.value.voice
    ttsSpeed.value = defaultTtsConfig.value.speed
    ttsApiUrl.value = defaultTtsConfig.value.api_url || ''
    // 豆包配置
    ttsAppId.value = defaultTtsConfig.value.app_id || ''
    ttsAccessKey.value = defaultTtsConfig.value.access_key || ''
    ttsResourceId.value = defaultTtsConfig.value.resource_id || ''
    // 硅基流动配置
    ttsSiliconFlowApiKey.value = res.data.tts?.siliconflow_api_key || ''
    ttsSiliconFlowModel.value = res.data.tts?.siliconflow_model || 'fnlp/MOSS-TTSD-v0.5'
    // Edge-TTS配置
    ttsEdgeTtsVoice.value = res.data.tts?.edge_tts_voice || 'en-US-AriaNeural'
    // MiniMax TTS配置
    ttsMinimaxApiKey.value = res.data.tts?.minimax_api_key || ''
    ttsMinimaxModel.value = res.data.tts?.minimax_model || 'speech-2.8-hd'
    ttsMinimaxVoice.value = res.data.tts?.minimax_voice || 'male-qn-qingse'
    ttsMinimaxSpeed.value = res.data.tts?.minimax_speed ?? 1.0

    // 加载UI设置（隐藏已读书籍状态）
    if (res.data.ui?.hide_read_books_map) {
      hideReadBooksMap.value = res.data.ui.hide_read_books_map
    }
  } catch (error) {
    console.error('加载用户设置失败:', error)
  }
}

// 加载TTS语音列表
const loadTtsVoices = async () => {
  try {
    const res = await api.get('/settings/tts/voices')
    // 如果返回的是数组，说明后端没有正确处理
    if (Array.isArray(res.data)) {
      // 手动转换字符串数组为对象数组
      ttsVoices.value = res.data.map((v: string) => ({ id: v, name: v }))
    } else {
      ttsVoices.value = res.data.voices || []
    }

    // 如果当前语音不在列表中，且是有效的Kokoro语音（以af_/am_/bf_/bm_开头），则添加它
    // 这处理了新语音可用但前端映射表未及时更新的情况
    if (ttsServiceName.value === 'kokoro-tts' && ttsVoice.value) {
      const voiceExists = ttsVoices.value.some((v: {id: string, name: string}) => v.id === ttsVoice.value)
      const isKokoroVoice = /^[ab]f_/.test(ttsVoice.value) || /^[ab]m_/.test(ttsVoice.value)
      if (!voiceExists && isKokoroVoice) {
        ttsVoices.value.unshift({
          id: ttsVoice.value,
          name: ttsVoice.value + ' (当前使用)'
        })
      }
    }
  } catch (error) {
    console.error('加载语音列表失败:', error)
    // 加载失败时清空列表，显示错误提示
    ttsVoices.value = []
    showNotify({ type: 'warning', message: '无法获取语音列表，请检查本地TTS服务是否运行' })
  }
}

// 加载Edge-TTS语音列表
const loadEdgeTtsVoices = async () => {
  try {
    const res = await api.get('/settings/tts/edge/voices')
    if (res.data.voices && res.data.voices.length > 0) {
      edgeTtsVoices.value = res.data.voices
    } else {
      edgeTtsVoices.value = []
      showNotify({ type: 'warning', message: '没有可用的Edge-TTS语音模型' })
    }
  } catch (error) {
    console.error('加载Edge-TTS语音列表失败:', error)
    edgeTtsVoices.value = []
    showNotify({ type: 'warning', message: '无法获取Edge-TTS语音列表，请确保edge-tts已安装' })
  }
}

// 加载MiniMax TTS语音列表
const loadMinimaxVoices = async () => {
  try {
    const res = await api.get('/settings/tts/minimax/voices')
    if (res.data.error) {
      console.warn('获取MiniMax语音列表失败:', res.data.error)
      minimaxVoices.value = []
    } else if (res.data.voices && res.data.voices.length > 0) {
      minimaxVoices.value = res.data.voices
    } else {
      minimaxVoices.value = []
    }
  } catch (error) {
    console.error('加载MiniMax语音列表失败:', error)
    minimaxVoices.value = []
  }
}

// 检查MiniMax用量
const checkMinimaxUsage = async () => {
  try {
    console.log('开始查询MiniMax用量...')
    const res = await api.get('/settings/tts/minimax/usage')
    console.log('MiniMax用量响应:', res.data)
    if (res.data.error) {
      showNotify({ type: 'warning', message: res.data.error })
      return null
    }
    return res.data
  } catch (error: any) {
    console.error('检查MiniMax用量失败:', error)
    showNotify({ type: 'warning', message: error.message || '无法查询MiniMax用量' })
    return null
  }
}

// 豆包TTS音色列表映射
const doubaoVoices = [
  { id: 'en_male_corey_emo_v2_mars_bigtts', name: '英式英语 - Corey' },
  { id: 'en_female_nadia_tips_emo_v2_mars_bigtts', name: '英式英语 - Nadia' },
  { id: 'zh_female_shuangkuaisisi_emo_v2_mars_bigtts', name: '中文/英式 - 爽快思思(多情感)' },
  { id: 'en_female_candice_emo_v2_mars_bigtts', name: '美式英语 - Candice' },
  { id: 'en_female_skye_emo_v2_mars_bigtts', name: '美式英语 - Serena' },
  { id: 'en_male_glen_emo_v2_mars_bigtts', name: '美式英语 - Glen' },
  { id: 'en_male_sylus_emo_v2_mars_bigtts', name: '美式英语 - Sylus' },
  { id: 'zh_female_yingyujiaoyu_mars_bigtts', name: '中文/英式 - Tina老师' },
  { id: 'en_female_emily_mars_bigtts', name: '英式英语 - Emily' },
  { id: 'zh_male_xudong_conversation_wvae_bigtts', name: '英式英语 - Daniel' },
  { id: 'en_female_anna_mars_bigtts', name: '英式英语 - Anna' },
  { id: 'zh_female_shuangkuaisisi_moon_bigtts', name: '中文/美式 - 爽快思思/Skye' },
]

// 根据服务类型获取对应的语音列表
const availableVoices = computed(() => {
  if (ttsServiceName.value === 'doubao-tts') {
    return doubaoVoices
  }
  if (ttsServiceName.value === 'siliconflow-tts') {
    return siliconflowVoices
  }
  if (ttsServiceName.value === 'edge-tts') {
    return edgeTtsVoices.value
  }
  if (ttsServiceName.value === 'minimax-tts') {
    return minimaxVoices.value
  }
  return ttsVoices.value
})

// 监听服务切换，从数据库恢复该服务的设置
watch(ttsServiceName, async (newService, oldService) => {
  if (newService !== oldService && oldService !== undefined) {

    try {
      // 从数据库获取最新设置
      const res = await api.get('/settings/')
      const ttsSettings = res.data.tts

      if (newService === 'kokoro-tts') {
        // 恢复 Kokoro 设置
        await loadTtsVoices()
        const savedVoice = ttsSettings?.kokoro_voice
        const savedSpeed = ttsSettings?.kokoro_speed

        // 优先使用数据库中的语音，如果没有则使用 .env 默认值
        if (savedVoice) {
          ttsVoice.value = savedVoice
        } else if (ttsVoices.value.length > 0) {
          // 检查默认语音是否在列表中
          const defaultVoice = defaultTtsConfig.value.voice || 'bf_v0isabella'
          const voiceExists = ttsVoices.value.some((v: {id: string, name: string}) => v.id === defaultVoice)
          ttsVoice.value = voiceExists ? defaultVoice : ttsVoices.value[0].id
        }

        // 恢复语速
        ttsSpeed.value = savedSpeed ?? defaultTtsConfig.value.speed ?? 1.0
      } else if (newService === 'siliconflow-tts') {
        // 恢复硅基流动设置（不支持语速调节）
        const savedVoice = ttsSettings?.siliconflow_voice
        const savedModel = ttsSettings?.siliconflow_model

        // 恢复语音和模型
        ttsVoice.value = savedVoice || 'anna'
        ttsSiliconFlowModel.value = savedModel || 'fnlp/MOSS-TTSD-v0.5'
      } else if (newService === 'edge-tts') {
        // 恢复 Edge-TTS 设置
        await loadEdgeTtsVoices()
        const savedVoice = ttsSettings?.edge_tts_voice
        const savedSpeed = ttsSettings?.edge_tts_speed

        // 恢复语音和语速
        if (savedVoice) {
          ttsVoice.value = savedVoice
        } else if (edgeTtsVoices.value.length > 0) {
          ttsVoice.value = edgeTtsVoices.value[0].id
        }
        ttsSpeed.value = savedSpeed ?? 1.0
      } else if (newService === 'minimax-tts') {
        // 恢复 MiniMax TTS 设置
        await loadMinimaxVoices()
        const savedVoice = ttsSettings?.minimax_voice
        const savedSpeed = ttsSettings?.minimax_speed
        const savedModel = ttsSettings?.minimax_model

        // 恢复语音、语速和模型
        if (savedVoice) {
          ttsVoice.value = savedVoice
        } else if (minimaxVoices.value.length > 0) {
          ttsVoice.value = minimaxVoices.value[0].id
        }
        ttsSpeed.value = savedSpeed ?? 1.0
        ttsMinimaxModel.value = savedModel || 'speech-2.8-hd'
      } else {
        // 恢复豆包设置
        const savedVoice = ttsSettings?.doubao_voice
        const savedSpeed = ttsSettings?.doubao_speed
        const savedResourceId = ttsSettings?.doubao_resource_id

        // 优先使用数据库中的语音
        ttsVoice.value = savedVoice || 'en_male_corey_emo_v2_mars_bigtts'
        ttsSpeed.value = savedSpeed ?? 1.0
        ttsResourceId.value = savedResourceId || defaultTtsConfig.value.resource_id || 'seed-tts-1.0'
      }
    } catch (error) {
      console.error('恢复设置失败:', error)
      // 使用默认值
      if (newService === 'kokoro-tts') {
        ttsVoice.value = 'bf_v0isabella'
        ttsSpeed.value = 1.0
      } else if (newService === 'siliconflow-tts') {
        ttsVoice.value = 'anna'
        ttsSiliconFlowModel.value = 'fnlp/MOSS-TTSD-v0.5'
      } else if (newService === 'edge-tts') {
        ttsVoice.value = ''
        ttsSpeed.value = 1.0
      } else if (newService === 'minimax-tts') {
        ttsVoice.value = 'male-qn-qingse'
        ttsSpeed.value = 1.0
        ttsMinimaxModel.value = 'speech-2.8-hd'
      } else {
        ttsVoice.value = 'en_male_corey_emo_v2_mars_bigtts'
        ttsSpeed.value = 1.0
        ttsResourceId.value = 'seed-tts-1.0'
      }
    }
  }
})

// 加载词典状态
const loadDictionaryStatus = async () => {
  try {
    const res = await api.get('/dictionary/status')
    ecdictAvailable.value = res.data.ecdict_available
  } catch (error) {
    console.error('加载词典状态失败:', error)
  }
}

// 保存词典设置
const saveDictionarySettings = async () => {
  try {
    await api.put('/settings/dictionary', {
      dictionary_source: dictionarySource.value
    })
    showNotify({ type: 'success', message: '词典设置已保存', duration: 1500 })
    showDictionarySettingsDialog.value = false
  } catch (error: any) {
    console.error('保存词典设置失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
  }
}

// 保存音标设置
const savePhoneticSettings = async () => {
  try {
    await api.put('/settings/phonetic', {
      accent: phoneticAccent.value
    })
    showNotify({ type: 'success', message: '音标设置已保存', duration: 1500 })
    showPhoneticSettingsDialog.value = false
  } catch (error: any) {
    console.error('保存音标设置失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
  }
}

// 加载翻译设置
const loadTranslationSettings = async () => {
  try {
    const res = await api.get('/translation/settings')
    selectedTranslationApiId.value = res.data.selected_api_id
    translationApis.value = res.data.apis || []
  } catch (error) {
    console.error('加载翻译设置失败:', error)
  }
}

// 添加百度翻译API
const addBaiduApi = async () => {
  if (!newBaiduAppId.value || !newBaiduAppKey.value) {
    showToast('请填写APP ID和APP Key')
    return
  }

  try {
    await api.post('/translation/apis', {
      name: '百度翻译',
      app_id: newBaiduAppId.value,
      app_key: newBaiduAppKey.value,
      is_active: true
    })
    showNotify({ type: 'success', message: '百度翻译API已添加', duration: 1500 })
    newBaiduAppId.value = ''
    newBaiduAppKey.value = ''
    // 自动选中新添加的API
    await loadTranslationSettings()
    if (translationApis.value.length > 0) {
      await saveSelectedTranslationApi(translationApis.value[0].id)
    }
  } catch (error: any) {
    console.error('添加翻译API失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '添加失败' })
  }
}

// 保存选中的翻译API
const saveSelectedTranslationApi = async (apiId: number | null) => {
  try {
    await api.put('/translation/select', null, {
      params: { api_id: apiId }
    })
    selectedTranslationApiId.value = apiId
  } catch (error: any) {
    console.error('切换翻译API失败:', error)
  }
}

// 更新翻译API启用状态
const saveTranslationApi = async () => {
  if (translationApis.value.length === 0) return

  try {
    await api.put(`/translation/apis/${translationApis.value[0].id}`, {
      name: '百度翻译',
      app_id: translationApis.value[0].app_id,
      app_key: '', // 不更新app_key
      is_active: translationApis.value[0].is_active
    })
  } catch (error: any) {
    console.error('更新翻译API失败:', error)
  }
}

// 删除翻译API
const deleteTranslationApi = async (apiId: number) => {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '确定要删除百度翻译API吗？'
    })
    await api.delete(`/translation/apis/${apiId}`)
    showNotify({ type: 'success', message: '翻译API已删除', duration: 1500 })
    await loadTranslationSettings()
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除翻译API失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
    }
  }
}

// 验证TTS URL格式
const validateTtsUrl = (value: string) => {
  if (!value || value.trim() === '') {
    return true // 允许为空
  }
  return value.startsWith('http://') || value.startsWith('https://')
}

// 显示TTS URL帮助
const showTtsUrlHelp = () => {
  showToast({
    message: '设置自定义Kokoro TTS服务地址，留空则使用系统默认配置',
    duration: 3000
  })
}

// 查询MiniMax用量
const handleCheckMinimaxUsage = async () => {
  minimaxUsageChecking.value = true
  try {
    const usage = await checkMinimaxUsage()
    console.log('[DEBUG] MiniMax usage response:', JSON.stringify(usage, null, 2))
    if (usage && usage.model_remains) {
      // 从 model_remains 数组中找到 speech-hd 的配额
      const speechHdRemain = usage.model_remains.find((item: any) => 
        item.model_name && item.model_name.toLowerCase().includes('speech-hd')
      )
      
      let message = ''
      
      if (speechHdRemain) {
        // current_interval_usage_count 实际是剩余配额（非已用）
        const dailyRemaining = speechHdRemain.current_interval_usage_count || 0
        const dailyTotal = speechHdRemain.current_interval_total_count || 0
        const dailyUsed = dailyTotal - dailyRemaining
        const weeklyRemaining = speechHdRemain.current_weekly_usage_count || 0
        const weeklyTotal = speechHdRemain.current_weekly_total_count || 0
        const weeklyUsed = weeklyTotal - weeklyRemaining
        
        message = `【speech-hd 语音配额】\n\n`
        if (dailyTotal > 0) {
          message += `今日配额: ${dailyTotal} 字符\n已用: ${dailyUsed} 字符\n剩余: ${dailyRemaining} 字符\n\n`
        }
        if (weeklyTotal > 0) {
          message += `本周配额: ${weeklyTotal} 字符\n已用: ${weeklyUsed} 字符\n剩余: ${weeklyRemaining} 字符`
        }
      } else {
        message = '未找到 speech-hd 配额信息'
      }
      
      showConfirmDialog({
        title: 'MiniMax 语音配额',
        message: message,
        confirmButtonText: '确定'
      })
    }
  } finally {
    minimaxUsageChecking.value = false
  }
}

// 停止TTS测试播放
const stopTtsTest = () => {
  if (currentTestAudio) {
    currentTestAudio.pause()
    currentTestAudio.currentTime = 0
    currentTestAudio = null
    ttsTesting.value = false
  }
}

// 测试TTS朗读
const testTts = async () => {
  // 如果正在播放，先停止
  if (currentTestAudio) {
    stopTtsTest()
    showNotify({ type: 'success', message: '已停止播放', duration: 1000 })
    return
  }

  ttsTesting.value = true
  try {
    // 使用界面当前设置的语音和语速
    const voice = ttsVoice.value || defaultTtsConfig.value.voice
    const speed = ttsSpeed.value ?? 1.0
    
    // 构建请求体
    const requestBody: any = {
      text: ttsTestText,
      voice: voice,
      speed: speed,
      service_name: ttsServiceName.value
    }
    
    // 如果是硅基流动，添加额外参数
    if (ttsServiceName.value === 'siliconflow-tts') {
      requestBody.siliconflow_api_key = ttsSiliconFlowApiKey.value || null
      requestBody.siliconflow_model = ttsSiliconFlowModel.value || null
    }
    
    // 如果是MiniMax，添加额外参数
    if (ttsServiceName.value === 'minimax-tts') {
      requestBody.minimax_api_key = ttsMinimaxApiKey.value || null
      requestBody.minimax_model = ttsMinimaxModel.value || null
    }
    
    const response = await fetch('/api/v1/tts/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify(requestBody)
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'TTS请求失败' }))
      throw new Error(errorData.detail || 'TTS请求失败')
    }

    const data = await response.json()
    
    // 支持 url 或 audio_data 两种格式
    if (data.audio_data) {
      // base64 音频数据
      const audioSrc = `data:audio/mp3;base64,${data.audio_data}`
      currentTestAudio = new Audio(audioSrc)
      if (ttsServiceName.value === 'doubao-tts' && speed !== 1.0) {
        currentTestAudio.playbackRate = speed
      }
      currentTestAudio.play()
      showNotify({ type: 'success', message: '正在播放测试语音', duration: 1500 })

      // 播放结束后清理
      currentTestAudio.onended = () => {
        currentTestAudio = null
      }
    } else if (data.url) {
      // 播放音频（豆包TTS使用前端播放速度控制）
      currentTestAudio = new Audio(data.url)
      if (ttsServiceName.value === 'doubao-tts' && speed !== 1.0) {
        currentTestAudio.playbackRate = speed
      }
      currentTestAudio.play()
      showNotify({ type: 'success', message: '正在播放测试语音', duration: 1500 })

      // 播放结束后清理
      currentTestAudio.onended = () => {
        currentTestAudio = null
      }
    } else {
      throw new Error('未获取到音频数据')
    }
  } catch (error: any) {
    console.error('TTS测试失败:', error)
    const errorMsg = error.message || '朗读测试失败'
    // 针对不同TTS服务的特殊提示
    if (ttsServiceName.value === 'doubao-tts' && errorMsg.includes('app_id')) {
      showNotify({ type: 'danger', message: '豆包TTS需要配置APP ID和Access Key，请在设置中填写' })
    } else if (ttsServiceName.value === 'siliconflow-tts' && errorMsg.includes('api_key')) {
      showNotify({ type: 'danger', message: '硅基流动TTS需要配置API Key，请在设置中填写' })
    } else {
      showNotify({ type: 'danger', message: errorMsg })
    }
  } finally {
    ttsTesting.value = false
  }
}

// 保存朗读设置
const saveTtsSettings = async () => {
  // 验证URL格式
  if (ttsApiUrl.value && !validateTtsUrl(ttsApiUrl.value)) {
    showNotify({ type: 'warning', message: '服务地址必须以 http:// 或 https:// 开头' })
    return
  }

  // 验证语速范围
  const isKokoro = ttsServiceName.value === 'kokoro-tts'
  const isSiliconFlow = ttsServiceName.value === 'siliconflow-tts'
  const isEdgeTts = ttsServiceName.value === 'edge-tts'
  const isMinimax = ttsServiceName.value === 'minimax-tts'
  if (isKokoro && (ttsSpeed.value < 0.25 || ttsSpeed.value > 4.0)) {
    showNotify({ type: 'warning', message: 'Kokoro 朗读速度必须在 0.25 到 4.0 之间' })
    return
  }
  if (isMinimax && (ttsSpeed.value < 0.25 || ttsSpeed.value > 4.0)) {
    showNotify({ type: 'warning', message: 'MiniMax 朗读速度必须在 0.25 到 4.0 之间' })
    return
  }
  if ((isEdgeTts || !isKokoro && !isSiliconFlow && !isMinimax) && (ttsSpeed.value < 0.5 || ttsSpeed.value > 2.0)) {
    showNotify({ type: 'warning', message: '朗读速度必须在 0.5 到 2.0 之间' })
    return
  }

  try {
    // 根据服务类型构建请求体
    const requestBody: any = {
      service_name: ttsServiceName.value.trim() || 'kokoro-tts'
    }

    if (isKokoro) {
      // Kokoro TTS 配置
      requestBody.kokoro_voice = ttsVoice.value.trim()
      requestBody.kokoro_speed = ttsSpeed.value
      requestBody.kokoro_api_url = ttsApiUrl.value.trim() || null
    } else if (isSiliconFlow) {
      // 硅基流动 TTS 配置（不支持语速调节）
      requestBody.siliconflow_api_key = ttsSiliconFlowApiKey.value.trim() || null
      requestBody.siliconflow_model = ttsSiliconFlowModel.value.trim() || null
      requestBody.siliconflow_voice = ttsVoice.value.trim()
    } else if (isEdgeTts) {
      // Edge-TTS 配置
      requestBody.edge_tts_voice = ttsVoice.value.trim()
      requestBody.edge_tts_speed = ttsSpeed.value
    } else if (isMinimax) {
      // MiniMax TTS 配置
      requestBody.minimax_api_key = ttsMinimaxApiKey.value.trim() || null
      requestBody.minimax_voice = ttsVoice.value.trim()
      requestBody.minimax_speed = ttsSpeed.value
      requestBody.minimax_model = ttsMinimaxModel.value.trim() || 'speech-2.8-hd'
    } else {
      // 豆包 TTS 配置
      requestBody.doubao_voice = ttsVoice.value.trim()
      requestBody.doubao_speed = ttsSpeed.value
      requestBody.doubao_app_id = ttsAppId.value.trim() || null
      requestBody.doubao_access_key = ttsAccessKey.value.trim() || null
      requestBody.doubao_resource_id = ttsResourceId.value.trim() || null
    }

    await api.put('/settings/tts', requestBody)
    showNotify({ type: 'success', message: '朗读设置已保存', duration: 1500 })
    showTtsSettingsDialog.value = false
  } catch (error: any) {
    console.error('保存朗读设置失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '保存失败' })
  }
}

// 书籍封面对应缓存（用于处理图片加载失败）
const coverErrorMap = ref<Record<string, boolean>>({})

// 横屏状态检测
const isLandscape = ref(false)

// 检测屏幕方向
const checkOrientation = () => {
  isLandscape.value = window.innerWidth > window.innerHeight
}

// 监听屏幕方向变化
const handleResize = () => {
  checkOrientation()
}

// 计算过滤后的分组
const filteredGroups = computed(() => {
  // 过滤掉没有书籍的"未分组"分类
  const groups = bookGroups.value.filter(group =>
    group.name !== '未分组' || group.books.length > 0
  )

  if (!searchText.value.trim()) {
    return groups
  }

  const keyword = searchText.value.toLowerCase().trim()
  return groups.map(group => ({
    ...group,
    books: group.books.filter(book =>
      book.title.toLowerCase().includes(keyword)
    )
  })).filter(group => group.books.length > 0)
})

// 设置/用户菜单
const settingsActions = computed<PopoverAction[]>(() => {
  const actions: PopoverAction[] = []

  // 听书模式
  actions.push({ text: '听书模式', icon: 'music-o', key: 'audiobook' })
  // 生词本
  actions.push({ text: '生词本', icon: 'records-o', key: 'vocabulary' })
  // 词典设置 - 所有用户可见
  actions.push({ text: '词典设置', icon: 'bookmark-o', key: 'dictionarySettings' })

  // 朗读设置、音标设置、修复书籍数据 - 仅管理员可见
  if (authStore.isAdmin) {
    // 朗读设置
    actions.push({ text: '朗读设置', icon: 'volume-o', key: 'ttsSettings' })
    // 音标设置
    actions.push({ text: '音标设置', icon: 'font-o', key: 'phoneticSettings' })
    // 修复书籍数据（仅管理员可见）
    actions.push({ text: '修复书籍数据', icon: 'replay', key: 'syncBooks' })
    // 压缩书籍图片（仅管理员可见）
    actions.push({ text: '压缩书籍图片', icon: 'photo-o', key: 'compressImages' })
    // 预编译缓存（仅管理员可见）
    actions.push({ text: '预编译缓存', icon: 'fire-o', key: 'precompile' })
    // 补充翻译+中文语音（仅管理员可见）
    actions.push({ text: '补充翻译+中文语音', icon: 'plus', key: 'supplementAll' })
  }

  return actions
})

// 书籍管理菜单
const bookActions = [
  { text: '添加分组', icon: 'plus', key: 'addGroup' },
  { text: '收起所有分组', icon: 'shrink', key: 'collapseAll' }
]

// 用户名下拉菜单
const userActions = computed<PopoverAction[]>(() => {
  const actions: PopoverAction[] = []

  // 用户管理 - 管理员可见
  if (authStore.isAdmin) {
    actions.push({ text: '用户管理', icon: 'friends-o', key: 'users' })
  } else {
    actions.push({ text: '个人信息', icon: 'user-o', key: 'users' })
  }

  // 退出登录
  actions.push({ text: '退出登录', icon: 'logout', key: 'logout' })

  return actions
})

// 用户菜单选择
const onUserSelect = (action: PopoverAction) => {
  if (action.key === 'users') {
    router.push('/users')
  } else if (action.key === 'logout') {
    showConfirmDialog({
      title: '确认退出',
      message: '确定要退出登录吗？'
    }).then(() => {
      authStore.logout()
      showToast('已退出登录')
      router.push('/login')
    }).catch(() => {
      // 取消操作
    })
  }
}

// 设置/用户菜单选择
const onSettingsSelect = (action: PopoverAction) => {
  if (action.key === 'audiobook') {
    router.push('/audiobook')
  } else if (action.key === 'vocabulary') {
    router.push('/vocabulary')
  } else if (action.key === 'ttsSettings') {
    loadTtsVoices()
    // 如果使用豆包且resource_id为空，使用默认值
    if (ttsServiceName.value === 'doubao-tts' && !ttsResourceId.value) {
      ttsResourceId.value = defaultTtsConfig.value.resource_id || 'seed-tts-1.0'
    }
    loadTtsVoices()
    loadEdgeTtsVoices()
    loadMinimaxVoices()  // 加载 MiniMax 语音列表
    showTtsSettingsDialog.value = true
  } else if (action.key === 'dictionarySettings') {
    loadTranslationSettings()
    showDictionarySettingsDialog.value = true
  } else if (action.key === 'phoneticSettings') {
    showPhoneticSettingsDialog.value = true
  } else if (action.key === 'users') {
    router.push('/users')
  } else if (action.key === 'syncBooks') {
    handleSyncBooks()
  } else if (action.key === 'compressImages') {
    handleCompressImages()
  } else if (action.key === 'precompile') {
    handlePrecompile()
  } else if (action.key === 'supplementAll') {
    handleSupplementAll()
  } else if (action.key === 'logout') {
    showConfirmDialog({
      title: '确认退出',
      message: '确定要退出登录吗？'
    }).then(() => {
      authStore.logout()
      showToast('已退出登录')
      router.push('/login')
    }).catch(() => {
      // 取消操作
    })
  }
}

// 语音检查错误清单弹窗
const showAudioErrorDialog = ref(false)
const audioErrorList = ref<{ book_id?: string; title: string; issues: string[] }[]>([])
const audioFixedList = ref<{ book_id?: string; title: string; fixed_fields: string[]; warnings: string[] }[]>([])

// 标记是否从音频修复弹窗进入编辑
const isEditingFromAudioFix = ref(false)

// 从音频修复弹窗点击编辑书籍
const handleEditBookFromAudioFix = async (bookId: string) => {
  // 标记从音频修复弹窗进入
  isEditingFromAudioFix.value = true
  
  // 关闭音频修复弹窗
  showAudioErrorDialog.value = false
  
  // 设置当前书籍 ID
  currentBookId.value = bookId
  
  // 加载书籍内容
  showLoadingToast({ message: '加载中...', forbidClick: true })
  try {
    const res = await api.get<{ title: string }>(`/books/${bookId}`)
    currentBookTitle.value = res.data.title

    const contentRes = await api.get<{ content: string }>(`/books/${bookId}/content`)
    editContent.value = contentRes.data.content
    closeToast()
    
    // 打开编辑对话框
    showEditDialog.value = true
  } catch (error) {
    console.error('加载书籍内容失败:', error)
    closeToast()
    showNotify({ type: 'danger', message: '加载书籍内容失败' })
  }
}

// 编辑保存后的统一处理
const onEditSavedHandler = async () => {
  if (isEditingFromAudioFix.value) {
    // 从音频修复弹窗进入，保存后只刷新列表，不重置标记
    // 标记保留，等关闭对话框时再检查音频
    await loadGroups()
  } else {
    // 正常编辑，只刷新书籍列表
    onEditSaved()
  }
}

// 编辑保存后重新检查音频
const onEditSavedAndRefreshAudio = async () => {
  // 刷新书籍列表
  await loadGroups()
  
  // 重新检查音频，显示 loading 提示
  showLoadingToast({
    message: '正在重新检查语音配置...',
    forbidClick: true,
    duration: 0
  })
  
  try {
    const res = await api.post('/books/sync')
    const result = res.data
    
    // 关闭 loading
    closeToast()
    
    // 更新音频修复列表
    audioFixedList.value = result.audio_fixed || []
    audioErrorList.value = result.audio_errors || []
    
    // 如果还有问题，重新显示弹窗
    if (audioFixedList.value.length > 0 || audioErrorList.value.length > 0) {
      showAudioErrorDialog.value = true
    }
  } catch (error) {
    console.error('重新检查音频失败:', error)
    closeToast()
    showNotify({ type: 'danger', message: '重新检查音频失败' })
  }
}

// 编辑对话框关闭时的处理
const onEditClosedHandler = async () => {
  // 如果是从音频修复弹窗进入的编辑模式，关闭时重新检查音频
  if (isEditingFromAudioFix.value) {
    isEditingFromAudioFix.value = false
    await onEditSavedAndRefreshAudio()
  }
}

// 修复书籍数据
const handleSyncBooks = async () => {
  showConfirmDialog({
    title: '修复书籍数据',
    message: '将扫描 Books 目录并同步数据库记录，同时检查语音配置文件完整性，是否继续？'
  }).then(async () => {
    try {
      // 显示全屏 Loading 遮罩
      showLoadingToast({
        message: '正在同步书籍...',
        forbidClick: true,
        duration: 0  // 0 表示不自动关闭，需要手动调用 closeToast
      })
      const res = await api.post('/books/sync')
      const result = res.data
      
      // 构建数据库同步结果消息
      const messages: string[] = []
      if (result.fixed?.length > 0) {
        messages.push(`修复 ${result.fixed.length} 本`)
      }
      if (result.added?.length > 0) {
        messages.push(`新增 ${result.added.length} 本`)
      }
      if (result.removed?.length > 0) {
        messages.push(`删除无效书籍 ${result.removed.length} 本`)
      }
      if (result.errors?.length > 0) {
        messages.push(`${result.errors.length} 本出错`)
      }
      // 语音配置自动修复
      if (result.audio_fixed?.length > 0) {
        messages.push(`自动修复语音配置 ${result.audio_fixed.length} 本`)
      }
      
      const needReload = (result.fixed?.length > 0) || (result.added?.length > 0) || (result.removed?.length > 0)

      // 关闭 Loading 遮罩
      closeToast()

      if (messages.length === 0) {
        showNotify({ type: 'success', message: '无需修复，数据已同步' })
      } else {
        showNotify({ type: 'success', message: messages.join('，') })
        if (needReload) {
          // 重新加载书籍列表
          await loadGroups()
        }
      }
      
      // 如果有语音配置修复结果或错误，弹出详细清单
      if (result.audio_fixed?.length > 0 || result.audio_errors?.length > 0) {
        audioFixedList.value = result.audio_fixed || []
        audioErrorList.value = result.audio_errors || []
        showAudioErrorDialog.value = true
      }
    } catch (error: any) {
      console.error('同步失败:', error)
      // 关闭 Loading 遮罩
      closeToast()
      showNotify({ type: 'danger', message: error.response?.data?.detail || '同步失败' })
    }
  }).catch(() => {
    // 取消操作
  })
}

// 压缩书籍图片
const handleCompressImages = async () => {
  showConfirmDialog({
    title: '压缩书籍图片',
    message: '将扫描所有书籍，将jpg/jpeg/png/bmp格式图片压缩并转换为WebP格式，是否继续？'
  }).then(async () => {
    try {
      showLoadingToast({
        message: '正在压缩图片...',
        forbidClick: true,
        duration: 0
      })
      const res = await api.post('/books/compress-images')
      const result = res.data
      
      closeToast()
      
      // 构建结果消息
      const messages: string[] = []
      if (result.processed_books > 0) {
        messages.push(`处理 ${result.processed_books} 本书籍`)
      }
      if (result.converted_images > 0) {
        messages.push(`转换 ${result.converted_images} 张图片`)
      }
      if (result.skipped_images > 0) {
        messages.push(`跳过 ${result.skipped_images} 张`)
      }
      if (result.errors?.length > 0) {
        messages.push(`${result.errors.length} 个错误`)
      }
      
      if (messages.length === 0) {
        showNotify({ type: 'success', message: '所有图片已是WebP格式，无需转换' })
      } else {
        showNotify({ type: 'success', message: messages.join('，') })
      }
    } catch (error: any) {
      console.error('压缩失败:', error)
      closeToast()
      showNotify({ type: 'danger', message: error.response?.data?.detail || '压缩失败' })
    }
  }).catch(() => {
    // 取消操作
  })
}

// 预编译缓存
const showPrecompileProgress = ref(false)
const precompileProgress = ref(0)
const precompileMessage = ref('')
const precompileLoading = ref(false)
const precompileCacheStatus = ref({ total: 0, cached: 0, percentage: 0 })

const handlePrecompile = async () => {
  // 先获取缓存状态
  try {
    const statusRes = await api.get('/books/precompile/status')
    const status = statusRes.data
    precompileCacheStatus.value = {
      total: status.total_books,
      cached: status.cached_books,
      percentage: status.cache_percentage
    }
  } catch (error) {
    console.error('获取缓存状态失败:', error)
  }

  const statusText = `当前缓存: ${precompileCacheStatus.value.cached}/${precompileCacheStatus.value.total} 本 (${precompileCacheStatus.value.percentage}%)`

  showConfirmDialog({
    title: '预编译缓存',
    message: `${statusText}\n\n预编译可加快书籍首次加载速度（约3500倍提升），是否开始编译未缓存的书籍？`
  }).then(async () => {
    // 显示进度对话框
    showPrecompileProgress.value = true
    precompileProgress.value = 0
    precompileMessage.value = '正在准备...'
    precompileLoading.value = true

    try {
      const response = await fetch('/api/v1/books/precompile', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authStore.token}`
        }
      })

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status} ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('无法读取响应流')
      }

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              precompileProgress.value = data.percentage || 0
              precompileMessage.value = data.message || ''
            } catch (e) {
              console.error('解析SSE数据失败:', e)
            }
          }
        }
      }

      // 处理完成
      precompileLoading.value = false
      precompileMessage.value = '编译完成！'
      precompileProgress.value = 100

      setTimeout(() => {
        showPrecompileProgress.value = false
        showNotify({ type: 'success', message: '预编译完成' })
      }, 1500)

    } catch (error: any) {
      console.error('预编译失败:', error)
      showPrecompileProgress.value = false
      precompileLoading.value = false
      showNotify({ type: 'danger', message: error.message || '预编译失败' })
    }
  }).catch(() => {
    // 取消操作
  })
}

// 补充翻译+中文语音
const showSupplementProgress = ref(false)
const supplementProgress = ref(0)
const supplementMessage = ref('')
const supplementLoading = ref(false)

const handleSupplementAll = async () => {
  showConfirmDialog({
    title: '补充翻译+中文语音',
    message: '将检查所有书籍，补充缺少的翻译和中文语音（不会覆盖已有内容），是否继续？'
  }).then(async () => {
    // 显示进度对话框
    showSupplementProgress.value = true
    supplementProgress.value = 0
    supplementMessage.value = '正在准备...'
    supplementLoading.value = true

    try {
      const response = await fetch('/api/v1/books/admin/books/supplement-all', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${authStore.token}`
        }
      })

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status} ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('无法读取响应流')
      }

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              supplementProgress.value = data.percentage || 0
              supplementMessage.value = data.message || ''
            } catch (e) {
              console.error('解析SSE数据失败:', e)
            }
          }
        }
      }

      // 处理完成
      supplementLoading.value = false
      supplementMessage.value = '处理完成！'
      supplementProgress.value = 100

      setTimeout(() => {
        showSupplementProgress.value = false
        showNotify({ type: 'success', message: '翻译和中文语音补充完成' })
      }, 1500)

    } catch (error: any) {
      console.error('补充翻译和中文语音失败:', error)
      showSupplementProgress.value = false
      supplementLoading.value = false
      showNotify({ type: 'danger', message: error.message || '补充失败' })
    }
  }).catch(() => {
    // 取消操作
  })
}

// 取消补充翻译+中文语音
const handleCancelSupplement = async () => {
  try {
    await api.post('/books/admin/books/supplement-all/cancel')
    supplementMessage.value = '正在取消...'
  } catch (error: any) {
    console.error('取消失败:', error)
    showNotify({ type: 'warning', message: '取消请求发送失败' })
  }
}

// 书籍管理菜单选择
const onBookActionSelect = (action: PopoverAction) => {
  if (action.key === 'addGroup') {
    showAddGroupDialog.value = true
  } else if (action.key === 'collapseAll') {
    activeNames.value = -1  // 使用 -1 表示没有展开任何分组
  }
}

// 加载分组书籍数据
const loadGroups = async () => {
  loading.value = true
  try {
    // 清除封面错误缓存和已检查标记，确保重新加载
    coverErrorMap.value = {}
    coverCheckedBooks.value.clear()
    const res = await api.get<BookGroup[]>('/categories/books/grouped')
    bookGroups.value = res.data

    // 默认展开第一个分组
    if (bookGroups.value.length > 0 && activeNames.value === 0) {
      activeNames.value = bookGroups.value[0].id
    }
  } catch (error) {
    console.error('加载分组失败:', error)
    showNotify({ type: 'danger', message: '加载分组失败' })
  } finally {
    loading.value = false
  }
}

// 处理搜索
const handleSearch = () => {
  // 搜索时会自动通过computed过滤
}

// 获取书籍封面
const coverCheckedBooks = ref<Set<string>>(new Set()) // 已检查封面的书籍

const getBookCover = (book: Book): string => {
  // 优先使用cover_path（数据库中明确记录的封面）
  if (book.cover_path) {
    // 添加时间戳防止缓存
    const timestamp = Date.now()
    return book.cover_path.includes('?') ? `${book.cover_path}&t=${timestamp}` : `${book.cover_path}?t=${timestamp}`
  }

  // 如果已经有加载失败的标记，直接返回空字符串（显示占位符）
  if (coverErrorMap.value[book.id]) {
    return ''
  }

  // 如果已经检查过封面不存在，直接返回空
  if (coverCheckedBooks.value.has(book.id)) {
    return ''
  }

  // 没有封面信息，返回空字符串显示占位符
  // 不尝试猜测封面路径，避免闪烁
  return ''
}

// 处理封面加载错误
const handleCoverError = (event: Event, book: Book) => {
  const img = event.target as HTMLImageElement
  // 标记封面加载失败
  coverErrorMap.value[book.id] = true
  // 隐藏图片，显示占位符
  img.style.display = 'none'
  // 标记已检查
  coverCheckedBooks.value.add(book.id)
}

// 切换书籍选中状态
const toggleBookSelect = (bookId: string) => {
  const index = selectedBooks.value.indexOf(bookId)
  if (index === -1) {
    selectedBooks.value.push(bookId)
  } else {
    selectedBooks.value.splice(index, 1)
  }
}

// 处理书籍点击
const handleBookClick = (bookId: string, _groupId: number) => {
  if (isMultiSelect.value) {
    toggleBookSelect(bookId)
  } else {
    openBook(bookId)
  }
}

// 处理封面点击（修改封面）
const handleCoverClick = (book: Book) => {
  if (isMultiSelect.value) {
    toggleBookSelect(book.id)
  }
}

// 显示右键菜单
const showContextMenu = (_event: MouseEvent, book: Book, groupId: number) => {
  contextMenuBook.value = book
  contextMenuGroupId.value = groupId
  // 菜单始终显示在屏幕中间
  const menuWidth = 150
  const menuHeight = 280
  const x = (window.innerWidth - menuWidth) / 2
  const y = (window.innerHeight - menuHeight) / 2
  contextMenuPos.value = { x, y }
  showContextMenuPopup.value = true
}

// 关闭右键菜单
const closeContextMenu = () => {
  showContextMenuPopup.value = false
}

// 切换书籍已读状态（从右键菜单）
const toggleBookReadStatus = async () => {
  if (!contextMenuBook.value) return
  const newStatus = contextMenuBook.value.is_read ? 0 : 1
  await markBookAsRead(contextMenuBook.value.id, newStatus)
  closeContextMenu()
}

// 打开重命名书籍对话框
const openRenameBookDialog = () => {
  closeContextMenu()
  if (contextMenuBook.value) {
    renameBookName.value = contextMenuBook.value.title
    showRenameBookDialog.value = true
  }
}

// 处理重命名书籍
const handleRenameBook = async () => {
  if (!contextMenuBook.value) return
  if (!renameBookName.value.trim()) {
    showNotify({ type: 'warning', message: '请输入书籍名称' })
    return
  }

  // 检查名称是否有变化
  if (renameBookName.value.trim() === contextMenuBook.value.title) {
    showRenameBookDialog.value = false
    return
  }

  try {
    const res = await api.put(`/books/${contextMenuBook.value.id}/rename`, {
      new_title: renameBookName.value.trim()
    })
    showNotify({ type: 'success', message: '书籍重命名成功', duration: 1500 })
    showRenameBookDialog.value = false
    
    // 更新当前书籍的ID（重命名后ID会改变）
    if (res.data.new_id) {
      contextMenuBook.value.id = res.data.new_id
      contextMenuBook.value.title = res.data.new_title
      contextMenuBook.value.cover_path = res.data.new_cover_path
    }
    
    // 强制清空封面缓存并重新加载
    coverErrorMap.value = {}
    coverCheckedBooks.value.clear()
    
    await loadGroups()
    
    // 强制重新渲染封面（等待DOM更新）
    await nextTick()
  } catch (error: any) {
    console.error('重命名书籍失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '重命名失败' })
  }
}

// 显示分组右键菜单
const showGroupContextMenu = (event: MouseEvent, group: BookGroup) => {
  contextMenuGroup.value = group
  // 计算菜单位置，确保不超出屏幕
  const x = Math.min(event.clientX, window.innerWidth - 150)
  const y = Math.min(event.clientY, window.innerHeight - 120)
  groupContextMenuPos.value = { x, y }
  showGroupContextMenuPopup.value = true
}

// 关闭分组右键菜单
const closeGroupContextMenu = () => {
  showGroupContextMenuPopup.value = false
}

// 切换隐藏已读书籍状态
const toggleHideReadBooks = async () => {
  if (contextMenuGroup.value) {
    const groupId = contextMenuGroup.value.id
    hideReadBooksMap.value[groupId] = !hideReadBooksMap.value[groupId]

    // 保存到数据库
    try {
      await api.put('/settings/ui', {
        hide_read_books_map: hideReadBooksMap.value
      })
    } catch (error: any) {
      console.error('保存隐藏已读书籍设置失败:', error)
      showNotify({ type: 'danger', message: '保存设置失败', duration: 1500 })
    }
  }
  closeGroupContextMenu()
}

// 获取可见的书籍（根据隐藏已读设置过滤）
const getVisibleBooks = (group: BookGroup): Book[] => {
  if (hideReadBooksMap.value[group.id]) {
    return group.books.filter(book => !book.is_read)
  }
  return group.books
}

// 处理滑动打开事件
const handleSwipeOpen = async (event: { position: 'left' | 'right' }, book: Book) => {
  // position: 'left' 表示向右滑动（显示左侧内容），标记为未读
  // position: 'right' 表示向左滑动（显示右侧内容），标记为已读
  const { position } = event
  if (position === 'left') {
    await markBookAsRead(book.id, 0)
  } else if (position === 'right') {
    await markBookAsRead(book.id, 1)
  }
  // 关闭滑动菜单
  const swipeCell = swipeCellRefs.value[book.id]
  if (swipeCell && swipeCell.close) {
    swipeCell.close()
  }
}

// 标记书籍已读状态
const markBookAsRead = async (bookId: string, isRead: number) => {
  try {
    await api.post(`/categories/books/${bookId}/read-status`, { is_read: isRead })
    // 更新本地状态
    for (const group of bookGroups.value) {
      const book = group.books.find(b => b.id === bookId)
      if (book) {
        book.is_read = isRead
        break
      }
    }
    // 关闭滑动菜单
    const swipeCell = swipeCellRefs.value[bookId]
    if (swipeCell && swipeCell.close) {
      swipeCell.close()
    }
    const statusText = isRead ? '已读' : '未读'
    showNotify({ type: 'success', message: `已标记为${statusText}`, duration: 1000 })
  } catch (error: any) {
    console.error('标记已读状态失败:', error)
    showNotify({ type: 'danger', message: '标记失败' })
  }
}

// 打开修改分组名称对话框
const openRenameGroupDialog = () => {
  closeGroupContextMenu()
  if (contextMenuGroup.value) {
    renameGroupName.value = contextMenuGroup.value.name
    showRenameGroupDialog.value = true
  }
}

// 处理修改分组名称
const handleRenameGroup = async () => {
  if (!contextMenuGroup.value) return
  if (!renameGroupName.value.trim()) {
    showNotify({ type: 'warning', message: '请输入分组名称' })
    return
  }

  try {
    await api.put(`/categories/${contextMenuGroup.value.id}`, {
      name: renameGroupName.value.trim()
    })
    showNotify({ type: 'success', message: '分组名称修改成功', duration: 1500 })
    showRenameGroupDialog.value = false
    await loadGroups()
  } catch (error: any) {
    console.error('修改分组名称失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '修改失败' })
  }
}

// 确认删除分组
const confirmDeleteGroup = async () => {
  closeGroupContextMenu()
  if (!contextMenuGroup.value) return

  const confirm = await showConfirmDialog({
    title: '确认删除',
    message: `确定要删除分组"${contextMenuGroup.value.name}"吗？分组内的书籍将自动移动到未分组。`
  }).catch(() => null)

  if (!confirm) return

  try {
    await api.delete(`/categories/${contextMenuGroup.value.id}`)
    showNotify({ type: 'success', message: '分组删除成功，书籍已移至未分组', duration: 1500 })
    await loadGroups()
  } catch (error: any) {
    console.error('删除分组失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
  }
}

// 启用多选模式
const enableMultiSelect = () => {
  closeContextMenu()
  isMultiSelect.value = true
  // 记录当前所在分组
  currentGroupId.value = activeNames.value || 0
  if (contextMenuBook.value) {
    selectedBooks.value = [contextMenuBook.value.id]
  }
}

// 取消多选模式
const cancelMultiSelect = () => {
  isMultiSelect.value = false
  selectedBooks.value = []
  currentGroupId.value = 0
}

// 获取所有可见书籍ID
const getAllVisibleBookIds = (): string[] => {
  const ids: string[] = []
  for (const group of filteredGroups.value) {
    const visibleBooks = getVisibleBooks(group)
    for (const book of visibleBooks) {
      ids.push(book.id)
    }
  }
  return ids
}

// 是否已全选
const isAllSelected = computed(() => {
  const allIds = getAllVisibleBookIds()
  return allIds.length > 0 && allIds.every(id => selectedBooks.value.includes(id))
})

// 全选/取消全选
const selectAllBooks = () => {
  if (isAllSelected.value) {
    selectedBooks.value = []
  } else {
    selectedBooks.value = getAllVisibleBookIds()
  }
}

// 全选当前分组书籍
const selectAllBooksInCurrentGroup = () => {
  // 找到当前展开的分组，如果没有则使用第一个有书籍的分组
  let targetGroup = null
  if (activeNames.value !== null && activeNames.value !== undefined) {
    targetGroup = filteredGroups.value.find(g => g.id === activeNames.value)
  }
  // 如果没有找到展开的分组，使用第一个有可见书籍的分组
  if (!targetGroup) {
    targetGroup = filteredGroups.value.find(g => getVisibleBooks(g).length > 0)
  }
  if (targetGroup) {
    const groupBookIds = getVisibleBooks(targetGroup).map(b => b.id)
    // 将当前分组的书籍添加到选中列表（不去重已有的）
    const newSelection = [...new Set([...selectedBooks.value, ...groupBookIds])]
    selectedBooks.value = newSelection
  }
}

// 判断某个分组是否已全选（所有可见书籍都被选中）
const isGroupAllSelected = (groupId: number): boolean => {
  const group = filteredGroups.value.find(g => g.id === groupId)
  if (!group) return false
  const visibleBooks = getVisibleBooks(group)
  if (visibleBooks.length === 0) return false
  return visibleBooks.every(book => selectedBooks.value.includes(book.id))
}

// 切换分组选择（选中/取消选中该分组下所有书籍）
const toggleGroupSelect = (groupId: number) => {
  const group = filteredGroups.value.find(g => g.id === groupId)
  if (!group) return

  const visibleBooks = getVisibleBooks(group)
  const groupBookIds = visibleBooks.map(b => b.id)
  const isCurrentlyAllSelected = isGroupAllSelected(groupId)

  if (isCurrentlyAllSelected) {
    // 取消选择该分组的所有书籍
    selectedBooks.value = selectedBooks.value.filter(id => !groupBookIds.includes(id))
  } else {
    // 选中该分组的所有书籍
    selectedBooks.value = [...new Set([...selectedBooks.value, ...groupBookIds])]
  }
}

// 批量移动书籍
const batchMoveBooks = async () => {
  // 加载分组列表用于选择
  try {
    const res = await api.get<{ id: number; name: string }[]>('/categories')
    // 过滤掉未分组(0)，如果当前不是未分组则还要过滤当前所在分组
    categoriesForMove.value = res.data.filter((c: { id: number; name: string }) => {
      // 从未分组移动时，显示所有其他分组
      if (currentGroupId.value === 0) {
        return c.id !== 0
      }
      // 从其他分组移动时，显示除当前分组和未分组外的所有分组
      return c.id !== 0 && c.id !== currentGroupId.value
    })
    // 默认选择第一个分类
    selectedMoveCategory.value = categoriesForMove.value.length > 0 ? categoriesForMove.value[0].id : 0
    showAddGroupInMove.value = false
    newGroupInMove.value = ''
    showMoveDialog.value = true
  } catch (error) {
    console.error('加载分组失败:', error)
  }
}

// 打开移动对话框（单个书籍）
const openMoveDialog = () => {
  closeContextMenu()
  if (contextMenuBook.value) {
    selectedBooks.value = [contextMenuBook.value.id]
  }
  // 记录当前分组ID，用于过滤
  currentGroupId.value = contextMenuGroupId.value
  batchMoveBooks()
}

// 确认移动书籍
const confirmMoveBooks = async () => {
  movingBooks.value = true
  try {
    // 如果创建新分组
    if (showAddGroupInMove.value && newGroupInMove.value.trim()) {
      const res = await api.post<{ id: number }>('/categories', { name: newGroupInMove.value.trim() })
      selectedMoveCategory.value = res.data.id
    }

    // 批量移动书籍到选中的分组
    for (const bookId of selectedBooks.value) {
      await api.post('/categories/books', {
        book_id: bookId,
        category_id: selectedMoveCategory.value
      })
    }

    showNotify({ type: 'success', message: '移动成功', duration: 1500 })
    showMoveDialog.value = false
    selectedBooks.value = []
    isMultiSelect.value = false
    await loadGroups()
  } catch (error: any) {
    console.error('移动失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '移动失败' })
  } finally {
    movingBooks.value = false
  }
}

// 在移动对话框中创建分组
const createGroupInMove = async () => {
  if (!newGroupInMove.value.trim()) {
    showNotify({ type: 'warning', message: '请输入分组名称' })
    return
  }

  try {
    const res = await api.post<{ id: number; name: string }>('/categories', { name: newGroupInMove.value.trim() })
    categoriesForMove.value.push(res.data)
    selectedMoveCategory.value = res.data.id
    showAddGroupInMove.value = false
    newGroupInMove.value = ''
    showNotify({ type: 'success', message: '分组创建成功', duration: 1500 })
  } catch (error: any) {
    console.error('创建分组失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '创建分组失败' })
  }
}

// 导出单本书籍
const exportSingleBook = async () => {
  closeContextMenu()
  if (!contextMenuBook.value) return

  await exportBooks([contextMenuBook.value.id])
}

// 导出选中的书籍
const exportSelectedBooks = async () => {
  if (selectedBooks.value.length === 0) {
    showNotify({ type: 'warning', message: '请先选择要导出的书籍' })
    return
  }

  await exportBooks(selectedBooks.value)
}

// 导出书籍通用函数
const exportBooks = async (bookIds: string[]) => {
  // 初始化进度状态
  showExportProgressDialog.value = true
  exportProgress.value = 0
  exportStatus.value = '正在准备导出...'
  exportCurrentBook.value = ''

  try {
    const totalBooks = bookIds.length
    let simulatedProgress = 0
    
    // 打包阶段的模拟进度（因为后端不支持流式进度）
    const progressInterval = setInterval(() => {
      if (simulatedProgress < 50) {
        simulatedProgress += 2
        exportProgress.value = simulatedProgress
        exportStatus.value = `正在打包书籍 (${totalBooks} 本)...`
      }
    }, 500)

    // 使用 XMLHttpRequest 来监听下载进度
    return new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/v1/books/export')
      xhr.setRequestHeader('Content-Type', 'application/json')
      xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
      xhr.responseType = 'blob'

      // 用于存储总文件大小
      let totalSize = 0

      // 监听下载进度
      xhr.addEventListener('progress', (event) => {
        clearInterval(progressInterval)
        
        // 尝试从响应头获取 Content-Length
        if (totalSize === 0) {
          const contentLength = xhr.getResponseHeader('Content-Length')
          if (contentLength) {
            totalSize = parseInt(contentLength, 10)
          }
        }
        
        const loaded = event.loaded
        const total = totalSize || event.total
        
        if (total > 0) {
          // 从50%开始计算下载进度，到95%
          const downloadPercent = Math.round((loaded / total) * 45) + 50
          exportProgress.value = Math.min(downloadPercent, 95)
          
          const loadedMB = (loaded / 1024 / 1024).toFixed(1)
          const totalMB = (total / 1024 / 1024).toFixed(1)
          exportStatus.value = `正在下载 ${loadedMB}MB / ${totalMB}MB`
        } else {
          // 如果无法获取总大小，显示已下载量
          exportProgress.value = 70
          const loadedMB = (loaded / 1024 / 1024).toFixed(1)
          exportStatus.value = `正在下载 ${loadedMB}MB...`
        }
      })

      // 添加 readystatechange 监听，在 headers 接收后获取 Content-Length
      xhr.addEventListener('readystatechange', () => {
        // readyState 2 = HEADERS_RECEIVED
        if (xhr.readyState === 2) {
          const contentLength = xhr.getResponseHeader('Content-Length')
          if (contentLength) {
            totalSize = parseInt(contentLength, 10)
            clearInterval(progressInterval)
            const totalMB = (totalSize / 1024 / 1024).toFixed(1)
            exportStatus.value = `正在下载 0MB / ${totalMB}MB`
          }
        }
      })

      xhr.addEventListener('load', () => {
        clearInterval(progressInterval)
        
        if (xhr.status >= 200 && xhr.status < 300) {
          // 获取文件名
          const contentDisposition = xhr.getResponseHeader('content-disposition')
          let filename = 'books_export.zip'
          if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/i)
            if (filenameMatch) {
              filename = decodeURIComponent(filenameMatch[1].trim().replace(/"/g, ''))
            }
          }

          exportProgress.value = 100
          exportStatus.value = '导出完成！'
          exportCurrentBook.value = filename

          // 下载文件
          const blob = xhr.response
          const url = window.URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = url
          link.download = filename
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
          window.URL.revokeObjectURL(url)

          // 延迟关闭对话框
          setTimeout(() => {
            showExportProgressDialog.value = false
            showNotify({ type: 'success', message: '书籍导出成功', duration: 1500 })
          }, 800)

          // 如果是多选模式，退出多选
          if (isMultiSelect.value) {
            cancelMultiSelect()
          }
          resolve()
        } else {
          showExportProgressDialog.value = false
          reject(new Error('导出失败'))
        }
      })

      xhr.addEventListener('error', () => {
        clearInterval(progressInterval)
        showExportProgressDialog.value = false
        reject(new Error('网络错误'))
      })

      xhr.addEventListener('abort', () => {
        clearInterval(progressInterval)
        showExportProgressDialog.value = false
        reject(new Error('导出已取消'))
      })

      // 发送请求
      xhr.send(JSON.stringify({ book_ids: bookIds }))
    })
  } catch (error: any) {
    showExportProgressDialog.value = false
    console.error('导出书籍失败:', error)
    showNotify({ type: 'danger', message: error.message || '导出失败' })
  }
}

// 批量删除书籍
const batchDeleteBooks = async () => {
  const confirm = await showConfirmDialog({
    title: '确认删除',
    message: `确定要删除选中的 ${selectedBooks.value.length} 本书籍吗？此操作不可恢复！`
  }).catch(() => null)

  if (!confirm) return

  try {
    // 先记录要删除的书籍ID，然后从UI中移除
    const deletedBookIds = new Set(selectedBooks.value)
    bookGroups.value = bookGroups.value.map(group => ({
      ...group,
      books: group.books.filter(book => !deletedBookIds.has(book.id))
    })).filter(group => group.books.length > 0)

    for (const bookId of selectedBooks.value) {
      await api.delete(`/books/${bookId}`)
    }

    showNotify({ type: 'success', message: '删除成功', duration: 1500 })
    selectedBooks.value = []
    isMultiSelect.value = false
    await loadGroups()
  } catch (error: any) {
    console.error('删除失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
    // 出错时重新加载列表
    await loadGroups()
  }
}

// 确认删除单个书籍
const confirmDeleteBook = async () => {
  closeContextMenu()
  if (!contextMenuBook.value) return

  const confirm = await showConfirmDialog({
    title: '确认删除',
    message: `确定要删除《${contextMenuBook.value.title}》吗？此操作不可恢复！`
  }).catch(() => null)

  if (!confirm) return

  try {
    const deletedBookId = contextMenuBook.value.id
    // 先从UI中移除该书籍
    bookGroups.value = bookGroups.value.map(group => ({
      ...group,
      books: group.books.filter(book => book.id !== deletedBookId)
    })).filter(group => group.books.length > 0)

    await api.delete(`/books/${deletedBookId}`)
    showNotify({ type: 'success', message: '删除成功', duration: 1500 })
    await loadGroups()
  } catch (error: any) {
    console.error('删除失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '删除失败' })
    // 出错时重新加载列表
    await loadGroups()
  }
}

// 打开修改封面对话框
const openCoverDialog = async () => {
  closeContextMenu()
  if (!contextMenuBook.value) return

  showCoverDialog.value = true
  previewCover.value = getBookCover(contextMenuBook.value) || ''
  selectedMdImage.value = ''
  mdImages.value = []

  // 加载书籍信息以获取书籍路径
  try {
    // 获取书籍详情来获取书籍路径
    const bookRes = await api.get<{ book_path: string }>(`/books/${contextMenuBook.value.id}`)
    const bookFolder = bookRes.data.book_path

    // 加载书籍内容
    const contentRes = await api.get<{ content: string }>(`/books/${contextMenuBook.value.id}/content-file`)
    const content = contentRes.data.content

    // 提取markdown中的所有图片
    const localImages: string[] = []

    // 使用match直接获取所有图片URL
    const allImgMatches = content.match(/!\[([^\]]*)\]\(([^)]+)\)/g) || []

    if (allImgMatches.length === 0) {
      // 尝试其他格式（预留）
      // const simpleMatches = content.match(/!\[[^\]]*\]\([^)]+\)/g) || []
    }

    for (const match of allImgMatches) {
      const urlMatch = match.match(/!\[([^\]]*)\]\(([^)]+)\)/)
      if (urlMatch) {
        const url = urlMatch[2]
        // 过滤掉http开头的远程图片，只保留本地图片
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
          localImages.push(url)
        }
      }
    }


    // 转换相对路径为完整URL
    mdImages.value = localImages.map((url: string) => {
      let resultUrl = url

      // 如果是 ./assets/xxx 格式
      if (url.startsWith('./assets/')) {
        resultUrl = `/books/${bookFolder}/assets/${url.replace('./assets/', '')}`
      }
      // 如果是 assets/xxx 格式
      else if (url.startsWith('assets/')) {
        resultUrl = `/books/${bookFolder}/assets/${url.replace('assets/', '')}`
      }
      // 如果是 ../xxx 格式（上级目录）
      else if (url.startsWith('../')) {
        resultUrl = `/books/${url.replace('../', '')}`
      }
      // 其他相对路径，假设在assets目录下
      else {
        resultUrl = `/books/${bookFolder}/assets/${url}`
      }

      return resultUrl
    })

  } catch (error) {
    console.error('加载书籍内容失败:', error)
  }
}

// 打开图片选择器
const openCoverPicker = () => {
  showCoverPicker.value = true
}

// 触发封面上传
const triggerCoverUpload = () => {
  coverInput.value?.click()
}

// 处理封面文件选择
const onCoverSelected = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      previewCover.value = e.target?.result as string
    }
    reader.readAsDataURL(file)
  }
}

// 从md图片中选择
const selectMdImage = (img: string) => {
  selectedMdImage.value = img
}

// 确认选择md图片
const confirmMdImage = () => {
  if (selectedMdImage.value) {
    previewCover.value = selectedMdImage.value
  }
  showCoverPicker.value = false
}

// 使用默认封面
const useDefaultCover = () => {
  previewCover.value = ''
}

// 保存封面
const saveCover = async () => {
  if (!contextMenuBook.value) return

  try {
    let coverPath = previewCover.value

    // 如果是base64图片，需要上传
    if (coverPath.startsWith('data:')) {
      // 将base64转换为文件上传
      const res = await fetch(coverPath)
      const blob = await res.blob()
      const formData = new FormData()
      formData.append('file', blob, 'cover.webp')

      // 上传到书籍资源目录
      const uploadRes = await fetch(`/api/v1/books/upload-cover?book_id=${contextMenuBook.value.id}`, {
        method: 'POST',
        body: formData,
        headers: {
          'Authorization': `Bearer ${authStore.token}`
        }
      })
      const uploadData = await uploadRes.json()
      coverPath = uploadData.path
    }

    // 保存封面路径到数据库
    await api.put(`/books/${contextMenuBook.value.id}/cover`, {
      cover_path: coverPath
    })

    showNotify({ type: 'success', message: '封面保存成功', duration: 1500 })
    showCoverDialog.value = false
    await loadGroups()
    // 强制触发 DOM 更新，确保封面刷新
    await nextTick()
  } catch (error: any) {
    console.error('保存封面失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '保存封面失败' })
  }
}

// 打开书籍
const openBook = (id: string) => {
  router.push(`/book/${id}`)
}

// 打开导入对话框
const openImportDialog = (categoryId: number) => {
  importCategoryId.value = categoryId
  showImportDialog.value = true
}

// 添加分组
const handleAddGroup = async () => {
  if (!newGroupName.value.trim()) {
    showNotify({ type: 'warning', message: '请输入分组名称' })
    return
  }

  try {
    await api.post('/categories', { name: newGroupName.value.trim() })
    showNotify({ type: 'success', message: '分组创建成功', duration: 1500 })
    newGroupName.value = ''
    showAddGroupDialog.value = false
    // 刷新分组列表
    await loadGroups()
  } catch (error: any) {
    console.error('创建分组失败:', error)
    showNotify({ type: 'danger', message: error.response?.data?.detail || '创建分组失败' })
  }
}

// 触发文件选择
const triggerFileInput = () => {
  // 导入中不能选择文件，但导入完成后可以选择新文件进行连续导入
  if (!importing.value) {
    fileInput.value?.click()
  }
}

// 文件拖放处理
const onFileDrop = (event: DragEvent) => {
  isDragOver.value = false
  if (importing.value) return

  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    handleFile(files[0])
  }
}

// 文件选择处理
const onFileSelected = (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = target.files

  if (files && files.length > 0) {
    if (files.length === 1) {
      // 单文件处理
      handleFile(files[0])
    } else {
      // 多文件处理（只接受MD文件）
      handleMultipleFiles(Array.from(files))
    }
  }
}

// 处理文件
const handleFile = async (file: File) => {
  // 检查文件类型
  if (!file.name.endsWith('.md') && !file.name.endsWith('.zip')) {
    showNotify({ type: 'danger', message: '只支持 .md 或 .zip 格式的文件' })
    return
  }

  // 检查是否已登录
  if (!authStore.isLoggedIn) {
    showToast('请先登录')
    router.push('/login')
    return
  }

  // 如果之前已完成导入，重置状态以支持连续导入
  if (importCompleted.value) {
    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = ''
    currentBookId.value = ''
    isZipImport.value = false
    isBatchImport.value = false
    importAction.value = null
    selectedDuplicateBooks.value = []
    duplicateCheckResult.value = {
      has_duplicates: false,
      duplicate_books: [],
      new_books: [],
      total_books: 0
    }
  }

  selectedFile.value = file
  selectedFiles.value = []
  isBatchImport.value = false
}

// 处理多文件选择（批量导入MD文件）
const handleMultipleFiles = async (files: File[]) => {
  // 过滤只保留MD文件
  const mdFiles = files.filter(f => f.name.endsWith('.md'))

  if (mdFiles.length === 0) {
    showNotify({ type: 'danger', message: '请至少选择一个 .md 格式的文件' })
    return
  }

  if (mdFiles.length !== files.length) {
    showNotify({ type: 'warning', message: `已过滤非MD文件，共选择 ${mdFiles.length} 个MD文件` })
  }

  // 检查是否已登录
  if (!authStore.isLoggedIn) {
    showToast('请先登录')
    router.push('/login')
    return
  }

  // 重置状态
  if (importCompleted.value) {
    importCompleted.value = false
    importProgress.value = 0
    importStatus.value = ''
    currentBookId.value = ''
    isZipImport.value = false
    isBatchImport.value = false
    importAction.value = null
    selectedDuplicateBooks.value = []
    duplicateCheckResult.value = {
      has_duplicates: false,
      duplicate_books: [],
      new_books: [],
      total_books: 0
    }
  }

  selectedFiles.value = mdFiles
  isBatchImport.value = true
}

// 批量导入MD文件
const handleBatchImport = async () => {
  importing.value = true
  importCompleted.value = false
  importProgress.value = 0
  importStatus.value = `正在批量导入 ${selectedFiles.value.length} 本书籍...`

  const totalFiles = selectedFiles.value.length
  let successCount = 0
  let failCount = 0

  for (let i = 0; i < totalFiles; i++) {
    const file = selectedFiles.value[i]
    // 计算当前文件的进度基数
    const baseProgress = Math.round((i / totalFiles) * 100)
    
    try {
      const formData = new FormData()
      formData.append('file', file)

      // 添加category_id参数（0表示未分组）
      const categoryId = importCategoryId.value
      let apiPath = '/api/v1/books/import'
      const params = new URLSearchParams()

      if (categoryId) {
        params.append('category_id', categoryId.toString())
      }

      if (params.toString()) {
        apiPath += `?${params.toString()}`
      }

      // 使用带进度回调的上传
      const result = await uploadWithProgressCallback(
        apiPath,
        formData,
        `正在上传 (${i + 1}/${totalFiles}): ${file.name}`,
        (progress) => {
          // 当前文件进度 + 基数 = 总体进度
          importProgress.value = Math.min(baseProgress + Math.round(progress / totalFiles), 99)
        }
      )

      if (result.ok) {
        successCount++
      } else {
        failCount++
        console.error(`导入失败: ${file.name}`)
      }
    } catch (error) {
      failCount++
      console.error(`导入异常: ${file.name}`, error)
    }
  }

  // 完成
  importProgress.value = 100
  importStatus.value = `批量导入完成: 成功 ${successCount} 本, 失败 ${failCount} 本`
  importCompleted.value = true
  importing.value = false
  showNotify({ type: 'success', message: `成功导入 ${successCount} 本书籍`, duration: 2000 })

  // 刷新分组列表（在importing设为false之后，确保UI及时更新）
  await loadGroups()
}

// 确认导入
const handleImportConfirm = async () => {
  // 批量导入模式
  if (isBatchImport.value && selectedFiles.value.length > 0) {
    // 先上传检查重复书籍（需要先上传才能检查内容）
    isBatchMdImport.value = true
    
    const duplicateCheck = await checkMdDuplicates(selectedFiles.value)
    
    if (duplicateCheck.has_duplicates) {
      // 显示重复书籍对话框
      duplicateCheckResult.value = duplicateCheck
      showDuplicateDialog.value = true
      importStatus.value = ''
      return
    }
    
    // 没有重复，直接导入
    await handleBatchImport()
    return
  }

  // 单文件导入模式
  if (!selectedFile.value) {
    showNotify({ type: 'warning', message: '请先选择文件' })
    return
  }

  importCompleted.value = false
  importProgress.value = 0
  importStatus.value = ''

  // 标记是否是ZIP导入
  isZipImport.value = selectedFile.value.name.endsWith('.zip')

  try {
    // ZIP文件：先检查重复书籍
    if (isZipImport.value) {
      // 上传检查重复书籍
      isBatchMdImport.value = false
      const duplicateCheck = await checkZipDuplicates(selectedFile.value)
      
      if (duplicateCheck.has_duplicates) {
        // 显示重复书籍对话框
        duplicateCheckResult.value = duplicateCheck
        showDuplicateDialog.value = true
        importStatus.value = ''
        return
      }
      
      // 没有重复，直接导入（使用doImportZip而非doImport）
      return await doImportZip(false, undefined)
    }

    // 单文件MD：先用文件名检查是否存在
    const filename = selectedFile.value.name
    const checkResponse = await fetch(`/api/v1/books/check/${encodeURIComponent(filename)}`, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    if (!checkResponse.ok) {
      throw new Error('检查书籍失败')
    }

    const checkData = await checkResponse.json()

    // 如果书籍已存在，弹出确认对话框
    if (checkData.exists) {
      const confirm = await showConfirmDialog({
        title: '书籍已存在',
        message: `《${checkData.title}》已存在，是否覆盖？`,
        confirmButtonText: '覆盖',
        cancelButtonText: '取消'
      }).catch(() => null)

      if (!confirm) {
        // 用户取消
        importing.value = false
        return
      }

      // 覆盖导入，传入已有书籍的book_id
      return await doImport(true, checkData.book_id)
    } else {
      // 正常导入
      return await doImport(false)
    }
  } catch (error: any) {
    console.error('检查书籍失败:', error)
    // 尝试直接导入
    return await doImport(false)
  }
}

// 带上传进度的请求函数
const uploadWithProgress = (
  url: string,
  formData: FormData,
  statusText: string = '正在上传'
): Promise<{ ok: boolean; data: any }> => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    
    // 监听上传进度
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const percentComplete = Math.round((event.loaded / event.total) * 100)
        uploadProgress.value = percentComplete
        uploadStatus.value = `${statusText}... ${percentComplete}%`
      }
    })
    
    xhr.addEventListener('load', () => {
      uploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = ''
      
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText)
          resolve({ ok: true, data })
        } catch (e) {
          resolve({ ok: true, data: null })
        }
      } else {
        resolve({ ok: false, data: null })
      }
    })
    
    xhr.addEventListener('error', () => {
      uploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = ''
      reject(new Error('Upload failed'))
    })
    
    xhr.addEventListener('abort', () => {
      uploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = ''
      reject(new Error('Upload aborted'))
    })
    
    // 设置请求
    xhr.open('POST', url)
    xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
    
    // 开始上传
    uploading.value = true
    uploadProgress.value = 0
    uploadStatus.value = `${statusText}...`
    xhr.send(formData)
  })
}

// 带进度回调的上传函数（用于批量导入）
const uploadWithProgressCallback = (
  url: string,
  formData: FormData,
  statusText: string,
  onProgress: (progress: number) => void
): Promise<{ ok: boolean; data: any }> => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    
    // 监听上传进度
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const percentComplete = Math.round((event.loaded / event.total) * 100)
        onProgress(percentComplete)
        // 上传接近完成时，提示后端正在处理
        if (percentComplete >= 95) {
          importStatus.value = `${statusText}，后端处理中...`
        } else {
          importStatus.value = `${statusText}... ${percentComplete}%`
        }
      }
    })
    
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText)
          resolve({ ok: true, data })
        } catch (e) {
          resolve({ ok: true, data: null })
        }
      } else {
        resolve({ ok: false, data: null })
      }
    })
    
    xhr.addEventListener('error', () => {
      reject(new Error('Upload failed'))
    })
    
    xhr.addEventListener('abort', () => {
      reject(new Error('Upload aborted'))
    })
    
    // 设置请求
    xhr.open('POST', url)
    xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
    xhr.send(formData)
  })
}

// 带上传进度的流式请求函数（用于导入书籍）
const uploadWithProgressAndStream = (
  url: string,
  formData: FormData,
  statusText: string = '正在上传'
): Promise<void> => {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    
    // 监听上传进度
    xhr.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) {
        const percentComplete = Math.round((event.loaded / event.total) * 100)
        uploadProgress.value = percentComplete
        // 上传接近完成时，提示后端正在处理
        if (percentComplete >= 95) {
          uploadStatus.value = '后端处理中，请稍候...'
        } else {
          uploadStatus.value = `${statusText}... ${percentComplete}%`
        }
      }
    })
    
    xhr.addEventListener('load', async () => {
      uploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = ''
      
      // 上传完成，切换到导入状态
      importing.value = true
      importProgress.value = 0
      importStatus.value = '正在处理...'
      
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const text = xhr.responseText
          // 解析SSE消息
          const matches = text.matchAll(/data: (\{.*?\})/g)
          for (const match of matches) {
            try {
              const data = JSON.parse(match[1])
              importProgress.value = data.percentage || 0
              importStatus.value = data.message || ''

              if (data.success === true) {
                showNotify({ type: 'success', message: data.message, duration: 1500 })
                // 如果没有返回book_id，使用覆盖导入时传入的overwriteMode
                if (!data.book_id && overwriteMode.value) {
                  currentBookId.value = overwriteMode.value
                } else {
                  currentBookId.value = data.book_id || ''
                }
                await loadGroups()
                importCompleted.value = true
                if (!isZipImport.value && !isBatchImport.value) {
                  showChoiceDialog.value = true
                }
              } else if (data.success === false) {
                showNotify({ type: 'danger', message: data.message })
              }
            } catch (e) {
              console.error('解析SSE数据失败:', e)
            }
          }
          resolve()
        } catch (e) {
          resolve()
        }
      } else {
        reject(new Error('导入请求失败'))
      }
    })
    
    xhr.addEventListener('error', () => {
      uploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = ''
      reject(new Error('Upload failed'))
    })
    
    xhr.addEventListener('abort', () => {
      uploading.value = false
      uploadProgress.value = 0
      uploadStatus.value = ''
      reject(new Error('Upload aborted'))
    })
    
    // 设置请求
    xhr.open('POST', url)
    xhr.setRequestHeader('Authorization', `Bearer ${authStore.token}`)
    
    // 开始上传
    uploading.value = true
    uploadProgress.value = 0
    uploadStatus.value = `${statusText}...`
    xhr.send(formData)
  })
}

// 检查ZIP文件中的重复书籍
const checkZipDuplicates = async (file: File): Promise<any> => {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const result = await uploadWithProgress(
      '/api/v1/books/check-zip-duplicates',
      formData,
      '正在上传ZIP检查重复'
    )

    if (!result.ok) {
      return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    }

    return result.data || { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
  } catch (error) {
    console.error('检查重复书籍失败:', error)
    return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
  }
}

// 检查多个MD文件的重复书籍
const checkMdDuplicates = async (files: File[]): Promise<any> => {
  const formData = new FormData()
  files.forEach(file => {
    formData.append('files', file)
  })

  try {
    const result = await uploadWithProgress(
      '/api/v1/books/check-md-duplicates',
      formData,
      '正在上传文件检查重复'
    )

    if (!result.ok) {
      return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    }

    return result.data || { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
  } catch (error) {
    console.error('检查MD文件重复书籍失败:', error)
    return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
  }
}

// 切换重复书籍选中状态
const toggleDuplicateSelect = (bookId: string) => {
  const index = selectedDuplicateBooks.value.indexOf(bookId)
  if (index === -1) {
    selectedDuplicateBooks.value.push(bookId)
  } else {
    selectedDuplicateBooks.value.splice(index, 1)
  }
}

// 全选所有重复书籍
const selectAllDuplicates = () => {
  selectedDuplicateBooks.value = duplicateCheckResult.value.duplicate_books.map((b: any) => b.book_id)
}

// 清空选中的重复书籍
const clearAllDuplicates = () => {
  selectedDuplicateBooks.value = []
}

// 覆盖导入（导入所有书籍，包括重复的）
const handleImportWithOverwrite = () => {
  showDuplicateDialog.value = false
  importAction.value = 'overwrite'
  // 不修改 selectedDuplicateBooks，保持为空以区分“覆盖全部”和“覆盖选中”
  
  if (isBatchMdImport.value) {
    doBatchImportWithAction()
  } else {
    doImportZipWithAction()
  }
}

// 跳过重复书籍导入
const handleImportSkipDuplicates = () => {
  showDuplicateDialog.value = false
  importAction.value = 'skip'
  selectedDuplicateBooks.value = [] // 清空选中，表示跳过全部
  
  if (isBatchMdImport.value) {
    doBatchImportWithAction()
  } else {
    doImportZipWithAction()
  }
}

// 覆盖选中的重复书籍
const handleImportSelected = () => {
  showDuplicateDialog.value = false
  importAction.value = 'selected'
  
  if (isBatchMdImport.value) {
    doBatchImportWithAction()
  } else {
    doImportZipWithAction()
  }
}

// 根据用户选择执行批量MD导入
const doBatchImportWithAction = async () => {
  if (selectedFiles.value.length === 0 || !importAction.value) return

  importing.value = true
  importProgress.value = 0
  importStatus.value = '正在导入书籍...'

  // 根据用户选择决定导入策略
  // 'skip': 跳过所有重复 
  // 'overwrite': 覆盖所有重复
  // 'selected': 只覆盖选中的重复书籍
  
  const skipBookIds = new Set<string>()
  const overwriteBookIds = new Set<string>()
  
  if (importAction.value === 'skip') {
    // 跳过全部重复书籍
    duplicateCheckResult.value.duplicate_books.forEach((b: any) => skipBookIds.add(b.book_id))
  } else if (importAction.value === 'overwrite') {
    // 覆盖全部重复书籍
    duplicateCheckResult.value.duplicate_books.forEach((b: any) => overwriteBookIds.add(b.book_id))
  } else if (importAction.value === 'selected') {
    // 只覆盖选中的书籍
    selectedDuplicateBooks.value.forEach(id => overwriteBookIds.add(id))
    // 未选中的重复书籍要跳过
    duplicateCheckResult.value.duplicate_books.forEach((b: any) => {
      if (!selectedDuplicateBooks.value.includes(b.book_id)) {
        skipBookIds.add(b.book_id)
      }
    })
  }

  // 建立filename到book_id的映射
  const filenameToBookId = new Map<string, string>()
  duplicateCheckResult.value.duplicate_books.forEach((b: any) => {
    filenameToBookId.set(b.filename, b.book_id)
  })
  duplicateCheckResult.value.new_books.forEach((b: any) => {
    filenameToBookId.set(b.filename, b.book_id)
  })

  const totalFiles = selectedFiles.value.length
  let successCount = 0
  let failCount = 0
  let skipCount = 0

  for (let i = 0; i < totalFiles; i++) {
    const file = selectedFiles.value[i]
    const bookId = filenameToBookId.get(file.name)
    // 计算当前文件的进度基数
    const baseProgress = Math.round((i / totalFiles) * 100)
    
    // 检查是否需要跳过
    if (bookId && skipBookIds.has(bookId)) {
      skipCount++
      importProgress.value = Math.min(baseProgress + Math.round(100 / totalFiles), 99)
      importStatus.value = `跳过 (${i + 1}/${totalFiles}): ${file.name}`
      continue
    }

    try {
      const formData = new FormData()
      formData.append('file', file)

      const categoryId = importCategoryId.value
      let apiPath = '/api/v1/books/import'
      const params = new URLSearchParams()

      if (categoryId) {
        params.append('category_id', categoryId.toString())
      }
      
      // 如果需要覆盖，使用overwrite_book_ids参数
      if (bookId && overwriteBookIds.has(bookId)) {
        params.append('overwrite_book_ids', bookId)
      }

      if (params.toString()) {
        apiPath += `?${params.toString()}`
      }

      // 使用带进度回调的上传
      const result = await uploadWithProgressCallback(
        apiPath,
        formData,
        `正在上传 (${i + 1}/${totalFiles}): ${file.name}`,
        (progress) => {
          // 当前文件进度 + 基数 = 总体进度
          importProgress.value = Math.min(baseProgress + Math.round(progress / totalFiles), 99)
        }
      )

      if (result.ok) {
        successCount++
      } else {
        failCount++
        console.error(`导入失败: ${file.name}`)
      }
    } catch (error) {
      failCount++
      console.error(`导入异常: ${file.name}`, error)
    }
  }

  // 完成
  importProgress.value = 100
  const summary = skipCount > 0 
    ? `批量导入完成: 成功 ${successCount} 本, 跳过 ${skipCount} 本, 失败 ${failCount} 本`
    : `批量导入完成: 成功 ${successCount} 本, 失败 ${failCount} 本`
  importStatus.value = summary
  importCompleted.value = true
  importing.value = false
  
  if (successCount > 0) {
    showNotify({ type: 'success', message: `成功导入 ${successCount} 本书籍`, duration: 2000 })
  }

  // 重置状态
  isBatchMdImport.value = false
  selectedDuplicateBooks.value = []
  
  // 刷新分组列表
  await loadGroups()
}

// 取消导入
const cancelImport = () => {
  showDuplicateDialog.value = false
  importAction.value = null
  importing.value = false
  importStatus.value = ''
  selectedFile.value = null
  importProgress.value = 0
  selectedDuplicateBooks.value = []
  isBatchMdImport.value = false
}

// 根据用户选择执行ZIP导入
const doImportZipWithAction = async () => {
  if (!selectedFile.value || !importAction.value) return

  importing.value = true
  importProgress.value = 0
  importStatus.value = '正在导入书籍...'

  // 根据用户选择决定导入策略
  // 'skip': 跳过所有重复 (skipDuplicates=true, overwriteBookIds=undefined)
  // 'overwrite': 覆盖所有重复 (skipDuplicates=false, overwriteBookIds=所有重复书籍ID)
  // 'selected': 只覆盖选中的重复书籍 (skipDuplicates=false, overwriteBookIds=选中的书籍ID)
  const skipDuplicates = importAction.value === 'skip'
  
  let overwriteBookIds: string[] | undefined = undefined
  if (importAction.value === 'overwrite') {
    // 覆盖全部：传递所有重复书籍的ID
    overwriteBookIds = duplicateCheckResult.value.duplicate_books.map((b: any) => b.book_id)
  } else if (importAction.value === 'selected') {
    // 覆盖选中：传递用户选中的书籍ID
    overwriteBookIds = selectedDuplicateBooks.value
  }
  // 'skip' 模式下 overwriteBookIds 保持 undefined

  await doImportZip(skipDuplicates, overwriteBookIds)
}

// 执行ZIP导入（支持跳过重复和指定覆盖）
const doImportZip = async (skipDuplicates: boolean = false, overwriteBookIds?: string[]) => {
  if (!selectedFile.value) return

  importing.value = true
  importCompleted.value = false
  importProgress.value = 0
  importStatus.value = '正在导入...'

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    // 添加category_id参数（0表示未分组）
    const categoryId = importCategoryId.value

    let apiPath = '/api/v1/books/import'
    const params = new URLSearchParams()

    // 添加skip_duplicates参数
    if (skipDuplicates) {
      params.append('skip_duplicates', 'true')
    }

    // 添加overwrite_book_ids参数（指定要覆盖的书籍ID）
    if (overwriteBookIds && overwriteBookIds.length > 0) {
      params.append('overwrite_book_ids', overwriteBookIds.join(','))
    }

    // 添加category_id参数
    if (categoryId) {
      params.append('category_id', categoryId.toString())
    }

    if (params.toString()) {
      apiPath += `?${params.toString()}`
    }

    await uploadWithProgressAndStream(apiPath, formData, '正在上传ZIP文件')
  } catch (error: any) {
    console.error('导入书籍失败:', error)
    const message = error.message || '导入失败，请重试'
    showNotify({ type: 'danger', message })
  } finally {
    importing.value = false
    // 清空文件输入
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

// 执行导入
const doImport = async (overwrite: boolean, existingBookId?: string) => {
  importing.value = true
  importCompleted.value = false
  importProgress.value = 0
  importStatus.value = '正在导入...'
  overwriteMode.value = existingBookId || ''

  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value!)

    // 添加category_id参数（0表示未分组）
    const categoryId = importCategoryId.value

    let apiPath = overwrite ? '/api/v1/books/import/overwrite' : '/api/v1/books/import'
    const params = new URLSearchParams()

    // 如果是覆盖导入，添加已有的book_id参数
    if (overwrite && existingBookId) {
      params.append('book_id', existingBookId)
    }

    // 添加category_id参数
    if (categoryId) {
      params.append('category_id', categoryId.toString())
    }

    if (params.toString()) {
      apiPath += `?${params.toString()}`
    }

    await uploadWithProgressAndStream(apiPath, formData, '正在上传文件')
  } catch (error: any) {
    console.error('导入书籍失败:', error)
    const message = error.message || '导入失败，请重试'
    showNotify({ type: 'danger', message })
  } finally {
    importing.value = false
    // 清空文件输入
    if (fileInput.value) {
      fileInput.value.value = ''
    }
  }
}

// 编辑文件并生成语音
const handleEditAndGenerate = async () => {
  const bookId = currentBookId.value
  if (!bookId) {
    showNotify({ type: 'danger', message: '书籍ID无效' })
    return
  }
  showChoiceDialog.value = false

  // 加载书籍内容
  showLoadingToast({ message: '加载中...', forbidClick: true })
  try {
    const res = await api.get<{ title: string }>(`/books/${bookId}`)
    currentBookTitle.value = res.data.title

    const contentRes = await api.get<{ content: string }>(`/books/${bookId}/content`)
    editContent.value = contentRes.data.content
    // 不关闭导入对话框，只关闭选择对话框
    showChoiceDialog.value = false
    showEditDialog.value = true
    closeToast()
  } catch (error) {
    console.error('加载书籍内容失败:', error)
    closeToast()
    showNotify({ type: 'danger', message: '加载书籍内容失败' })
  }
}

// 编辑保存后的回调
const onEditSaved = () => {
  loadGroups()
}

// 关闭导入对话框
const closeImportDialog = () => {
  showImportDialog.value = false
}

// 导入对话框关闭后的回调（清空所有状态）
const onImportDialogClosed = () => {
  showChoiceDialog.value = false
  showDuplicateDialog.value = false
  selectedFile.value = null
  selectedFiles.value = []
  importProgress.value = 0
  importStatus.value = ''
  overwriteMode.value = ''
  importing.value = false
  importCompleted.value = false
  currentBookId.value = ''
  isZipImport.value = false
  isBatchImport.value = false
  isBatchMdImport.value = false
  importAction.value = null
  selectedDuplicateBooks.value = []
  duplicateCheckResult.value = {
    has_duplicates: false,
    duplicate_books: [],
    new_books: [],
    total_books: 0
  }
}

// BookEditDialog 组件引用
const bookEditDialogRef = ref<{
  closeImagePreview: () => void
} | null>(null)

// 处理浏览器前进/后退按钮
const handleBrowserNavigation = () => {
  if (showEditDialog.value) {
    // 如果编辑弹窗打开，先关闭图片预览
    bookEditDialogRef.value?.closeImagePreview()
    // 关闭编辑弹窗
    showEditDialog.value = false
    // 触发关闭后的事件
    onEditClosedHandler()
  } else {
    // 如果编辑弹窗关闭，说明是前进操作（从关闭状态到打开状态），需要打开弹窗
    // 检查是否有待恢复的状态
    const state = window.history.state
    if (state && state.openEditDialog) {
      // 前进到编辑状态，恢复弹窗
      showEditDialog.value = true
    }
  }
}

// 监听浏览器前进/后退按钮
window.addEventListener('popstate', handleBrowserNavigation)

// 当编辑弹窗打开/关闭时，管理浏览器历史记录
watch(showEditDialog, (newVal) => {
  if (newVal) {
    // 弹窗打开时，向历史记录栈中添加一条记录
    // 这样点击后退时会回到关闭状态，而不是离开页面
    window.history.pushState({ openEditDialog: true, bookId: currentBookId.value }, '')
  } else {
    // 弹窗关闭时，回退到之前的历史记录
    // 使用 replaceState 而不是 pushState，避免在历史栈中添加额外记录
    window.history.replaceState(null, '', window.location.pathname)
  }
})

// 生命周期
onMounted(async () => {
  // 初始化横屏检测
  checkOrientation()
  window.addEventListener('resize', handleResize)

  // 点击页面其他区域关闭导航栏菜单
  window.addEventListener('click', handleCloseNavMenus)

  loadGroups()
  await loadUserSettings()
  loadDictionaryStatus()
  // 如果当前是Kokoro TTS，加载语音列表
  if (ttsServiceName.value === 'kokoro-tts') {
    await loadTtsVoices()
  }
})

// 处理菜单显示 - 实现互斥（打开一个关闭其他）
const handlePopoverShow = (show: boolean, current: string) => {
  if (show) {
    // 打开一个菜单时，关闭其他菜单
    if (current !== 'book') showBookPopover.value = false
    if (current !== 'user') showUserPopover.value = false
    if (current !== 'settings') showSettingsPopover.value = false
  }
}

// 关闭导航栏菜单
const handleCloseNavMenus = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  // 检查点击是否在导航操作区域内或 popover 内部
  const navActions = target.closest('.nav-actions')
  const inPopover = target.closest('.van-popover')
  if (!navActions && !inPopover) {
    // 点击在导航栏和popover外，关闭所有菜单
    showBookPopover.value = false
    showUserPopover.value = false
    showSettingsPopover.value = false
  }
}

// keep-alive 激活时（从阅读页返回）
// 组件被缓存，滚动位置和状态自动保持
// 书籍正文修改不影响列表，无需刷新

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  window.removeEventListener('click', handleCloseNavMenus)
  window.removeEventListener('popstate', handleBrowserNavigation)
})
</script>

<style scoped>
.home {
  min-height: 100vh;
  background: #f7f8fa;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
  -webkit-tap-highlight-color: transparent;
}

.nav-search {
  display: flex;
  align-items: center;
  background: #f7f8fa;
  border-radius: 20px;
  padding: 4px 12px;
  width: 140px;
}

@media (max-width: 375px) {
  .nav-search {
    width: 120px;
  }
}

.search-icon {
  color: #969799;
  margin-right: 6px;
  font-size: 16px;
}

.search-input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 14px;
  width: 100%;
}

.nav-icon {
  font-size: 20px;
  color: #1989fa;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.nav-icon:active {
  opacity: 0.6;
}

.nav-icon-wrap {
  padding: 4px;
  -webkit-tap-highlight-color: transparent;
}

.nav-icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}

.nav-icon-btn:active {
  background: rgba(0, 0, 0, 0.05);
}

.nav-actions {
  display: flex;
  align-items: center;
  -webkit-tap-highlight-color: transparent;
  gap: 8px;
}

@media (max-width: 375px) {
  .nav-actions {
    gap: 4px;
  }
}

.nav-btn {
  min-width: 32px;
}

.username-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.username-link {
  font-size: 14px;
  color: #333;
  margin: 0 8px;
  cursor: pointer;
}

.username-link:hover {
  color: #1989fa;
}

.username {
  font-size: 14px;
  color: #333;
  margin: 0 2px;
}

@media (max-width: 375px) {
  .username {
    font-size: 12px;
    max-width: 50px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.content {
  padding-bottom: 50px;
}

.group-item {
  margin-bottom: 8px;
  background: #fff;
}

.group-title {
  display: flex;
  align-items: center;
}

.group-checkbox {
  display: flex;
  align-items: center;
  margin-right: 8px;
}

.group-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
  accent-color: #1989fa;
}

.group-name {
  font-size: 16px;
  font-weight: 500;
}

.book-count {
  font-size: 12px;
  color: #969799;
  margin-left: 8px;
}

.group-actions {
  display: flex;
  align-items: center;
}

.group-import-btn {
  min-width: 28px;
  height: 24px;
}

.book-list {
  padding: 0;
}

.book-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid #f5f5f5;
  cursor: pointer;
}

.book-item:last-child {
  border-bottom: none;
}

.book-item:hover {
  background: #f7f8fa;
}

.book-cover {
  width: 60px;
  height: 80px;
  flex-shrink: 0;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}

.book-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.book-info {
  flex: 1;
  margin-left: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.book-title {
  font-size: 15px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.book-meta {
  font-size: 12px;
  color: #969799;
  margin-top: 4px;
}

.empty-tip {
  text-align: center;
  padding: 20px;
  color: #969799;
  font-size: 14px;
}

/* 多选模式样式 */
.book-item.selected {
  background: #e6f7ff;
}

.book-checkbox {
  margin-right: 8px;
  display: flex;
  align-items: center;
}

.book-checkbox input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

/* 批量操作栏 */
.batch-actions {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: #fff;
  padding: 10px 16px;
  display: flex;
  justify-content: center;
  gap: 12px;
  box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.1);
  z-index: 100;
}

/* 右键菜单 */
.context-menu {
  position: fixed !important;
  width: 150px;
  top: 50% !important;
  left: 50% !important;
  transform: translate(-50%, -50%) !important;
}

/* 移动到分组对话框 */
.move-dialog {
  max-height: 60vh;
  display: flex;
  flex-direction: column;
}

.move-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #eee;
  font-size: 16px;
  font-weight: 500;
}

.move-dialog-content {
  flex: 1;
  overflow-y: auto;
}

.move-dialog-footer {
  display: flex;
  justify-content: space-between;
  padding: 16px;
  gap: 12px;
  border-top: 1px solid #eee;
}

/* 封面对话框 */
.cover-dialog-content {
  padding: 16px;
}

.cover-preview {
  width: 120px;
  height: 160px;
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  border-radius: 8px;
  overflow: hidden;
}

.cover-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cover-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cover-picker {
  padding: 16px;
  max-height: 60vh;
  display: flex;
  flex-direction: column;
}

.cover-picker-title {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 12px;
  text-align: center;
  flex-shrink: 0;
}

.cover-picker-content {
  flex: 1;
  overflow-y: auto;
  min-height: 150px;
  max-height: 40vh;
}

.cover-picker-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.cover-picker-footer {
  flex-shrink: 0;
  margin-top: 12px;
}

.cover-picker-item {
  aspect-ratio: 1;
  border-radius: 4px;
  overflow: hidden;
  cursor: pointer;
  border: 2px solid transparent;
}

.cover-picker-item.selected {
  border-color: #1989fa;
}

.cover-picker-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

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

/* 导出进度对话框样式 */
.export-progress-content {
  padding: 24px 20px;
  text-align: center;
}

.export-status {
  margin-top: 16px;
  font-size: 14px;
  color: #323233;
  font-weight: 500;
}

.export-current-book {
  margin-top: 8px;
  font-size: 12px;
  color: #969799;
  word-break: break-all;
  max-width: 100%;
}

.choice-dialog-content {
  padding: 20px;
  text-align: center;
}

.choice-hint {
  margin-bottom: 20px;
  color: #646566;
}

.choice-dialog-content .van-button {
  padding: 0 24px;
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

.edit-dialog-content {
  height: 70vh;
  display: flex;
  flex-direction: column;
}

.edit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #eee;
}

.audio-progress {
  padding: 10px 16px;
  background: #f7f8fa;
}

.progress-msg {
  display: block;
  font-size: 12px;
  color: #969799;
  margin-top: 4px;
  text-align: center;
}

.edit-title {
  font-size: 14px;
  color: #333;
}

.edit-body {
  flex: 1;
  overflow: hidden;
}

/* 设置弹窗样式 */
.settings-dialog-content {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.settings-dialog-content .van-field {
  margin-bottom: 8px;
}

.settings-dialog-content .van-field:last-of-type {
  margin-bottom: 0;
}

.settings-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 8px;
  color: #969799;
  font-size: 14px;
}

.dict-label {
  font-size: 12px;
  color: #969799;
}

.disabled-cell {
  opacity: 0.5;
}

.field-info-icon {
  margin-left: 4px;
  color: #1989fa;
  font-size: 14px;
  cursor: pointer;
}

.field-hint {
  font-size: 12px;
  color: #969799;
  padding: 4px 16px 12px;
  margin-top: 0;
}

.usage-check-btn {
  margin: 12px 16px;
  width: calc(100% - 32px);
}

/* 翻译设置样式 */
.translation-settings-content {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}

.translation-api-list {
  margin-bottom: 16px;
}

.translation-api-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #323233;
}

.translation-api-item {
  display: flex;
  align-items: center;
  gap: 8px;

  .api-name {
    font-weight: 500;
  }

  .api-appid {
    font-size: 12px;
    color: #969799;
  }
}

.api-actions {
  display: flex;
  align-items: center;
  gap: 8px;

  .api-edit-btn {
    color: #1989fa;
    cursor: pointer;
    font-size: 16px;
  }

  .api-delete-btn {
    color: #ee0a24;
    cursor: pointer;
    font-size: 16px;
  }
}

/* 百度翻译设置样式 */
.baidu-settings {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #eee;
}

.baidu-settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #323233;
}

.translation-api-item {
  display: flex;
  align-items: center;
  gap: 8px;

  .api-name {
    font-weight: 500;
  }

  .api-appid {
    font-size: 12px;
    color: #969799;
  }
}

.api-actions {
  display: flex;
  align-items: center;
  gap: 8px;

  .api-edit-btn {
    color: #1989fa;
    cursor: pointer;
    font-size: 16px;
  }

  .api-delete-btn {
    color: #ee0a24;
    cursor: pointer;
    font-size: 16px;
  }
}

.translation-hint {
  text-align: center;
  font-size: 12px;
  color: #969799;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 4px;

  &.warning {
    color: #ff976a;
  }
}

.tts-voice-select {
  width: 100%;
  height: 32px;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  background: #fff;
  font-size: 14px;
  color: #323233;
  outline: none;
  padding: 0 8px;
}

.tts-voice-select option {
  background: #fff;
  color: #323233;
}

.tts-speed-input {
  width: 80px;
  height: 24px;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  padding: 0 8px;
  font-size: 14px;
  color: #323233;
  outline: none;
}

.speed-unit {
  margin-left: 8px;
  color: #969799;
  font-size: 14px;
}

.tts-test-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #eee;
}

.test-text {
  margin-top: 8px;
  font-size: 12px;
  color: #646566;
  line-height: 1.5;
  font-style: italic;
}

/* 已读书籍样式 */
.book-item.is-read {
  opacity: 0.7;
}

.book-item.is-read .book-title {
  text-decoration: line-through;
  color: #969799;
}

.read-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  background: #07c160;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.book-cover {
  position: relative;
}

/* 滑动操作样式 */
.swipe-action {
  height: 100%;
  width: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  gap: 4px;
}

.swipe-action.unread {
  background: #ff976a;
}

.swipe-action.read {
  background: #07c160;
}

/* 补充翻译进度弹窗样式 */
.supplement-progress-content {
  padding: 24px 16px;
}

.supplement-progress-content .van-progress {
  margin-bottom: 16px;
}

.progress-message {
  text-align: center;
  font-size: 14px;
  color: #646566;
  word-break: break-all;
  min-height: 20px;
}
</style>
