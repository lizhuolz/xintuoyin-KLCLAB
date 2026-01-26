<template>
  <el-drawer :model-value="visible" @update:model-value="val => emit('update:visible', val)" width="400px"
    :close-on-click-modal="false" :close-on-press-escape="false" @close="handleCancel">
    <template #header>
      <span class="custom-dialog-title">{{ title }}</span>
    </template>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px" class="dept-form">
      <el-form-item label="部门名称" prop="deptName" required>
        <el-input v-model="form.deptName" placeholder="请输入" clearable />
      </el-form-item>
      <el-form-item label="部门ID" prop="deptId" v-if="title !== '编辑部门'">
        <el-input v-model="form.deptId" placeholder="请输入" clearable />
      </el-form-item>
      <el-form-item label="上级部门" prop="parentDept">
        <el-tree-select v-model="form.parentDept" :data="parentDeptTreeData"
          :props="{ children: 'childDeptVoList', label: 'name', value: 'id' }" placeholder="请选择上级部门" style="width: 100%"
          clearable check-strictly :render-after-expand="false" :default-expand-all="true" />
      </el-form-item>
    </el-form>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" @click="handleConfirm" class="drawer-confirm-btn">确定</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: Boolean,
  parentDeptList: {
    type: Array,
    default: () => []
  },
  title: String,
  editData: {
    type: Object,
    default: null
  }
})
const emit = defineEmits(['update:visible', 'confirm', 'refresh'])

const formRef = ref()
const form = reactive({
  deptName: '',
  deptId: '',
  parentDept: ''
})

const rules = {
  deptName: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
  parentDept: [{ required: true, message: '请选择上级部门', trigger: 'change' }]
}


const parentDeptTreeData = computed(() => {
  // 递归过滤只保留 level < 4 的部门
  function filterDepts(list) {
    return list.filter(item => {
      if (item.level >= 4) {
        return false
      }
      // 如果有子部门，递归过滤子部门
      if (item.childDeptVoList && item.childDeptVoList.length > 0) {
        item.childDeptVoList = filterDepts(item.childDeptVoList)
      }
      return true
    })
  }
  return filterDepts(props.parentDeptList)
})

watch(() => props.visible, (val) => {
  if (val) {
    console.log('props.parentDeptList', props.parentDeptList)
    console.log('parentDeptTreeData:', parentDeptTreeData.value)

    // 如果是编辑模式，填充表单数据
    if (props.editData && props.title === '编辑部门') {
      form.deptName = props.editData.name || ''
      form.deptId = props.editData.code || ''
      form.parentDept = props.editData.parentId || ''
    }
  }
})

watch(() => props.visible, (val) => {
  if (!val) resetForm()
})

function resetForm() {
  form.deptName = ''
  form.deptId = ''
  form.parentDept = ''
  formRef.value?.clearValidate()
}

function handleCancel() {
  emit('update:visible', false)
}

async function handleConfirm() {
  await formRef.value.validate()
  emit('confirm', { ...form })
  // 不在这里关闭弹窗和显示成功消息，由父组件控制
}
</script>

<style scoped>
.dept-form {
  padding: 10px 0;
}

.dialog-footer {
  text-align: right;
}

/* 隐藏树形选择器中的图标 */
:deep(.el-tree-select .el-tree-node__expand-icon) {
  display: none;
}

:deep(.el-tree-select .el-tree-node__content) {
  padding-left: 0;
}


/* .primary-btn {
  background: var(--primary-btn-bg);
  color: var(--primary-btn-text);
  border: none;

  &:hover {
    background: var(--primary-btn-hover-bg);
  }
} */

</style>
