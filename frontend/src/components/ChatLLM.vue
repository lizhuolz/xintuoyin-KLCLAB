<template>
  <div class="chat-shell">
    <aside class="sidebar">
      <div class="sidebar-header">
        <button class="new-chat-btn" @click="createNewChat">
          <span class="plus-icon">+</span>
          <span>新建对话</span>
        </button>
      </div>

      <div class="sidebar-list">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="sidebar-item"
          :class="{ active: currentId === conv.id }"
          @click="selectConv(conv.id)"
        >
          <span class="conv-title">{{ conv.title || '新对话' }}</span>
          <button class="delete-btn" @click.stop="deleteConv(conv.id)">删</button>
        </div>
      </div>

      <div class="sidebar-footer">
        <div class="user-card">
          <div class="avatar">{{ userIdentity.charAt(0).toUpperCase() }}</div>
          <div class="user-meta">
            <div class="user-name">{{ userIdentity }}</div>
            <div class="user-role">{{ getRoleName(userIdentity) }}</div>
          </div>
        </div>
        <el-select v-model="userIdentity" size="small" class="identity-selector">
          <el-option label="超级管理员" value="admin" />
          <el-option label="技术部主管" value="dept_a_manager" />
          <el-option label="财务部主管" value="dept_b_manager" />
          <el-option label="技术员 A1" value="user_a1" />
          <el-option label="技术员 A2" value="user_a2" />
          <el-option label="会计师 B1" value="user_b1" />
          <el-option label="访客" value="guest" />
        </el-select>
      </div>
    </aside>

    <main class="main-chat" :class="{ 'initial-view': currentMessages.length === 0 }">
      <header class="chat-header" v-if="currentMessages.length > 0">
        <div class="chat-title">{{ currentConv?.title || '新对话' }}</div>
        <div class="chat-tools">
          <span class="status-pill" :class="{ active: webSearchEnabled }">联网 {{ webSearchEnabled ? '开启' : '关闭' }}</span>
          <span class="status-pill" :class="{ active: !!selectedDB }">数据库 {{ selectedDB || '未选' }}</span>
        </div>
      </header>

      <div v-if="currentMessages.length === 0" class="initial-greeting">
        <h1>需要我为你做什么</h1>
        <p>现在会同时展示主回答、工具调用过程和网页搜索结果。</p>
      </div>

      <div class="messages-container" ref="scrollRef" v-show="currentMessages.length > 0">
        <div
          v-for="msg in currentMessages"
          :key="msg.id"
          class="message-row"
          :class="msg.role"
        >
          <div class="message-inner">
            <div class="message-avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
            <div class="message-body">
              <div v-if="msg.role === 'assistant'" class="assistant-toolbar">
                <button
                  class="ghost-btn"
                  :class="{ active: selectedTraceMessageId === msg.id }"
                  @click="selectTraceMessage(msg.id)"
                >
                  过程
                </button>
                <button
                  class="ghost-btn"
                  :disabled="!msg.searchResults?.length"
                  @click="openSearchDialog(msg)"
                >
                  网页搜索
                </button>
                <span v-if="msg.traceLoading" class="minor-status">过程加载中</span>
                <span v-else-if="msg.traceEvents?.length" class="minor-status">{{ msg.traceEvents.length }} 个事件</span>
              </div>

              <div v-if="msg.role === 'assistant'" class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
              <div v-else class="user-text">{{ msg.content }}</div>

              <div v-if="msg.files?.length" class="message-files">
                <span v-for="file in msg.files" :key="file" class="file-tag">{{ file }}</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="loading" class="message-row assistant">
          <div class="message-inner">
            <div class="message-avatar">AI</div>
            <div class="message-body loading-box">模型正在输出中...</div>
          </div>
        </div>
      </div>

      <footer class="chat-footer">
        <div class="input-wrapper">
          <textarea
            ref="textareaRef"
            v-model="inputMessage"
            rows="1"
            placeholder="输入消息..."
            @keydown.enter.exact.prevent="sendMessage"
            @input="resizeTextarea"
          />

          <div v-if="files.length > 0" class="file-preview-area">
            <div v-for="(file, idx) in files" :key="`${file.name}-${idx}`" class="file-preview-item">
              <span>{{ file.name }}</span>
              <button class="remove-file" @click="removeFile(idx)">×</button>
            </div>
          </div>

          <div class="action-bar">
            <div class="left-tools">
              <label class="tool-btn">
                <input type="file" multiple style="display:none" @change="handleFileUpload" />
                <span>附件</span>
              </label>
              <button class="tool-btn" :class="{ active: webSearchEnabled }" @click="toggleWebSearch">联网</button>
              <div class="db-wrapper">
                <button class="tool-btn" :class="{ active: !!selectedDB }" @click="toggleDBMenu">数据库</button>
                <div v-if="showDBMenu" class="db-menu">
                  <div class="db-item" :class="{ active: selectedDB === 'V0' }" @click="selectDB('V0')">数据库 V0</div>
                  <div class="db-item" :class="{ active: selectedDB === 'V1' }" @click="selectDB('V1')">数据库 V1</div>
                </div>
              </div>
            </div>
            <button class="send-btn" :disabled="sendDisabled" @click="sendMessage">发送</button>
          </div>
        </div>
      </footer>
    </main>

    <aside class="trace-panel">
      <div class="trace-header">
        <div>
          <div class="trace-title">模型过程</div>
          <div class="trace-subtitle">展示工具调用、SQL、搜索和回答增量</div>
        </div>
      </div>

      <div v-if="!selectedTraceMessage" class="trace-empty">
        发送一条消息后，点击回答上的“过程”查看详情。
      </div>

      <div v-else class="trace-content">
        <div class="trace-summary">
          <div>最终回答长度: {{ selectedTraceMessage.content?.length || 0 }}</div>
          <div>搜索结果数: {{ selectedTraceMessage.searchResults?.length || 0 }}</div>
        </div>

        <div v-if="selectedTraceMessage.traceLoading" class="trace-loading">正在拉取模型过程...</div>

        <div v-else-if="!selectedTraceMessage.traceEvents?.length" class="trace-empty">
          暂无过程数据。
        </div>

        <div v-else class="trace-list">
          <div v-for="(event, idx) in selectedTraceMessage.traceEvents" :key="`${event.type}-${idx}`" class="trace-item">
            <div class="trace-type">{{ event.type }}</div>
            <div class="trace-meta">节点: {{ event.node || '-' }}</div>
            <div v-if="event.tool_name" class="trace-meta">工具: {{ event.tool_name }}</div>
            <pre v-if="event.arguments" class="trace-code">{{ formatJson(event.arguments) }}</pre>
            <pre v-else-if="event.preview" class="trace-code">{{ event.preview }}</pre>
            <div v-else-if="event.delta" class="trace-delta">{{ event.delta }}</div>
            <div v-else-if="event.count !== undefined" class="trace-meta">结果数: {{ event.count }}</div>
          </div>
        </div>
      </div>
    </aside>

    <el-dialog v-model="searchDialogVisible" title="网页搜索结果" width="860px" top="5vh">
      <div v-if="!activeSearchResults.length" class="search-empty">当前回答没有网页搜索结果。</div>
      <div v-else class="search-result-list">
        <div v-for="(item, idx) in activeSearchResults" :key="`${item.url}-${idx}`" class="search-card">
          <div class="search-card-head">
            <div>
              <div class="search-main-title">{{ item.main_title || '无标题' }}</div>
              <div class="search-sub-title">{{ item.sub_title || '无副标题' }}</div>
            </div>
            <a :href="item.url" target="_blank" rel="noreferrer">打开原文</a>
          </div>
          <div class="search-summary">{{ item.summary || '无摘要' }}</div>
          <details class="search-details">
            <summary>查看抓取原文</summary>
            <pre>{{ item.raw_content || '无原文内容' }}</pre>
          </details>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { ElMessage } from 'element-plus'
