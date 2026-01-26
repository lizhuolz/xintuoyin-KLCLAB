<template>
  <div class="kb-management-container">
    <div class="header-section">
      <span class="title">知识库列表</span>
    </div>

    <!-- 表格区域 -->
    <el-table :data="kbList" style="width: 100%" v-loading="loading">
      <el-table-column prop="name" label="知识库名称" min-width="150" />
      <el-table-column prop="fileCount" label="文件数量" width="100" align="center" />
      <el-table-column label="使用人" min-width="200">
        <template #default="scope">
          <el-tag 
            v-for="user in scope.row.users" 
            :key="user" 
            size="small" 
            class="user-tag"
          >
            {{ user }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
      <el-table-column prop="updatedAt" label="更新时间" width="180" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="handleEdit(scope.row)">编辑</el-button>
          <el-switch 
            v-model="scope.row.enabled" 
            inline-prompt 
            class="status-switch"
            @change="handleStatusChange(scope.row)"
          />
          <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 底部操作与分页 -->
    <div class="footer-actions">
      <div class="left">
        <el-button type="primary" circle @click="handleAdd">
          <el-icon><Plus /></el-icon>
        </el-button>
      </div>
      <el-pagination
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :page-size="10"
      />
    </div>

    <!-- 添加知识库对话框 -->
    <el-dialog v-model="addVisible" title="添加知识库" width="450px" align-center>
      <el-form :model="addForm" label-width="100px">
        <el-form-item label="知识库名称:" required>
          <el-input v-model="addForm.name" placeholder="请输入" />
        </el-form-item>
        <el-form-item label="分层类别:">
          <el-select v-model="addForm.category" placeholder="请选择">
            <el-option label="企业级 (Org)" value="org" />
            <el-option label="部门级 (Depts)" value="depts/dept_a" />
            <el-option label="个人级 (Users)" value="users/user_a1" />
          </el-select>
        </el-form-item>
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

    <!-- 编辑知识库对话框 -->
    <el-dialog v-model="editVisible" title="编辑知识库" width="800px" top="5vh">
      <div class="edit-dialog-content">
        <!-- 上传区 -->
        <div class="upload-section">
          <div class="upload-header">
            <span>上传文件</span>
            <el-tooltip content="变动文件后 RAG 索引将自动后台更新">
              <el-icon class="info-icon"><InfoFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-upload
            class="kb-uploader"
            drag
            :action="uploadUrl"
            multiple
            :on-success="handleUploadSuccess"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">点击上传文件</div>
          </el-upload>
        </div>

        <!-- 文件列表 -->
        <el-table :data="currentFiles" style="width: 100%; margin-top: 20px" size="small">
          <el-table-column prop="name" label="文件名" />
          <el-table-column prop="size" label="文件大小" width="120" />
          <el-table-column label="操作" width="80" align="center">
            <template #default="scope">
              <el-button link type="danger" @click="deleteFile(scope.row.name)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 其他信息 -->
        <el-form :model="editForm" label-position="top" style="margin-top: 20px">
          <el-form-item label="知识库名称:">
            <el-input v-model="editForm.name" placeholder="请输入" />
          </el-form-item>
          <el-form-item label="知识库备注:">
            <el-input 
              v-model="editForm.remark" 
              type="textarea" 
              rows="3" 
              placeholder="请输入" 
            />
          </el-form-item>
          <div class="user-select-row">
            <el-form-item label="使用人:" style="flex: 1; margin-right: 20px">
              <el-input 
                v-model="editForm.usersDisplay" 
                readonly 
                placeholder="请选择使用人" 
              />
            </el-form-item>
            <el-form-item label="状态:">
              <div style="display: flex; align-items: center; height: 32px">
                <span style="margin-right: 8px">启用</span>
                <el-switch v-model="editForm.enabled" />
              </div>
            </el-form-item>
            <el-button 
              type="primary" 
              plain 
              style="margin-top: 30px" 
              @click="openUserSelect"
            >
              选择使用人
            </el-button>
          </div>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmEdit">确认</el-button>
      </template>
    </el-dialog>

    <!-- 选择使用人对话框 -->
    <el-dialog v-model="userSelectVisible" title="选择使用人" width="600px">
      <div class="user-select-container">
        <el-input v-model="userSearch" placeholder="请输入关键字搜索" class="search-input">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <div class="transfer-box">
          <div class="tree-panel">
            <div class="panel-header">组织架构</div>
            <el-tree
              ref="treeRef"
              :data="deptTree"
              show-checkbox
              node-key="label"
              default-expand-all
              :props="{ label: 'label', children: 'children' }"
            />
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="userSelectVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmUserSelection">确认选择</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { Plus, InfoFilled, UploadFilled, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const loading = ref(false)
const total = ref(0)
const kbList = ref([])

// 获取列表
const fetchKBList = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/kb/list')
    kbList.value = res.data
    total.value = res.data.length
  } catch (err) {
    ElMessage.error('获取知识库列表失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchKBList)

// 添加逻辑
const addVisible = ref(false)
const addForm = reactive({ name: '', model: 'openai', category: 'org' })
const handleAdd = () => { addVisible.value = true }
const confirmAdd = async () => {
  if (!addForm.name) return ElMessage.warning('请输入名称')
  
  const fd = new FormData()
  fd.append('name', addForm.name)
  fd.append('model', addForm.model)
  fd.append('category', addForm.category)

  try {
    await axios.post('/api/kb/create', fd)
    ElMessage.success('知识库创建成功')
    addVisible.value = false
    fetchKBList()
  } catch (err) {
    ElMessage.error('创建失败')
  }
}

// 编辑逻辑
const editVisible = ref(false)
const editingId = ref(null)
const editForm = reactive({ name: '', remark: '', enabled: true, usersDisplay: '', users: [] })
const currentFiles = ref([])

const handleEdit = async (row) => {
  editingId.value = row.id
  editForm.name = row.name
  editForm.remark = row.remark
  editForm.enabled = row.enabled
  editForm.users = row.users || []
  editForm.usersDisplay = editForm.users.join(', ')
  
  await fetchFiles()
  editVisible.value = true
}

const fetchFiles = async () => {
  try {
    const res = await axios.get(`/api/kb/${editingId.value}/files`)
    currentFiles.value = res.data
  } catch (e) {
    currentFiles.value = []
  }
}

const confirmEdit = async () => {
  const fd = new FormData()
  fd.append('id', editingId.value)
  fd.append('name', editForm.name)
  fd.append('remark', editForm.remark)
  fd.append('enabled', editForm.enabled)
  fd.append('users', JSON.stringify(editForm.users))
  
  try {
    await axios.post('/api/kb/update', fd)
    ElMessage.success('更新成功')
    editVisible.value = false
    fetchKBList()
  } catch (err) {
    ElMessage.error('更新失败')
  }
}

const handleStatusChange = (row) => {
  const fd = new FormData()
  fd.append('id', row.id)
  fd.append('enabled', row.enabled)
  axios.post('/api/kb/update', fd).catch(() => {
    ElMessage.error('状态切换失败')
    row.enabled = !row.enabled
  })
}

// 删除逻辑
const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要彻底删除知识库 "${row.name}" 吗？`, '警告', { type: 'error' })
    .then(async () => {
      await axios.delete(`/api/kb/${row.id}`)
      ElMessage.success('已删除')
      fetchKBList()
    })
}

// 文件上传
const uploadUrl = computed(() => `/api/kb/${editingId.value}/upload`)
const handleUploadSuccess = () => {
  ElMessage.success('上传成功，RAG 索引已自动刷新')
  fetchFiles()
  fetchKBList() // 刷新主表文件数量
}

const deleteFile = async (filename) => {
  const fd = new FormData()
  fd.append('filename', filename)
  try {
    await axios.post(`/api/kb/${editingId.value}/delete_file`, fd)
    ElMessage.success('文件已删除')
    fetchFiles()
    fetchKBList() // 刷新主表文件数量
  } catch (e) {
    ElMessage.error('文件删除失败')
  }
}

// 用户选择
const userSelectVisible = ref(false)
const userSearch = ref('')
const treeRef = ref(null)
const deptTree = [
  { label: '人事', children: [ { label: '人事部全员' } ] },
  { label: '财务', children: [
    { label: '张三' },
    { label: '李四' },
    { label: '王五' },
  ]},
  { label: '技术', children: [ { label: 'A1员工' }, { label: 'B1员工' } ] }
]

const openUserSelect = () => {
  userSelectVisible.value = true
  nextTick(() => {
    if (treeRef.value) {
      treeRef.value.setCheckedKeys(editForm.users)
    }
  })
}

const confirmUserSelection = () => {
  const selectedNodes = treeRef.value.getCheckedNodes(true) // 只拿叶子节点
  editForm.users = selectedNodes.map(node => node.label)
  editForm.usersDisplay = editForm.users.join(', ')
  userSelectVisible.value = false
}

</script>

<style scoped lang="less">
.kb-management-container {
  padding: 24px;
  background: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.header-section {
  margin-bottom: 20px;
  .title {
    font-size: 18px;
    font-weight: 600;
    color: #303133;
  }
}

.user-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.status-switch {
  margin: 0 12px;
}

.footer-actions {
  margin-top: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.edit-dialog-content {
  .upload-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    font-size: 14px;
    color: #606266;
    .info-icon { color: #909399; }
  }
}

.user-select-row {
  display: flex;
  align-items: flex-start;
}

.user-select-container {
  .search-input { margin-bottom: 16px; }
  .transfer-box {
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    height: 350px;
    overflow-y: auto;
    
    .tree-panel {
      padding: 10px;
      .panel-header {
        font-size: 12px;
        color: #909399;
        margin-bottom: 8px;
      }
    }
  }
}
</style>
