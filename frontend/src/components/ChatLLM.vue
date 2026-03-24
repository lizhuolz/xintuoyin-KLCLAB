<template>
  <div class="chat-container">
    <!-- 1. 左侧栏：对话历史 (支持收起) -->
    <aside class="sidebar" :class="{ collapsed: isSidebarCollapsed }">
      <div class="sidebar-header">
        <button v-if="!isSidebarCollapsed" class="new-chat-btn" @click="createNewChat">
          <span class="plus-icon">+</span> 新建对话
        </button>
        <button class="toggle-btn" @click="isSidebarCollapsed = !isSidebarCollapsed">
          <el-icon><Fold v-if="!isSidebarCollapsed" /><Expand v-else /></el-icon>
        </button>
      </div>

      <!-- 侧边栏搜索框 -->
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
      
      <!-- 侧边栏底部操作区 -->
      <div class="sidebar-footer">
        <div v-if="!isSidebarCollapsed" class="sidebar-actions">
          <button class="manage-history-btn" @click="openHistoryManager">
            <el-icon><Setting /></el-icon> 管理对话记录
          </button>
        </div>
        

      </div>
    </aside>

    <!-- 2. 中间：聊天主区域 -->
    <main class="main-chat">
      <header class="chat-header" v-if="currentMessages.length > 0">
        <span class="current-conv-title">{{ currentConv?.title || '新对话' }}</span>
      </header>

      <!-- 初始欢迎页 (当没有消息时) -->
      <div v-if="currentMessages.length === 0" class="initial-greeting">
        <div class="greeting-content">
          <h1 class="gradient-text">用户你好</h1>
          <h2 class="sub-text">需要我为你做什么</h2>
        </div>
      </div>

      <!-- 消息列表 -->
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
              <div class="message-content">
                <div v-if="msg.role === 'assistant'" class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                <div v-else class="user-text">{{ msg.content }}</div>
              </div>
              
              <!-- 推荐提问气泡 -->
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
                  <button class="icon-action" :class="{ active: msg.liked }" @click="handleLike(msg, index)"><el-icon><CaretTop /></el-icon></button>
                  <button class="icon-action" :class="{ active: msg.disliked }" @click="handleDislike(msg, index)"><el-icon><CaretBottom /></el-icon></button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="loading" class="loading-row"><span class="dot">.</span><span class="dot">.</span><span class="dot">.</span></div>
      </div>

      <!-- 底部输入区 -->
      <footer class="chat-input-area">
        <div class="input-container-inner">
          <div class="kg-entrance-wrapper">
            <a href="https://www.baidu.com" target="_blank" class="kg-bubble">知识图谱</a>
          </div>
          <div class="input-box-wrapper">
            <textarea v-model="inputMessage" @keydown.enter.exact.prevent="sendMessage" placeholder="输入消息..." ref="textareaRef"></textarea>
            <div v-if="files.length > 0" class="mini-previews">
              <div v-for="(f, i) in files" :key="i" class="mini-file"><span>{{ f.name }}</span><i @click="removeFile(i)">×</i></div>
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
                    <div v-for="v in ['V0','V1']" :key="v" @click="selectedDB=(selectedDB===v?null:v);showDBMenu=false" :class="{active:selectedDB===v}">数据库 {{v}}</div>
                  </div>
                </div>
                <button class="tool-btn" :class="{ active: ragEnabled }" @click="ragEnabled = !ragEnabled"><el-icon><Notebook /></el-icon></button>
              </div>
              <button class="send-submit-btn" :disabled="!inputMessage.trim() && !files.length || loading" @click="sendMessage"><el-icon><Promotion /></el-icon></button>
            </div>
          </div>
          <div class="legal-footer">©2025-新拓银人工智能 | 渝ICP备2024037824号-1 | v1.0.0</div>
        </div>
      </footer>
    </main>

    <!-- 3. 右侧栏：参考链接 -->
    <transition name="slide-fade">
      <aside v-if="sidebarSources.length > 0" class="sources-sidebar">
        <div class="sidebar-sources-header"><h3>参考链接</h3><button @click="sidebarSources = []" class="close-sidebar">×</button></div>
        <div class="sidebar-sources-content">
          <div v-for="(s, idx) in sidebarSources" :key="idx" class="source-card">
            <div class="s-num">{{ idx + 1 }}</div>
            <div class="s-info">
              <h4 class="s-title">{{ s.main_title }}</h4>
              <p class="s-summary">{{ s.summary }}</p>
              <a :href="s.url" target="_blank" class="s-link">查看原文 <el-icon><TopRight /></el-icon></a>
            </div>
          </div>
        </div>
      </aside>
    </transition>

    <!-- 历史记录管理弹窗 -->
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

    <!-- 反馈弹窗 (点踩重构 - 严格参考原型图) -->
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
import { Link, DocumentCopy, CaretTop, CaretBottom, Search, Paperclip, Coin, Notebook, Promotion, TopRight, Fold, Expand, ChatDotRound, Delete, Plus, Setting } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const md = new MarkdownIt({ html:false, linkify:true, typographer:true, highlight:(s,l)=>{
  if(l && hljs.getLanguage(l)) try{return hljs.highlight(s,{language:l}).value}catch(e){}
  return md.utils.escapeHtml(s)
}});
const renderMarkdown = (t) => md.render(t || '')

