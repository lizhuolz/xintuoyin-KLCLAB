<template>
  <div class="kb-management-container">
    <div class="header-section">
      <span class="title">知识库管理</span>
      <el-tabs v-model="activeTab" @tab-change="handleTabChange" class="kb-tabs">
        <el-tab-pane label="用户知识库" name="user" />
        <el-tab-pane label="基础知识库" name="base" />
      </el-tabs>
      <div class="header-actions">
        <el-button @click="fetchKBList">刷新</el-button>
        <el-button type="primary" @click="handleAdd">新增知识库</el-button>
      </div>
    </div>

    <el-table :data="kbList" style="width: 100%" v-loading="loading" stripe header-cell-class-name="kb-table-header">
      <el-table-column prop="name" label="知识库名称" min-width="180" />
      <el-table-column prop="fileCount" label="文件数量" width="100" align="center" />
      <el-table-column v-if="!isBaseTab" label="使用人" min-width="220">
        <template #default="scope">
          <span>{{ formatUsers(scope.row.users) || '暂未分配' }}</span>
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
            <el-input v-model="editForm.remark" type="textarea" :rows="remarkUsingTemplate ? 10 : 4" placeholder="请输入备注或使用说明" />
            <el-button link type="primary" style="margin-top: 4px" @click="toggleRemarkTemplate">{{ remarkUsingTemplate ? '取消模版' : '使用模版' }}</el-button>
          </el-form-item>
        </el-form>

        <div v-if="!isBaseTab" class="user-editor">
          <div class="section-head">
            <span>使用人</span>
            <el-button size="small" type="primary" @click="userPickerVisible = true">选择使用人</el-button>
          </div>
          <div class="user-tags">
            <el-tag v-for="item in editForm.users" :key="item" closable @close="removeUser(item)">{{ item }}</el-tag>
            <span v-if="!editForm.users.length" class="no-user-tip">暂未选择使用人</span>
          </div>
        </div>

        <el-dialog v-model="userPickerVisible" title="选择使用人" width="600px" append-to-body>
          <div class="user-picker">
            <div class="picker-left">
              <div class="picker-count">{{ allMemberNames.length }} 人</div>
              <div v-for="dept in deptUsers" :key="dept.department" class="dept-group">
                <div class="dept-name">
                  <el-checkbox :model-value="isDeptAllSelected(dept)" :indeterminate="isDeptPartial(dept)" @change="toggleDept(dept, $event)">{{ dept.department }}</el-checkbox>
                </div>
                <div class="dept-members">
                  <el-checkbox v-for="name in dept.members" :key="name" :model-value="pickerSelected.includes(name)" @change="toggleMember(name, $event)">{{ name }}</el-checkbox>
                </div>
              </div>
            </div>
            <div class="picker-actions">
              <el-button :icon="ArrowRight" @click="addSelected" :disabled="!pickerSelected.length" />
              <el-button :icon="ArrowLeft" @click="removeSelected" :disabled="!pickerChosen.length" />
            </div>
            <div class="picker-right">
              <div class="picker-count">{{ pickerChosen.length }} 人</div>
              <div v-for="name in pickerChosen" :key="name" class="chosen-item">
                <el-checkbox :model-value="true" @change="removeChosen(name)">{{ name }}</el-checkbox>
              </div>
            </div>
          </div>
          <template #footer>
            <el-button @click="userPickerVisible = false">取消</el-button>
            <el-button type="primary" @click="confirmUserPicker">确认</el-button>
          </template>
        </el-dialog>

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

          <el-upload
            class="kb-uploader-box"
            drag
            multiple
            :auto-upload="false"
            :show-file-list="false"
            :on-change="handleKbFileSelect"
          >
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

import { FolderOpened, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiApi } from '@/api/ai'

