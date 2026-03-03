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
          <van-icon name="plus" class="nav-icon" @click="openImportDialog(0)" />
        </div>
      </template>
      <template #right>
        <div class="nav-actions">
          <!-- 书籍管理下拉菜单 -->
          <van-popover
            v-model:show="showBookPopover"
            placement="bottom-end"
            :actions="bookActions"
            @select="onBookActionSelect"
          >
            <template #reference>
              <div class="nav-icon-btn">
                <van-icon name="bars" class="nav-icon" />
              </div>
            </template>
          </van-popover>
          <!-- 用户名称显示 -->
          <span class="username">{{ authStore.user?.username || '用户' }}</span>
          <!-- 设置下拉菜单 -->
          <van-popover
            v-model:show="showSettingsPopover"
            placement="bottom-end"
            :actions="settingsActions"
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
          v-show="group.id !== 0 || group.books.length > 0"
        >
          <!-- 分组标题 -->
          <template #title>
            <div
              class="group-title"
              @contextmenu.prevent="showGroupContextMenu($event, group)"
              @longpress="showGroupContextMenu($event, group)"
            >
              <span class="group-name">{{ group.name }}</span>
              <span class="book-count">({{ group.books.length }})</span>
            </div>
          </template>
          <!-- 分组右侧操作 -->
          <template #right-icon>
            <div class="group-actions" @click.stop>
              <!-- 该分组下的导入按钮 -->
              <van-button
                type="primary"
                size="small"
                icon="plus"
                @click="openImportDialog(group.id)"
                class="group-import-btn"
              />
            </div>
          </template>

          <!-- 书籍列表 -->
          <div class="book-list" :class="{ 'sorting-mode': isSorting }">
            <van-swipe-cell
              v-for="book in getVisibleBooks(group)"
              :key="book.id"
              :ref="(el) => { if (el) swipeCellRefs[book.id] = el }"
              :disabled="isMultiSelect || isSorting"
              :stop-propagation="true"
              @open="handleSwipeOpen($event, book)"
            >
              <div
                class="book-item"
                :class="{ 'selected': selectedBooks.includes(book.id), 'sorting': isSorting, 'is-read': book.is_read }"
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
                <!-- 排序拖拽手柄 -->
                <div v-if="isSorting" class="sort-handle">
                  <van-icon name="wap-nav" />
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
          <template v-if="selectedFile">
            <van-icon name="description" size="40" color="#1989fa" />
            <p class="file-name">{{ selectedFile.name }}</p>
            <p class="file-hint">点击更换文件</p>
          </template>
          <template v-else>
            <van-icon name="plus" size="40" color="#969799" />
            <p>拖拽MD或ZIP文件到这里，或点击选择</p>
            <p class="hint">支持 .md 和 .zip 格式</p>
          </template>
        </div>

        <input
          ref="fileInput"
          type="file"
          accept=".md,.zip"
          hidden
          @change="onFileSelected"
        />

        <!-- 导入进度 -->
        <div v-if="importing || importProgress === 100" class="import-progress">
          <van-progress
            :percentage="importProgress"
            :stroke-width="8"
            :show-pivot="true" />
          <p class="import-status">{{ importStatus }}</p>
        </div>

        <!-- 操作按钮 -->
        <div class="import-actions">
          <van-button
            type="primary"
            size="large"
            :disabled="!selectedFile || importing"
            :loading="importing"
            @click="importCompleted ? closeImportDialog() : handleImportConfirm()"
          >
            {{ importing ? '导入中...' : (importCompleted ? '关闭' : '开始导入') }}
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
      v-model="showEditDialog"
      :book-id="currentBookId"
      :title="currentBookTitle"
      :initial-content="editContent"
      @saved="onEditSaved"
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
        <van-cell title="修改书籍顺序" clickable @click="enableSorting" v-if="!isSorting" />
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
        <van-cell title="修改名称" clickable @click="openRenameGroupDialog" v-if="contextMenuGroup?.id !== 0" />
        <van-cell title="删除分组" clickable @click="confirmDeleteGroup" v-if="contextMenuGroup?.id !== 0" />
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
                clickable
                @click="selectedMoveCategory = 0"
              >
                <template #title>
                  <span>未分组</span>
                </template>
                <template #right-icon>
                  <van-radio :name="0" />
                </template>
              </van-cell>
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
          <van-button size="small" type="primary" @click="confirmMoveBooks">
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

        <!-- 朗读速度 -->
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
          范围: {{ ttsServiceName === 'kokoro-tts' ? '0.25 - 4.0' : '0.5 - 2.0' }} (默认 1.0)
        </div>

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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showNotify, showToast, showLoadingToast, closeToast } from 'vant'
import { useAuthStore, api } from '@/store/auth'
import BookEditDialog from '@/components/BookEditDialog.vue'

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

