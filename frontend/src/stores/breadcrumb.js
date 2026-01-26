import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useBreadcrumbStore = defineStore('breadcrumb', () => {
  const breadcrumbList = ref([])
  
  // 添加面包屑
  function addBreadcrumb(breadcrumb) {
    // 检查是否已存在相同路径的面包屑
    const existingIndex = breadcrumbList.value.findIndex(item => item.path === breadcrumb.path)
    if (existingIndex === -1) {
      // 如果不存在，直接添加
      breadcrumbList.value.push(breadcrumb)
    }
    // 如果已存在，不做任何操作，保持现有状态
  }
  
  // 移除面包屑
  function removeBreadcrumb(index) {
    breadcrumbList.value.splice(index, 1)
  }
  
  // 清空面包屑
  function clearBreadcrumb() {
    breadcrumbList.value = []
  }
  
  // 设置面包屑列表
  function setBreadcrumbList(list) {
    breadcrumbList.value = list
  }
  
  // 获取面包屑列表
  function getBreadcrumbList() {
    return breadcrumbList.value
  }
  
  // 检查面包屑是否存在
  function hasBreadcrumb(path) {
    return breadcrumbList.value.some(item => item.path === path)
  }
  
  return {
    breadcrumbList,
    addBreadcrumb,
    removeBreadcrumb,
    clearBreadcrumb,
    setBreadcrumbList,
    getBreadcrumbList,
    hasBreadcrumb
  }
}) 