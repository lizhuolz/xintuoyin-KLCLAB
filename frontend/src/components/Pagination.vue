<template>
  <div class="pagination-wrapper">
    <el-pagination
      :current-page="currentPage"
      :page-size="pageSize"
      :page-sizes="pageSizes"
      :total="total"
      :layout="layout"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  // 当前页码
  currentPage: {
    type: Number,
    default: 1
  },
  // 每页条数
  pageSize: {
    type: Number,
    default: 10
  },
  // 总条数
  total: {
    type: Number,
    default: 0
  },
  // 每页条数选项
  pageSizes: {
    type: Array,
    default: () => [10, 20, 50, 100]
  },
  // 布局
  layout: {
    type: String,
    default: 'prev, pager, next, sizes, jumper'
  }
})

const emits = defineEmits(['update:currentPage', 'update:pageSize', 'change'])

// 分页大小改变
const handleSizeChange = (size) => {
  // 触发事件
  emits('update:pageSize', size)
  emits('update:currentPage', 1)
  emits('change', {
    currentPage: 1,
    pageSize: size
  })
}

// 当前页改变
const handleCurrentChange = (page) => {
  // 触发事件
  emits('update:currentPage', page)
  emits('change', {
    currentPage: page,
    pageSize: props.pageSize
  })
}
</script>

<style scoped>
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  padding: 24px 0;
}
.pagination-wrapper :deep(.pagination-wrapper .el-pagination .el-pager li.is-active){
  background-color: #0D5DFF;
  border-color: #0D5DFF;
  color: #fff;
}

.pagination-wrapper :deep(.el-pagination) {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-wrapper :deep(.el-pagination .btn-prev),
.pagination-wrapper :deep(.el-pagination .btn-next) {
  background-color: #fff;
  border: 1px solid #dcdfe6;
  color: #606266;
  border-radius: 4px;
  padding: 8px 12px;
  min-width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pagination-wrapper :deep(.el-pagination .btn-prev:hover),
.pagination-wrapper :deep(.el-pagination .btn-next:hover) {
  background-color: #f5f7fa;
  border-color: #c0c4cc;
  color: #409eff;
}

.pagination-wrapper :deep(.el-pagination .el-pager li) {
  background-color: #fff;
  border: 1px solid #dcdfe6;
  color: #606266;
  border-radius: 4px;
  min-width: 32px;
  height: 32px;
  line-height: 30px;
  margin: 0 2px;
}

.pagination-wrapper :deep(.el-pagination .el-pager li.is-active) {
  background-color: #409eff;
  border-color: #409eff;
  color: #fff;
}

.pagination-wrapper :deep(.el-pagination .el-pager li:hover) {
  background-color: #f5f7fa;
  border-color: #c0c4cc;
  color: #409eff;
}

.pagination-wrapper :deep(.el-pagination .el-pagination__sizes) {
  margin-left: 16px;
}

.pagination-wrapper :deep(.el-pagination .el-pagination__sizes .el-select .el-input) {
  width: 110px;
}

.pagination-wrapper :deep(.el-pagination .el-pagination__jump) {
  margin-left: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-wrapper :deep(.el-pagination .el-pagination__jump .el-input) {
  width: 50px;
}
</style> 