// 导入相关
const showImportDialog = ref(false)
const importCategoryId = ref(0) // 导入到的分类ID
const fileInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const importCompleted = ref(false)
const selectedFile = ref<File | null>(null)
const isDragOver = ref(false)
const importProgress = ref(0)
const importStatus = ref('')
const currentBookId = ref('')
const showChoiceDialog = ref(false)
const overwriteMode = ref('')
const isZipImport = ref(false) // 标记是否是ZIP导入
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

// 排序模式
const isSorting = ref(false)

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

// 修改封面对话框
const showCoverDialog = ref(false)
const coverInput = ref<HTMLInputElement | null>(null)
const previewCover = ref('')
const showCoverPicker = ref(false)
const mdImages = ref<string[]>([])
const selectedMdImage = ref('')

// 朗读设置弹窗
const showTtsSettingsDialog = ref(false)
const ttsServiceName = ref('kokoro-tts')
const ttsVoice = ref('')
const ttsSpeed = ref(1.0)
const ttsApiUrl = ref('')
// 豆包TTS配置
const ttsAppId = ref('')
const ttsAccessKey = ref('')
const ttsResourceId = ref('')
const defaultTtsConfig = ref({
  service_name: 'kokoro-tts',
  voice: 'bf_v0isabella',
  speed: 1.0,
  api_url: 'http://localhost:8880/v1/audio/speech',
  app_id: '',
  access_key: '',
  resource_id: ''
})
const ttsVoices = ref<{id: string, name: string}[]>([])
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

// 加载用户设置
const loadUserSettings = async () => {
  try {
    const res = await api.get('/settings/')
    dictionarySource.value = res.data.dictionary.dictionary_source
    phoneticAccent.value = res.data.phonetic?.accent || 'uk'

    // 获取服务名称
    const serviceName = res.data.tts?.service_name || 'kokoro-tts'

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
      resource_id: res.data.tts?.doubao_resource_id || ''
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
  } catch (error) {
    console.error('加载用户设置失败:', error)
  }
}

