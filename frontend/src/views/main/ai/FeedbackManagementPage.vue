<template>
  <div class="feedback-management-container">
    <div class="header-section">
      <div class="title-row">
        <span class="title">{{ pageTitle }}</span>
      </div>
      <el-form :inline="true" class="filter-form">
        <div class="filter-row">
          <el-form-item label="搜索">
            <el-input v-model="filters.search" placeholder="输入反馈人、联系方式、所属企业" style="width: 300px" clearable />
          </el-form-item>
          <el-form-item label="反馈类型">
            <el-select v-model="filters.feedback_type" style="width: 160px">
              <el-option v-for="item in feedbackTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="mode === 'all'" label="处理状态">
            <el-select v-model="filters.process_status" style="width: 140px" clearable>
              <el-option v-for="item in feedbackStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="反馈日期">
            <el-date-picker v-model="filters.dateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="x" style="width: 280px" />
          </el-form-item>
          <el-form-item label="处理日期">
            <el-date-picker v-model="filters.processedDateRange" type="daterange" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" value-format="x" style="width: 280px" />
          </el-form-item>
        </div>
        <div class="button-row">
          <el-button @click="resetFilters">重置</el-button>
          <el-button type="primary" @click="fetchFeedbacks">查询</el-button>
        </div>
        <div class="export-row">
          <el-button type="success" @click="handleExport">导出</el-button>
        </div>
      </el-form>
    </div>

    <el-table :data="feedbackList" v-loading="loading" style="width: 100%; margin-top: 10px" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" />
      <el-table-column type="index" label="序号" width="70" align="center" />
      <el-table-column label="反馈人" width="100">
        <template #default="scope">{{ scope.row.user?.name || '-' }}</template>
      </el-table-column>
      <el-table-column label="联系方式" width="140">
        <template #default="scope">{{ scope.row.user?.phone || '-' }}</template>
      </el-table-column>
      <el-table-column label="所属企业" min-width="160" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.user?.enterprise || '-' }}</template>
      </el-table-column>
      <el-table-column label="反馈类型" min-width="160">
        <template #default="scope">{{ (scope.row.feedback_type?.labels || []).join(' / ') || (scope.row.type === 'dislike' ? '点踩' : '点赞') }}</template>
      </el-table-column>
      <el-table-column label="提交时间" width="180">
        <template #default="scope">{{ scope.row.times?.createdAt || scope.row.createdAt || '-' }}</template>
      </el-table-column>
      <!-- 反馈列表模式：处理状态 + 处理结果 + 处理/详情按钮 -->
      <template v-if="mode === 'all'">
        <el-table-column label="处理状态" width="100" align="center">
          <template #default="scope">{{ scope.row.process_status || '未处理' }}</template>
        </el-table-column>
        <el-table-column label="处理结果" min-width="140" show-overflow-tooltip>
          <template #default="scope">{{ scope.row.process_result || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right" align="center">
          <template #default="scope">
            <el-button v-if="scope.row.process_status === '已处理'" link type="primary" @click="viewDetail(scope.row)">详情</el-button>
            <el-button v-else link type="primary" @click="handleProcessClick(scope.row)">处理</el-button>
          </template>
        </el-table-column>
      </template>
      <!-- 待优化/良好模式：处理人 + 详情+删除按钮 -->
      <template v-else>
        <el-table-column label="处理人" width="120" align="center">
          <template #default="scope">{{ scope.row.processor || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="scope">
            <el-button link type="primary" @click="viewDetail(scope.row)">详情</el-button>
            <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </template>
    </el-table>

    <div class="table-pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        layout="total, prev, pager, next, sizes"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        @current-change="fetchFeedbacks"
        @size-change="fetchFeedbacks"
      />
    </div>

    <el-dialog v-model="detailVisible" :title="isProcessMode ? '反馈处理' : '反馈详情'" width="750px" custom-class="feedback-detail-dialog">
      <div v-if="currentDetail" class="feedback-detail-content">
        <div class="metadata-grid">
          <div class="meta-item"><span class="label">反馈人：</span><el-input :model-value="currentDetail.user?.name || '-'" readonly /></div>
          <div class="meta-item"><span class="label">联系方式：</span><el-input :model-value="currentDetail.user?.phone || '-'" readonly /></div>
          <div class="meta-item"><span class="label">反馈公司：</span><el-input :model-value="currentDetail.user?.enterprise || '-'" readonly /></div>
          <div class="meta-item"><span class="label">反馈类型：</span><el-input :model-value="detailTypeLabel" readonly /></div>
        </div>
        <div class="qa-section">
          <h4 class="section-title">反馈对象：</h4>
          <div class="qa-box">
            <div class="qa-item">
              <span class="prefix">问</span>
              <div class="qa-content">
                <div v-if="currentDetail.uploaded_files?.length" class="qa-file-list">
                  <div v-for="file in currentDetail.uploaded_files" :key="file.file_id || file.filename" class="qa-file-row">
                    <span class="file-name">{{ file.filename }}</span>
                    <el-button link type="primary" @click="downloadFeedbackHistoryFile(file)">下载</el-button>
                  </div>
                </div>
                <p class="text">{{ currentDetail.question }}</p>
              </div>
            </div>
            <div class="qa-item"><span class="prefix">答</span><p class="text">{{ currentDetail.answer }}</p></div>
          </div>
        </div>
        <div class="description-section">
          <h4 class="section-title">更多描述：</h4>
          <el-input type="textarea" :model-value="currentDetail.comment || '用户未填写额外描述'" readonly rows="2" />
        </div>
        <div class="image-section" v-if="currentDetail.pictures?.length">
          <h4 class="section-title">附件图片：</h4>
          <div class="image-list">
            <el-image
              v-for="(item, index) in currentDetail.pictures"
              :key="item"
              class="feedback-img"
              :src="currentDetail.picture_urls?.[index] || ''"
              :preview-src-list="currentDetail.picture_urls || []"
              fit="cover"
            />
          </div>
        </div>
        <el-divider />
        <div class="process-section">
          <h4 class="section-title">处理结果</h4>
          <div v-if="isProcessMode">
            <el-select v-model="processResult" placeholder="请选择处理结果" style="width: 100%">
              <el-option v-for="item in processResultOptions" :key="item" :label="item" :value="item" />
              <el-option label="删除" value="删除" />
            </el-select>
          </div>
          <div v-else>
            <el-select :model-value="'已' + (currentDetail.process_result || '')" disabled style="width: 100%">
              <el-option :label="'已' + (currentDetail.process_result || '')" :value="'已' + (currentDetail.process_result || '')" />
            </el-select>
          </div>
        </div>
      </div>
      <template #footer v-if="isProcessMode">
        <el-button @click="detailVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProcess" :disabled="!processResult">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiApi, buildHistoryFileDownloadUrl } from '@/api/ai'

