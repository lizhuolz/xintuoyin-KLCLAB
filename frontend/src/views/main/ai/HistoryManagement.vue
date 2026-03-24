<template>
  <div class="history-management-container">
    <div class="header-section">
      <div class="title-row">
        <span class="title">历史对话记录浏览</span>
      </div>

      <el-form :inline="true" :model="searchForm" class="filter-form">
        <div class="filter-row">
          <el-form-item label="搜索">
            <el-input v-model="searchForm.composite" placeholder="请输入标题或对话内容" style="width: 320px" clearable />
          </el-form-item>

          <el-form-item label="对话日期">
            <el-date-picker
              v-model="searchForm.dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="x"
              style="width: 280px"
            />
          </el-form-item>
        </div>

        <div class="button-row">
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="fetchHistories">查询</el-button>
        </div>
      </el-form>
    </div>

    <div class="action-bar">
      <el-button @click="exportData">导出</el-button>
    </div>

    <el-table
      ref="tableRef"
      :data="historyList"
      v-loading="loading"
      stripe
      @selection-change="handleSelectionChange"
      style="width: 100%; margin-top: 10px"
      header-cell-class-name="custom-table-header"
    >
      <el-table-column type="selection" width="55" />
      <el-table-column type="index" label="序号" width="70" align="center" />
      <el-table-column prop="title" label="对话输入" min-width="250" show-overflow-tooltip />
      <el-table-column label="用户信息" min-width="180">
        <template #default="scope">
          {{ scope.row.user?.name || '-' }} / {{ scope.row.user?.phone || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="所属企业" min-width="180" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.user?.categoryName || '-' }}</template>
      </el-table-column>
      <el-table-column label="对话时间" width="180">
        <template #default="scope">{{ scope.row.updatedAtDisplay }}</template>
      </el-table-column>
      <el-table-column prop="message_count" label="轮次" width="90" align="center" />
      <el-table-column label="操作" width="100" fixed="right" align="center">
        <template #default="scope">
          <el-button link type="primary" @click="viewDetail(scope.row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="detailVisible" title="对话详情" width="800px" destroy-on-close custom-class="history-detail-dialog">
      <div class="history-detail-content">
        <div class="metadata-grid">
          <div class="meta-item">
            <span class="label">用户姓名：</span>
            <el-input :model-value="currentMeta.name" readonly class="meta-input" />
          </div>
          <div class="meta-item">
            <span class="label">联系方式：</span>
            <el-input :model-value="currentMeta.phone" readonly class="meta-input" />
          </div>
          <div class="meta-item">
            <span class="label">所属企业：</span>
            <el-input :model-value="currentMeta.company" readonly class="meta-input" />
          </div>
          <div class="meta-item">
            <span class="label">对话时间：</span>
            <el-input :model-value="currentMeta.timeDisplay" readonly class="meta-input" />
          </div>
        </div>

        <div class="conversation-section">
          <h4 class="section-title">对话详情：</h4>
          <div class="history-detail-list">
            <div v-for="(msg, idx) in detailMessages" :key="idx" class="detail-msg-wrap">
              <div class="msg-type-label">{{ msg.role === 'user' ? '问' : '答' }}</div>
              <div class="msg-content-box" :class="msg.role">
                <div class="msg-text" v-html="renderMarkdown(msg.content)"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'
import { ElMessage } from 'element-plus'
import { aiApi, flattenHistoryMessages, formatTimestamp } from '@/api/ai'

const md = new MarkdownIt({ html: false, linkify: true, typographer: true })
const renderMarkdown = (text) => md.render(text || '')

const historyList = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const detailMessages = ref([])
const selectedRows = ref([])

const currentMeta = reactive({
  name: '',
  phone: '',
  company: '',
  timeDisplay: '',
})

const searchForm = reactive({
  composite: '',
  dateRange: null,
})

async function fetchHistories() {
  loading.value = true
  try {
    const params = {
      search: searchForm.composite || '',
      start_time: searchForm.dateRange?.[0] || undefined,
      end_time: searchForm.dateRange?.[1] || undefined,
    }
    const data = await aiApi.listHistories(params)
    historyList.value = (data.list || []).map((item) => ({
      ...item,
      updatedAtDisplay: item.updatedAt || formatTimestamp(item.updated_at),
    }))
  } catch (error) {
    ElMessage.error(error.message || '获取历史记录失败')
  } finally {
    loading.value = false
  }
}

function resetSearch() {
  searchForm.composite = ''
  searchForm.dateRange = null
  fetchHistories()
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

async function viewDetail(row) {
  currentMeta.name = row.user?.name || ''
  currentMeta.phone = row.user?.phone || ''
  currentMeta.company = row.user?.categoryName || ''
  currentMeta.timeDisplay = row.updatedAtDisplay || '-'

  try {
    const detail = await aiApi.getHistoryDetail(row.conversation_id)
    detailMessages.value = flattenHistoryMessages(detail)
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(error.message || '获取详情失败')
  }
}

function exportData() {
  const dataToExport = selectedRows.value.length > 0 ? selectedRows.value : historyList.value
  if (!dataToExport.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }

  const headers = ['序号', '对话输入', '用户姓名', '联系方式', '所属企业', '对话时间', '轮次']
  const rows = dataToExport.map((item, index) => [
    index + 1,
    item.title || '新对话',
    item.user?.name || '',
    item.user?.phone || '',
    item.user?.categoryName || '',
    item.updatedAtDisplay || '',
    item.message_count || 0,
  ])

  let csvContent = '\ufeff' + headers.join(',') + '\n'
  rows.forEach((row) => {
    csvContent += row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(',') + '\n'
  })

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', `对话记录_${new Date().toLocaleDateString()}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

onMounted(fetchHistories)
</script>

<style scoped lang="less">
.history-management-container { padding: 24px; background: #fff; min-height: 100vh; }
.header-section { margin-bottom: 24px; .title-row { margin-bottom: 20px; .title { font-size: 20px; font-weight: 600; color: #333; } } }

.filter-form {
  background: #fcfcfc;
  padding: 24px;
  border: 1px solid #ebeef5;
  border-radius: 8px;

  .filter-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .button-row {
    margin-top: 16px;
    display: flex;
    gap: 12px;
  }
}

.action-bar { margin: 20px 0 12px; }

.metadata-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 30px;
  background: #fdfdfd;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #f0f0f0;

  .meta-item {
    display: flex;
    align-items: center;
    .label {
      width: 80px;
      font-size: 14px;
      color: #666;
      flex-shrink: 0;
    }
    .meta-input {
      :deep(.el-input__inner) {
        background-color: #f9f9f9;
        cursor: default;
      }
    }
  }
}

.history-detail-list { display: flex; flex-direction: column; gap: 14px; }
.detail-msg-wrap { display: flex; gap: 14px; }
.msg-type-label { width: 34px; height: 34px; border-radius: 50%; background: #eef4ff; color: #2f6de6; display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; }
.msg-content-box { flex: 1; padding: 14px 16px; border-radius: 14px; border: 1px solid #edf1f7; }
.msg-content-box.user { background: #fafbff; }
.msg-content-box.assistant { background: #fff; }
.msg-text { color: #334155; line-height: 1.7; }
</style>
