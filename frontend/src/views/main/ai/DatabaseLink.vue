<template>
  <div class="database-link-container">
    <div class="database-link-row">
      <span class="label">链接数据库：</span>
      <el-select
        v-model="selectedDb"
        placeholder="请选择"
        style="width: 320px"
        @change="handleDbChange"
      >
        <el-option
          v-for="option in dbOptions"
          :key="option.id"
          :label="option.label"
          :value="option.id"
        />
      </el-select>
      <el-button :icon="Plus" circle @click="openAddDialog" title="新增数据库" />
    </div>

    <el-dialog
      v-model="addDialogVisible"
      title="新增数据库"
      width="520px"
      :close-on-click-modal="false"
      @closed="resetAddForm"
    >
      <el-form
        ref="addFormRef"
        :model="addForm"
        :rules="addFormRules"
        label-width="90px"
        label-position="right"
        @submit.prevent
      >
        <el-form-item label="数据库名" prop="name">
          <el-input v-model="addForm.name" placeholder="MySQL schema 名，如 r_d_test" />
        </el-form-item>
        <el-form-item label="IP 地址" prop="host">
          <el-input v-model="addForm.host" placeholder="例如 183.69.138.62" />
        </el-form-item>
        <el-form-item label="端口" prop="port">
          <el-input-number v-model="addForm.port" :min="1" :max="65535" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="用户名" prop="user">
          <el-input v-model="addForm.user" placeholder="MySQL 用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="addForm.password" type="password" show-password placeholder="MySQL 密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="adding" @click="handleAddSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { aiApi } from '@/api/ai'

const selectedDb = ref('')
const previousDb = ref('')
const dbOptions = ref([])

const addDialogVisible = ref(false)
const adding = ref(false)
const addFormRef = ref(null)
const addForm = reactive({
  name: '',
  host: '',
  port: 3306,
  user: '',
  password: '',
})
const addFormRules = {
  name: [{ required: true, message: '请输入数据库名', trigger: 'blur' }],
  host: [{ required: true, message: '请输入 IP 地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  user: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function loadDbOptions() {
  try {
    const data = await aiApi.getDbOptions()
    if (Array.isArray(data.databases)) {
      dbOptions.value = data.databases
    }
    if (data.active_id) {
      selectedDb.value = data.active_id
      previousDb.value = data.active_id
    }
  } catch (error) {
    ElMessage.error(error.message || '获取数据库列表失败')
  }
}

async function handleDbChange(value) {
  try {
    await aiApi.selectDb(value)
    previousDb.value = value
    ElMessage.success('数据库已切换')
  } catch (error) {
    selectedDb.value = previousDb.value
    ElMessage.error(error.message || '切换失败')
  }
}

function openAddDialog() {
  addDialogVisible.value = true
}

function resetAddForm() {
  addForm.name = ''
  addForm.host = ''
  addForm.port = 3306
  addForm.user = ''
  addForm.password = ''
  addFormRef.value?.clearValidate()
}

async function handleAddSubmit() {
  if (!addFormRef.value) return
  try {
    await addFormRef.value.validate()
  } catch {
    return
  }
  adding.value = true
  try {
    const created = await aiApi.addDatabase({
      name: addForm.name.trim(),
      host: addForm.host.trim(),
      port: addForm.port,
      user: addForm.user.trim(),
      password: addForm.password,
    })
    dbOptions.value = [...dbOptions.value, created]
    addDialogVisible.value = false
    ElMessage.success('数据库已新增')
  } catch (error) {
    ElMessage.error(`添加失败：${error.message || '未知错误'}`)
  } finally {
    adding.value = false
  }
}

onMounted(loadDbOptions)
</script>

<style scoped>
.database-link-container {
  padding: 24px;
  background: #fff;
  min-height: 100%;
}

.database-link-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.label {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  white-space: nowrap;
}
</style>
