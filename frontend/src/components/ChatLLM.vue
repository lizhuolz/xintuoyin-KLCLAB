<template>
  <div class="chat-container">
    <!-- Sidebar: Conversation List -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <button class="new-chat-btn" @click="createNewChat">
          <span class="plus-icon">+</span> 新建对话
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
          <!-- Icon removed -->
          <span class="conv-title">{{ conv.title || '新对话' }}</span>
          <!-- Delete Button -->
          <span class="delete-btn" @click.stop="deleteConv(conv.id)" title="删除对话">
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </span>
        </div>
      </div>
      <div class="sidebar-footer">
        <div class="user-profile">
          <div class="avatar">{{ userName.charAt(0).toUpperCase() }}</div>
          <span>{{ userName }}</span>
        </div>
      </div>
    </aside>

    <!-- Main Chat Area -->
    <main class="main-chat" :class="{ 'initial-view': currentMessages.length === 0 }">
      <!-- Chat Header (Visible only in active chat) -->
      <header class="chat-view-header" v-if="currentMessages.length > 0">
        <span class="view-title">{{ currentConv?.title || '新对话' }}</span>
      </header>

      <!-- Initial Greeting (Only shown when empty) -->
      <div v-if="currentMessages.length === 0" class="initial-greeting">
        <h1>用户你好</h1>
        <h2>需要我为你做什么</h2>
      </div>

      <!-- Messages Scroll Area -->
      <div class="messages-container" ref="scrollRef" v-show="currentMessages.length > 0">
        <!-- Empty state block removed -->
        
        <div 
          v-for="(msg, index) in currentMessages" 
          :key="index" 
          class="message-row"
          :class="msg.role"
        >
          <div class="message-inner">
            <div class="message-avatar">
              <span v-if="msg.role === 'user'" class="user-icon">👤</span>
              <div v-else class="assistant-icon">
                <!-- Gemini Star Icon -->
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="url(#paint0_linear)" stroke="none"/>
                  <defs>
                    <linearGradient id="paint0_linear" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
                      <stop stop-color="#4E86F8"/>
                      <stop offset="1" stop-color="#D6409F"/>
                    </linearGradient>
                  </defs>
                </svg>
              </div>
            </div>
            <div class="message-content">
              <!-- Markdown Rendered Content -->
              <div 
                v-if="msg.role === 'assistant'" 
                class="markdown-body"
                v-html="renderMarkdown(msg.content)"
              ></div>
              <!-- Plain Text for User -->
              <div v-else class="user-text">{{ msg.content }}</div>
              
              <div v-if="msg.files && msg.files.length" class="message-files">
                <span class="file-tag" v-for="f in msg.files" :key="f">📎 {{ f }}</span>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Loading State -->
        <div v-if="loading" class="message-row assistant">
          <div class="message-inner">
            <div class="message-avatar"><div class="assistant-icon">...</div></div>
            <div class="message-content loading">
              <span class="dot">·</span><span class="dot">·</span><span class="dot">·</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <footer class="chat-footer">
        <div class="input-container">
          
          <!-- New Gemini-style Input Wrapper -->
          <div class="input-wrapper">
            <textarea 
                v-model="inputMessage" 
                @keydown.enter.exact.prevent="sendMessage"
                placeholder="输入消息..."
                rows="1"
                ref="textareaRef"
                @input="resizeTextarea"
             ></textarea>

             <!-- File Previews (Inside the box now) -->
             <div v-if="files.length > 0" class="file-preview-area">
                <div v-for="(file, idx) in files" :key="idx" class="file-preview-item">
                  <span class="file-name">{{ file.name }}</span>
                  <span class="remove-file" @click="removeFile(idx)">×</span>
                </div>
             </div>

             <!-- Action Bar -->
             <div class="action-bar">
                <div class="left-tools">
                  <label class="tool-btn" title="上传文件">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
                    <input type="file" multiple @change="handleFileUpload" style="display:none" />
                  </label>
                  
                  <!-- Web Search Button -->
                  <button 
                    class="tool-btn" 
                    :class="{ active: webSearchEnabled }"
                    @click="toggleWebSearch"
                    title="联网搜索"
                  >
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="11" cy="11" r="8"></circle>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                    </svg>
                  </button>

                  <!-- Database Button -->
                  <div class="db-wrapper">
                    <button
                      class="tool-btn"
                      :class="{ active: selectedDB !== null }"
                      @click="toggleDBMenu"
                      title="数据库"
                    >
                      <!-- database icon -->
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                        <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"></path>
                        <path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"></path>
                      </svg>
                    </button>

                    <!-- 二级菜单 -->
                    <div v-if="showDBMenu" class="db-menu">
                      <div
                        class="db-item"
                        :class="{ active: selectedDB === 'V0' }"
                        @click="selectDB('V0')"
                      >
                        数据库 V0
                      </div>
                      <div
                        class="db-item"
                        :class="{ active: selectedDB === 'V1' }"
                        @click="selectDB('V1')"
                      >
                        数据库 V1
                      </div>
                    </div>
                  </div>

                  <!-- Knowledge Base Button -->
                  <div class="db-wrapper">
                    <button
                      class="tool-btn"
                      :class="{ active: selectedKBCategory !== null }"
                      @click="toggleKBMenu"
                      title="知识库"
                    >
                      <!-- book icon -->
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                      </svg>
                    </button>

                    <!-- KB Menu -->
                    <div v-if="showKBMenu" class="db-menu">
                      <div class="db-item" :class="{ active: selectedKBCategory === 'contracts' }" @click="selectKB('contracts')">
                        合同管理
                      </div>
                      <div class="db-item" :class="{ active: selectedKBCategory === 'projects' }" @click="selectKB('projects')">
                        项目资料
                      </div>
                      <div class="db-item" :class="{ active: selectedKBCategory === 'research' }" @click="selectKB('research')">
                        调研检索
                      </div>
                    </div>
                  </div>

                </div>
                
                <button 
                  class="send-btn"
                  :disabled="!inputMessage.trim() && files.length === 0 || loading"
                  @click="sendMessage"
                >
                  <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                </button>
             </div>
          </div>
        </div>
      </footer>
      
      <!-- Footer Note (Always at bottom) -->
      <div class="footer-note">
         <div class="footer-legal">
           <span>©2025-新拓银（深圳）人工智能科技有限公司. All rights reserved.</span>
           <span>备案号：渝ICP备2024037824号-1</span>
           <span>公网安备 494号待定</span>
           <span>v1.0.0.20250203_Base_91320100MA25M8A78N</span>
         </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css' // Light theme for code
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const userName = computed(() => userStore.userInfo?.name || userStore.userInfo?.username || '用户')

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>';
      } catch (__error__) {}
    }
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>';
  }
});

