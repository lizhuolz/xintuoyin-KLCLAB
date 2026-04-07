<template>
  <div class="chat-container">
    <aside class="sidebar" :class="{ collapsed: isSidebarCollapsed }">
      <div class="sidebar-header">
        <button v-if="!isSidebarCollapsed" class="new-chat-btn" @click="createNewChat">
          <span class="plus-icon">+</span> 新建对话
        </button>
        <button class="toggle-btn" @click="isSidebarCollapsed = !isSidebarCollapsed">
          <el-icon><Fold v-if="!isSidebarCollapsed" /><Expand v-else /></el-icon>
        </button>
      </div>

      <div v-if="!isSidebarCollapsed" class="sidebar-search-wrapper">
        <el-input
          v-model="sidebarSearch"
          placeholder="搜索对话记录或内容..."
          prefix-icon="Search"
          clearable
          size="small"
          @input="handleSidebarSearch"
        />
      </div>

      <div class="sidebar-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="sidebar-item"
          :class="{ active: String(currentId) === String(conv.id) }"
          @click="selectConv(conv.id)"
        >
          <el-icon class="conv-icon"><ChatDotRound /></el-icon>
          <span v-if="!isSidebarCollapsed" class="conv-title" :title="conv.title">{{ conv.title || '新对话' }}</span>
        </div>
      </div>

      <div class="sidebar-footer">
        <div v-if="!isSidebarCollapsed" class="sidebar-actions">
          <button class="manage-history-btn" @click="openHistoryManager">
            <el-icon><Setting /></el-icon> 管理对话记录
          </button>
        </div>
      </div>
    </aside>

    <main class="main-chat">
      <header class="chat-header" v-if="currentMessages.length > 0">
        <span class="current-conv-title">{{ currentConv?.title || '新对话' }}</span>
      </header>

      <div v-if="currentMessages.length === 0" class="initial-greeting">
        <div class="greeting-content">
          <h1 class="gradient-text">用户你好</h1>
          <h2 class="sub-text">需要我为你做什么</h2>
        </div>
      </div>

      <div class="messages-container" ref="scrollRef" v-show="currentMessages.length > 0">
        <div v-for="(msg, index) in currentMessages" :key="index" class="message-row" :class="msg.role">
          <div class="message-inner">
            <div class="message-avatar">
              <span v-if="msg.role === 'user'" class="user-icon">👤</span>
              <div v-else class="assistant-icon-fixed">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="url(#p1)"/></svg>
              </div>
            </div>
            <div class="message-content-wrapper">
              <div v-if="msg.role === 'assistant' && (msg.thinkingVisible || msg.thinkingText || msg.thinkingLoading || msg.thinkingError)" class="thinking-panel" :class="{ loading: msg.thinkingLoading, error: msg.thinkingError }">
                <div class="thinking-title">回答前，我做了这些准备</div>
                <div v-if="msg.thinkingLoading" class="thinking-placeholder">正在整理回答前的处理过程...</div>
                <div v-else-if="msg.thinkingText" class="thinking-body">{{ msg.thinkingText }}</div>
                <div v-else-if="msg.thinkingError" class="thinking-placeholder">这次没有成功拿到回答前说明，你可以稍后重试。</div>
              </div>

              <div class="message-content">
                <div v-if="msg.role === 'assistant'" class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                <div v-else class="user-text">{{ msg.content }}</div>
              </div>

              <div v-if="msg.role === 'user' && msg.uploadedFiles?.length" class="upload-file-list">
                <a v-for="file in msg.uploadedFiles" :key="file.url" :href="file.url" target="_blank" class="upload-file-chip">{{ file.filename }}</a>
              </div>

              <div v-if="msg.role === 'assistant' && index === currentMessages.length - 1 && msg.recommendations?.length > 0" class="recommendations-area">
                <div v-for="(rec, rIdx) in msg.recommendations" :key="rIdx" class="rec-bubble" @click="sendRecommendedMessage(rec)">{{ rec }}</div>
              </div>

              <div v-if="msg.role === 'assistant'" class="msg-footer">
                <div class="footer-info">
                  <span class="ai-tag">本回答由 AI 生成，仅供参考</span>
                  <el-button v-if="msg.sources?.length" type="primary" link size="small" @click="toggleSidebarSources(msg.sources)" class="ref-btn">
                    <el-icon><Link /></el-icon> 参考链接 ({{ msg.sources.length }})
                  </el-button>
                </div>
                <div class="footer-right">
                  <button class="icon-action" @click="copyText(msg.content)"><el-icon><DocumentCopy /></el-icon></button>
                  <button class="icon-action" :class="{ active: msg.liked }" @click="handleLike(msg)"><el-icon><CaretTop /></el-icon></button>
                  <button class="icon-action" :class="{ active: msg.disliked }" @click="handleDislike(msg)"><el-icon><CaretBottom /></el-icon></button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="loading" class="loading-row"><span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></div>
      </div>

      <footer class="chat-input-area">
        <div class="input-container-inner">
          <div class="kg-entrance-wrapper">
            <router-link to="/ai/kb" class="kg-bubble">知识库管理</router-link>
          </div>
          <div class="input-box-wrapper">
            <textarea v-model="inputMessage" @keydown.enter.exact.prevent="sendMessage" placeholder="输入消息..." ref="textareaRef"></textarea>
            <div v-if="files.length > 0" class="mini-previews">
              <div v-for="(file, index) in files" :key="`${file.name}-${index}`" class="mini-file"><span>{{ file.name }}</span><i @click="removeFile(index)">×</i></div>
            </div>
            <div class="bottom-toolbar">
              <div class="tools-left">
                <label class="tool-btn">
                  <el-icon><Paperclip /></el-icon>
                  <input type="file" multiple @change="handleFileUpload" accept=".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.xls,.xlsx,.csv" hidden />
                </label>
                <button class="tool-btn" :class="{ active: webSearchEnabled }" @click="webSearchEnabled = !webSearchEnabled"><el-icon><Search /></el-icon></button>
                <div class="pop-wrapper">
                  <button class="tool-btn" :class="{ active: !!selectedDB }" @click="showDBMenu = !showDBMenu"><el-icon><Coin /></el-icon></button>
                  <div v-if="showDBMenu" class="pop-menu">
                    <div v-for="option in dbOptions" :key="option.value" @click="toggleDbVersion(option.value)" :class="{ active: selectedDB === option.value }">{{ option.label }}</div>
                  </div>
                </div>
              </div>
              <button class="send-submit-btn" :disabled="(!inputMessage.trim() && !files.length) || loading" @click="sendMessage"><el-icon><Promotion /></el-icon></button>
            </div>
          </div>
          <div class="legal-footer">©2025-新拓银人工智能 | 渝ICP备2024037824号-1 | v1.0.0</div>
        </div>
      </footer>
    </main>

    <transition name="slide-fade">
      <aside v-if="sidebarSources.length > 0" class="sources-sidebar">
        <div class="sidebar-sources-header"><h3>参考链接</h3><button @click="sidebarSources = []" class="close-sidebar">×</button></div>
        <div class="sidebar-sources-content">
          <div v-for="(source, index) in sidebarSources" :key="index" class="source-card">
            <div class="s-num">{{ index + 1 }}</div>
            <div class="s-info">
              <h4 class="s-title">{{ source.title || '未命名来源' }}</h4>
              <p class="s-summary">{{ source.content }}</p>
              <a :href="source.link" target="_blank" class="s-link">查看原文 <el-icon><TopRight /></el-icon></a>
            </div>
          </div>
        </div>
      </aside>
    </transition>

    <el-dialog v-model="historyManagerVisible" title="管理对话记录" width="700px" custom-class="history-manager-dialog">
      <div class="history-manager-content">
        <div class="manager-header">
          <span class="count-tip">对话记录 ({{ managerList.length }}条)</span>
          <el-input
            v-model="managerSearch"
            placeholder="搜索名称或对话内容"
            prefix-icon="Search"
            class="search-input"
            clearable
            @input="handleManagerSearch"
          />
        </div>

        <el-table
          :data="managerList"
          height="400px"
          v-loading="managerLoading"
          @selection-change="handleManagerSelection"
          style="width: 100%"
        >
          <el-table-column type="selection" width="50" />
          <el-table-column label="对话名称" min-width="250">
            <template #default="scope">
              <div class="conv-name-cell">
                <el-icon class="icon"><ChatDotRound /></el-icon>
                <span>{{ scope.row.title || '新对话' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="updatedAtDisplay" label="最近通话时间" width="180" />
          <el-table-column label="操作" width="80" align="center">
            <template #default="scope">
              <el-button link type="danger" @click="handleSingleDelete(scope.row)">
                <el-icon size="16"><Delete /></el-icon>
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="manager-footer">
          <div class="left">
            <span class="hint">对话记录保存90天</span>
          </div>
          <div class="right">
            <el-button @click="historyManagerVisible = false">取消</el-button>
            <el-button type="danger" :disabled="selectedManagerIds.length === 0" @click="handleBatchDelete">
              批量删除 <span v-if="selectedManagerIds.length">({{ selectedManagerIds.length }})</span>
            </el-button>
          </div>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="feedbackVisible" title="反馈" width="650px" custom-class="dislike-feedback-dialog">
      <div class="feedback-guidelines">
        <p>1、用户可在以下表单发起投诉、举报、反馈信息。</p>
        <p>2、系统收到信息后由工作人员在2-5个工作日内处理，并对用户个人信息予以必要性的保密。</p>
        <p>3、工作人员对涉及重要事件的如BUG漏洞上报到公司高层领导，必要的上报到有关部门如国家互联网应急中心</p>
        <p>4、工作人员根据情况可能直接联系投诉举报的用户和被投诉举报者，解决问题。</p>
        <p>5、通过用户留下的手机号码、邮箱方式，最终将处理结果反馈给用户。</p>
        <p>6、若您有紧急事务，请直接联系我们：18908397188。</p>
      </div>

      <el-form :model="feedbackForm" label-position="top" class="custom-feedback-form">
        <el-form-item label="针对问题">
          <el-radio-group v-model="feedbackForm.reasons.question">
            <el-radio label="不理解问题" />
            <el-radio label="遗忘上下文" />
            <el-radio label="未遵循要求" />
          </el-radio-group>
        </el-form-item>

        <el-form-item label="针对回答效果">
          <el-radio-group v-model="feedbackForm.reasons.answer">
            <el-radio label="回答错误" />
            <el-radio label="逻辑混乱" />
            <el-radio label="时效性差" />
            <el-radio label="可读性差" />
            <el-radio label="回答不完整" />
            <el-radio label="回答笼统不专业" />
          </el-radio-group>
        </el-form-item>

        <el-form-item label="举报">
          <el-radio-group v-model="feedbackForm.reasons.report">
            <el-radio label="色情低俗" />
            <el-radio label="政治敏感" />
            <el-radio label="违法犯罪" />
            <el-radio label="歧视或偏见回答" />
            <el-radio label="侵犯隐私" />
            <el-radio label="内容侵权" />
          </el-radio-group>
        </el-form-item>

        <el-form-item label="更多描述">
          <el-input type="textarea" v-model="feedbackForm.comment" rows="3" placeholder="请输入" />
        </el-form-item>

        <el-form-item label="上传照片" class="upload-item">
          <el-upload
            action="#"
            list-type="picture-card"
            :auto-upload="false"
            multiple
            :limit="4"
            :on-change="handleFeedbackFile"
            :on-remove="handleFeedbackRemove"
            class="custom-uploader"
          >
            <div class="upload-trigger">
              <el-icon><Plus /></el-icon>
              <div class="text">上传照片</div>
              <div class="count">{{ feedbackFiles.length }}/4</div>
            </div>
          </el-upload>
          <div class="upload-tip">只支持.jpg.png格式</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="feedback-footer">
          <el-button @click="feedbackVisible = false" class="footer-btn">取消</el-button>
          <el-button type="primary" @click="submitFeedback" class="footer-btn submit-btn">提交</el-button>
        </div>
      </template>
    </el-dialog>

    <svg style="width:0;height:0;position:absolute"><defs><linearGradient id="p1" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#4E86F8"/><stop offset="100%" stop-color="#D6409F"/></linearGradient></defs></svg>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { Link, DocumentCopy, CaretTop, CaretBottom, Search, Paperclip, Coin, Promotion, TopRight, Fold, Expand, ChatDotRound, Delete, Plus, Setting } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiApi, flattenHistoryMessages, formatTimestamp } from '@/api/ai'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: (source, lang) => {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(source, { language: lang }).value
      } catch (error) {
        return md.utils.escapeHtml(source)
      }
    }
    return md.utils.escapeHtml(source)
  },
})
const renderMarkdown = (text) => md.render(text || '')

