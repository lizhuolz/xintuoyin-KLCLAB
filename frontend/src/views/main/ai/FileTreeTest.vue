<template>
  <div class="file-tree-container">
    <div class="header">
      <h2>调试页已下线</h2>
      <router-link to="/ai/kb" class="jump-link">前往知识库管理</router-link>
    </div>

    <el-alert
      title="该页面已不再依赖后端调试接口"
      type="info"
      description="原先的 /api/test/file_tree 不在当前 backend/app.py 中，因此这里改为说明页，避免前端出现固定 404。若需要查看知识库文件，请在“知识库管理”页面中直接查看对应库的文件列表。"
      show-icon
      :closable="false"
    />
  </div>
</template>

<style scoped lang="less">
.file-tree-container {
  padding: 24px;
  background: #ffffff;
  min-height: calc(100vh - 64px);
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  h2 {
    margin: 0;
    font-weight: 600;
    color: #303133;
  }
}
.jump-link {
  color: #2f6de6;
  text-decoration: none;
  font-weight: 600;
}
</style>