// 加载TTS语音列表
const loadTtsVoices = async () => {
  try {
    const res = await api.get('/settings/tts/voices')
    console.log('TTS voices response:', res.data)
    console.log('Response type:', typeof res.data)
    console.log('Is array:', Array.isArray(res.data))
    // 如果返回的是数组，说明后端没有正确处理
    if (Array.isArray(res.data)) {
      // 手动转换字符串数组为对象数组
      ttsVoices.value = res.data.map((v: string) => ({ id: v, name: v }))
    } else {
      ttsVoices.value = res.data.voices || []
    }
    console.log('Loaded voices:', ttsVoices.value)

    // 如果当前语音不在列表中，且是有效的Kokoro语音（以af_/am_/bf_/bm_开头），则添加它
    // 这处理了新语音可用但前端映射表未及时更新的情况
    if (ttsServiceName.value === 'kokoro-tts' && ttsVoice.value) {
      const voiceExists = ttsVoices.value.some((v: {id: string, name: string}) => v.id === ttsVoice.value)
      const isKokoroVoice = /^[ab]f_/.test(ttsVoice.value) || /^[ab]m_/.test(ttsVoice.value)
      if (!voiceExists && isKokoroVoice) {
        console.log('Kokoro语音不在列表中，添加:', ttsVoice.value)
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
  return ttsVoices.value
})

// 监听服务切换，从数据库恢复该服务的设置
watch(ttsServiceName, async (newService, oldService) => {
  if (newService !== oldService && oldService !== undefined) {
    console.log(`TTS服务切换: ${oldService} -> ${newService}`)

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
        console.log(`Kokoro设置已恢复: voice=${ttsVoice.value}, speed=${ttsSpeed.value}`)
      } else {
        // 恢复豆包设置
        const savedVoice = ttsSettings?.doubao_voice
        const savedSpeed = ttsSettings?.doubao_speed
        const savedResourceId = ttsSettings?.doubao_resource_id

        // 优先使用数据库中的语音
        ttsVoice.value = savedVoice || 'en_male_corey_emo_v2_mars_bigtts'
        ttsSpeed.value = savedSpeed ?? 1.0
        ttsResourceId.value = savedResourceId || defaultTtsConfig.value.resource_id || 'seed-tts-1.0'
        console.log(`豆包设置已恢复: voice=${ttsVoice.value}, speed=${ttsSpeed.value}`)
      }
    } catch (error) {
      console.error('恢复设置失败:', error)
      // 使用默认值
      if (newService === 'kokoro-tts') {
        ttsVoice.value = 'bf_v0isabella'
        ttsSpeed.value = 1.0
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

// 停止TTS测试播放
const stopTtsTest = () => {
  if (currentTestAudio) {
    currentTestAudio.pause()
    currentTestAudio.currentTime = 0
    currentTestAudio = null
    ttsTesting.value = false
    console.log('TTS测试播放已停止')
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
    console.log(`TTS测试: service=${ttsServiceName.value}, voice=${voice}, speed=${speed}`)
    const response = await fetch('/api/v1/tts/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify({
        text: ttsTestText,
        voice: voice,
        speed: speed,
        service_name: ttsServiceName.value  // 传递当前选择的服务名称
      })
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'TTS请求失败' }))
      throw new Error(errorData.detail || 'TTS请求失败')
    }

    const data = await response.json()
    if (data.url) {
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
      throw new Error('未获取到音频URL')
    }
  } catch (error: any) {
    console.error('TTS测试失败:', error)
    const errorMsg = error.message || '朗读测试失败'
    // 针对豆包TTS的特殊提示
    if (ttsServiceName.value === 'doubao-tts' && errorMsg.includes('app_id')) {
      showNotify({ type: 'danger', message: '豆包TTS需要配置APP ID和Access Key，请在设置中填写' })
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
  if (isKokoro && (ttsSpeed.value < 0.25 || ttsSpeed.value > 4.0)) {
    showNotify({ type: 'warning', message: 'Kokoro 朗读速度必须在 0.25 到 4.0 之间' })
    return
  }
  if (!isKokoro && (ttsSpeed.value < 0.5 || ttsSpeed.value > 2.0)) {
    showNotify({ type: 'warning', message: '豆包朗读速度必须在 0.5 到 2.0 之间' })
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
  if (!searchText.value.trim()) {
    return bookGroups.value
  }

  const keyword = searchText.value.toLowerCase().trim()
  return bookGroups.value.map(group => ({
    ...group,
    books: group.books.filter(book =>
      book.title.toLowerCase().includes(keyword)
    )
  })).filter(group => group.books.length > 0)
})

// 设置/用户菜单
const settingsActions = computed<PopoverAction[]>(() => {
  const actions: PopoverAction[] = []

  // 生词本
  actions.push({ text: '生词本', icon: 'records-o', key: 'vocabulary' })
  // 朗读设置
  actions.push({ text: '朗读设置', icon: 'volume-o', key: 'ttsSettings' })
  // 词典设置
  actions.push({ text: '词典设置', icon: 'bookmark-o', key: 'dictionarySettings' })
  // 音标设置
  actions.push({ text: '音标设置', icon: 'font-o', key: 'phoneticSettings' })

  if (authStore.isAdmin) {
    actions.push({ text: '用户管理', icon: 'friends-o', key: 'users' })
    // 修复书籍数据（仅管理员可见）
    actions.push({ text: '修复书籍数据', icon: 'sync-o', key: 'syncBooks' })
  } else {
    actions.push({ text: '个人信息', icon: 'user-o', key: 'users' })
  }

  actions.push({ text: '退出登录', icon: 'logout', key: 'logout' })

  return actions
})

// 书籍管理菜单
const bookActions = [
  { text: '添加分组', icon: 'plus', key: 'addGroup' },
  { text: '收起所有分组', icon: 'shrink', key: 'collapseAll' }
]

// 设置/用户菜单选择
const onSettingsSelect = (action: PopoverAction) => {
  if (action.key === 'vocabulary') {
    router.push('/vocabulary')
  } else if (action.key === 'ttsSettings') {
    loadTtsVoices()
    // 如果使用豆包且resource_id为空，使用默认值
    if (ttsServiceName.value === 'doubao-tts' && !ttsResourceId.value) {
      ttsResourceId.value = defaultTtsConfig.value.resource_id || 'seed-tts-1.0'
    }
    showTtsSettingsDialog.value = true
  } else if (action.key === 'dictionarySettings') {
    showDictionarySettingsDialog.value = true
  } else if (action.key === 'phoneticSettings') {
    showPhoneticSettingsDialog.value = true
  } else if (action.key === 'users') {
    router.push('/users')
  } else if (action.key === 'syncBooks') {
    handleSyncBooks()
  } else if (action.key === 'logout') {
    showConfirmDialog({
      title: '确认退出',
      message: '确定要退出登录吗？'
    }).then(() => {
      authStore.logout()
      showNotify('已退出登录')
      router.push('/login')
    }).catch(() => {
      // 取消操作
    })
  }
}

// 修复书籍数据
const handleSyncBooks = async () => {
  showConfirmDialog({
    title: '修复书籍数据',
    message: '将扫描 Books 目录并同步数据库记录，是否继续？'
  }).then(async () => {
    try {
      showNotify({ type: 'success', message: '正在同步...', duration: 1000 })
      const res = await api.post('/books/sync')
      const result = res.data
      
      // 构建结果消息
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
      
      if (messages.length === 0) {
        showNotify({ type: 'success', message: '无需修复，数据已同步' })
      } else {
        showNotify({ type: 'success', message: messages.join('，') })
        // 重新加载书籍列表
        await loadGroups()
      }
    } catch (error: any) {
      console.error('同步失败:', error)
      showNotify({ type: 'danger', message: error.response?.data?.detail || '同步失败' })
    }
  }).catch(() => {
    // 取消操作
  })
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
    console.log('loadGroups response:', JSON.stringify(res.data))
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
  } else if (isSorting.value) {
    // 排序模式下点击暂时不做处理
  } else {
    openBook(bookId)
  }
}

// 处理封面点击（修改封面）
const handleCoverClick = (book: Book) => {
  if (isMultiSelect.value) {
    toggleBookSelect(book.id)
  } else if (isSorting.value) {
    // 排序模式
  } else {
    // 正常打开书籍
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
const toggleHideReadBooks = () => {
  if (contextMenuGroup.value) {
    const groupId = contextMenuGroup.value.id
    hideReadBooksMap.value[groupId] = !hideReadBooksMap.value[groupId]
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
  if (contextMenuBook.value) {
    selectedBooks.value = [contextMenuBook.value.id]
  }
}

// 启用排序模式
const enableSorting = () => {
  closeContextMenu()
  isSorting.value = true
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

// 批量移动书籍
const batchMoveBooks = async () => {
  // 加载分组列表用于选择
  try {
    const res = await api.get<{ id: number; name: string }[]>('/categories')
    // 过滤掉当前所在分组和未分组(0)
    categoriesForMove.value = res.data.filter((c: { id: number; name: string }) =>
      c.id !== 0 && c.id !== currentGroupId.value
    )
    selectedMoveCategory.value = 0
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
    // 模拟进度更新（因为后端是一次性返回，这里用前端模拟进度）
    const totalBooks = bookIds.length
    let processedBooks = 0

    // 开始进度模拟
    const progressInterval = setInterval(() => {
      if (processedBooks < totalBooks) {
        processedBooks++
        exportProgress.value = Math.round((processedBooks / totalBooks) * 90) // 最多到90%，留给下载
        exportStatus.value = `正在打包书籍 (${processedBooks}/${totalBooks})...`
        // 查找当前处理的书籍名称
        for (const group of bookGroups.value) {
          const book = group.books.find(b => b.id === bookIds[processedBooks - 1])
          if (book) {
            exportCurrentBook.value = book.title
            break
          }
        }
      }
    }, 2000) // 每2000ms更新一本，让进度显示更平滑

    const response = await fetch('/api/v1/books/export', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify({ book_ids: bookIds })
    })

    clearInterval(progressInterval)

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: '导出失败' }))
      throw new Error(errorData.detail || '导出失败')
    }

    // 获取文件名
    const contentDisposition = response.headers.get('content-disposition')
    let filename = 'books_export.zip'
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename\*?=(?:UTF-8'')?([^;]+)/i)
      if (filenameMatch) {
        filename = decodeURIComponent(filenameMatch[1].trim().replace(/"/g, ''))
      }
    }

    exportProgress.value = 95
    exportStatus.value = '正在下载文件...'
    exportCurrentBook.value = filename

    // 下载文件
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    exportProgress.value = 100
    exportStatus.value = '导出完成！'

    // 延迟关闭对话框
    setTimeout(() => {
      showExportProgressDialog.value = false
      showNotify({ type: 'success', message: '书籍导出成功', duration: 1500 })
    }, 800)

    // 如果是多选模式，退出多选
    if (isMultiSelect.value) {
      cancelMultiSelect()
    }
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
    console.log('Loading cover for book:', contextMenuBook.value.id, contextMenuBook.value.title)

    // 获取书籍详情来获取书籍路径
    const bookRes = await api.get<{ book_path: string }>(`/books/${contextMenuBook.value.id}`)
    const bookFolder = bookRes.data.book_path

    console.log('Book folder:', bookFolder)

    // 加载书籍内容
    const contentRes = await api.get<{ content: string }>(`/books/${contextMenuBook.value.id}/content-file`)
    const content = contentRes.data.content
    console.log('Content length:', content.length)

    // 提取markdown中的所有图片
    const localImages: string[] = []

    // 使用match直接获取所有图片URL
    const allImgMatches = content.match(/!\[([^\]]*)\]\(([^)]+)\)/g) || []
    console.log('All image matches:', allImgMatches)

    if (allImgMatches.length === 0) {
      console.log('No images found in content!')
      // 尝试其他格式
      const simpleMatches = content.match(/!\[[^\]]*\]\([^)]+\)/g) || []
      console.log('Simple image matches:', simpleMatches)
    }

    for (const match of allImgMatches) {
      const urlMatch = match.match(/!\[([^\]]*)\]\(([^)]+)\)/)
      if (urlMatch) {
        const url = urlMatch[2]
        console.log('Found image URL:', url)
        // 过滤掉http开头的远程图片，只保留本地图片
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
          localImages.push(url)
        }
      }
    }

    console.log('Local images found:', localImages)

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

      console.log('Converted URL:', url, '->', resultUrl)
      return resultUrl
    })

    console.log('Full image URLs:', mdImages.value)
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
      formData.append('file', blob, 'cover.jpg')

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
  const file = target.files?.[0]

  if (file) {
    handleFile(file)
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
}

