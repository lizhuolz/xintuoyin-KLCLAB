<template>
  <el-dialog 
    :model-value="visible" 
    width="420px" 
    :show-close="true"
    @close="handleClose" 
    class="delete-confirm-dialog" 
    :close-on-click-modal="false" 
    :close-on-press-escape="false"
  >
    <div class="dialog-header">
      <div class="warning-icon">
        <el-icon color="#ED7B00" size="20">
          <WarningFilled />
        </el-icon>
      </div>
      <span class="dialog-title">{{ title }}</span>
    </div>
    <div class="dialog-content">
      <p class="message">{{ message }}</p>
    </div>
    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" class="dialog-confirm-btn" @click="handleConfirm">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  visible: Boolean,
  title: {
    type: String,
    default: '删除'
  },
  message: {
    type: String,
    default: '确定要删除这条记录吗？'
  }
})

const emits = defineEmits(['update:visible', 'confirm'])

function handleConfirm() {
  emits('confirm')
  emits('update:visible', false)
}

function handleCancel() {
  emits('update:visible', false)
}

function handleClose() {
  emits('update:visible', false)
}
</script>

<style scoped>
.delete-confirm-dialog :deep(.el-dialog__header) {
  border-bottom: none;
  padding-bottom: 0;
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 18px;
  height: 40px;
  padding-left: 12px;
}

.warning-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
}

.dialog-title {
  font-size: 18px;
  font-weight: bold;
  color: #222;
}

.dialog-content {
  padding-left: 40px;
}

.message {
  margin: 0;
  color: #333;
  font-size: 14px;
  line-height: 1.5;
}

.dialog-confirm-btn {
  background: #0256FF !important;
  border-color: #0256FF !important;
  color: #fff !important;
}

.delete-confirm-dialog :deep(.el-dialog__footer) {
  padding: 0 24px !important;
}

.dialog-divider {
  width: calc(100% + 28px);
  margin-left: -14px;
  margin-right: -14px;
  height: 1px;
  background: #eee;
}

.header-divider {
  margin-top: 10px;
}

:deep(.el-dialog__footer) {
  padding-bottom: 0 !important;
}
</style> 