const conversations = ref([])
const currentId = ref(null)
const inputMessage = ref('')
const files = ref([])
const loading = ref(false)
const webSearchEnabled = ref(false)
const showDBMenu = ref(false)
const selectedDB = ref(null)
const dbOptions = ref([
  { label: '数据库1', value: '1' },
  { label: '数据库2', value: '2' },
])
const userIdentity = ref('guest')
const sidebarSources = ref([])
const scrollRef = ref(null)
const textareaRef = ref(null)
const isSidebarCollapsed = ref(false)

const currentConv = computed(() => conversations.value.find((item) => String(item.id) === String(currentId.value)))
const currentMessages = computed(() => currentConv.value?.messages || [])

function debounce(fn, delay) {
  let timer = null
  return function debounced(...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn.apply(this, args), delay)
  }
}

function createLocalConversation(id, title = '新对话') {
  return {
    id: String(id),
    title,
    updatedAt: '',
    loaded: false,
    messages: [],
  }
}

function mergeConversationList(serverList) {
  const localMap = new Map(conversations.value.map((item) => [String(item.id), item]))
  return serverList.map((item) => {
    const id = String(item.conversation_id)
    const existing = localMap.get(id)
    return {
      id,
      title: item.title || existing?.title || '新对话',
      updatedAt: item.updatedAt || item.updated_at || existing?.updatedAt || '',
      loaded: existing?.loaded || false,
      messages: existing?.messages || [],
      user: item.user || existing?.user || {},
    }
  })
}