// 确认导入
const handleImportConfirm = async () => {
  if (!selectedFile.value) {
    showNotify({ type: 'warning', message: '请先选择文件' })
    return
  }

  importing.value = true
  importCompleted.value = false
  importProgress.value = 0
  importStatus.value = '正在检查书籍...'

  // 标记是否是ZIP导入
  isZipImport.value = selectedFile.value.name.endsWith('.zip')

  try {
    // 1. 如果是ZIP文件，先检查资源完整性和重复书籍
    if (isZipImport.value) {
      importStatus.value = '正在检查ZIP文件完整性...'
      const integrityCheck = await checkZipIntegrity(selectedFile.value)

      if (!integrityCheck.is_valid) {
        // 资源不完整，询问用户是否继续
        const confirm = await showConfirmDialog({
          title: '资源不完整',
          message: `${integrityCheck.message}，继续导入可能影响使用体验，是否继续？`,
          confirmButtonText: '继续导入',
          cancelButtonText: '取消'
        }).catch(() => null)

        if (!confirm) {
          importing.value = false
          importStatus.value = ''
          return
        }
      }

      // 检查重复书籍
      importStatus.value = '正在检查重复书籍...'
      const duplicateCheck = await checkZipDuplicates(selectedFile.value)

      if (duplicateCheck.has_duplicates) {
        // 显示重复书籍对话框
        duplicateCheckResult.value = duplicateCheck
        showDuplicateDialog.value = true
        importing.value = false
        importStatus.value = ''
        return
      }
    }

    // 2. 检查书籍是否已存在
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

    // 3. 如果书籍已存在，弹出确认对话框
    if (checkData.exists) {
      console.log('Book exists, book_id:', checkData.book_id)
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

      // 4. 覆盖导入（不生成音频），传入已有书籍的book_id
      console.log('Calling doImport with book_id:', checkData.book_id)
      return await doImport(true, checkData.book_id)
    } else {
      // 5. 正常导入
      return await doImport(false)
    }
  } catch (error: any) {
    console.error('检查书籍失败:', error)
    // 尝试直接导入
    return await doImport(false)
  }
}