function renderMarkdown(text) {
  return md.render(text || '');
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
const showKBMenu = ref(false)
const selectedKBCategory = ref(null)

const currentConv = computed(() => conversations.value.find(c => c.id === currentId.value))
const currentMessages = computed(() => currentConv.value ? currentConv.value.messages : [])

onMounted(() => {
  const saved = localStorage.getItem('chatgpt_convs')
  if (saved) {
    try {
      conversations.value = JSON.parse(saved)
    } catch (e) {
      console.error("Failed to load history", e)
    }
  }
  
  if (conversations.value.length === 0) {
    createNewChat()
  } else {
    currentId.value = conversations.value[0].id
  }
  scrollToBottom()
})

function resizeTextarea() {
  const el = textareaRef.value
  if(el) {
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }
}

watch(inputMessage, resizeTextarea)

function createNewChat() {
  const newChat = {
    id: Date.now(),
    title: '新对话',
    updatedAt: Date.now(),
    messages: []
  }
  conversations.value.unshift(newChat)
  currentId.value = newChat.id
  saveHistory()
}

function selectConv(id) {
  currentId.value = id
  scrollToBottom()
}

function deleteConv(id) {
  if(!confirm('确定要删除这个对话吗？')) return
  
  const index = conversations.value.findIndex(c => c.id === id)
  if(index !== -1) {
    conversations.value.splice(index, 1)
    saveHistory()
    
    // Create new if empty, or select next available
    if(conversations.value.length === 0) {
      createNewChat()
    } else if(currentId.value === id) {
      currentId.value = conversations.value[0].id
    }
  }

  // Delete from server
  fetch(`/api/chat/${id}`, { method: 'DELETE' })
    .catch(err => console.error("Failed to delete server history:", err))
}

function handleFileUpload(event) {
  files.value = [...files.value, ...Array.from(event.target.files)]
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
  if (selectedDB.value === val) {
    selectedDB.value = null
  } else {
    selectedDB.value = val
  }
  showDBMenu.value = false
}

function toggleKBMenu() {
  showKBMenu.value = !showKBMenu.value
}

function selectKB(val) {
  if (selectedKBCategory.value === val) {
    selectedKBCategory.value = null
  } else {
    selectedKBCategory.value = val
  }
  showKBMenu.value = false
}

function scrollToBottom() {
  nextTick(() => {
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  })
}

function saveHistory() {
  localStorage.setItem('chatgpt_convs', JSON.stringify(conversations.value))
}

async function sendMessage() {
  if ((!inputMessage.value.trim() && files.value.length === 0) || loading.value) return
  
  const text = inputMessage.value
  const currentFiles = [...files.value]
  
  inputMessage.value = ''
  files.value = []
  resizeTextarea()

  const conv = conversations.value.find(c => c.id === currentId.value)
  if (!conv) return

  conv.messages.push({
    role: 'user',
    content: text + (currentFiles.length ? `\n[Attached ${currentFiles.length} files]` : ''),
    files: currentFiles.map(f => f.name)
  })
  
  if (conv.messages.length === 1) {
    conv.title = text.slice(0, 30) || '新对话'
  }
  conv.updatedAt = Date.now()
  scrollToBottom()
  saveHistory()

  loading.value = true

  const assistantMsg = reactive({
    role: 'assistant',
    content: '',
    files: []
  })
  conv.messages.push(assistantMsg)

  const fd = new FormData()
  fd.append('message', text)
  fd.append('stream', 'true')
  // Send conversation_id so backend can manage history
  fd.append('conversation_id', String(conv.id))
  // Send web_search status
  fd.append('web_search', String(webSearchEnabled.value))
  // Send db_version if selected
  if (selectedDB.value) {
    fd.append('db_version', selectedDB.value)
  }
  // Send kb_category if selected
  if (selectedKBCategory.value) {
    fd.append('kb_category', selectedKBCategory.value)
  }
  
  // No longer sending full history to save bandwidth. Backend loads it from file.
  // const historyMessages = conv.messages.slice(0, -1)
  // fd.append('history', JSON.stringify(historyMessages))

  currentFiles.forEach(f => fd.append('files', f))

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      body: fd,
    })

    if (!response.ok) {
      const errText = await response.text()
      throw new Error(`Server Error (${response.status}): ${errText.slice(0, 100)}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value, { stream: true })
      assistantMsg.content += chunk
      scrollToBottom()
    }

    saveHistory()

  } catch (err) {
    console.error(err)
    assistantMsg.content += `\n\n**Error:** ${err.message || 'Failed to receive response.'}`
  } finally {
    loading.value = false
    saveHistory()
    scrollToBottom()
  }
}
</script>

<style scoped>
/* --- Light Theme Variables --- */
.chat-container {
  display: flex;
  height: 100%; /* Fit to parent container */
  width: 100%;
  font-family: 'Söhne', 'ui-sans-serif', 'system-ui', -apple-system, 'Segoe UI', Roboto, Ubuntu, Cantarell, 'Noto Sans', sans-serif, 'Helvetica Neue', Arial, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji';
  color: #1f1f1f;
  background-color: #ffffff;
  border-radius: 8px; /* Optional: Match layout rounding */
  overflow: hidden; /* Prevent spillover */
}

/* Hide Layout Footer when in Chat */
:global(.main-footer) {
  display: none !important;
}

/* --- Sidebar (Light Grey) --- */
.sidebar {
  width: 260px;
  background-color: #f0f4f9; /* Gemini Sidebar Color */
  display: flex;
  flex-direction: column;
  padding: 12px;
  flex-shrink: 0;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 12px 16px;
  background: #dde3ea;
  border: none;
  border-radius: 24px;
  color: #444746;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
  margin-bottom: 20px;
}
.new-chat-btn:hover { background: #d0d7de; }
.plus-icon { font-size: 18px; }

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar-item {
  padding: 10px 16px;
  border-radius: 20px;
  cursor: pointer;
  color: #444746;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 15px; /* Increased from 14px */
  transition: background 0.2s;
  position: relative;
  overflow: hidden;
}
.sidebar-item:hover { background-color: #e1e5ea; }
.sidebar-item.active { background-color: #d3e3fd; color: #001d35; font-weight: 500; }

.conv-icon { opacity: 0.6; }
.conv-title {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

/* Delete Button (Hidden by default, show on hover/active) */
.delete-btn {
  opacity: 0;
  color: #747775;
  transition: opacity 0.2s, color 0.2s;
  padding: 4px;
  border-radius: 4px;
}
.sidebar-item:hover .delete-btn,
.sidebar-item.active .delete-btn { opacity: 1; }
.delete-btn:hover { background: #ffcccc; color: #d32f2f; }

.sidebar-footer {
  margin-top: auto;
  padding-top: 10px;
}
.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 8px;
  color: #444746;
}
.user-profile:hover { background-color: #e1e5ea; }
.avatar {
  width: 32px; height: 32px; background: #8e44ad; color: white; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px;
}

/* --- Main Chat Area --- */
.main-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background-color: #ffffff;
}

/* Initial View Layout (Gemini Style) */
.main-chat.initial-view {
  justify-content: center;
  align-items: center;
  padding-bottom: 10vh; /* Visual balance */
}

.initial-greeting {
  text-align: left;
  margin-bottom: 32px; /* Reduced gap */
  width: 100%;
  max-width: 48rem;
  padding: 0 16px;
}
.initial-greeting h1 {
  font-size: 40px; /* Smaller */
  font-weight: 500;
  background: linear-gradient(90deg, #4285F4, #9B72CB, #D96570);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  margin-bottom: 8px; /* Spacing between lines */
  letter-spacing: -1px;
}
.initial-greeting h2 {
  font-size: 32px; /* Smaller */
  font-weight: 500;
  color: #c4c7c5;
  margin: 0;
  letter-spacing: -0.5px;
}

/* Override for Initial View */
.initial-view .chat-footer {
  position: static;
  background: transparent;
  padding: 0;
  width: 100%;
}
/* Reduce height in initial view but style it richer */
.initial-view .input-wrapper {
  background: #f0f4f9;
  min-height: 100px; /* Reduced from 160px */
  padding: 16px 20px 10px; /* Balanced padding */
  border-radius: 28px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  border: 1px solid rgba(0,0,0,0.02);
  justify-content: space-between;
}
.initial-view .input-wrapper:hover {
  background: #ffffff;
  box-shadow: 0 6px 24px rgba(0,0,0,0.12);
}

.chat-header {
  padding: 10px 16px;
  display: flex;
  align-items: center;
  color: #444746;
  font-weight: 500;
  border-bottom: 1px solid #e0e0e0;
}

.chat-view-header {
  height: 40px; /* Sorter header */
  display: flex;
  align-items: center;
  justify-content: center;
  /* border-bottom removed */
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(5px);
  position: sticky;
  top: 0;
  z-index: 10;
  flex-shrink: 0;
}
.view-title {
  font-size: 13px; /* Smaller */
  font-weight: 400; /* Lighter weight */
  color: #757575; /* Lighter color */
}

/* Scroll Area Layout Fix */
.messages-container {
  flex: 1; /* Takes all available space */
  overflow-y: auto; /* Internal scroll */
  padding-top: 0; /* Remove padding as header is now separate */
  padding-bottom: 20px;
  display: flex;
  flex-direction: column;
  scroll-behavior: smooth;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #1f1f1f;
  margin-bottom: 100px;
}
.logo-placeholder {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 20px;
  background: linear-gradient(90deg, #4E86F8, #D6409F);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.empty-state h1 { font-size: 28px; margin-bottom: 10px; font-weight: 400; }
.empty-state p { color: #757575; }

/* Message Rows */
.message-row {
  width: 100%;
}
/* No zebra striping for Gemini style, just clean white */
.message-row.assistant { background-color: #ffffff; }
.message-row.user { background-color: #ffffff; }

.message-inner {
  max-width: 48rem;
  margin: 0 auto;
  padding: 24px 16px;
  display: flex;
  gap: 16px;
}

.message-avatar {
  flex-shrink: 0;
  padding-top: 4px;
}
.user-icon { font-size: 24px; }
.assistant-icon {
  width: 28px; height: 28px;
  animation: rotate 10s linear infinite;
}
@keyframes rotate {
  0% { transform: rotate(0deg); } 
  100% { transform: rotate(360deg); }
}

.message-content {
  flex: 1;
  font-size: 16px;
  line-height: 1.6;
  color: #1f1f1f;
  overflow-x: hidden;
}

.user-text { white-space: pre-wrap; }

/* Markdown Styling Light */
:deep(.markdown-body) {
  color: #1f1f1f !important;
  font-family: inherit;
}
:deep(p) { margin-bottom: 1rem; }
:deep(pre) {
  background: #f6f8fa !important;
  padding: 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
  border: 1px solid #d0d7de;
}
:deep(code) {
  font-family: 'Consolas', monospace;
  font-size: 0.9em;
  color: #24292f;
}

/* --- Input Area (Fixed Bottom) --- */
.chat-footer {
  /* No absolute positioning! */
  background: #ffffff;
  padding: 10px 0 60px; /* Increased bottom padding for footer-note space */
  width: 100%;
  flex-shrink: 0; /* Prevent shrinking */
}

.input-container {
  max-width: 48rem;
  margin: 0 auto;
  padding: 0 16px;
  position: relative;
}

.file-preview-area {
  display: flex;
  gap: 10px;
  margin-top: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
  padding: 0 4px;
}
.file-preview-item {
  background: #ffffff;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #e0e0e0;
}
.remove-file { cursor: pointer; color: #d32f2f; font-weight: bold; padding: 0 4px; }

/* New Input Wrapper (The Box) */
.input-wrapper {
  background: #f0f4f9;
  border: 1px solid transparent;
  border-radius: 16px; /* Slightly less rounded than pill for multi-line feel */
  padding: 12px 16px 8px;
  display: flex;
  flex-direction: column;
  transition: background 0.2s, box-shadow 0.2s;
}

.input-wrapper:focus-within {
  background: #ffffff;
  box-shadow: 0 1px 6px rgba(0,0,0,0.15);
  border-color: #d0d7de;
}

textarea {
  flex: 1;
  background: transparent;
  border: none;
  color: #1f1f1f;
  resize: none;
  max-height: 200px;
  font-family: inherit;
  font-size: 16px;
  line-height: 1.5;
  padding: 4px 0 0; /* Reduced bottom padding */
  margin: 0;
  min-height: 24px;
}
textarea:focus { outline: none; }

/* Action Bar at Bottom */
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 2px; /* Reduced gap */
}

.left-tools {
  display: flex;
  gap: 4px; /* Tighter buttons */
}

.tool-btn {
  color: #444746;
  cursor: pointer;
  padding: 6px; /* Smaller padding */
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: none;
  background: transparent;
  transition: background 0.2s;
}
.tool-btn:hover:not(:disabled) { background: #e1e5ea; color: #1f1f1f; }
.tool-btn:disabled { opacity: 0.5; cursor: default; }
/* Active state for tool buttons (e.g. Web Search) */
.tool-btn.active {
  color: #4285F4;
  background-color: #e8f0fe;
}

.send-btn {
  background: transparent;
  color: #1f1f1f;
  border: none;
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}
.send-btn:disabled {
  color: #c4c7c5;
  cursor: default;
}
.send-btn:hover:not(:disabled) {
  background: #e1e5ea;
}

.footer-note {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  text-align: center;
  color: #757575;
  font-size: 11px;
  padding-bottom: 8px;
  line-height: 1.5;
  background: rgba(255,255,255,0.8); /* Optional: semi-transparent bg if overlaying */
  pointer-events: none; /* Let clicks pass through if needed, though links need events */
}
/* Re-enable pointer events for links inside footer */
.footer-note * { pointer-events: auto; }

.footer-legal {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  opacity: 0.8;
}

.footer-note {
  text-align: center;
  color: #757575;
  font-size: 11px;
  margin-top: 12px;
  padding-bottom: 8px;
  line-height: 1.5;
}

.footer-legal {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  opacity: 0.8;
}

.loading .dot {
  color: #444746;
  animation: blink 1.4s infinite both;
  font-size: 24px;
}
.loading .dot:nth-child(2) { animation-delay: 0.2s; }
.loading .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  0% { opacity: 0.2; } 
  20% { opacity: 1; }
  100% { opacity: 0.2; }
}

/* Database Menu */
.db-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.db-menu {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-bottom: 10px;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  padding: 4px;
  min-width: 120px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.db-item {
  padding: 8px 12px;
  font-size: 13px;
  color: #444746;
  cursor: pointer;
  border-radius: 6px;
  white-space: nowrap;
  transition: background 0.2s, color 0.2s;
  text-align: center;
}

.db-item:hover {
  background-color: #f0f4f9;
}

.db-item.active {
  color: #1967d2;
  background-color: #e8f0fe;
  font-weight: 500;
}
</style>
