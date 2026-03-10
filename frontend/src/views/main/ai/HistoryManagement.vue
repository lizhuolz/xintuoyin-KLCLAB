<template>
  <div class="history-management-container">
    <div class="header-section">
      <div class="title-row">
        <span class="title">历史对话维护</span>
      </div>
      <!-- 搜索栏 -->
      <div class="filter-toolbar">
        <el-input 
          v-model="searchKeyword" 
          placeholder="搜索对话全文内容 (关键词)..." 
          class="search-input"
          clearable
          @keyup.enter="fetchHistories"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="fetchHistories">全文检索</el-button>
        <el-button type="danger" :disabled="!selectedIds.length" @click="handleBatchDelete">
          批量删除 ({{ selectedIds.length }})
        </el-button>
      </div>
    </div>

    <!-- 列表展示 -->
    <el-table 
      :data="historyList" 
      v-loading="loading" 
      style="width: 100%; margin-top: 20px"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" />
      <el-table-column prop="title" label="对话主题" min-width="350" show-overflow-tooltip />
      <el-table-column prop="messageCount" label="消息数" width="100" align="center" />
      <el-table-column label="最后活跃" width="200">
        <template #default="scope">
          {{ formatTime(scope.row.updatedAt) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="viewDetail(scope.row)">详情预览</el-button>
          <el-button link type="danger" @click="handleDelete(scope.row.id)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 对话详情弹窗 -->
    <el-dialog v-model="detailVisible" :title="'对话回放：' + currentTitle" width="750px" top="5vh">
      <div class="chat-detail-content">
        <div v-for="(msg, idx) in currentDetail" :key="idx" class="detail-msg-row" :class="msg.role">
          <div class="detail-avatar">{{ msg.role === 'user' ? 'U' : 'AI' }}</div>
          <div class="detail-bubble">
            <div class="msg-meta">{{ msg.role === 'user' ? '用户' : '智能助手' }}</div>
            <div class="msg-text">{{ msg.content }}</div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const historyList = ref([])
const loading = ref(false)
const searchKeyword = ref('')
const selectedIds = ref([])

const fetchHistories = async () => {
  loading.value = true
  try {
    const res = await axios.get(`/api/history/list?search=${searchKeyword.value}`)
    historyList.value = res.data
  } finally {
    loading.value = false
  }
}

const handleSelectionChange = (val) => {
  selectedIds.value = val.map(item => item.id)
}

const handleDelete = (id) => {
  ElMessageBox.confirm('确定要删除这条历史记录吗？', '提示', { type: 'warning' }).then(async () => {
    await axios.delete(`/api/chat/${id}`)
    ElMessage.success('已删除')
    fetchHistories()
  }).catch(() => {})
}

const handleBatchDelete = () => {
  ElMessageBox.confirm(`确定要删除选中的 ${selectedIds.value.length} 条记录吗？`, '警告', { type: 'error' }).then(async () => {
    await axios.post('/api/history/batch_delete', { ids: selectedIds.value })
    ElMessage.success('批量删除成功')
    fetchHistories()
  }).catch(() => {})
}

// 详情展示
const detailVisible = ref(false)
const currentDetail = ref([])
const currentTitle = ref('')
const viewDetail = async (row) => {
  currentTitle.value = row.title
  const res = await axios.get(`/api/history/${row.id}`)
  currentDetail.value = res.data
  detailVisible.value = true
}

const formatTime = (t) => new Date(t * 1000).toLocaleString()

onMounted(fetchHistories)
</script>

<style scoped lang="less">
.history-management-container { padding: 24px; background: #fff; min-height: 100%; }
.header-section { margin-bottom: 24px; .title { font-size: 18px; font-weight: 600; display: block; margin-bottom: 16px; } }
.filter-toolbar { display: flex; gap: 12px; align-items: center; background: #f9f9f9; padding: 16px; border-radius: 8px; .search-input { width: 400px; } }

.chat-detail-content { max-height: 65vh; overflow-y: auto; padding: 20px; background: #f0f2f5; border-radius: 8px; display: flex; flex-direction: column; gap: 20px; }
.detail-msg-row {
  display: flex; gap: 12px;
  &.user { flex-direction: row-reverse; .detail-bubble { background: #95ec69; border-radius: 8px 0 8px 8px; } .msg-meta { text-align: right; } }
  &.assistant { .detail-bubble { background: #fff; border-radius: 0 8px 8px 8px; } }
  .detail-avatar { width: 36px; height: 36px; border-radius: 4px; background: #4080FF; color: #fff; display: flex; align-items: center; justify-content: center; font-weight: bold; flex-shrink: 0; }
  .detail-bubble { max-width: 80%; padding: 10px 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); .msg-meta { font-size: 11px; color: rgba(0,0,0,0.4); margin-bottom: 4px; } .msg-text { font-size: 14px; line-height: 1.6; white-space: pre-wrap; color: #1f1f1f; } }
}
</style>
