<template>
  <div class="kb-management-container">
    <div class="header-section">
      <span class="title">知识库列表</span>
      <div class="header-actions">
        <el-button @click="fetchKBList">刷新</el-button>
        <el-button type="primary" @click="handleAdd">新增知识库</el-button>
      </div>
    </div>

    <el-table :data="kbList" style="width: 100%" v-loading="loading" stripe header-cell-class-name="kb-table-header">
      <el-table-column prop="name" label="知识库名称" min-width="180" />
      <el-table-column prop="fileCount" label="文件数量" width="100" align="center" />
      <el-table-column label="使用人" min-width="220">
        <template #default="scope">
          <span class="users-link" @click="handleEdit(scope.row)">{{ formatUsers(scope.row.users) || '暂未分配' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
      <el-table-column prop="updatedAt" label="更新时间" width="180" />
      <el-table-column label="状态" width="120" align="center">
        <template #default="scope">
          <el-switch v-model="scope.row.enabled" inline-prompt class="status-switch" @change="handleStatusChange(scope.row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right" align="center">
        <template #default="scope">
          <el-button link type="primary" @click="handleEdit(scope.row)">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="footer-actions">
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          layout="total, prev, pager, next, sizes"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          @current-change="fetchKBList"
          @size-change="fetchKBList"
        />
      </div>
    </div>

    <el-dialog v-model="addVisible" title="添加知识库" width="450px" align-center>
      <el-form :model="addForm" label-width="100px">
        <el-form-item label="知识库名称:" required><el-input v-model="addForm.name" /></el-form-item>
        <el-form-item label="向量模型:">
          <el-select v-model="addForm.model" placeholder="请选择">
            <el-option label="OpenAI - Text Embedding 3" value="openai" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmAdd">确认</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="知识库维护" width="820px" top="5vh" custom-class="kb-edit-dialog">
      <div class="edit-dialog-content">
        <div class="basic-grid">
          <div class="basic-item">
            <span class="label">知识库名称</span>
            <el-input v-model="editForm.name" />
          </div>
          <div class="basic-item status-item">
            <span class="label">状态</span>
            <el-switch v-model="editForm.enabled" class="blue-switch" />
          </div>
        </div>

        <el-form :model="editForm" label-position="top" style="margin-top: 16px">
          <el-form-item label="知识库备注">
            <el-input v-model="editForm.remark" type="textarea" rows="4" placeholder="请输入备注或使用说明" />
          </el-form-item>
        </el-form>

        <div class="user-editor">
          <div class="section-head">
            <span>使用人</span>
          </div>
          <div class="user-tags">
            <el-tag v-for="item in editForm.users" :key="item" closable @close="removeUser(item)">{{ item }}</el-tag>
            <el-input v-model="userDraft" class="user-input" placeholder="输入姓名后回车添加" @keyup.enter="appendUser" />
          </div>
        </div>

        <div class="file-section">
          <div class="section-head">
            <span>知识库文件</span>
            <div class="section-actions">
              <el-tag v-if="hasPendingChanges" type="warning" effect="light">
                待提交变更: 删除 {{ pendingDeleteFileNames.length }} 个 / 上传 {{ pendingUploadFiles.length }} 个
              </el-tag>
              <el-button size="small" :disabled="!hasPendingChanges" @click="resetPendingChanges">撤销暂存</el-button>
              <el-button size="small" type="danger" :disabled="selectedFileNames.length === 0" @click="deleteSelectedFiles">批量删除</el-button>
            </div>
          </div>

          <el-upload class="kb-uploader-box" drag multiple :show-file-list="false" :http-request="uploadFileRequest">
            <el-icon class="el-icon--upload"><FolderOpened /></el-icon>
            <div class="el-upload__text">点击或拖拽上传文件</div>
          </el-upload>

          <el-table :data="displayFiles" style="width: 100%; margin-top: 20px" size="small" border header-cell-class-name="sub-table-header" @selection-change="handleFileSelectionChange">
            <el-table-column type="selection" width="40" />
            <el-table-column label="文件名">
              <template #default="scope">
                <span :class="{ 'pending-delete-name': isPendingDelete(scope.row.name), 'pending-upload-name': scope.row.__pendingUpload }">{{ scope.row.name }}</span>
                <el-tag v-if="scope.row.__pendingUpload" size="small" type="success" style="margin-left: 6px">待上传</el-tag>
                <el-tag v-if="isPendingDelete(scope.row.name)" size="small" type="danger" style="margin-left: 6px">待删除</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="文件大小" width="100" align="center">
              <template #default="scope">{{ formatFileSize(scope.row.size) }}</template>
            </el-table-column>
            <el-table-column prop="uploadedAt" label="上传时间" width="180" align="center" />
            <el-table-column label="操作" width="90" align="center">
              <template #default="scope">
                <el-button v-if="scope.row.__pendingUpload" link type="warning" @click="removePendingUpload(scope.row.name)">撤销</el-button>
                <el-button v-else-if="isPendingDelete(scope.row.name)" link type="warning" @click="restoreFile(scope.row.name)">恢复</el-button>
                <el-button v-else link type="danger" @click="deleteFile(scope.row.name)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleCancelEdit">取消</el-button>
          <el-button type="primary" @click="confirmEdit" class="confirm-btn">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { FolderOpened } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiApi } from '@/api/ai'

const loading = ref(false)
const total = ref(0)
const kbList = ref([])
const currentFiles = ref([])
const selectedFileNames = ref([])
const pendingUploadFiles = ref([])
const pendingDeleteFileNames = ref([])
const pagination = reactive({ page: 1, size: 10 })

const formatUsers = (users = []) => users.map((item) => item?.name || item).join(', ')
const formatFileSize = (size) => typeof size === 'number' ? `${(size / 1024).toFixed(1)} KB` : size || '-'
const hasPendingChanges = computed(() => pendingUploadFiles.value.length > 0 || pendingDeleteFileNames.value.length > 0)
const displayFiles = computed(() => {
  const deleteSet = new Set(pendingDeleteFileNames.value)
  const baseFiles = currentFiles.value.map((item) => ({ ...item, __pendingUpload: false })).filter((item) => !deleteSet.has(item.name))
  const stagedUploads = pendingUploadFiles.value.map((file) => ({
    name: file.name,
    size: file.size,
    uploadedAt: '待提交',
    __pendingUpload: true,
  }))
  return [...baseFiles, ...stagedUploads]
})

function isPendingDelete(filename) {
  return pendingDeleteFileNames.value.includes(filename)
}

async function fetchKBList() {
  loading.value = true
  try {
    const data = await aiApi.listKnowledgeBases({ page: pagination.page, size: pagination.size })
    kbList.value = data.list || []
    total.value = data.total || kbList.value.length
    pagination.page = data.page || pagination.page
    pagination.size = data.size || pagination.size
  } catch (error) {
    ElMessage.error(error.message || '获取知识库列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchKBList)

const addVisible = ref(false)
const addForm = reactive({ name: '', model: 'openai' })

function handleAdd() {
  addVisible.value = true
}

async function confirmAdd() {
  if (!addForm.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  const formData = new FormData()
  formData.append('name', addForm.name)
  formData.append('model', addForm.model)
  try {
    await aiApi.createKnowledgeBase(formData)
    addVisible.value = false
    addForm.name = ''
    addForm.model = 'openai'
    await fetchKBList()
    ElMessage.success('创建成功')
  } catch (error) {
    ElMessage.error(error.message || '创建失败')
  }
}

const editVisible = ref(false)
const editingId = ref('')
const editForm = reactive({ name: '', remark: '', enabled: true, users: [] })
const userDraft = ref('')

async function fetchFiles() {
  if (!editingId.value) return
  try {
    const data = await aiApi.listKnowledgeBaseFiles(editingId.value)
    currentFiles.value = data.files || []
  } catch (error) {
    currentFiles.value = []
    ElMessage.error(error.message || '获取文件失败')
  }
}

async function handleEdit(row) {
  editingId.value = row.id
  editForm.name = row.name || ''
  editForm.remark = row.remark || ''
  editForm.enabled = row.enabled !== false
  editForm.users = (row.users || []).map((item) => item?.name || item).filter(Boolean)
  selectedFileNames.value = []
  pendingUploadFiles.value = []
  pendingDeleteFileNames.value = []
  userDraft.value = ''
  await fetchFiles()
  editVisible.value = true
}

function appendUser() {
  const value = userDraft.value.trim()
  if (!value) return
  if (!editForm.users.includes(value)) {
    editForm.users.push(value)
  }
  userDraft.value = ''
}

function removeUser(name) {
  editForm.users = editForm.users.filter((item) => item !== name)
}

function handleFileSelectionChange(selection) {
  selectedFileNames.value = selection.map((item) => item.name)
}

async function uploadFileRequest({ file, onSuccess, onError }) {
  try {
    pendingUploadFiles.value = [...pendingUploadFiles.value, file]
    pendingDeleteFileNames.value = pendingDeleteFileNames.value.filter((name) => name !== file.name)
    ElMessage.success(`${file.name} 已加入待提交列表`)
    onSuccess?.({})
  } catch (error) {
    ElMessage.error(error.message || '上传失败')
    onError?.(error)
  }
}

function deleteFile(filename) {
  if (!pendingDeleteFileNames.value.includes(filename)) {
    pendingDeleteFileNames.value = [...pendingDeleteFileNames.value, filename]
  }
  pendingUploadFiles.value = pendingUploadFiles.value.filter((file) => file.name !== filename)
  selectedFileNames.value = selectedFileNames.value.filter((name) => name !== filename)
  ElMessage.success('已加入待删除列表')
}

function restoreFile(filename) {
  pendingDeleteFileNames.value = pendingDeleteFileNames.value.filter((name) => name !== filename)
}

function removePendingUpload(filename) {
  pendingUploadFiles.value = pendingUploadFiles.value.filter((file) => file.name !== filename)
}

function deleteSelectedFiles() {
  if (!selectedFileNames.value.length) return
  const currentNames = new Set(currentFiles.value.map((item) => item.name))
  selectedFileNames.value.forEach((name) => {
    if (currentNames.has(name) && !pendingDeleteFileNames.value.includes(name)) {
      pendingDeleteFileNames.value.push(name)
    } else {
      pendingUploadFiles.value = pendingUploadFiles.value.filter((file) => file.name !== name)
    }
  })
  selectedFileNames.value = []
  ElMessage.success('已加入待删除列表')
}

function resetPendingChanges() {
  pendingUploadFiles.value = []
  pendingDeleteFileNames.value = []
  selectedFileNames.value = []
}

function handleCancelEdit() {
  resetPendingChanges()
  editVisible.value = false
}

function buildUpdateFormData(confirmValue) {
  const formData = new FormData()
  formData.append('id', editingId.value)
  formData.append('name', editForm.name)
  formData.append('remark', editForm.remark)
  formData.append('enabled', String(editForm.enabled))
  formData.append('users', JSON.stringify(editForm.users.map((name) => ({ name, phone: '', categoryName: '' }))))
  formData.append('delete_files', JSON.stringify(pendingDeleteFileNames.value))
  formData.append('confirm', String(confirmValue))
  pendingUploadFiles.value.forEach((file) => formData.append('files', file))
  return formData
}

async function confirmEdit() {
  try {
    const preview = await aiApi.updateKnowledgeBase(buildUpdateFormData(false))
    const pending = preview.pending || {}
    await ElMessageBox.confirm(
      `将删除 ${pending.delete_files?.length || 0} 个文件，上传 ${pending.upload_files?.length || 0} 个文件，并保存当前基础信息。是否确认提交？`,
      '确认知识库更新',
      {
        confirmButtonText: '确认提交',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '预览更新失败')
    }
    return
  }

  try {
    await aiApi.updateKnowledgeBase(buildUpdateFormData(true))
    resetPendingChanges()
    editVisible.value = false
    await fetchKBList()
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error(error.message || '保存失败')
  }
}

async function handleStatusChange(row) {
  const original = !row.enabled
  const formData = new FormData()
  formData.append('id', row.id)
  formData.append('enabled', String(row.enabled))
  try {
    await aiApi.updateKnowledgeBase(formData)
    ElMessage.success('状态已更新')
  } catch (error) {
    row.enabled = original
    ElMessage.error(error.message || '状态更新失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`彻底删除 "${row.name}"?`, '提示', { type: 'warning' })
    await aiApi.deleteKnowledgeBase(row.id)
    await fetchKBList()
    ElMessage.success('删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}
</script>

<style scoped lang="less">
.kb-management-container { padding: 24px; background: #fff; min-height: 100vh; }
.header-section { margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; .title { font-size: 18px; font-weight: bold; } }
.header-actions { display: flex; gap: 12px; }

:deep(.kb-table-header) { background-color: #f8f9fb !important; color: #666; }
.users-link { color: #4080FF; cursor: pointer; text-decoration: underline; }
.status-switch { margin: 0 auto; }

.footer-actions { margin-top: 24px; .pagination-wrapper { display: flex; justify-content: flex-end; } }
.basic-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
.basic-item { display: flex; flex-direction: column; gap: 8px; }
.label { font-size: 13px; color: #667085; }
.user-editor, .file-section { margin-top: 20px; }
.section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; font-weight: 600; color: #344054; }
.section-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.user-tags { display: flex; flex-wrap: wrap; gap: 10px; padding: 14px; border: 1px solid #e5e7eb; border-radius: 12px; background: #fafbfc; }
.user-input { width: 220px; }
.pending-delete-name { text-decoration: line-through; color: #d14343; }
.pending-upload-name { color: #1f8f53; }

.kb-uploader-box {
  :deep(.el-upload-dragger) {
    padding: 32px;
    border: 1px dashed #c8d2e3;
    background: linear-gradient(180deg, #fafcff 0%, #f5f7fb 100%);
    .el-icon--upload { font-size: 42px; color: #7c8aa5; margin-bottom: 10px; }
  }
}

:deep(.sub-table-header) { background-color: #fcfcfc !important; font-size: 12px; }
.confirm-btn { background: #4080FF; padding: 10px 30px; }

@media (max-width: 960px) {
  .header-section { flex-direction: column; align-items: flex-start; gap: 12px; }
  .basic-grid { grid-template-columns: 1fr; }
}
</style>
