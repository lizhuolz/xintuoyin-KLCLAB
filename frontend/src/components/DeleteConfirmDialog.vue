<template>
    <el-dialog :model-value="visible" @update:model-value="val => $emit('update:visible', val)" width="320px"
        :close-on-click-modal="false" :close-on-press-escape="false" :show-close="false">
        <!-- 第一步：警告 -->
        <div v-if="currentStep === 'warning'" class="dialog-content">
            <div class="dialog-text">
                <div class="dialog-title"><el-icon class="icon-danger" size="20">
                      <WarningFilled />
                    </el-icon><div>删除部门</div></div>
                <div class="dialog-desc">需先移除所有子部门和成员</div>
            </div>
        </div>
        <!-- 第二步：确认 -->
        <div v-else class="dialog-content">

            <div class="dialog-text">
                <div class="dialog-title" style="color:#f56c6c;"> <el-icon class="icon-danger" size="20">
                      <WarningFilled />
                    </el-icon>
                    <div>删除</div>
                </div>
                <div class="dialog-desc">确定要删除吗？</div>
            </div>
        </div>
        <template #footer>
            <div class="dialog-footer">
                <el-button v-if="currentStep === 'warning'" type="primary" @click="handleWarningOk">
                    好的
                </el-button>
                <template v-else>
                    <el-button @click="handleCancel">
                        取消
                    </el-button>
                    <el-button type="danger" @click="handleConfirm">
                        删除
                    </el-button>
                </template>
            </div>
        </template>
    </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { WarningFilled, Lightning } from '@element-plus/icons-vue'

const props = defineProps({
    visible: Boolean,
    editData: Object
})
const emit = defineEmits(['update:visible', 'confirm'])

const currentStep = ref('warning')

watch(() => props.visible, (val) => {
    if (val) {
        // 检查是否有子部门或成员
        if (hasChildrenOrMembers(props.editData)) {
            currentStep.value = 'warning'
        } else {
            currentStep.value = 'confirm'
        }
    }
})

function handleWarningOk() {
    // 点击"好的"直接关闭弹窗
    emit('update:visible', false)
}
function hasChildrenOrMembers(editData) {
    if (!editData) return false
    const hasChildren = Array.isArray(editData.childDeptVoList) && editData.childDeptVoList.length > 0
    const hasMembers = Number(editData.deptPeopleQuantity) > 0
    return hasChildren || hasMembers
}
function handleCancel() {
    emit('update:visible', false)
}
function handleConfirm() {
    emit('confirm', props.editData)
    emit('update:visible', false)
}
watch(() => props.editData, (val) => {
  console.log('DeleteConfirmDialog收到的editData', val)
})
</script>

<style scoped>
.dialog-content {
    display: flex;
    align-items: flex-start;
    gap: 12px;
}

.dialog-text {
    flex: 1;
}

.icon-warning {
    color: #409eff;
    font-size: 28px;
    margin-top: 2px;
}

.icon-danger {
    color: #f56c6c;
    font-size: 28px;
    margin-top: 2px;
}

.dialog-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: bold;
    font-size: 16px;
    margin-bottom: 4px;
}

.dialog-desc {
    padding-left: 38px;
    font-size: 14px;
    color: #666;
}

.dialog-footer {
    text-align: right;
}

.lightning-icon {
    margin-left: 4px;
    color: #495060;
}
</style>