async function fetchConversations(query = '') {
  try {
    const data = await aiApi.listHistories({ search: query })
    conversations.value = mergeConversationList(data.list || [])
    if (currentId.value && !conversations.value.some((item) => String(item.id) === String(currentId.value))) {
      currentId.value = conversations.value[0]?.id || null
    }
  } catch (error) {
    conversations.value = conversations.value.filter((item) => item.messages.length)
  }
}

function moveConversationToTop(conversation) {
  conversations.value = [conversation, ...conversations.value.filter((item) => String(item.id) !== String(conversation.id))]
}

const sidebarSearch = ref('')
const handleSidebarSearch = debounce(async () => {
  await fetchConversations(sidebarSearch.value)
}, 300)

const historyManagerVisible = ref(false)
const managerList = ref([])
const managerSearch = ref('')
const selectedManagerIds = ref([])
const managerLoading = ref(false)

async function refreshManagerList(query = '') {
  managerLoading.value = true
  try {
    const data = await aiApi.listHistories({ search: query })
    managerList.value = (data.list || []).map((item) => ({
      ...item,
      id: String(item.conversation_id),
      updatedAtDisplay: item.updatedAt || formatTimestamp(item.updated_at),
    }))
  } finally {
    managerLoading.value = false
  }
}

async function openHistoryManager() {
  historyManagerVisible.value = true
  managerSearch.value = ''
  selectedManagerIds.value = []
  await refreshManagerList()
}

