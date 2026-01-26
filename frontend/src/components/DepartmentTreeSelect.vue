<template>
    <el-tree-select
      v-model="innerValue"
      :data="treeData"
      :props="{ children: 'childDeptVoList', label: 'name', value: 'id' }"
      placeholder="请选择部门"
      style="width: 160px"
      :default-expand-all="true"
      check-strictly
      :render-after-expand="false"
    />
  </template>
  
  <script setup>
  import { ref, watch } from 'vue'
  const props = defineProps({
    modelValue: [String, Number],
    treeData: {
      type: Array,
      default: () => []
    }
  })
  const emit = defineEmits(['update:modelValue'])
  
  const innerValue = ref(props.modelValue)
  
  watch(() => props.modelValue, (val) => {
    innerValue.value = val
  })
  
  watch(innerValue, (val) => {
    emit('update:modelValue', val)
  })
  </script>