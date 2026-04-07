<template>
  <div class="feedback-management-container">
    <div class="header-section">
      <div class="title-row">
        <span class="title">正向反馈记录维护 (点赞)</span>
      </div>
      <div class="filter-toolbar">
        <el-input v-model="filters.name" placeholder="反馈人姓名" class="filter-item" clearable />
        <el-input v-model="filters.enterprise" placeholder="所属企业" class="filter-item" clearable />
        <el-select v-model="filters.feedback_type" class="filter-item" style="width: 180px">
          <el-option label="点赞" value="点赞" />
          <el-option label="针对回答效果" value="针对回答效果" />
          <el-option label="全部" value="全部" />
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
      <el-table-column label="原因" width="150">
        <template #default="scope">{{ scope.row.feedback_type?.primary || '点赞' }}</template>
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
          <el-checkbox v-model="processForm.is_collect">是否收录于优秀回答</el-checkbox>
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
          <div class="meta-item"><span class="label">反馈类型：</span><el-input :model-value="(currentDetail.feedback_type?.labels || ['点赞']).join(' / ')" readonly /></div>
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiApi } from '@/api/ai'

const feedbackList = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const currentDetail = ref(null)
const filters = reactive({ name: '', enterprise: '', type: 'like', feedback_type: '点赞' })
const pagination = reactive({ page: 1, size: 10, total: 0 })

const processVisible = ref(false)
const processForm = reactive({ id: '', processor: '', is_collect: false })

async function fetchFeedbacks() {
  loading.value = true
  try {
    const data = await aiApi.listFeedbacks({
      ...filters,
      page: pagination.page,
      size: pagination.size,
    })
    feedbackList.value = data.list || []
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
  filters.type = 'like'
  filters.feedback_type = '点赞'
  pagination.page = 1
  pagination.size = 10
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

function handleProcessClick(row) {
  if (row.process_status === '已处理') return
  processForm.id = row.id
  processForm.processor = ''
  processForm.is_collect = false
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

onMounted(fetchFeedbacks)
</script>

<style scoped lang="less">
@import "./feedback-shared.less";
</style>