const handleManagerSearch = debounce(async () => {
  await refreshManagerList(managerSearch.value)
}, 300)

function handleManagerSelection(selection) {
  selectedManagerIds.value = selection.map((item) => item.id)
}

async function replaceCurrentConversationAfterDeletion(deletedId) {
  if (String(currentId.value) !== String(deletedId)) return
  if (conversations.value.length > 0) {
    await selectConv(conversations.value[0].id)
  } else {
    await createNewChat()
  }
}

async function handleSingleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除对话“${row.title || '新对话'}”吗？删除后无法恢复并找回。`, '确认删除', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'danger-btn',
      type: 'warning',
    })
    await aiApi.deleteConversation(row.id)
    conversations.value = conversations.value.filter((item) => String(item.id) !== String(row.id))
    await replaceCurrentConversationAfterDeletion(row.id)
    await refreshManagerList(managerSearch.value)
    ElMessage.success('已删除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

async function handleBatchDelete() {
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selectedManagerIds.value.length} 条记录吗？删除后对话记录无法恢复并找回。`, '确认删除', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'danger-btn',
      type: 'warning',
    })
    const deletedIds = [...selectedManagerIds.value]
    await aiApi.batchDeleteHistories(deletedIds)
    conversations.value = conversations.value.filter((item) => !deletedIds.includes(String(item.id)))
    if (deletedIds.includes(String(currentId.value))) {
      await replaceCurrentConversationAfterDeletion(currentId.value)
    }
    selectedManagerIds.value = []
    await refreshManagerList(managerSearch.value)
    ElMessage.success('批量删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量删除失败')
    }
  }
}

const feedbackVisible = ref(false)
const currentFeedbackMsgIndex = ref(-1)
const feedbackForm = reactive({
  reasons: { question: '', answer: '', report: '' },
  comment: '',
})
const feedbackFiles = ref([])

function resetFeedbackForm() {
  feedbackForm.reasons = { question: '', answer: '', report: '' }
  feedbackForm.comment = ''
  feedbackFiles.value = []
}

function updateAssistantFeedback(messageIndex, feedbackState) {
  const message = currentMessages.value.find((item) => item.role === 'assistant' && item.messageIndex === messageIndex)
  if (!message) return
  message.feedback = feedbackState ?? null
  message.liked = feedbackState === 'like'
  message.disliked = feedbackState === 'dislike'
}