const activeTab = ref('user')
const isBaseTab = computed(() => activeTab.value === 'base')
function handleTabChange() {
  pagination.page = 1
  fetchKBList()
}

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
  const stagedUploads = pendingUploadFiles.value.map((item) => ({
    name: item.name,
    size: item.size || 0,
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
    const data = await aiApi.listKnowledgeBases({ page: pagination.page, size: pagination.size, type: activeTab.value })
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
  try {
    await aiApi.createKnowledgeBase({ name: addForm.name, model: addForm.model, type: activeTab.value })
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
const remarkUsingTemplate = ref(false)
const remarkBeforeTemplate = ref('')
const REMARK_TEMPLATE = `概述：[一句话描述，简要说明知识库的核心内容和使用目的]

主要内容：
【文件一名称】[对该主题的简短描述，包括关键词或概念]
【文件二名称】[对该主题的简短描述，包括关键词或概念]
【文件三名称】[对该主题的简短描述，包括关键词或概念]

适用场景：[描述哪些类型的查询或问题，这个知识库能够提供帮助]`

function toggleRemarkTemplate() {
  if (remarkUsingTemplate.value) {
    editForm.remark = remarkBeforeTemplate.value
    remarkUsingTemplate.value = false
  } else {
    remarkBeforeTemplate.value = editForm.remark
    editForm.remark = REMARK_TEMPLATE
    remarkUsingTemplate.value = true
  }
}

// 使用人选择器
const userPickerVisible = ref(false)
const deptUsers = ref([])
const pickerSelected = ref([])
const pickerChosen = ref([])
const allMemberNames = computed(() => deptUsers.value.flatMap((d) => d.members))

async function fetchDeptUsers() {
  try {
    deptUsers.value = await aiApi.getDepartmentUsers() || []
  } catch { deptUsers.value = [] }
}

function isDeptAllSelected(dept) {
  return dept.members.every((n) => pickerSelected.value.includes(n))
}
function isDeptPartial(dept) {
  const count = dept.members.filter((n) => pickerSelected.value.includes(n)).length
  return count > 0 && count < dept.members.length
}
function toggleDept(dept, checked) {
  if (checked) {
    const set = new Set(pickerSelected.value)
    dept.members.forEach((n) => set.add(n))
    pickerSelected.value = [...set]
  } else {
    pickerSelected.value = pickerSelected.value.filter((n) => !dept.members.includes(n))
  }
}
function toggleMember(name, checked) {
  if (checked) {
    if (!pickerSelected.value.includes(name)) pickerSelected.value.push(name)
  } else {
    pickerSelected.value = pickerSelected.value.filter((n) => n !== name)
  }
}
function addSelected() {
  const set = new Set(pickerChosen.value)
  pickerSelected.value.forEach((n) => set.add(n))
  pickerChosen.value = [...set]
  pickerSelected.value = []
}
function removeSelected() {
  pickerChosen.value = []
}
function removeChosen(name) {
  pickerChosen.value = pickerChosen.value.filter((n) => n !== name)
}
function confirmUserPicker() {
  editForm.users = [...pickerChosen.value]
  userPickerVisible.value = false
}

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
  remarkUsingTemplate.value = false
  remarkBeforeTemplate.value = ''
  editForm.users = (row.users || []).map((item) => item?.name || item).filter(Boolean)
  selectedFileNames.value = []
  pendingUploadFiles.value = []
  pendingDeleteFileNames.value = []
  pickerSelected.value = []
  pickerChosen.value = [...editForm.users]
  await fetchFiles()
  await fetchDeptUsers()
  editVisible.value = true
}


function removeUser(name) {
  editForm.users = editForm.users.filter((item) => item !== name)
}

function handleFileSelectionChange(selection) {
  selectedFileNames.value = selection.map((item) => item.name)
}

let kbPendingRawFiles = []
let kbFlushTimer = null

function handleKbFileSelect(uploadFile) {
  if (!uploadFile?.raw) return
  kbPendingRawFiles.push(uploadFile.raw)
  if (kbFlushTimer) clearTimeout(kbFlushTimer)
  kbFlushTimer = setTimeout(flushKbUploads, 50)
}

async function flushKbUploads() {
  kbFlushTimer = null
  const batch = kbPendingRawFiles.splice(0)
  if (!batch.length) return
  try {
    const result = await aiApi.uploadFiles(batch)
    const uploaded = result.files || []
    if (!uploaded.length) return
    const uploadedNames = new Set(uploaded.map((item) => item.filename))
    pendingUploadFiles.value = [
      ...pendingUploadFiles.value,
      ...uploaded.map((item) => ({ file_id: item.file_id, name: item.filename })),
    ]
    pendingDeleteFileNames.value = pendingDeleteFileNames.value.filter((name) => !uploadedNames.has(name))
    ElMessage.success(`已上传 ${uploaded.length} 个文件`)
  } catch (error) {
    ElMessage.error(error.message || '上传失败')
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

function buildUpdatePayload(confirmValue) {
  return {
    id: editingId.value,
    name: editForm.name,
    remark: editForm.remark,
    enabled: String(editForm.enabled),
    users: JSON.stringify(editForm.users.map((name) => ({ name, phone: '', categoryName: '' }))),
    delete_files: JSON.stringify(pendingDeleteFileNames.value),
    add_file_ids: pendingUploadFiles.value.map((f) => f.file_id),
    confirm: String(confirmValue),
  }
}

async function confirmEdit() {
  try {
    const preview = await aiApi.updateKnowledgeBase(buildUpdatePayload(false))
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
    await aiApi.updateKnowledgeBase(buildUpdatePayload(true))
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
  if (row.enabled) {
    try {
      await ElMessageBox.confirm(`确认应用知识库「${row.name}」？`, '提示', { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' })
    } catch {
      row.enabled = original
      return
    }
  }
  try {
    await aiApi.toggleKnowledgeBaseEnabled(row.id, row.enabled)
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
.header-section { margin-bottom: 20px; .title { font-size: 18px; font-weight: bold; } }
.kb-tabs { margin-bottom: 16px; }
.header-actions { display: flex; gap: 12px; }

:deep(.kb-table-header) { background-color: #f8f9fb !important; color: #666; }
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

.no-user-tip { color: #999; font-size: 13px; }

.user-picker {
  display: flex; gap: 16px; min-height: 280px;
  .picker-left, .picker-right {
    flex: 1; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; overflow-y: auto; max-height: 350px;
  }
  .picker-actions { display: flex; flex-direction: column; justify-content: center; gap: 12px; }
  .picker-count { font-size: 12px; color: #999; margin-bottom: 8px; }
  .dept-group { margin-bottom: 8px; }
  .dept-name { font-weight: 600; margin-bottom: 4px; }
  .dept-members { padding-left: 20px; display: flex; flex-direction: column; gap: 2px; }
  .chosen-item { margin-bottom: 2px; }
}

@media (max-width: 960px) {
  .header-section { flex-direction: column; align-items: flex-start; gap: 12px; }
  .basic-grid { grid-template-columns: 1fr; }
}
</style>