// // 模拟已登录用户信息 (与 user.json 保持一致)
// const MOCK_USER = {
//   name: '王颖奇',
//   phone: '15323720032',
//   company: '图湃（北京）医疗科技'
// }
import userData from '../../../user.json'
const MOCK_USER = userData

const conversations = ref([]); const currentId = ref(null); const inputMessage = ref(''); const files = ref([]); const loading = ref(false);
const webSearchEnabled = ref(false); const showDBMenu = ref(false); const selectedDB = ref(null); const ragEnabled = ref(false);
const user_identity = ref('admin'); const sidebarSources = ref([]); const scrollRef = ref(null); const textareaRef = ref(null);
const isSidebarCollapsed = ref(false);

const currentConv = computed(() => conversations.value.find(c => String(c.id) === String(currentId.value)))
const currentMessages = computed(() => currentConv.value?.messages || [])

// 搜索防抖函数
function debounce(fn, delay) {
  let timer = null;
  return function(...args) {
    if(timer) clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  }
}

// 侧边栏搜索逻辑
const sidebarSearch = ref('')
const handleSidebarSearch = debounce(async () => {
  await fetchConversations(sidebarSearch.value);
}, 300)

async function fetchConversations(query = "") {
  try {
    const res = await fetch(`/api/history/list?search=${encodeURIComponent(query)}`)
    if (res.ok) {
      const serverList = await res.json()
      conversations.value = serverList.map(item => ({ id: String(item.id), title: item.title, messages: [] }))
    }
  } catch (e) {}
}

// 历史记录管理弹窗逻辑
const historyManagerVisible = ref(false)
const managerList = ref([])
const managerSearch = ref('')
const selectedManagerIds = ref([])
const managerLoading = ref(false)

async function openHistoryManager() {
  historyManagerVisible.value = true;
  managerSearch.value = '';
  await refreshManagerList();
}

const handleManagerSearch = debounce(async () => {
  await refreshManagerList(managerSearch.value);
}, 300)

async function refreshManagerList(query = "") {
  managerLoading.value = true;
  try {
    const res = await fetch(`/api/history/list?search=${encodeURIComponent(query)}`)
    if(res.ok) {
      const list = await res.json();
      managerList.value = list.map(item => ({
        ...item,
        updatedAtDisplay: new Date(item.updatedAt * 1000).toLocaleString()
      }))
    }
  } catch(e) {} finally {
    managerLoading.value = false;
  }
}