async function submitFeedbackState(messageIndex, type, extraFormData = null) {
  const formData = extraFormData || new FormData()
  formData.append('conversation_id', String(currentId.value))
  formData.append('message_index', String(messageIndex))
  formData.append('type', type)
  return aiApi.submitChatFeedback(formData)
}

const handleLike = async (msg) => {
  try {
    const result = await submitFeedbackState(msg.messageIndex, 'like')
    updateAssistantFeedback(msg.messageIndex, result.state)
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  }
}

const handleDislike = async (msg) => {
  if (msg.disliked) {
    try {
      const result = await submitFeedbackState(msg.messageIndex, 'dislike')
      updateAssistantFeedback(msg.messageIndex, result.state)
    } catch (error) {
      ElMessage.error(error.message || '操作失败')
    }
    return
  }
  currentFeedbackMsgIndex.value = msg.messageIndex
  resetFeedbackForm()
  feedbackVisible.value = true
}

function handleFeedbackFile(file, fileList) {
  feedbackFiles.value = fileList.map((item) => item.raw).filter(Boolean).slice(0, 4)
  return false
}

function handleFeedbackRemove(uploadFile, fileList) {
  feedbackFiles.value = fileList.map((item) => item.raw).filter(Boolean)
}

async function submitFeedback() {
  const hasReason = Object.values(feedbackForm.reasons).some((value) => Boolean(value))
  if (!hasReason && !feedbackForm.comment.trim() && feedbackFiles.value.length === 0) {
    ElMessage.warning('请至少选择一个原因或填写文字描述')
    return
  }

  const formData = new FormData()
  formData.append('reasons', JSON.stringify(feedbackForm.reasons))
  formData.append('comment', feedbackForm.comment)
  feedbackFiles.value.forEach((file) => formData.append('files', file))

  try {
    const result = await submitFeedbackState(currentFeedbackMsgIndex.value, 'dislike', formData)
    updateAssistantFeedback(currentFeedbackMsgIndex.value, result.state)
    feedbackVisible.value = false
    ElMessage.success('感谢您的反馈！')
  } catch (error) {
    ElMessage.error(error.message || '提交失败')
  }
}

function toggleSidebarSources(sources) {
  sidebarSources.value = sidebarSources.value === sources ? [] : sources
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

async function fetchThinkingText(conversationId, messageIndex, onChunk) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    try {
      return await aiApi.getChatThinkingStream(conversationId, messageIndex, (_chunk, fullText) => {
        onChunk?.(fullText)
      })
    } catch (error) {
      if (!/获取思考过程失败|请求失败|not found/i.test(error.message || '') || attempt === 4) {
        throw error
      }
      await new Promise((resolve) => setTimeout(resolve, 300 * (attempt + 1)))
    }
  }
  return ''
}

async function selectConv(id) {
  currentId.value = String(id)
  sidebarSources.value = []
  const conversation = conversations.value.find((item) => String(item.id) === String(id))
  if (!conversation || conversation.loaded) {
    nextTick(scrollToBottom)
    return
  }
  try {
    const detail = await aiApi.getHistoryDetail(id)
    conversation.messages = flattenHistoryMessages(detail)
    conversation.loaded = true
    conversation.title = detail.title || conversation.title
    conversation.updatedAt = detail.updatedAt || detail.updated_at || conversation.updatedAt
  } catch (error) {
    conversation.messages = []
    conversation.loaded = true
  }
  nextTick(scrollToBottom)
}

async function createNewChat() {
  try {
    const data = await aiApi.createChatSession()
    const conversation = createLocalConversation(data.conversation_id)
    conversations.value.unshift(conversation)
    currentId.value = conversation.id
  } catch (error) {
    const fallback = createLocalConversation(Date.now())
    conversations.value.unshift(fallback)
    currentId.value = fallback.id
    ElMessage.warning(error.message || '新建对话失败，已创建本地草稿')
  }
}

function handleFileUpload(event) {
  const allowed = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'txt', 'md', 'xls', 'xlsx', 'csv']
  const selected = Array.from(event.target.files || [])
  const accepted = selected.filter((file) => allowed.includes(file.name.split('.').pop()?.toLowerCase()))
  if (accepted.length < selected.length) {
    ElMessage.warning('部分文件格式不支持')
  }
  files.value = [...files.value, ...accepted]
  event.target.value = ''
}

function removeFile(index) {
  files.value.splice(index, 1)
}

function scrollToBottom() {
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}

function sendRecommendedMessage(text) {
  inputMessage.value = text
  sendMessage()
}

function toggleDbVersion(version) {
  selectedDB.value = selectedDB.value === version ? null : version
  showDBMenu.value = false
}

