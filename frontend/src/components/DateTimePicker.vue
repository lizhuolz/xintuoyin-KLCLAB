<template>
  <el-date-picker
    v-model="dateValue"
    type="date"
    placeholder="请选择日期"
    format="YYYY-MM-DD"
    value-format="YYYY-MM-DD"
    :disabled="disabled"
    :clearable="clearable"
    :editable="editable"
    :size="size"
    :disabled-date="disabledDate"
    :shortcuts="shortcuts"
    style="width: 100%"
    @change="handleChange"
  />
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: [String, Date],
    default: ''
  },
  disabled: {
    type: Boolean,
    default: false
  },
  clearable: {
    type: Boolean,
    default: true
  },
  editable: {
    type: Boolean,
    default: false
  },
  size: {
    type: String,
    default: 'default'
  },
  // 是否禁用未来日期
  disableFuture: {
    type: Boolean,
    default: false
  },
  // 是否禁用过去日期
  disablePast: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'change'])

const dateValue = ref(props.modelValue)

// 快捷选项
const shortcuts = [
  {
    text: '今天',
    value: new Date()
  },
  {
    text: '昨天',
    value: () => {
      const date = new Date()
      date.setTime(date.getTime() - 3600 * 1000 * 24)
      return date
    }
  },
  {
    text: '一周前',
    value: () => {
      const date = new Date()
      date.setTime(date.getTime() - 3600 * 1000 * 24 * 7)
      return date
    }
  }
]

// 禁用日期函数
const disabledDate = (time) => {
  if (props.disableFuture) {
    return time.getTime() > Date.now()
  }
  if (props.disablePast) {
    return time.getTime() < Date.now() - 8.64e7 // 禁用昨天及之前的日期
  }
  return false
}

// 监听外部传入的值变化
watch(() => props.modelValue, (newVal) => {
  dateValue.value = newVal
})

// 监听内部值变化，向外部发送更新
watch(dateValue, (newVal) => {
  emit('update:modelValue', newVal)
})

// 处理日期变化
const handleChange = (value) => {
  emit('change', value)
}
</script>

<style scoped>
/* 可以添加自定义样式 */
</style> 