function handleManagerSelection(selection) {
  selectedManagerIds.value = selection.map(item => item.id)
}

async function handleSingleDelete(row) {
  try {
    await ElMessageBox.confirm(`确认删除对话“${row.title || '新对话'}”吗？删除后无法恢复并找回。`, '确认删除', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'danger-btn',
      type: 'warning'
    })
    await fetch(`/api/chat/${row.id}`, { method: 'DELETE' })
    ElMessage.success('已删除')
    
    const idx = conversations.value.findIndex(c => String(c.id) === String(row.id))
    if(idx !== -1) conversations.value.splice(idx, 1)
    
    if(String(currentId.value) === String(row.id)) {
      if(conversations.value.length) selectConv(conversations.value[0].id)
      else await createNewChat()
    }
    
    refreshManagerList(managerSearch.value)
  } catch(e) {}
}

async function handleBatchDelete() {
  try {
    await ElMessageBox.confirm(`确认删除选中的 ${selectedManagerIds.value.length} 条记录吗？删除后对话记录无法恢复并找回。`, '确认删除', {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'danger-btn',
      type: 'warning'
    })
    
    await fetch('/api/history/batch_delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: selectedManagerIds.value })
    })
    
    ElMessage.success('批量删除成功')
    
    let currentWasDeleted = false;
    selectedManagerIds.value.forEach(id => {
      if(String(currentId.value) === String(id)) currentWasDeleted = true;
      const idx = conversations.value.findIndex(c => String(c.id) === String(id))
      if(idx !== -1) conversations.value.splice(idx, 1)
    })
    
    if(currentWasDeleted) {
      if(conversations.value.length) selectConv(conversations.value[0].id)
      else await createNewChat()
    }
    
    refreshManagerList(managerSearch.value);
    selectedManagerIds.value = [];
  } catch(e) {}
}

// 反馈逻辑 (状态同步重构)
const feedbackVisible = ref(false);
const currentFeedbackMsgIndex = ref(-1);
const feedbackForm = reactive({ 
  reasons: { question: '', answer: '', report: '' },
  comment: "" 
});
const feedbackFiles = ref([]);

const handleLike = async (msg, index) => {
  // 切换本地状态 (Like 逻辑维持 Toggle)
  const isNowLiked = !msg.liked;
  msg.liked = isNowLiked;
  if (isNowLiked) msg.disliked = false;

  const fd = new FormData();
  fd.append('conversation_id', String(currentId.value));
  fd.append('message_index', String(index));
  fd.append('type', 'like');
  try { await fetch('/api/chat/feedback', { method: 'POST', body: fd }); } catch(e) {}
}

const handleDislike = async (msg, index) => {
  if (msg.disliked) {
    // 已经是点踩状态（表示之前提交过信息），再次点击视为直接取消
    msg.disliked = false;
    const fd = new FormData();
    fd.append('conversation_id', String(currentId.value));
    fd.append('message_index', String(index));
    fd.append('type', 'dislike');
    try { await fetch('/api/chat/feedback', { method: 'POST', body: fd }); } catch(e) {}
  } else {
    // 尚未点踩，弹出反馈框。注意：此时不改变 msg.disliked，不亮按钮。
    currentFeedbackMsgIndex.value = index;
    // 重置表单
    feedbackForm.reasons = { question: '', answer: '', report: '' };
    feedbackForm.comment = "";
    feedbackFiles.value = [];
    feedbackVisible.value = true;
  }
}

const handleFeedbackFile = (file) => { feedbackFiles.value.push(file.raw); }