import 'highlight.js/styles/github.css'

const backendPort = import.meta.env.VITE_BACKEND_PORT || '8069'
const backendBaseUrl = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.DEV ? `http://${window.location.hostname}:${backendPort}` : '')

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang, ignoreIllegals: true }).value}</code></pre>`
      } catch (_) {}
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  }
})

function renderMarkdown(text) {
  return md.render(text || '')
}

function buildApiUrl(path) {
  return backendBaseUrl ? `${backendBaseUrl}${path}` : path
}

async function parseJsonResponse(response) {
  const text = await response.text()
  let payload = null
  try {
    payload = text ? JSON.parse(text) : null
  } catch (_) {
    payload = null
  }
  return { text, payload }
}

function getErrorMessage(response, payload, fallbackText, defaultMessage) {
  if (payload?.message) return payload.message
  if (fallbackText) return fallbackText
  return `${defaultMessage}: ${response.status}`
}

function createMessage(role, content = '', extra = {}) {
  return {
    id: `${role}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    role,
    content,
    files: [],
    traceEvents: [],
    traceLoading: false,
    searchResults: [],
    searchLoading: false,
    ...extra
  }
}

const conversations = ref([])
const currentId = ref(null)
const inputMessage = ref('')
const files = ref([])
const loading = ref(false)
const scrollRef = ref(null)
const textareaRef = ref(null)
const webSearchEnabled = ref(false)
const showDBMenu = ref(false)
const selectedDB = ref(null)
const userIdentity = ref('admin')
const searchDialogVisible = ref(false)
const activeSearchResults = ref([])
const selectedTraceMessageId = ref(null)

