<template>
  <div class="kb-management-container">
    <div class="header-section">
      <span class="title">知识库列表</span>
    </div>

    <!-- 表格区域 -->
    <el-table :data="kbList" style="width: 100%" v-loading="loading" stripe header-cell-class-name="kb-table-header">
      <el-table-column prop="name" label="知识库名称" min-width="180" />
      <el-table-column prop="fileCount" label="文件数量" width="100" align="center" />
      <el-table-column label="使用人" min-width="220">
        <template #default="scope">
          <span class="users-link" @click="handleEdit(scope.row)">{{ scope.row.users?.join(', ') || '暂未分配' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="150" show-overflow-tooltip />
      <el-table-column prop="updatedAt" label="更新时间" width="180" />
      <el-table-column label="操作" width="200" fixed="right" align="center">
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
      <div class="center-add">
        <el-button type="primary" circle size="large" @click="handleAdd">
          <el-icon><Plus /></el-icon>
        </el-button>
      </div>
      <div class="pagination-wrapper">
        <el-pagination layout="total, sizes, prev, pager, next, jumper" :total="total" :page-size="10" />
      </div>
    </div>

    <!-- 添加知识库对话框 -->
    <el-dialog v-model="addVisible" title="添加知识库" width="450px" align-center>
      <el-form :model="addForm" label-width="100px">
        <el-form-item label="知识库名称:" required><el-input v-model="addForm.name" /></el-form-item>
        <el-form-item label="分层类别:">
          <el-select v-model="addForm.category">
            <el-option label="企业级" value="企业知识库" />
            <el-option label="部门级" value="部门知识库" />
            <el-option label="个人级" value="个人知识库" />
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

    <!-- 编辑/上传文件对话框 (严格参考原型图) -->
    <el-dialog v-model="editVisible" title="上传文件" width="700px" top="5vh" custom-class="kb-edit-dialog">
      <template #header>
        <div class="dialog-header-custom">
          <span>上传文件</span>
          <el-tooltip content="单文件支持最大字数为100w字，超出部分将不会转化为向量" placement="right">
            <el-icon class="info-icon"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
      </template>

      <div class="edit-dialog-content">
        <!-- 上传区 -->
        <el-upload class="kb-uploader-box" drag :action="uploadUrl" multiple :on-success="handleUploadSuccess">
          <el-icon class="el-icon--upload"><FolderOpened /></el-icon>
          <div class="el-upload__text">点击上传文件</div>
        </el-upload>

        <!-- 文件列表 -->
        <el-table :data="currentFiles" style="width: 100%; margin-top: 20px" size="small" border header-cell-class-name="sub-table-header">
          <el-table-column type="selection" width="40" />
          <el-table-column prop="name" label="文件名" />
          <el-table-column prop="size" label="文件大小" width="100" align="center" />
          <el-table-column label="操作" width="80" align="center">
            <template #default="scope">
              <el-button link type="danger" @click="deleteFile(scope.row.name)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 备注 -->
        <el-form :model="editForm" label-position="left" style="margin-top: 20px">
          <el-form-item label="*知识库备注:">
            <el-input v-model="editForm.remark" type="textarea" rows="4" placeholder="请输入" />
            <div class="use-template">使用模板</div>
          </el-form-item>

          <!-- 使用人与状态 -->
          <div class="footer-form-row">
            <div class="meta-field">
              <span class="label">使用人：</span>
              <span class="users-link-display" @click="openUserSelect">
                {{ editForm.users.length ? editForm.users.join(', ') : '选择使用人...' }}
              </span>
            </div>
            <div class="meta-field status-field">
              <span class="label">状态：</span>
              <span class="status-text">{{ editForm.enabled ? '启动' : '禁用' }}</span>
              <el-switch v-model="editForm.enabled" class="blue-switch" />
            </div>
          </div>
        </el-form>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="editVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmEdit" class="confirm-btn">确认</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 选择使用人弹窗 (参考原型图) -->
    <el-dialog v-model="userSelectVisible" title="选择使用人" width="600px" append-to-body>
      <div class="user-select-container">
        <el-input v-model="userSearch" placeholder="请输入" prefix-icon="Search" class="search-input" />
        <div class="transfer-main">
          <div class="source-panel">
            <div class="panel-header">{{ checkedNodesCount }}/{{ totalNodesCount }}</div>
            <el-tree
              ref="userTreeRef"
              :data="orgTree"
              show-checkbox
              node-key="label"
              default-expand-all
              @check="handleTreeCheck"
            />
          </div>
          <div class="transfer-btns">
            <el-button :disabled="!hasChecked"><el-icon><ArrowRight /></el-icon></el-button>
            <el-button><el-icon><ArrowLeft /></el-icon></el-button>
          </div>
          <div class="target-panel">
            <div class="panel-header">{{ selectedUsers.length }}/{{ totalNodesCount }}</div>
            <div class="selected-list">
              <div v-for="u in selectedUsers" :key="u" class="selected-item">{{ u }}</div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="userSelectVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmUserSelection">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { Plus, InfoFilled, FolderOpened, Search, ArrowRight, ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const loading = ref(false); const total = ref(0); const kbList = ref([]);
const fetchKBList = async () => {
  loading.value = true; try { const res = await axios.get('/api/kb/list'); kbList.value = res.data; total.value = res.data.length; } finally { loading.value = false }
}
onMounted(fetchKBList)

// 添加
const addVisible = ref(false); const addForm = reactive({ name: '', model: 'openai', category: '企业知识库' })
const handleAdd = () => { addVisible.value = true }
const confirmAdd = async () => {
  if (!addForm.name) return ElMessage.warning('请输入名称')
  const fd = new FormData(); fd.append('name', addForm.name); fd.append('category', addForm.category)
  try { await axios.post('/api/kb/create', fd); ElMessage.success('创建成功'); addVisible.value = false; fetchKBList(); } catch (e) {}
}

// 编辑与文件
const editVisible = ref(false); const editingId = ref(null); const currentFiles = ref([]);
const editForm = reactive({ name: '', remark: '', enabled: true, users: [] })
const handleEdit = async (row) => {
  editingId.value = row.id; editForm.name = row.name; editForm.remark = row.remark || ''; 
  editForm.enabled = row.enabled; editForm.users = row.users || [];
  await fetchFiles(); editVisible.value = true;
}
const fetchFiles = async () => { try { const res = await axios.get(`/api/kb/${editingId.value}/files`); currentFiles.value = res.data; } catch (e) {} }
const uploadUrl = computed(() => `/api/kb/${editingId.value}/upload`)
const handleUploadSuccess = () => { ElMessage.success('上传成功'); fetchFiles(); fetchKBList(); }
const deleteFile = async (fn) => {
  const fd = new FormData(); fd.append('filename', fn)
  try { await axios.post(`/api/kb/${editingId.value}/delete_file`, fd); fetchFiles(); fetchKBList(); } catch (e) {}
}
const confirmEdit = async () => {
  const fd = new FormData(); fd.append('id', editingId.value); fd.append('remark', editForm.remark); 
  fd.append('enabled', String(editForm.enabled)); fd.append('users', JSON.stringify(editForm.users))
  try { await axios.post('/api/kb/update', fd); ElMessage.success('保存成功'); editVisible.value = false; fetchKBList(); } catch (e) {}
}

// 使用人选择逻辑
const userSelectVisible = ref(false); const userSearch = ref(''); const userTreeRef = ref(null);
const selectedUsers = ref([]);
const orgTree = [
  { label: '人事', children: [{ label: '张三' }, { label: '李四' }] },
  { label: '财务', children: [{ label: '王五' }, { label: '赵六' }] },
  { label: '技术部', children: [{ label: '王颖奇' }, { label: '陈七' }] }
]
const totalNodesCount = 6;
const checkedNodesCount = ref(0);
const hasChecked = computed(() => checkedNodesCount.value > 0);

const openUserSelect = () => {
  selectedUsers.value = [...editForm.users];
  userSelectVisible.value = true;
  nextTick(() => {
    if (userTreeRef.value) userTreeRef.value.setCheckedKeys(selectedUsers.value);
  });
}
const handleTreeCheck = () => {
  const nodes = userTreeRef.value.getCheckedNodes(true);
  checkedNodesCount.value = nodes.length;
  selectedUsers.value = nodes.map(n => n.label);
}
const confirmUserSelection = () => {
  editForm.users = [...selectedUsers.value];
  userSelectVisible.value = false;
}

const handleStatusChange = (row) => {
  const fd = new FormData(); fd.append('id', row.id); fd.append('enabled', String(row.enabled))
  axios.post('/api/kb/update', fd)
}
const handleDelete = (row) => {
  ElMessageBox.confirm(`彻底删除 "${row.name}"?`, '提示', { type: 'warning' }).then(async () => {
    await axios.delete(`/api/kb/${row.id}`); fetchKBList();
  })
}
</script>

<style scoped lang="less">
.kb-management-container { padding: 24px; background: #fff; min-height: 100vh; }
.header-section { margin-bottom: 20px; .title { font-size: 18px; font-weight: bold; } }

:deep(.kb-table-header) { background-color: #f8f9fb !important; color: #666; }
.users-link { color: #4080FF; cursor: pointer; text-decoration: underline; }
.status-switch { margin: 0 10px; }

.footer-actions {
  margin-top: 30px;
  .center-add { display: flex; justify-content: center; margin-bottom: 20px; }
  .pagination-wrapper { display: flex; justify-content: flex-end; }
}

/* 弹窗样式重构 */
.dialog-header-custom { display: flex; align-items: center; gap: 8px; .info-icon { color: #999; font-size: 16px; cursor: pointer; } }

.kb-uploader-box {
  :deep(.el-upload-dragger) {
    padding: 40px; border: 1px solid #dcdfe6; background: #fafafa;
    .el-icon--upload { font-size: 48px; color: #999; margin-bottom: 10px; }
  }
}

:deep(.sub-table-header) { background-color: #fcfcfc !important; font-size: 12px; }

.use-template { color: #4080FF; font-size: 12px; cursor: pointer; position: absolute; right: 0; bottom: -22px; }

.footer-form-row {
  display: flex; justify-content: space-between; align-items: center; margin-top: 35px;
  .meta-field {
    display: flex; align-items: center; gap: 10px; font-size: 14px;
    .label { font-weight: bold; }
    .users-link-display {
      color: #4080FF; text-decoration: underline; cursor: pointer; border: 1px solid #eee; padding: 4px 12px; border-radius: 4px; min-width: 150px;
    }
  }
  .status-field { .status-text { margin-right: 8px; } }
}

.confirm-btn { background: #4080FF; padding: 10px 30px; }

/* 选择使用人样式 */
.user-select-container {
  .search-input { margin-bottom: 15px; }
  .transfer-main {
    display: flex; gap: 15px; align-items: center;
    .source-panel, .target-panel {
      flex: 1; border: 1px solid #dcdfe6; border-radius: 4px; height: 300px; display: flex; flex-direction: column;
      .panel-header { background: #f5f7fa; padding: 8px 12px; border-bottom: 1px solid #dcdfe6; font-size: 12px; color: #999; }
      .selected-list { padding: 10px; overflow-y: auto; .selected-item { padding: 4px 0; font-size: 13px; } }
    }
    .transfer-btns { display: flex; flex-direction: column; gap: 10px; }
  }
}
</style>