const submitFeedback = async () => {
  // 校验前端必填 (至少选一个原因或填了评论)
  const hasReason = Object.values(feedbackForm.reasons).some(v => !!v);
  if (!hasReason && !feedbackForm.comment.trim() && feedbackFiles.value.length === 0) {
    ElMessage.warning("请至少选择一个原因或填写文字描述");
    return;
  }

  const fd = new FormData();
  fd.append('conversation_id', String(currentId.value));
  fd.append('message_index', String(currentFeedbackMsgIndex.value));
  fd.append('type', 'dislike');
  fd.append('reasons', JSON.stringify(feedbackForm.reasons));
  fd.append('comment', feedbackForm.comment);
  feedbackFiles.value.forEach(file => fd.append('files', file));

  try {
    const res = await fetch('/api/chat/feedback', { method: 'POST', body: fd });
    if(res.ok) {
      ElMessage.success("感谢您的反馈！");
      // 只有提交成功后，才在 UI 上亮起按钮
      const msg = currentMessages.value[currentFeedbackMsgIndex.value];
      if (msg) {
        msg.disliked = true;
        msg.liked = false;
      }
      feedbackVisible.value = false;
    } else {
      const err = await res.json();
      ElMessage.error(err.error || "提交失败");
    }
  } catch (e) { ElMessage.error("提交失败"); }
}

const toggleSidebarSources = (s) => { sidebarSources.value = (sidebarSources.value === s ? [] : s) }
const copyText = (t) => { navigator.clipboard.writeText(t).then(()=>ElMessage.success('已复制')) }

onMounted(async () => {
  await fetchConversations();
  if (!conversations.value.length) await createNewChat()
  else selectConv(conversations.value[0].id)
})

async function selectConv(id) {
  currentId.value = String(id)
  const conv = conversations.value.find(c => String(c.id) === String(id))
  if (conv && conv.messages.length === 0 && conv.title !== '新对话') {
    try {
      const res = await fetch(`/api/history/${id}`)
      if (res.ok) {
        const rawMsgs = await res.json()
        // 映射后端 feedback 字段到前端状态
        conv.messages = rawMsgs.map(m => ({
          ...m,
          liked: m.feedback === 'like',
          disliked: m.feedback === 'dislike'
        }))
      }
    } catch (e) {}
  }
  nextTick(scrollToBottom)
}

const createNewChat = async () => {
  try {
    const res = await fetch('/api/chat/new_session');
    const data = await res.json();
    const n = { id: data.conversation_id, title: '新对话', messages: [] }
    conversations.value.unshift(n); currentId.value = n.id;
  } catch (e) {
    const n = { id: String(Date.now()), title: '新对话', messages: [] }
    conversations.value.unshift(n); currentId.value = n.id;
  }
}