const currentConv = computed(() => conversations.value.find((item) => item.id === currentId.value))
const currentMessages = computed(() => currentConv.value?.messages || [])
const selectedTraceMessage = computed(() => {
  if (!selectedTraceMessageId.value) return null
  return currentMessages.value.find((item) => item.id === selectedTraceMessageId.value) || null
})
const sendDisabled = computed(() => (!inputMessage.value.trim() && files.value.length === 0) || loading.value)

function getRoleName(id) {
  const roles = {
    admin: '系统管理员',
    dept_a_manager: '技术部主管',
    dept_b_manager: '财务部主管',
    user_a1: '高级工程师 (A1)',
    user_a2: '初级技术员 (A2)',
    user_b1: '财务会计 (B1)',
    guest: '访客'
  }
  return roles[id] || '普通用户'
}

function formatJson(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch (_) {
    return String(value)
  }
}

function saveHistory() {
  localStorage.setItem('chatgpt_convs_v2', JSON.stringify(conversations.value))
}

function scrollToBottom() {
  nextTick(() => {
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  })
}

function resizeTextarea() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 200)}px`
}

watch(inputMessage, resizeTextarea)

onMounted(() => {
  const saved = localStorage.getItem('chatgpt_convs_v2') || localStorage.getItem('chatgpt_convs')
  if (saved) {
    try {
      conversations.value = JSON.parse(saved).map(normalizeConversation)
    } catch (_) {
      conversations.value = []
    }
  }
  if (!conversations.value.length) {
    createNewChat()
  } else {
    currentId.value = conversations.value[0].id
  }
  scrollToBottom()
})

function createNewChat() {
  const chat = {
    id: String(Date.now()),
    title: '新对话',
    updatedAt: Date.now(),
    messages: []
  }
  conversations.value.unshift(chat)
  currentId.value = chat.id
  selectedTraceMessageId.value = null
  saveHistory()
}

function selectConv(id) {
  currentId.value = id
  const firstAssistant = currentMessages.value.find((item) => item.role === 'assistant')
  selectedTraceMessageId.value = firstAssistant?.id || null
  scrollToBottom()
}

function selectTraceMessage(id) {
  selectedTraceMessageId.value = id
}

function deleteConv(id) {
  if (!window.confirm('确定要删除这个对话吗？')) return
  const index = conversations.value.findIndex((item) => item.id === id)
  if (index === -1) return
  conversations.value.splice(index, 1)
  if (!conversations.value.length) {
    createNewChat()
  } else if (currentId.value === id) {
    currentId.value = conversations.value[0].id
  }
  saveHistory()
  fetch(buildApiUrl(`/api/chat/${id}`), { method: 'DELETE' }).catch(() => {})
}

function handleFileUpload(event) {
  const nextFiles = Array.from(event.target.files || [])
  files.value = [...files.value, ...nextFiles]
  event.target.value = ''
}

function removeFile(index) {
  files.value.splice(index, 1)
}

function toggleWebSearch() {
  webSearchEnabled.value = !webSearchEnabled.value
}

function toggleDBMenu() {
  showDBMenu.value = !showDBMenu.value
}

function selectDB(val) {
  selectedDB.value = selectedDB.value === val ? null : val
  showDBMenu.value = false
}

function openSearchDialog(message) {
  activeSearchResults.value = message.searchResults || []
  searchDialogVisible.value = true
}

function buildFormData(text, currentFiles, conversationId) {
  const fd = new FormData()
  fd.append('message', text)
  fd.append('conversation_id', String(conversationId))
  fd.append('web_search', String(webSearchEnabled.value))
  fd.append('user_identity', userIdentity.value)
  if (selectedDB.value) {
    fd.append('db_version', selectedDB.value)
  }
  currentFiles.forEach((file) => fd.append('files', file))
  return fd
}

async function streamAnswer(assistantMsg, formData) {
  const response = await fetch(buildApiUrl('/api/chat'), {
    method: 'POST',
    body: formData
  })
  if (!response.ok) {
    const { text, payload } = await parseJsonResponse(response)
    throw new Error(getErrorMessage(response, payload, text, '主回答接口失败'))
  }
  if (!response.body) {
    throw new Error('主回答接口未返回可读流')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    assistantMsg.content += decoder.decode(value, { stream: true })
    scrollToBottom()
  }
}

async function loadTrace(assistantMsg, formData) {
  assistantMsg.traceLoading = true
  try {
    const response = await fetch(buildApiUrl('/api/chat/events'), {
      method: 'POST',
      body: formData
    })
    const { text, payload } = await parseJsonResponse(response)
    if (!response.ok || !payload.success) {
      throw new Error(getErrorMessage(response, payload, text, '过程接口失败'))
    }
    assistantMsg.traceEvents = payload.data?.events || []
    if (!assistantMsg.content && payload.data?.final_answer) {
      assistantMsg.content = payload.data.final_answer
    }
    if (payload.data?.search_results?.length) {
      assistantMsg.searchResults = payload.data.search_results
    }
  } catch (error) {
    assistantMsg.traceEvents = [
      {
        type: 'trace.error',
        node: 'frontend',
        preview: error.message || '过程获取失败'
      }
    ]
  } finally {
    assistantMsg.traceLoading = false
    saveHistory()
  }
}

async function loadSearchArtifacts(assistantMsg, formData) {
  if (!webSearchEnabled.value) return
  assistantMsg.searchLoading = true
  try {
    const response = await fetch(buildApiUrl('/api/chat/search-artifacts'), {
      method: 'POST',
      body: formData
    })
    const { text, payload } = await parseJsonResponse(response)
    if (!response.ok || !payload.success) {
      throw new Error(getErrorMessage(response, payload, text, '搜索结果接口失败'))
    }
    assistantMsg.searchResults = payload.data?.search_results || []
  } catch (error) {
    assistantMsg.searchResults = []
    assistantMsg.traceEvents = [
      ...(assistantMsg.traceEvents || []),
      {
        type: 'search.error',
        node: 'frontend',
        preview: error.message || '搜索结果获取失败'
      }
    ]
  } finally {
    assistantMsg.searchLoading = false
    saveHistory()
  }
}

async function sendMessage() {
  if (sendDisabled.value) return

  const text = inputMessage.value.trim() || '请结合我上传的附件进行分析。'
  const currentFiles = [...files.value]
  inputMessage.value = ''
  files.value = []
  resizeTextarea()

  const conv = currentConv.value
  if (!conv) return

  const userMessage = createMessage('user', text || '[仅上传附件]', {
    files: currentFiles.map((file) => file.name)
  })
  conv.messages.push(userMessage)

  if (conv.messages.length === 1) {
    conv.title = (text || currentFiles[0]?.name || '新对话').slice(0, 30)
  }
  conv.updatedAt = Date.now()

  const assistantMsg = reactive(createMessage('assistant', '', {
    files: [],
    traceLoading: true,
    searchLoading: webSearchEnabled.value
  }))
  conv.messages.push(assistantMsg)
  selectedTraceMessageId.value = assistantMsg.id
  loading.value = true
  saveHistory()
  scrollToBottom()

  const answerForm = buildFormData(text, currentFiles, conv.id)
  const traceForm = buildFormData(text, currentFiles, conv.id)
  const searchForm = buildFormData(text, currentFiles, conv.id)

  try {
    await Promise.allSettled([
      streamAnswer(assistantMsg, answerForm),
      loadTrace(assistantMsg, traceForm),
      loadSearchArtifacts(assistantMsg, searchForm)
    ])
    if (!assistantMsg.content.trim()) {
      assistantMsg.content = '未获取到模型回答。'
    }
    if (assistantMsg.searchResults?.length) {
      ElMessage.success(`已获取 ${assistantMsg.searchResults.length} 条网页搜索结果`)
    }
  } catch (error) {
    assistantMsg.content = `\n\n**Error:** ${error.message || '请求失败'}`
  } finally {
    loading.value = false
    saveHistory()
    scrollToBottom()
  }
}
</script>

<style scoped>
.chat-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 360px;
  height: 100%;
  width: 100%;
  background: linear-gradient(180deg, #f7f8fb 0%, #eef2f7 100%);
  color: #1f2937;
}

.sidebar {
  background: #f1f5f9;
  border-right: 1px solid #dbe4ef;
  display: flex;
  flex-direction: column;
  padding: 16px;
  min-width: 0;
}

.sidebar-header {
  margin-bottom: 16px;
}

.new-chat-btn {
  width: 100%;
  border: none;
  border-radius: 14px;
  background: #0f172a;
  color: #fff;
  padding: 12px 14px;
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.6);
  cursor: pointer;
}

.sidebar-item.active {
  background: #dbeafe;
  color: #0f172a;
}

.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-btn {
  border: none;
  background: transparent;
  color: #64748b;
  cursor: pointer;
}

.sidebar-footer {
  margin-top: 16px;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #fff;
  border-radius: 14px;
  margin-bottom: 10px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #0891b2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.user-name {
  font-weight: 600;
}

.user-role {
  color: #64748b;
  font-size: 12px;
}

.identity-selector {
  width: 100%;
}

.main-chat {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #fff;
}

.main-chat.initial-view {
  justify-content: center;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 22px;
  border-bottom: 1px solid #e5e7eb;
}

.chat-title {
  font-size: 16px;
  font-weight: 700;
}

.chat-tools {
  display: flex;
  gap: 8px;
}

.status-pill {
  border-radius: 999px;
  padding: 6px 10px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
}

.status-pill.active {
  background: #dbeafe;
  color: #1d4ed8;
}

.initial-greeting {
  max-width: 720px;
  margin: 0 auto;
  padding: 24px;
}

.initial-greeting h1 {
  font-size: 40px;
  margin: 0 0 8px;
  background: linear-gradient(90deg, #2563eb, #0f766e, #ca8a04);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.initial-greeting p {
  color: #6b7280;
  margin: 0;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0 24px;
}

.message-row {
  width: 100%;
}

.message-inner {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  gap: 14px;
  padding: 18px 24px;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #0f172a;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.message-body {
  flex: 1;
  min-width: 0;
}

.assistant-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.ghost-btn {
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 999px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 12px;
}

.ghost-btn.active {
  background: #e0f2fe;
  border-color: #7dd3fc;
  color: #0369a1;
}

.ghost-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.minor-status {
  color: #64748b;
  font-size: 12px;
}

.user-text {
  white-space: pre-wrap;
  line-height: 1.75;
}

:deep(.markdown-body) {
  line-height: 1.75;
  color: #111827;
}

:deep(.markdown-body pre) {
  background: #0f172a;
  color: #e5e7eb;
  border-radius: 14px;
  padding: 14px;
  overflow-x: auto;
}

.message-files {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.file-tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
}

.loading-box {
  color: #64748b;
}

.chat-footer {
  border-top: 1px solid #e5e7eb;
  padding: 16px 24px 18px;
  background: #fff;
}

.input-wrapper {
  max-width: 760px;
  margin: 0 auto;
  border: 1px solid #dbe4ef;
  border-radius: 20px;
  padding: 14px 16px 10px;
  background: #f8fafc;
  position: relative;
}

textarea {
  width: 100%;
  border: none;
  resize: none;
  background: transparent;
  font: inherit;
  color: #111827;
  min-height: 28px;
  max-height: 200px;
}

textarea:focus {
  outline: none;
}

.file-preview-area {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 10px 0;
}

.file-preview-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e5e7eb;
  font-size: 12px;
}

.remove-file {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #dc2626;
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.left-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-btn,
.send-btn {
  border: none;
  border-radius: 999px;
  background: #fff;
  padding: 8px 12px;
  cursor: pointer;
}

.tool-btn.active {
  background: #dbeafe;
  color: #1d4ed8;
}

.send-btn {
  background: #0f172a;
  color: #fff;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.db-wrapper {
  position: relative;
}

.db-menu {
  position: absolute;
  left: 0;
  bottom: 44px;
  min-width: 120px;
  background: #fff;
  border: 1px solid #dbe4ef;
  border-radius: 12px;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.12);
  overflow: hidden;
}

.db-item {
  padding: 10px 12px;
  cursor: pointer;
}

.db-item:hover,
.db-item.active {
  background: #eff6ff;
}

.trace-panel {
  border-left: 1px solid #dbe4ef;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.trace-header {
  padding: 18px 18px 14px;
  border-bottom: 1px solid #dbe4ef;
}

.trace-title {
  font-size: 16px;
  font-weight: 700;
}

.trace-subtitle {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.trace-content,
.trace-empty {
  padding: 16px 18px;
  overflow-y: auto;
}

.trace-empty {
  color: #64748b;
}

.trace-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 14px;
}

.trace-summary > div {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 10px;
  font-size: 12px;
}

.trace-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trace-item {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 12px;
}

.trace-type {
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 6px;
}

.trace-meta,
.trace-delta,
.trace-loading {
  font-size: 12px;
  color: #475569;
}

.trace-code {
  margin: 8px 0 0;
  padding: 10px;
  border-radius: 10px;
  background: #0f172a;
  color: #e5e7eb;
  font-size: 12px;
  overflow-x: auto;
  white-space: pre-wrap;
}

.search-empty {
  color: #64748b;
}

.search-result-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 70vh;
  overflow-y: auto;
}

.search-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 16px;
  background: #f8fafc;
}

.search-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.search-main-title {
  font-size: 16px;
  font-weight: 700;
}

.search-sub-title {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.search-summary {
  line-height: 1.7;
  margin-bottom: 10px;
}

.search-details pre {
  white-space: pre-wrap;
  background: #fff;
  border: 1px solid #e5e7eb;
  padding: 12px;
  border-radius: 12px;
  max-height: 240px;
  overflow-y: auto;
}

@media (max-width: 1400px) {
  .chat-shell {
    grid-template-columns: 240px minmax(0, 1fr);
  }

  .trace-panel {
    display: none;
  }
}

@media (max-width: 900px) {
  .chat-shell {
    grid-template-columns: 1fr;
  }

  .sidebar {
    display: none;
  }

  .message-inner,
  .input-wrapper {
    max-width: 100%;
  }
}
</style>
