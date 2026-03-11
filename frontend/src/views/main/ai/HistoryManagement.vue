<template>
  <div class="history-management-container">
    <!-- 1. 搜索面板 -->
    <div class="header-section">
      <div class="title-row">
        <span class="title">历史对话记录浏览</span>
      </div>
      
      <el-form :inline="true" :model="searchForm" class="filter-form">
        <div class="filter-row">
          <el-form-item label="搜索">
            <el-input 
              v-model="searchForm.composite" 
              placeholder="请输入IP地址、用户ID、RecordID搜索" 
              style="width: 320px"
              clearable
            />
          </el-form-item>
          
          <el-form-item label="对话日期">
            <el-date-picker
              v-model="searchForm.dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="X"
              style="width: 280px"
            />
          </el-form-item>

          <el-form-item label="审核状态">
            <el-select v-model="searchForm.auditStatus" placeholder="全部" style="width: 150px" clearable>
              <el-option label="通过" value="pass" />
              <el-option label="驳回" value="reject" />
              <el-option label="待审" value="pending" />
            </el-select>
          </el-form-item>

          <el-form-item label="处理状态">
            <el-select v-model="searchForm.processStatus" placeholder="全部" style="width: 150px" clearable>
              <el-option label="已完成" value="done" />
              <el-option label="处理中" value="processing" />
            </el-select>
          </el-form-item>
        </div>

        <div class="button-row">
          <el-button @click="resetSearch">重置</el-button>
          <el-button type="primary" @click="fetchHistories">查询</el-button>
        </div>
      </el-form>
    </div>

    <!-- 2. 操作区 -->
    <div class="action-bar">
      <el-button @click="exportData">导出</el-button>
    </div>

    <!-- 3. 数据表格 -->
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
      <el-table-column prop="ip_address" label="IP地址" width="140" />
      <el-table-column prop="user_id_display" label="用户ID" width="120" />
      <el-table-column label="对话时间" width="180">
        <template #default="scope">
          {{ new Date(scope.row.updatedAt * 1000).toLocaleString() }}
        </template>
      </el-table-column>
      <el-table-column prop="nlg_status" label="NLG" width="100" align="center">
        <template #default="scope">
          <el-tag :type="scope.row.nlg_status === '已生成' ? 'success' : 'info'" size="small">
            {{ scope.row.nlg_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="record_id" label="RecordID" width="180" />
      <el-table-column label="操作" width="100" fixed="right" align="center">
        <template #default="scope">
          <el-button link type="primary" @click="viewDetail(scope.row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="反馈详情" width="800px" destroy-on-close custom-class="history-detail-dialog">
      <div class="history-detail-content">
        <!-- 顶部元数据展示栏 (2x2 布局) -->
        <div class="metadata-grid">
          <div class="meta-item">
            <span class="label">IP地址：</span>
            <el-input :model-value="currentMeta.ip_address" readonly class="meta-input" />
          </div>
          <div class="meta-item">
            <span class="label">用户ID：</span>
            <el-input :model-value="currentMeta.user_id_display" readonly class="meta-input" />
          </div>
          <div class="meta-item">
            <span class="label">对话时间：</span>
            <el-input :model-value="currentMeta.timeDisplay" readonly class="meta-input" />
          </div>
          <div class="meta-item">
            <span class="label">RecordID：</span>
            <el-input :model-value="currentMeta.record_id" readonly class="meta-input" />
          </div>
        </div>

        <!-- 对话详情部分 -->
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
import axios from 'axios'
import MarkdownIt from 'markdown-it'
import { ElMessage } from 'element-plus'

const md = new MarkdownIt()
const renderMarkdown = (t) => md.render(t || '')

const historyList = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const detailMessages = ref([])
const currentTitle = ref('')
const selectedRows = ref([])

// 当前详情的元数据
const currentMeta = reactive({
  ip_address: '',
  user_id_display: '',
  timeDisplay: '',
  record_id: ''
})

// 搜索表单
const searchForm = reactive({
  composite: '',
  dateRange: null,
  auditStatus: '',
  processStatus: ''
})

// 演示用 Mock 数据补全
const mockDemoFields = (data) => {
  return data.map((item, index) => ({
    ...item,
    ip_address: `183.230.12.${100 + (index % 150)}`,
    user_id_display: `UID_${2025000 + (index % 1000)}`,
    record_id: `RID_${Date.now().toString().slice(-6)}${index.toString().padStart(3, '0')}`,
    nlg_status: '' // NLG 内容置空
  }))
}

const fetchHistories = async () => {
  loading.value = true
  try {
    const params = {
      search: searchForm.composite,
      start_time: searchForm.dateRange ? searchForm.dateRange[0] : null,
      end_time: searchForm.dateRange ? searchForm.dateRange[1] : null
    }
    const res = await axios.get('/api/history/list', { params })
    // 将 API 原始数据与演示 Mock 字段杂糅
    historyList.value = mockDemoFields(res.data)
  } catch (e) {
    ElMessage.error('获取历史记录失败')
  } finally {
    loading.value = false
  }
}

const resetSearch = () => {
  searchForm.composite = ''
  searchForm.dateRange = null
  searchForm.auditStatus = ''
  searchForm.processStatus = ''
  fetchHistories()
}

const handleSelectionChange = (val) => {
  selectedRows.value = val
}

const viewDetail = async (row) => {
  currentTitle.value = row.title
  // 填充元数据
  currentMeta.ip_address = row.ip_address
  currentMeta.user_id_display = row.user_id_display
  currentMeta.timeDisplay = new Date(row.updatedAt * 1000).toLocaleString()
  currentMeta.record_id = row.record_id

  try {
    const res = await axios.get(`/api/history/${row.id}`)
    detailMessages.value = res.data
    detailVisible.value = true
  } catch (e) {
    ElMessage.error('获取详情失败')
  }
}

// 导出 CSV 逻辑
const exportData = () => {
  const dataToExport = selectedRows.value.length > 0 ? selectedRows.value : historyList.value
  if (dataToExport.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }

  const headers = ['序号', '对话输入', 'IP地址', '用户ID', '对话时间', 'NLG', 'RecordID']
  const rows = dataToExport.map((item, index) => [
    index + 1,
    item.title || '新对话',
    item.ip_address,
    item.user_id_display,
    new Date(item.updatedAt * 1000).toLocaleString(),
    item.nlg_status,
    item.record_id
  ])

  // \ufeff 是 UTF-8 的 BOM，保证 Excel 打开不乱码
  let csvContent = "\ufeff" + headers.join(",") + "\n"
  rows.forEach(row => {
    csvContent += row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(",") + "\n"
  })

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.setAttribute("href", url)
  link.setAttribute("download", `演示数据_对话记录_${new Date().toLocaleDateString()}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

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

/* 详情弹窗样式升级 */
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

.conversation-section {
  .section-title {
    font-size: 16px;
    color: #333;
    margin-bottom: 15px;
    font-weight: 600;
  }
}

.history-detail-list {
  max-height: 50vh;
  overflow-y: auto;
  padding-right: 10px;
}

.detail-msg-wrap {
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;

  .msg-type-label {
    font-size: 15px;
    font-weight: bold;
    color: #333;
  }

  .msg-content-box {
    padding: 12px 0;
    font-size: 14px;
    line-height: 1.6;
    color: #444;
    
    &.user {
      color: #333;
    }
    
    &.assistant {
      color: #555;
      border-top: 1px dashed #eee;
      padding-top: 15px;
    }
  }
}

:deep(.custom-table-header) {
  background-color: #f5f7fa !important;
  color: #606266;
  font-weight: bold;
}
</style>
