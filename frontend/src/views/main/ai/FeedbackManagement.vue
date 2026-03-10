<template>
  <div class="feedback-management-container">
    <div class="header-section">
      <div class="title-row">
        <span class="title">反馈记录维护</span>
      </div>
      <!-- 筛选工具栏 -->
      <div class="filter-toolbar">
        <el-input v-model="filters.name" placeholder="反馈人姓名" class="filter-item" clearable />
        <el-input v-model="filters.enterprise" placeholder="所属企业" class="filter-item" clearable />
        <el-select v-model="filters.reason" placeholder="反馈分类 (点踩原因)" class="filter-item" clearable>
          <el-option label="回答不准确" value="回答不准确" />
          <el-option label="内容不完整" value="内容不完整" />
          <el-option label="逻辑混乱" value="逻辑混乱" />
          <el-option label="其他" value="其他" />
        </el-select>
        <el-button type="primary" @click="fetchFeedbacks">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <el-button type="danger" :disabled="selectedItems.length === 0" @click="handleBatchDelete">
          批量删除 ({{ selectedItems.length }})
        </el-button>
      </div>
    </div>

    <!-- 列表展示 -->
    <el-table 
      :data="feedbackList" 
      v-loading="loading" 
      style="width: 100%; margin-top: 20px"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" />
      <el-table-column prop="contact_name" label="反馈人" width="150" />
      <el-table-column prop="enterprise" label="所属企业" width="180" show-overflow-tooltip />
      <el-table-column label="原因" min-width="200">
        <template #default="scope">
          <el-tag v-for="r in scope.row.reasons" :key="r" size="small" style="margin-right: 4px">{{ r }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="comment" label="文字描述" min-width="250" show-overflow-tooltip />
      <el-table-column prop="createdAt" label="提交时间" width="180" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="viewDetail(scope.row)">详情</el-button>
          <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="反馈详情" width="650px">
      <div v-if="currentDetail" class="feedback-detail">
        <div class="info-grid">
          <div><span class="label">反馈人:</span> {{ currentDetail.contact_name }}</div>
          <div><span class="label">联系方式:</span> {{ currentDetail.contact_phone || '未填写' }}</div>
          <div><span class="label">企业:</span> {{ currentDetail.enterprise || '未填写' }}</div>
          <div><span class="label">时间:</span> {{ currentDetail.createdAt }}</div>
        </div>
        <el-divider />
        <div class="detail-row">
          <span class="label">详细描述:</span>
          <p class="comment-box">{{ currentDetail.comment || '无描述' }}</p>
        </div>
        <div class="detail-row" v-if="currentDetail.images?.length">
          <span class="label">图片附件:</span>
          <div class="image-gallery">
            <el-image 
              v-for="img in currentDetail.images" 
              :key="img"
              class="thumb-img"
              :src="'/api/static/feedbacks/' + currentDetail.date_path + '/' + currentDetail.id + '/' + img"
              :preview-src-list="currentDetail.images.map(i => '/api/static/feedbacks/' + currentDetail.date_path + '/' + currentDetail.id + '/' + i)"
              fit="cover"
            />
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessageBox, ElMessage } from 'element-plus'

const feedbackList = ref([])
const loading = ref(false)
const detailVisible = ref(false)
const currentDetail = ref(null)
const selectedItems = ref([])

const filters = reactive({ name: '', enterprise: '', reason: '' })

const fetchFeedbacks = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/feedback/list', { params: filters })
    feedbackList.value = res.data
  } finally {
    loading.value = false 
  }
}

const resetFilters = () => {
  filters.name = ''; filters.enterprise = ''; filters.reason = '';
  fetchFeedbacks()
}

const handleSelectionChange = (val) => {
  selectedItems.value = val
}

const viewDetail = (row) => {
  currentDetail.value = row; detailVisible.value = true;
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这条反馈记录吗？删除后无法恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
    const date = row.date_path
    const id = row.id
    await axios.delete(`/api/feedback/${date}/${id}`)
    ElMessage.success('删除成功')
    fetchFeedbacks()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedItems.value.length} 条记录吗？`, '警告', {
      type: 'warning'
    })
    const itemsToDelete = selectedItems.value.map(item => ({ date: item.date_path, id: item.id }))
    await axios.post('/api/feedback/batch_delete', { items: itemsToDelete })
    ElMessage.success('批量删除成功')
    fetchFeedbacks()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('批量删除失败')
  }
}

onMounted(fetchFeedbacks)
</script>

<style scoped lang="less">
.feedback-management-container { padding: 24px; background: #fff; }
.header-section { margin-bottom: 24px; .title-row { margin-bottom: 16px; .title { font-size: 20px; font-weight: 600; color: #333; } } }
.filter-toolbar { display: flex; gap: 12px; align-items: center; background: #f9f9f9; padding: 16px; border-radius: 8px; .filter-item { width: 180px; } }
.feedback-detail { .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 14px; .label { color: #999; margin-right: 8px; } } .detail-row { margin-top: 16px; .label { font-size: 14px; color: #999; display: block; margin-bottom: 8px; } .comment-box { background: #f5f7fa; padding: 12px; border-radius: 6px; margin: 0; } } .image-gallery { display: flex; gap: 10px; margin-top: 10px; .thumb-img { width: 100px; height: 100px; border-radius: 4px; cursor: pointer; } } }
</style>
