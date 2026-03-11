<template>
  <div class="feedback-management-container">
    <div class="header-section">
      <div class="title-row">
        <span class="title">正向反馈记录维护 (点赞)</span>
      </div>
      <div class="filter-toolbar">
        <el-input v-model="filters.name" placeholder="反馈人姓名" class="filter-item" clearable />
        <el-input v-model="filters.enterprise" placeholder="所属企业" class="filter-item" clearable />
        <el-select v-model="filters.type" placeholder="反馈类型" class="filter-item" clearable>
          <el-option label="全部" value="like" />
          <el-option label="用户点赞" value="like" />
        </el-select>
        <el-button type="primary" @click="fetchFeedbacks">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </div>

    <el-table :data="feedbackList" v-loading="loading" style="width: 100%; margin-top: 20px">
      <el-table-column type="index" label="序号" width="70" align="center" />
      <el-table-column prop="contact_name" label="反馈人" width="120" />
      <el-table-column prop="enterprise" label="所属企业" width="180" show-overflow-tooltip />
      <el-table-column label="原因" width="150">
        <template #default>用户点赞</template>
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
      <el-table-column prop="processor" label="处理人" width="120" align="center" />
      <el-table-column prop="createdAt" label="提交时间" width="180" />
      <el-table-column label="操作" width="120" fixed="right" align="center">
        <template #default="scope">
          <el-button link type="primary" @click="viewDetail(scope.row)">详情</el-button>
          <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 处理弹窗 -->
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="反馈详情" width="750px" custom-class="feedback-detail-dialog">
      <div v-if="currentDetail" class="feedback-detail-content">
        <div class="metadata-grid">
          <div class="meta-item">
            <span class="label">反馈人：</span>
            <el-input :model-value="currentDetail.contact_name" readonly />
          </div>
          <div class="meta-item">
            <span class="label">联系方式：</span>
            <el-input :model-value="currentDetail.contact_phone" readonly />
          </div>
          <div class="meta-item">
            <span class="label">反馈公司：</span>
            <el-input :model-value="currentDetail.enterprise" readonly />
          </div>
          <div class="meta-item">
            <span class="label">反馈类型：</span>
            <el-input model-value="正向反馈" readonly />
          </div>
        </div>
        <div class="qa-section">
          <h4 class="section-title">反馈对象：</h4>
          <div class="qa-box">
            <div class="qa-item"><span class="prefix">问</span><p class="text">{{ currentDetail.target_question }}</p></div>
            <div class="qa-item"><span class="prefix">答</span><p class="text">{{ currentDetail.target_answer }}</p></div>
          </div>
        </div>
        <div class="description-section">
          <h4 class="section-title">更多描述：</h4>
          <el-input type="textarea" :model-value="currentDetail.comment" readonly rows="2" />
        </div>
        <el-divider />
        <div class="process-section">
          <h4 class="section-title process-title">处理信息</h4>
          <div class="meta-item full-width">
            <span class="label"><span class="required">*</span> 处理结果：</span>
            <el-input :model-value="currentDetail.process_result || '未处理'" readonly />
          </div>
          <div class="meta-item full-width" v-if="currentDetail.processor">
            <span class="label">处理人：</span>
            <el-input :model-value="currentDetail.processor" readonly />
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

const feedbackList = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const currentDetail = ref(null)
const filters = reactive({ name: '', enterprise: '', type: 'like' })

const processVisible = ref(false)
const processForm = reactive({ id: '', date_path: '', processor: '', is_collect: false })

const fetchFeedbacks = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/feedback/list', { params: filters })
    feedbackList.value = res.data
  } finally { loading.value = false }
}

const resetFilters = () => {
  filters.name = ''; filters.enterprise = ''; filters.type = 'like';
  fetchFeedbacks()
}

const viewDetail = (row) => {
  currentDetail.value = row; detailVisible.value = true;
}

const handleProcessClick = (row) => {
  if (row.process_status === '已处理') return
  processForm.id = row.id
  processForm.date_path = row.date_path
  processForm.processor = ''
  processForm.is_collect = false
  processVisible.value = true
}

const submitProcess = async () => {
  if (!processForm.processor) return ElMessage.warning('请填写处理人姓名')
  try {
    await axios.post('/api/feedback/process', processForm)
    ElMessage.success('处理成功')
    processVisible.value = false
    fetchFeedbacks()
  } catch (e) { ElMessage.error('操作失败') }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除吗？', '警告', { type: 'warning' })
    await axios.delete(`/api/feedback/${row.date_path}/${row.id}`)
    ElMessage.success('已删除')
    fetchFeedbacks()
  } catch (e) {}
}

onMounted(fetchFeedbacks)
</script>

<style scoped lang="less">
@import "./feedback-shared.less";
</style>
