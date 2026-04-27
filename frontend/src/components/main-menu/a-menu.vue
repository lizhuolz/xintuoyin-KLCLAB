<template>
  <div class="sidebar-wrapper">
    <!-- 顶部品牌区 -->
    <div class="brand-header" :class="{ collapsed: layout.isCollapse }">
      <div class="logo-icon">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 6C13.66 6 15 7.34 15 8.4C15 9.46 13.66 10.8 12 10.8C10.34 10.8 9 9.46 9 8.4C9 7.34 10.34 6 12 6ZM12 19.2C9.5 19.2 7.29 17.92 6 15.75C6.03 13.75 10 12.66 12 12.66C13.99 12.66 17.97 13.75 18 15.75C16.71 17.92 14.5 19.2 12 19.2Z" fill="white"/>
        </svg>
      </div>
      <span class="brand-text">研发猫AI</span>
    </div>

    <!-- 滚动菜单区 -->
    <div class="menu-scroll-area">
      <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical-demo"
        :collapse="layout.isCollapse"
        :collapse-transition="false"
        unique-opened
        router
      >
        <!-- AI问答（用户端） -->
        <el-menu-item index="/ai/chat">
          <template #title>AI问答</template>
        </el-menu-item>

        <!-- AI后台（管理端） -->
        <el-sub-menu index="admin">
          <template #title>
            <span>AI后台</span>
          </template>

          <el-menu-item index="/admin/history">
            <template #title>对话日志</template>
          </el-menu-item>

          <el-menu-item index="/admin/kb">
            <template #title>知识库</template>
          </el-menu-item>

          <el-menu-item index="/admin/database">
            <template #title>链接数据库</template>
          </el-menu-item>

          <el-sub-menu index="admin-feedback">
            <template #title>
              <span>反馈管理</span>
            </template>
            <el-menu-item index="/admin/feedback">反馈列表</el-menu-item>
            <el-menu-item index="/admin/feedback-negative">待优化回答</el-menu-item>
            <el-menu-item index="/admin/feedback-positive">回答良好</el-menu-item>
          </el-sub-menu>
        </el-sub-menu>
      </el-menu>
    </div>

    <!-- 底部收起按钮区 -->
    <div class="collapse-footer" @click="layout.toggleCollapse">
      <el-icon size="16">
        <Expand v-if="layout.isCollapse" />
        <Fold v-else />
      </el-icon>
      <span class="collapse-text" v-if="!layout.isCollapse">收起导航</span>
    </div>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import { useRoute } from 'vue-router'
import { Fold, Expand } from '@element-plus/icons-vue'

const route = useRoute()
const layout = inject('layout')
const activeMenu = computed(() => route.path)
</script>

<style scoped lang="less">
@header-bg: #4080FF;
@menu-bg: #ffffff;
@active-bg: #e6f7ff;
@active-text: #1890ff;

.sidebar-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: @menu-bg;
  border-right: 1px solid #e8e8e8;
  transition: width 0.3s;
  overflow: hidden;
}

.brand-header {
  height: 56px;
  background: @header-bg;
  display: flex;
  align-items: center;
  padding: 0 20px;
  color: white;
  flex-shrink: 0;
  &.collapsed { padding: 0; justify-content: center; .brand-text { display: none; } }
  .logo-icon { width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; }
  .brand-text { margin-left: 12px; font-size: 16px; font-weight: 600; white-space: nowrap; }
}

.menu-scroll-area { flex: 1; overflow-y: auto; &::-webkit-scrollbar { width: 0; } }

:deep(.el-menu) { border-right: none; }
:deep(.el-menu-item), :deep(.el-sub-menu__title) {
  height: 50px; line-height: 50px; margin: 4px 8px; border-radius: 4px;
  &:hover { background-color: #f5f5f5; }
}
:deep(.el-menu-item.is-active) { background-color: @active-bg; color: @active-text; font-weight: 500; }

// 强制 AI后台 下的子菜单项和嵌套子菜单标题对齐
:deep(.el-sub-menu .el-menu .el-menu-item) {
  padding-left: 45px !important;
}
:deep(.el-sub-menu .el-menu .el-sub-menu > .el-sub-menu__title) {
  padding-left: 45px !important;
}
// 反馈管理展开后的三级菜单项再缩进
:deep(.el-sub-menu .el-menu .el-sub-menu .el-menu .el-menu-item) {
  padding-left: 65px !important;
}

.collapse-footer {
  height: 48px; border-top: 1px solid #f0f0f0; display: flex; align-items: center; padding-left: 24px;
  cursor: pointer; color: #666; font-size: 14px;
  &:hover { color: @active-text; }
  .collapse-text { margin-left: 12px; white-space: nowrap; }
}
</style>