const route = useRoute()
const mode = computed(() => route.meta.mode || 'all')

const feedbackOptions = reactive({
  question_issues: {},
  answer_effects: {},
  report_reasons: {},
  type_options: [{ label: '全部', value: '全部' }],
  status_options: [{ label: '全部', value: '' }],
  process_results: [{ label: '录入待优化回答', value: '录入待优化回答' }, { label: '录入良好回答', value: '录入良好回答' }],
})

async function loadFeedbackOptions() {
  try {
    const data = await aiApi.getFeedbackOptions()
    Object.assign(feedbackOptions, data)
  } catch (e) {
    console.error('加载反馈选项失败:', e)
  }
}

const PAGE_META = {
  all: { title: '反馈列表', type: '', processResult: '' },
  negative: { title: '待优化回答', type: '', processResult: '录入待优化回答' },
  positive: { title: '良好回答', type: '', processResult: '录入良好回答' },
}

const feedbackList = ref([])
const selectedRows = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const currentDetail = ref(null)
const pagination = reactive({ page: 1, size: 10, total: 0 })
const filters = reactive({ search: '', type: PAGE_META[mode.value]?.type || '', process_status: '', process_result: PAGE_META[mode.value]?.processResult || '', feedback_type: '全部', dateRange: null, processedDateRange: null })

const isProcessMode = ref(false)
const processResult = ref('')
const processingId = ref('')

const pageTitle = computed(() => PAGE_META[mode.value]?.title || '反馈列表')
const feedbackTypeOptions = computed(() => feedbackOptions.type_options)
const feedbackStatusOptions = computed(() => feedbackOptions.status_options)
const processResultOptions = computed(() => feedbackOptions.process_results.map((item) => typeof item === 'string' ? item : item.label))
const detailTypeLabel = computed(() => {
  if (!currentDetail.value) return '-'
  const labels = currentDetail.value.feedback_type?.labels || []
  if (labels.length) return labels.join(' / ')
  return currentDetail.value.type === 'dislike' ? '点踩' : '点赞'
})

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

function applyModeDefaults() {
  filters.type = PAGE_META[mode.value]?.type || ''
  filters.process_result = PAGE_META[mode.value]?.processResult || ''
  filters.feedback_type = '全部'
  filters.process_status = ''
  filters.search = ''
  filters.dateRange = null
}