async function loadDbOptions() {
  try {
    const data = await aiApi.getDbOptions()
    if (Array.isArray(data.options) && data.options.length) {
      dbOptions.value = data.options
    }
  } catch (error) {
    dbOptions.value = [
      { label: '数据库1', value: '1' },
      { label: '数据库2', value: '2' },
    ]
  }
}

async function ensureCurrentConversation() {
  if (currentConv.value) return currentConv.value
  if (!conversations.value.length) {
    await createNewChat()
  }
  return currentConv.value
}

async function sendMessage() {
  if ((!inputMessage.value.trim() && !files.value.length) || loading.value) return
  const conversation = await ensureCurrentConversation()
  if (!conversation) return

  const text = inputMessage.value.trim()
  const pendingFiles = [...files.value]
  inputMessage.value = ''
  files.value = []

  const userMessage = reactive({
    role: 'user',
    content: text,
    files: pendingFiles.map((file) => file.name),
    uploadedFiles: [],
    messageIndex: null,
  })
  const assistantMessage = reactive({
    role: 'assistant',
    content: '',
    sources: [],
    recommendations: [],
    thinkingText: '',
    thinkingVisible: true,
    thinkingLoading: true,
    thinkingError: false,
    liked: false,
    disliked: false,
    feedback: null,
    messageIndex: null,
  })

  conversation.messages.push(userMessage, assistantMessage)
  conversation.loaded = true
  if (!conversation.title || conversation.title === '新对话') {
    conversation.title = text.slice(0, 20) || '新对话'
  }
  moveConversationToTop(conversation)

  loading.value = true
  nextTick(scrollToBottom)

  const formData = new FormData()
  formData.append('message', text)
  formData.append('conversation_id', String(conversation.id))
  formData.append('web_search', String(webSearchEnabled.value))
  formData.append('user_identity', userIdentity.value)
  if (selectedDB.value) {
    formData.append('db_version', selectedDB.value)
  }
  pendingFiles.forEach((file) => formData.append('files', file))

  try {
    const data = await aiApi.sendChatStream(formData, (event) => {
      if (!event || typeof event !== 'object') return
      if (event.type === 'thinking_delta') {
        assistantMessage.thinkingText += event.delta || ''
        assistantMessage.thinkingVisible = Boolean(assistantMessage.thinkingText)
        assistantMessage.thinkingLoading = false
        assistantMessage.thinkingError = false
        nextTick(scrollToBottom)
        return
      }
      if (event.type === 'answer_delta') {
        assistantMessage.content += event.delta || ''
        nextTick(scrollToBottom)
        return
      }
      if (event.type === 'answer_replace') {
        assistantMessage.content = event.content || ''
        nextTick(scrollToBottom)
      }
    })

    assistantMessage.content = data.answer || assistantMessage.content || ''
    assistantMessage.sources = data.resource || []
    assistantMessage.recommendations = data.recommend_answer || []
    assistantMessage.liked = data.feedback === 'like'
    assistantMessage.disliked = data.feedback === 'dislike'
    assistantMessage.feedback = data.feedback ?? null
    assistantMessage.messageIndex = data.message_index

    userMessage.messageIndex = data.message_index
    userMessage.uploadedFiles = data.uploaded_files || []
    userMessage.files = data.files || userMessage.files

    conversation.updatedAt = data.updatedAt || data.updated_at || Date.now()
    moveConversationToTop(conversation)
    assistantMessage.thinkingLoading = false
    assistantMessage.thinkingError = false
    assistantMessage.thinkingVisible = Boolean(assistantMessage.thinkingText)
  } catch (error) {
    assistantMessage.content = `
**连接错误**
${error.message || '请求失败'}`
    assistantMessage.thinkingLoading = false
    assistantMessage.thinkingError = true
  } finally {
    loading.value = false
    nextTick(scrollToBottom)
  }
}

onMounted(async () => {
  await loadDbOptions()
  await fetchConversations()
  if (!conversations.value.length) {
    await createNewChat()
  } else {
    await selectConv(conversations.value[0].id)
  }
})

watch(currentMessages, () => nextTick(scrollToBottom), { deep: true })
</script>