const handleFileUpload = (e) => {
  const allowed = ['pdf','doc','docx','ppt','pptx','txt','md','xls','xlsx','csv'];
  const added = Array.from(e.target.files).filter(f => allowed.includes(f.name.split('.').pop().toLowerCase()));
  if (added.length < e.target.files.length) ElMessage.warning("部分格式不支持");
  files.value = [...files.value, ...added]; e.target.value = '';
}
const removeFile = (i) => files.value.splice(i, 1)
const scrollToBottom = () => { if(scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight }
const sendRecommendedMessage = (text) => { inputMessage.value = text; sendMessage(); }

async function sendMessage() {
  if (!inputMessage.value.trim() && !files.value.length || loading.value) return
  const text = inputMessage.value; const cFiles = [...files.value]; 
  inputMessage.value = ''; files.value = [];
  
  const conv = currentConv.value;
  if(!conv) return;
  
  conv.messages.push({ role: 'user', content: text, files: cFiles.map(f => f.name) })
  if (conv.title === '新对话') conv.title = text.slice(0, 20)
  
  loading.value = true;
  const assistantMsg = reactive({ role: 'assistant', content: '', sources: [], recommendations: [] })
  conv.messages.push(assistantMsg)

  const fd = new FormData();
  fd.append('message', text); fd.append('conversation_id', String(conv.id));
  fd.append('web_search', String(webSearchEnabled.value)); fd.append('user_identity', user_identity.value);
  if(selectedDB.value) fd.append('db_version', selectedDB.value);
  if(ragEnabled.value) fd.append('kb_category', 'all');
  cFiles.forEach(f => fd.append('files', f))

  try {
    const res = await fetch('/api/chat', { method: 'POST', body: fd })
    const reader = res.body.getReader(); const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      
      const tags = ["[SOURCES_JSON]:", "[RECOMMENDATIONS]:"];
      let foundTag = false;
      for (const tag of tags) {
        if (buffer.includes(tag)) {
          const parts = buffer.split(tag);
          assistantMsg.content += parts[0];
          const jsonStr = parts[1].trim();
          if (jsonStr.startsWith("[") && jsonStr.includes("]")) {
            const end = jsonStr.lastIndexOf("]") + 1;
            const data = JSON.parse(jsonStr.substring(0, end));
            if (tag.includes("SOURCES")) assistantMsg.sources = data;
            else assistantMsg.recommendations = data;
            buffer = jsonStr.substring(end);
          } else { buffer = tag + parts[1]; }
          foundTag = true; break;
        }
      }
      
      if (!foundTag) {
        const nextStart = buffer.indexOf("[");
        if (nextStart === -1) {
          assistantMsg.content += buffer; buffer = "";
        } else if (nextStart > 0) {
          assistantMsg.content += buffer.substring(0, nextStart);
          buffer = buffer.substring(nextStart);
        }
      }
      scrollToBottom();
    }
  } catch (e) { assistantMsg.content += "\n**连接错误**"; } finally { loading.value = false; }
}
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