// 检查ZIP文件完整性
const checkZipIntegrity = async (file: File): Promise<{ is_valid: boolean; message: string }> => {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch('/api/v1/books/check-zip-integrity', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      },
      body: formData
    })

    if (!response.ok) {
      return { is_valid: true, message: '' } // 检查失败时允许继续导入
    }

    return await response.json()
  } catch (error) {
    console.error('检查ZIP完整性失败:', error)
    return { is_valid: true, message: '' } // 检查失败时允许继续导入
  }
}

// 检查ZIP文件中的重复书籍
const checkZipDuplicates = async (file: File): Promise<any> => {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch('/api/v1/books/check-zip-duplicates', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      },
      body: formData
    })

    if (!response.ok) {
      return { has_duplicates: false, duplicate_books: [], new_books: [], total_books: 0 }
    }

    return await response.json()
  } catch (error) {
    console.error('检查重复书籍失败:', error)
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
  // 不修改 selectedDuplicateBooks，保持为空以区分"覆盖全部"和"覆盖选中"
  doImportZipWithAction()
}

// 跳过重复书籍导入
const handleImportSkipDuplicates = () => {
  showDuplicateDialog.value = false
  importAction.value = 'skip'
  selectedDuplicateBooks.value = [] // 清空选中，表示跳过全部
  doImportZipWithAction()
}

