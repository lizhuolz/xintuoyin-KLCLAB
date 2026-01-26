<template>
  <div class="apply-dialog-mask">
    <div class="apply-dialog-box">
      <div class="apply-dialog-header">
        <span>申请免费体验</span>
        <span class="close-btn" @click="onClose">×</span>
      </div>
      <div class="apply-dialog-body">
        <el-form :model="form" :rules="rules" ref="formRef" label-width="90px" label-position="left">
          <el-form-item label="姓名：" prop="name" required>
            <template #label>
              <span class="required">*</span> 姓名：
            </template>
            <el-input v-model="form.name" placeholder="请输入" />
          </el-form-item>
          <el-form-item label="公司名称：" prop="company" required>
            <template #label>
              <span class="required">*</span> 公司名称：
            </template>
            <el-input v-model="form.company" placeholder="请输入" />
          </el-form-item>
          <el-form-item label="手机号：" prop="phone" required>
            <template #label>
              <span class="required">*</span> 手机号：
            </template>
            <el-input v-model="form.phone" placeholder="请输入" />
          </el-form-item>
          <el-form-item label="验证码：" prop="code" required>
            <template #label>
              <span class="required">*</span> 验证码：
            </template>
            <el-input v-model="form.code" placeholder="请输入" style="width: 140px; margin-right: 8px;" />
            <el-link type="primary" :underline="false" class="get-code" @click="getCode" :disabled="countdown > 0">
              <span :style="{ color: countdown > 0 ? '#bbb' : '#1677ff' }">
                {{ countdown > 0 ? countdown + 's' : '获取验证码' }}
              </span>
            </el-link>
          </el-form-item>
          <el-form-item label="留言：">
            <el-input v-model="form.message" type="textarea" :rows="2" placeholder="请输入" />
          </el-form-item>
        </el-form>
        <el-button type="primary" class="submit-btn" @click="onSubmit" :disabled="submitting">确定</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const emit = defineEmits(['close'])

const formRef = ref()
const form = ref({
  name: '',
  company: '',
  phone: '',
  code: '',
  message: ''
})
const rules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  company: [{ required: true, message: '请输入公司名称', trigger: 'blur' }],
  phone: [{ required: true, message: '请输入手机号', trigger: 'blur' }],
  code: [{ required: true, message: '请输入验证码', trigger: 'blur' }]
}

const countdown = ref(0)
const submitting = ref(false)
let timer = null

function getCode() {
  if (!form.value.phone) {
    ElMessage.warning('请先输入手机号')
    return
  }
  if (countdown.value > 0) return
  ElMessage.success('验证码已发送（模拟）')
  countdown.value = 60
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) clearInterval(timer)
  }, 1000)
}

function onSubmit() {
  formRef.value.validate(valid => {
    if (valid) {
      submitting.value = true
      setTimeout(() => {
        ElMessage.success('提交成功（模拟）')
        submitting.value = false
        onClose()
      }, 1000)
    }
  })
}
function onClose() {
  emit('close')
}
</script>

<style scoped>
.apply-dialog-mask {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.08);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
}

.apply-dialog-box {
  width: 400px;
  background: #eaf4ff;
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.10);
  overflow: hidden;
}

.apply-dialog-header {
  background: #1677ff;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: 8px 8px 0 0;
  border-bottom: 3px solid #fff;
}

.close-btn {
  color: #fff;
  font-size: 22px;
  font-weight: bold;
  cursor: pointer;
  transition: color 0.2s;
}

.close-btn:hover {
  color: #ffb6b6;
}

.apply-dialog-body {
  padding: 24px 24px 18px 24px;
  background: #eaf4ff;
}

.el-form {
  background: #eaf4ff;
}

.el-form-item {
  margin-bottom: 16px;
}

.el-form-item__label {
  color: #333;
  font-weight: bold;
  font-size: 15px;
  padding-right: 0;
}

.required {
  color: #ff4d4f;
  margin-right: 2px;
  font-size: 16px;
}

.get-code {
  font-size: 14px;
  margin-left: 4px;
  cursor: pointer;
  user-select: none;
}

.submit-btn {
  width: 100%;
  margin-top: 8px;
  font-size: 16px;
  font-weight: bold;
  background: #bfc7d1;
  border: none;
  color: #fff;
  border-radius: 6px;
  height: 38px;
}

.submit-btn:enabled {
  background: #1677ff;
}
</style>