<style scoped lang="less">
.chat-container { display: flex; height: 100%; background: #fff; overflow: hidden; }
.sidebar { width: 260px; background: #f9f9f9; display: flex; flex-direction: column; border-right: 1px solid #eee; padding: 12px; transition: width 0.3s; }
.sidebar.collapsed { width: 64px; padding: 12px 8px; }
.sidebar-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.collapsed .sidebar-header { justify-content: center; }
.new-chat-btn { background: #eee; border: none; padding: 10px; border-radius: 20px; cursor: pointer; flex: 1; margin-right: 8px; font-weight: 500; white-space: nowrap; overflow: hidden; }
.toggle-btn { background: none; border: none; cursor: pointer; color: #666; font-size: 18px; display: flex; }

.sidebar-search-wrapper { margin-bottom: 12px; }

.sidebar-list { flex: 1; overflow-y: auto; }
.sidebar-item { padding: 10px 12px; border-radius: 12px; cursor: pointer; display: flex; align-items: center; gap: 12px; margin-bottom: 4px; transition: 0.2s; position: relative; }
.sidebar-item.active { background: #e6f0ff; color: #4080FF; }
.conv-title { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 14px; }
.collapsed .sidebar-item { justify-content: center; padding: 10px 0; }

.sidebar-footer { margin-top: auto; }
.sidebar-actions { padding: 10px 0; }
.manage-history-btn { width: 100%; text-align: left; background: none; border: none; padding: 10px 12px; font-size: 14px; color: #666; cursor: pointer; border-radius: 8px; transition: 0.2s; display: flex; align-items: center; gap: 8px; }
.manage-history-btn:hover { background: #eee; color: #333; }

.main-chat { flex: 1; display: flex; flex-direction: column; position: relative; min-width: 0; }
.chat-header { height: 50px; display: flex; align-items: center; justify-content: center; border-bottom: 1px solid #f0f0f0; font-size: 14px; color: #666; }
.initial-greeting { flex: 1; display: flex; align-items: center; justify-content: center; }
.greeting-content { width: 100%; max-width: 600px; padding: 0 20px; }
.gradient-text { font-size: 48px; background: linear-gradient(90deg, #4285F4, #9B72CB, #D96570); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
.sub-text { font-size: 36px; color: #eee; margin: 0; }
.messages-container { flex: 1; overflow-y: auto; padding: 20px 0; }
.message-inner { max-width: 850px; margin: 0 auto; display: flex; gap: 16px; padding: 12px 24px; }
.assistant-icon-fixed { width: 28px; height: 28px; animation: rotate 10s linear infinite; }
@keyframes rotate { from {transform: rotate(0deg)} to {transform: rotate(360deg)} }
.message-content-wrapper { flex: 1; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.thinking-panel { background: linear-gradient(180deg, #f7fbf2 0%, #eef8e3 100%); border: 1px solid #bddb9c; border-left: 4px solid #78a942; border-radius: 16px; padding: 14px 16px; box-shadow: 0 8px 20px rgba(120, 169, 66, 0.10); }
.thinking-panel.loading { border-left-color: #d6a33f; background: linear-gradient(180deg, #fff9ef 0%, #fff3d9 100%); border-color: #edd39d; box-shadow: 0 8px 20px rgba(214, 163, 63, 0.10); }
.thinking-panel.error { border-left-color: #d46a6a; background: linear-gradient(180deg, #fff6f6 0%, #ffeaea 100%); border-color: #efc2c2; box-shadow: 0 8px 20px rgba(212, 106, 106, 0.08); }
.thinking-title { font-size: 13px; font-weight: 700; color: #36511d; margin-bottom: 8px; }
.thinking-body { font-size: 13px; line-height: 1.8; color: #425466; white-space: pre-wrap; word-break: break-word; }
.thinking-placeholder { font-size: 13px; line-height: 1.7; color: #7a6b3c; }
.thinking-panel.error .thinking-title { color: #8f3f3f; }
.thinking-panel.error .thinking-placeholder { color: #8f5b5b; }
.message-content { font-size: 16px; line-height: 1.7; color: #1f1f1f; }
.assistant .message-content { background: #f8faff; padding: 16px 20px; border-radius: 4px 20px 20px 20px; border: 1px solid #eef2ff; }
.user .message-content { background: #f4f4f4; padding: 12px 18px; border-radius: 20px 4px 20px 20px; align-self: flex-end; }
.upload-file-list { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.upload-file-chip { display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 999px; background: #f3f6fb; color: #47607a; font-size: 12px; text-decoration: none; }
.recommendations-area { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.rec-bubble { background: #fff; border: 1px solid #e0e0e0; padding: 6px 14px; border-radius: 18px; font-size: 13px; color: #666; cursor: pointer; transition: 0.2s; }
.rec-bubble:hover { border-color: #4080FF; color: #4080FF; background: #f0f7ff; }
.msg-footer { display: flex; justify-content: space-between; align-items: center; padding: 0 4px; }
.ai-tag { font-size: 11px; color: #bbb; }
.footer-info { display: flex; align-items: center; gap: 10px; }
.footer-right { display: flex; align-items: center; gap: 8px; }
.icon-action { border: none; background: transparent; cursor: pointer; color: #97a3b6; width: 32px; height: 32px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; }
.icon-action:hover { background: #eef4ff; color: #356dd9; }
.icon-action.active { background: #e7f0ff; color: #2f6de6; }
.loading-row { display: flex; justify-content: center; padding: 24px; font-size: 28px; color: #a0abc0; letter-spacing: 6px; }
.chat-input-area { padding: 18px 24px 24px; border-top: 1px solid #f2f4f7; }
.input-container-inner { max-width: 960px; margin: 0 auto; }
.kg-entrance-wrapper { margin-bottom: 10px; }
.kg-bubble { display: inline-flex; align-items: center; padding: 8px 14px; border-radius: 999px; background: linear-gradient(135deg, #edf3ff 0%, #f8f2ff 100%); color: #335ea8; text-decoration: none; font-size: 13px; }
.input-box-wrapper { border: 1px solid #dfe6f0; border-radius: 22px; padding: 14px 16px 12px; box-shadow: 0 12px 24px rgba(20, 40, 80, 0.06); }
textarea { width: 100%; min-height: 90px; resize: none; border: none; outline: none; font-size: 15px; line-height: 1.7; font-family: inherit; }
.mini-previews { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.mini-file { display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 999px; background: #f4f6fa; color: #50627a; font-size: 12px; }
.mini-file i { font-style: normal; cursor: pointer; color: #8b98aa; }
.bottom-toolbar { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
.tools-left { display: flex; align-items: center; gap: 8px; }
.tool-btn { width: 38px; height: 38px; border-radius: 50%; border: none; background: #f5f7fb; color: #73829b; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; position: relative; }
.tool-btn.active { background: #e6f0ff; color: #2f6de6; }
.pop-wrapper { position: relative; }
.pop-menu { position: absolute; bottom: 48px; left: 0; min-width: 120px; background: #fff; border: 1px solid #e5e9f2; border-radius: 12px; box-shadow: 0 18px 32px rgba(22, 39, 77, 0.12); overflow: hidden; }
.pop-menu > div { padding: 10px 14px; cursor: pointer; font-size: 13px; color: #516179; }
.pop-menu > div:hover, .pop-menu > div.active { background: #eef4ff; color: #2f6de6; }
.menu-divider { height: 1px; padding: 0 !important; background: #eef1f6; cursor: default !important; }
.send-submit-btn { width: 46px; height: 46px; border-radius: 50%; border: none; background: linear-gradient(135deg, #3575f6 0%, #56a4ff 100%); color: #fff; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 10px 18px rgba(53, 117, 246, 0.25); }
.send-submit-btn:disabled { background: #d8deea; box-shadow: none; cursor: not-allowed; }
.legal-footer { margin-top: 12px; text-align: center; font-size: 12px; color: #a0abc0; }
.db-selector-toolbar { display: flex; gap: 12px; }
.db-selector-summary { margin-top: 12px; color: #516179; font-size: 13px; }
.db-column-comments { white-space: pre-wrap; line-height: 1.6; color: #516179; }
.sources-sidebar { width: 340px; border-left: 1px solid #eef1f6; background: #fbfcfe; display: flex; flex-direction: column; }
.sidebar-sources-header { padding: 18px 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #eef1f6; }
.close-sidebar { border: none; background: transparent; font-size: 24px; color: #93a0b3; cursor: pointer; }
.sidebar-sources-content { padding: 18px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
.source-card { display: flex; gap: 12px; padding: 14px; background: #fff; border: 1px solid #eef2f7; border-radius: 16px; }
.s-num { width: 28px; height: 28px; border-radius: 50%; background: #eef4ff; color: #2f6de6; display: flex; align-items: center; justify-content: center; font-size: 13px; font-weight: 700; flex-shrink: 0; }
.s-info { min-width: 0; }
.s-title { margin: 0 0 6px; font-size: 14px; color: #21314d; }
.s-summary { margin: 0 0 10px; font-size: 13px; line-height: 1.6; color: #617089; }
.s-link { display: inline-flex; align-items: center; gap: 4px; color: #2f6de6; text-decoration: none; font-size: 13px; }
@media (max-width: 960px) {
  .chat-container { flex-direction: column; }
  .sidebar { width: 100%; border-right: none; border-bottom: 1px solid #eee; }
  .sidebar.collapsed { width: 100%; }
  .sources-sidebar { width: 100%; border-left: none; border-top: 1px solid #eef1f6; }
  .message-inner { padding: 12px 16px; }
  .chat-input-area { padding: 16px; }
}
</style>