// 覆盖选中的重复书籍
const handleImportSelected = () => {
  showDuplicateDialog.value = false
  importAction.value = 'selected'
  doImportZipWithAction()
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

    const response = await fetch(apiPath, {
      method: 'POST',
      body: formData,
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    if (!response.ok) {
      throw new Error('导入请求失败')
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    while (reader) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      // 解析SSE消息
      const matches = text.matchAll(/data: (\{.*?\})/g)
      for (const match of matches) {
        try {
          const data = JSON.parse(match[1])
          importProgress.value = data.percentage || 0
          importStatus.value = data.message || ''

          if (data.success === true) {
            showNotify({ type: 'success', message: data.message, duration: 1500 })
            currentBookId.value = data.book_id || ''
            // 刷新分组列表
            await loadGroups()
            // 标记导入完成
            importCompleted.value = true
          } else if (data.success === false) {
            showNotify({ type: 'danger', message: data.message })
          }
        } catch (e) {
          console.error('解析SSE数据失败:', e)
        }
      }
    }
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
      console.log('Overwrite import with existingBookId:', existingBookId)
    }

    // 添加category_id参数
    if (categoryId) {
      params.append('category_id', categoryId.toString())
    }

    if (params.toString()) {
      apiPath += `?${params.toString()}`
    }

    const response = await fetch(apiPath, {
      method: 'POST',
      body: formData,
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    })

    if (!response.ok) {
      throw new Error('导入请求失败')
    }

    const reader = response.body?.getReader()
    const decoder = new TextDecoder()

    while (reader) {
      const { done, value } = await reader.read()
      if (done) break

      const text = decoder.decode(value)
      // 解析SSE消息
      const matches = text.matchAll(/data: (\{.*?\})/g)
      for (const match of matches) {
        try {
          const data = JSON.parse(match[1])
          importProgress.value = data.percentage || 0
          importStatus.value = data.message || ''

          if (data.success === true) {
            console.log('Import success, data:', data)
            showNotify({ type: 'success', message: data.message, duration: 1500 })
            // 如果没有返回book_id，使用覆盖导入时传入的existingBookId
            if (!data.book_id && overwriteMode.value) {
              currentBookId.value = overwriteMode.value
            } else {
              currentBookId.value = data.book_id || ''
            }
            // 刷新分组列表
            await loadGroups()
            // 标记导入完成
            importCompleted.value = true
            // 只有非ZIP导入才显示编辑对话框
            if (!isZipImport.value) {
              showChoiceDialog.value = true
            }
          } else if (data.success === false) {
            showNotify({ type: 'danger', message: data.message })
          }
        } catch (e) {
          console.error('解析SSE数据失败:', e)
        }
      }
    }
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
  console.log('handleEditMD called with bookId:', bookId)
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
  importProgress.value = 0
  importStatus.value = ''
  overwriteMode.value = ''
  importing.value = false
  importCompleted.value = false
  currentBookId.value = ''
  isZipImport.value = false
  importAction.value = null
  selectedDuplicateBooks.value = []
  duplicateCheckResult.value = {
    has_duplicates: false,
    duplicate_books: [],
    new_books: [],
    total_books: 0
  }
}

// 生命周期
onMounted(async () => {
  // 初始化横屏检测
  checkOrientation()
  window.addEventListener('resize', handleResize)
  
  loadGroups()
  await loadUserSettings()
  loadDictionaryStatus()
  // 如果当前是Kokoro TTS，加载语音列表
  if (ttsServiceName.value === 'kokoro-tts') {
    await loadTtsVoices()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
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

.sort-handle {
  color: #969799;
  font-size: 18px;
  padding: 4px;
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
</style>