function buildSearchParams() {
  const params = {
    search: filters.search || '',
    feedback_type: filters.feedback_type || '全部',
    process_status: filters.process_status || '',
    process_result: filters.process_result || '',
    start_time: filters.dateRange?.[0] || undefined,
    end_time: filters.dateRange?.[1] || undefined,
    processed_start_time: filters.processedDateRange?.[0] || undefined,
    processed_end_time: filters.processedDateRange?.[1] || undefined,
  }
  if (filters.type) params.type = filters.type
  return params
}

async function fetchFeedbacks() {
  loading.value = true
  try {
    const params = {
      ...buildSearchParams(),
      page: pagination.page,
      size: pagination.size,
    }
    const data = await aiApi.listFeedbacks(params)
    const list = data.list || []
    feedbackList.value = list
    pagination.total = data.total || 0
    pagination.page = data.page || pagination.page
    pagination.size = data.size || pagination.size
  } catch (error) {
    ElMessage.error(error.message || '获取反馈列表失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.search = ''
  filters.process_status = ''
  filters.dateRange = null
  filters.processedDateRange = null
  pagination.page = 1
  pagination.size = 10
  applyModeDefaults()
  fetchFeedbacks()
}

async function handleExport() {
  try {
    const params = buildSearchParams()
    if (selectedRows.value.length) {
      params.ids = selectedRows.value.map((row) => row.id)
    }
    const response = await fetch('/api/feedback/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.msg || '导出失败')
    }
    const blob = await response.blob()
    const disposition = response.headers.get('content-disposition') || ''
    const rfc5987 = disposition.match(/filename\*=UTF-8''([^;]+)/i)
    let filename = '反馈导出.xlsx'
    if (rfc5987?.[1]) {
      try { filename = decodeURIComponent(rfc5987[1]) } catch { /* ignore */ }
    } else {
      const basic = disposition.match(/filename="?([^";]+)"?/i)
      if (basic?.[1]) filename = basic[1]
    }
    triggerBlobDownload(blob, filename)
  } catch (error) {
    ElMessage.error(error.message || '导出失败')
  }
}

async function openDetail(row, processMode) {
  try {
    currentDetail.value = await aiApi.getFeedbackDetail(row.id)
    isProcessMode.value = processMode
    processResult.value = ''
    processingId.value = row.id
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(error.message || '获取详情失败')
  }
}

function viewDetail(row) {
  openDetail(row, false)
}

function handleProcessClick(row) {
  openDetail(row, true)
}

async function downloadFeedbackHistoryFile(file) {
  try {
    const url = buildHistoryFileDownloadUrl(currentDetail.value?.conversation_id, currentDetail.value?.message_index, file.file_id)
    const { blob, filename } = await aiApi.downloadByUrl(url, '下载附件失败')
    triggerBlobDownload(blob, filename || file.filename || '附件')
  } catch (error) {
    ElMessage.error(error.message || '下载附件失败')
  }
}

async function submitProcess() {
  if (!processResult.value) {
    ElMessage.warning('请选择处理结果')
    return
  }
  if (processResult.value === '删除') {
    await handleDeleteFromProcess()
    return
  }
  try {
    await aiApi.processFeedback({
      id: processingId.value,
      process_result: processResult.value,
    })
    detailVisible.value = false
    await fetchFeedbacks()
    ElMessage.success('处理成功')
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  }
}

async function handleDeleteFromProcess() {
  try {
    await ElMessageBox.confirm('确定删除该反馈吗？', '警告', { type: 'warning' })
    await aiApi.batchDeleteFeedback([processingId.value])
    detailVisible.value = false
    await fetchFeedbacks()
    ElMessage.success('已删除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该反馈吗？', '警告', { type: 'warning' })
    await aiApi.batchDeleteFeedback([row.id])
    await fetchFeedbacks()
    ElMessage.success('已删除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

applyModeDefaults()
watch(mode, () => {
  applyModeDefaults()
  pagination.page = 1
  fetchFeedbacks()
})

onMounted(() => {
  loadFeedbackOptions()
  fetchFeedbacks()
})
</script>

<style scoped lang="less">
@import "./feedback-shared.less";

.filter-form {
  background: #fcfcfc;
  padding: 24px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  .filter-row { display: flex; flex-wrap: wrap; gap: 8px; }
  .button-row { margin-top: 16px; display: flex; gap: 12px; }
  .export-row { margin-top: 16px; }
}

.qa-content { flex: 1; }
.qa-file-list { margin-bottom: 8px; display: flex; flex-direction: column; gap: 4px; }
.qa-file-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.qa-file-row .file-name { font-size: 13px; color: #606266; }
</style>
