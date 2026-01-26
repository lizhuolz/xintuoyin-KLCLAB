<template>
  <div class="file-tree-container">
    <div class="header">
      <h2>知识库物理结构测试</h2>
      <el-button type="primary" size="small" @click="fetchTree" :loading="loading">
        刷新结构
      </el-button>
    </div>
    
    <div class="tree-wrapper">
      <el-tree
        :data="treeData"
        :props="defaultProps"
        default-expand-all
        highlight-current
      >
        <template #default="{ node, data }">
          <span class="custom-tree-node">
            <el-icon v-if="data.children" class="folder-icon"><FolderOpened /></el-icon>
            <el-icon v-else class="file-icon"><Document /></el-icon>
            <span>{{ node.label }}</span>
          </span>
        </template>
      </el-tree>
    </div>

    <div class="info-footer">
      <el-alert
        title="提示"
        type="info"
        description="此页面仅用于开发调试，展示后端 documents/ 目录下的真实物理文件层级，与 RAG 检索范围一一对应。"
        show-icon
        :closable="false"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { FolderOpened, Document } from '@element-plus/icons-vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const treeData = ref([])
const loading = ref(false)

const defaultProps = {
  children: 'children',
  label: 'label',
}

const fetchTree = async () => {
  loading.value = true
  try {
    const res = await axios.get('/api/test/file_tree')
    treeData.value = res.data
  } catch (err) {
    ElMessage.error('获取文件树失败')
  } finally {
    loading.value = false
  }
}

onMounted(fetchTree)
</script>

<style scoped lang="less">
.file-tree-container {
  padding: 24px;
  background: #ffffff;
  min-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  h2 { margin: 0; font-weight: 600; color: #303133; }
}

.tree-wrapper {
  flex: 1;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 20px;
  background: #fafafa;
  overflow-y: auto;
}

.custom-tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  
  .folder-icon { color: #e6a23c; }
  .file-icon { color: #909399; }
}

.info-footer {
  margin-top: 24px;
}
</style>