.user-profile-wrapper { background: #fff; padding: 12px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.user-profile { display: flex; gap: 10px; align-items: center; }
.avatar { width: 32px; height: 32px; background: #4080FF; color: #fff; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; }
.user-info { display: flex; flex-direction: column; overflow: hidden; }
.user-name { font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; } 
.user-role { font-size: 11px; color: #999; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

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
.message-content { font-size: 16px; line-height: 1.7; color: #1f1f1f; }
.assistant .message-content { background: #f8faff; padding: 16px 20px; border-radius: 4px 20px 20px 20px; border: 1px solid #eef2ff; }
.user .message-content { background: #f4f4f4; padding: 12px 18px; border-radius: 20px 4px 20px 20px; align-self: flex-end; }
.recommendations-area { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
.rec-bubble { background: #fff; border: 1px solid #e0e0e0; padding: 6px 14px; border-radius: 18px; font-size: 13px; color: #666; cursor: pointer; transition: 0.2s; }
.rec-bubble:hover { border-color: #4080FF; color: #4080FF; background: #f0f7ff; }
.msg-footer { display: flex; justify-content: space-between; align-items: center; padding: 0 4px; }
.ai-tag { font-size: 11px; color: #bbb; }
.ref-btn { margin-left: 10px; font-size: 11px; }
.footer-right { display: flex; gap: 4px; }
.icon-action { background: none; border: none; color: #bbb; cursor: pointer; padding: 4px; border-radius: 4px; }
.icon-action.active { color: #4080FF; }
.icon-action:hover { color: #4080FF; background: #f0f0f0; }
.chat-input-area { padding: 10px 0 30px; }
.input-container-inner { max-width: 800px; margin: 0 auto; padding: 0 20px; position: relative; }
.kg-entrance-wrapper { margin-bottom: 10px; display: flex; justify-content: flex-start; }
.kg-bubble { background: #4080FF; color: #fff; padding: 4px 12px; border-radius: 12px; font-size: 12px; text-decoration: none; box-shadow: 0 2px 6px rgba(64,128,255,0.3); transition: 0.2s; }
.kg-bubble:hover { transform: translateY(-2px); opacity: 0.9; }
.input-box-wrapper { background: #f4f4f4; border-radius: 20px; padding: 12px 16px; display: flex; flex-direction: column; box-shadow: 0 2px 12px rgba(0,0,0,0.03); }
textarea { background: none; border: none; resize: none; width: 100%; min-height: 44px; font-size: 16px; outline: none; line-height: 1.5; }
.bottom-toolbar { display: flex; justify-content: space-between; align-items: center; margin-top: 8px; }
.tools-left { display: flex; gap: 4px; }
.tool-btn { width: 32px; height: 32px; border-radius: 50%; border: none; background: none; color: #666; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 18px; transition: 0.2s; }
.tool-btn:hover { background: #e0e0e0; }
.tool-btn.active { color: #4080FF; background: #e6f0ff; }
.send-submit-btn { width: 32px; height: 32px; border-radius: 50%; background: #4080FF; color: #fff; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.send-submit-btn:disabled { background: #ccc; }
.sources-sidebar { width: 320px; background: #fff; border-left: 1px solid #eee; display: flex; flex-direction: column; }
.sidebar-sources-header { padding: 16px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
.close-sidebar { border: none; background: none; font-size: 20px; cursor: pointer; }
.sidebar-sources-content { flex: 1; overflow-y: auto; padding: 16px; }
.source-card { display: flex; gap: 12px; margin-bottom: 20px; }
.s-num { width: 20px; height: 20px; background: #e6f0ff; color: #4080FF; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; flex-shrink: 0; }
.s-title { margin: 0 0 4px; font-size: 14px; color: #333; }
.s-summary { font-size: 13px; color: #666; line-height: 1.5; margin-bottom: 6px; }
.s-link { font-size: 12px; color: #4080FF; text-decoration: none; display: flex; align-items: center; gap: 2px; }
.legal-footer { text-align: center; font-size: 11px; color: #ccc; margin-top: 12px; }
.slide-fade-enter-active { transition: all 0.3s ease-out; }
.slide-fade-leave-active { transition: all 0.2s ease-in; }
.slide-fade-enter-from, .slide-fade-leave-to { transform: translateX(30px); opacity: 0; }

// 管理弹窗样式
.history-manager-content { padding: 0 10px; }
.manager-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.count-tip { font-size: 14px; color: #666; }
.search-input { width: 240px; }
.conv-name-cell { display: flex; align-items: center; gap: 8px; color: #333; }
.conv-name-cell .icon { color: #999; }
.manager-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding-top: 16px; border-top: 1px solid #f0f0f0; }
.manager-footer .hint { font-size: 12px; color: #ccc; }
.manager-footer .right { display: flex; gap: 12px; }

/* 点踩反馈弹窗样式 (严格参考原型图) */
.dislike-feedback-dialog {
  .feedback-guidelines {
    background: #fdfdfd;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 24px;
    p {
      margin: 4px 0;
      font-size: 13px;
      color: #666;
      line-height: 1.6;
    }
  }
  
  .custom-feedback-form {
    :deep(.el-form-item__label) {
      font-weight: bold;
      color: #333;
      padding-bottom: 8px;
      font-size: 15px;
    }

    :deep(.el-radio-group) {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      .el-radio { margin-right: 0; min-width: 100px; }
    }
  }

  .custom-uploader {
    :deep(.el-upload--picture-card) {
      width: 100px;
      height: 100px;
      border: 1px dashed #d9d9d9;
      background: #fafafa;
    }
    .upload-trigger {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: #999;
      line-height: 1.2;
      .el-icon { font-size: 24px; margin-bottom: 4px; }
      .text { font-size: 12px; }
      .count { color: #ccc; font-size: 11px; margin-top: 2px; }
    }
  }
  .upload-tip { font-size: 12px; color: #bbb; margin-top: 8px; }

  .feedback-footer {
    display: flex;
    justify-content: center;
    gap: 20px;
    padding-bottom: 10px;
    .footer-btn { width: 120px; border-radius: 4px; height: 40px; font-size: 15px; }
    .submit-btn { background: #4080FF; border-color: #4080FF; }
  }
}
</style>
