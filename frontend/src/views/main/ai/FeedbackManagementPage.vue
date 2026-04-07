<template>
  <div class="feedback-management-container">
    <div class="header-section">
      <div class="title-row">
        <span class="title">{{ pageTitle }}</span>
      </div>
      <div class="filter-toolbar">
        <el-input v-model="filters.name" placeholder="反馈人姓名" class="filter-item" clearable />
        <el-input v-model="filters.enterprise" placeholder="所属企业" class="filter-item" clearable />
        <el-select v-if="showTypeFilter" v-model="filters.type" placeholder="反馈主类型" class="filter-item" style="width: 160px" clearable>
          <el-option label="全部" value="" />
          <el-option label="待优化回答" value="dislike" />
          <el-option label="良好回答" value="like" />
        </el-select>
        <el-select v-model="filters.feedback_type" placeholder="反馈细分类型" class="filter-item" style="width: 180px">
          <el-option v-for="item in feedbackTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select
          v-if="showReasonFilter"
          v-model="reasonKeyword"
          placeholder="反馈原因分类"
          class="filter-item"
          style="width: 220px"
          clearable
        >
          <el-option label="全部" value="" />
          <el-option-group label="针对问题">
            <el-option v-for="item in REASON_MAP.question" :key="item" :label="item" :value="item" />
          </el-option-group>
          <el-option-group label="针对回答效果">
            <el-option v-for="item in REASON_MAP.answer" :key="item" :label="item" :value="item" />
          </el-option-group>
          <el-option-group label="举报">
            <el-option v-for="item in REASON_MAP.report" :key="item" :label="item" :value="item" />
          </el-option-group>
        </el-select>
        <el-button type="primary" @click="fetchFeedbacks">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </div>

    <el-table :data="feedbackList" v-loading="loading" style="width: 100%; margin-top: 20px">
      <el-table-column type="index" label="序号" width="70" align="center" />
      <el-table-column label="反馈人" width="120">
        <template #default="scope">{{ scope.row.user?.name || '-' }}</template>
      </el-table-column>
      <el-table-column label="所属企业" width="180" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.user?.enterprise || '-' }}</template>
      </el-table-column>
      <el-table-column label="反馈分类" width="150" align="center">
        <template #default="scope">{{ scope.row.type === 'dislike' ? '待优化回答' : '良好回答' }}</template>
      </el-table-column>
      <el-table-column label="原因" min-width="220">
        <template #default="scope">
          <template v-if="scope.row.reasons?.length">
            <el-tag v-for="item in scope.row.reasons || []" :key="item" size="small" style="margin-right: 4px">{{ item }}</el-tag>
          </template>
          <span v-else>{{ scope.row.feedback_type?.primary || (scope.row.type === 'dislike' ? '点踩' : '点赞') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="处理状态" width="120" align="center">
        <template #default="scope">
          <el-tag
            :type="scope.row.process_status === '已处理' ? 'success' : 'danger'"
            :effect="scope.row.process_status === '已处理' ? 'light' : 'plain'"
            style="cursor: pointer"
            @click="handleProcessClick(scope.row)"
          >
            {{ scope.row.process_status || '未处理' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="处理人" width="120" align="center">
        <template #default="scope">{{ scope.row.processor || '-' }}</template>
      </el-table-column>
      <el-table-column label="提交时间" width="180">
        <template #default="scope">{{ scope.row.times?.createdAt || scope.row.createdAt || '-' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right" align="center">
        <template #default="scope">
          <el-button link type="primary" @click="viewDetail(scope.row)">详情</el-button>
          <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
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

    <el-dialog v-model="processVisible" title="反馈处理" width="400px">
      <el-form label-position="top">
        <el-form-item label="处理人姓名" required>
          <el-input v-model="processForm.processor" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="processForm.is_collect">{{ collectLabel }}</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="processVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProcess">确认收录</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="detailVisible" title="反馈详情" width="750px" custom-class="feedback-detail-dialog">
      <div v-if="currentDetail" class="feedback-detail-content">
        <div class="metadata-grid">
          <div class="meta-item"><span class="label">反馈人：</span><el-input :model-value="currentDetail.user?.name || '-'" readonly /></div>
          <div class="meta-item"><span class="label">联系方式：</span><el-input :model-value="currentDetail.user?.phone || '-'" readonly /></div>
          <div class="meta-item"><span class="label">反馈公司：</span><el-input :model-value="currentDetail.user?.enterprise || '-'" readonly /></div>
          <div class="meta-item"><span class="label">反馈类型：</span><el-input :model-value="detailTypeLabel" readonly /></div>
          <div class="meta-item"><span class="label">RecordID：</span><el-input :model-value="currentDetail.user?.record_id || currentDetail.record_id || '-'" readonly /></div>
          <div class="meta-item"><span class="label">UserID：</span><el-input :model-value="currentDetail.user?.user_id || currentDetail.user_id || '-'" readonly /></div>
        </div>
        <div class="qa-section">
          <h4 class="section-title">反馈对象：</h4>
          <div class="qa-box">
            <div class="qa-item"><span class="prefix">问</span><p class="text">{{ currentDetail.question }}</p></div>
            <div class="qa-item"><span class="prefix">答</span><p class="text">{{ currentDetail.answer }}</p></div>
          </div>
        </div>
        <div class="description-section">
          <h4 class="section-title">更多描述：</h4>
          <el-input type="textarea" :model-value="currentDetail.comment || '用户未填写额外描述'" readonly rows="2" />
        </div>
        <div class="download-section" v-if="currentDetail.uploaded_files?.length">
          <h4 class="section-title">原始提问附件：</h4>
          <div class="download-file-list">
            <div v-for="file in currentDetail.uploaded_files" :key="file.file_id || file.filename" class="download-file-row">
              <span class="file-name">{{ file.filename }}</span>
              <el-button link type="primary" @click="downloadFeedbackHistoryFile(file)">下载</el-button>
            </div>
          </div>
        </div>
        <div class="image-section" v-if="currentDetail.pictures?.length">
          <h4 class="section-title">附件图片：</h4>
          <div class="image-list">
            <el-image
              v-for="item in currentDetail.pictures"
              :key="item"
              class="feedback-img"
              :src="buildPictureUrl(currentDetail, item)"
              :preview-src-list="currentDetail.pictures.map((name) => buildPictureUrl(currentDetail, name)).filter(Boolean)"
              fit="cover"
            />
          </div>
        </div>
        <el-divider />
        <div class="process-section">
          <h4 class="section-title process-title">处理信息</h4>
          <div class="meta-item full-width"><span class="label"><span class="required">*</span> 处理结果：</span><el-input :model-value="currentDetail.process_result || '未处理'" readonly /></div>
          <div class="meta-item full-width" v-if="currentDetail.processor"><span class="label">处理人：</span><el-input :model-value="currentDetail.processor" readonly /></div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiApi, buildFeedbackPictureUrl, buildHistoryFileDownloadUrl } from '@/api/ai'

const props = defineProps({
  mode: {
    type: String,
    default: 'all',
  },
})

const REASON_MAP = {
  question: ['不理解问题', '遗忘上下文', '未遵循要求'],
  answer: ['回答错误', '逻辑混乱', '时效性差', '可读性差', '回答不完整', '回答笼统不专业'],
  report: ['色情低俗', '政治敏感', '违法犯罪', '歧视或偏见回答', '侵犯隐私', '内容侵权'],
}

const PAGE_META = {
  all: { title: '反馈列表', type: '' },
  negative: { title: '待优化回答', type: 'dislike' },
  positive: { title: '良好回答', type: 'like' },
}

const feedbackList = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const currentDetail = ref(null)
const reasonKeyword = ref('')
const pagination = reactive({ page: 1, size: 10, total: 0 })
const filters = reactive({ name: '', enterprise: '', type: PAGE_META[props.mode]?.type || '', feedback_type: '全部' })

const processVisible = ref(false)
const processForm = reactive({ id: '', processor: '', is_collect: false, type: '' })

const pageTitle = computed(() => PAGE_META[props.mode]?.title || '反馈列表')
const showTypeFilter = computed(() => props.mode === 'all')
const showReasonFilter = computed(() => props.mode !== 'positive')
const feedbackTypeOptions = computed(() => {
  const common = [{ label: '全部', value: '全部' }]
  if (props.mode === 'positive') {
    return [...common, { label: '点赞', value: '点赞' }, { label: '针对回答效果', value: '针对回答效果' }]
  }
  if (props.mode === 'negative') {
    return [...common, { label: '点踩', value: '点踩' }, { label: '针对问题', value: '针对问题' }, { label: '针对回答效果', value: '针对回答效果' }, { label: '举报', value: '举报' }]
  }
  return [...common, { label: '点赞', value: '点赞' }, { label: '点踩', value: '点踩' }, { label: '针对问题', value: '针对问题' }, { label: '针对回答效果', value: '针对回答效果' }, { label: '举报', value: '举报' }]
})
const collectLabel = computed(() => processForm.type === 'like' ? '是否收录于优秀回答' : '是否收录于负面回答')
const detailTypeLabel = computed(() => {
  if (!currentDetail.value) return '-'
  const labels = currentDetail.value.feedback_type?.labels || []
  if (labels.length) return labels.join(' / ')
  return currentDetail.value.type === 'dislike' ? '点踩' : '点赞'
})

function buildPictureUrl(detail, filename) {
  return buildFeedbackPictureUrl(detail, filename)
}

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

function applyModeDefaults() {
  filters.type = PAGE_META[props.mode]?.type || ''
  filters.feedback_type = '全部'
}

async function fetchFeedbacks() {
  loading.value = true
  try {
    const params = {
      ...filters,
      page: pagination.page,
      size: pagination.size,
    }
    if (!params.type) delete params.type
    const data = await aiApi.listFeedbacks(params)
    const list = data.list || []
    feedbackList.value = reasonKeyword.value ? list.filter((item) => (item.reasons || []).includes(reasonKeyword.value)) : list
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
  filters.name = ''
  filters.enterprise = ''
  reasonKeyword.value = ''
  pagination.page = 1
  pagination.size = 10
  applyModeDefaults()
  fetchFeedbacks()
}

async function viewDetail(row) {
  try {
    currentDetail.value = await aiApi.getFeedbackDetail(row.id)
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(error.message || '获取详情失败')
  }
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

function handleProcessClick(row) {
  if (row.process_status === '已处理') return
  processForm.id = row.id
  processForm.processor = ''
  processForm.is_collect = false
  processForm.type = row.type || ''
  processVisible.value = true
}

async function submitProcess() {
  if (!processForm.processor.trim()) {
    ElMessage.warning('请填写处理人姓名')
    return
  }
  try {
    await aiApi.processFeedback({
      id: processForm.id,
      processor: processForm.processor,
      is_collect: processForm.is_collect,
    })
    processVisible.value = false
    await fetchFeedbacks()
    ElMessage.success('处理成功')
  } catch (error) {
    ElMessage.error(error.message || '操作失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除吗？', '警告', { type: 'warning' })
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
onMounted(fetchFeedbacks)
</script>

<style scoped lang="less">
@import "./feedback-shared.less";
</style>
