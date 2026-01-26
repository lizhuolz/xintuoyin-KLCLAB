<template>
  <div class="sidebar-wrapper">
    <!-- 1. 顶部品牌区 (蓝色背景) -->
    <div class="brand-header" :class="{ collapsed: layoutStore.isCollapse }">
      <div class="logo-icon">
        <!-- 简单的猫形状 SVG -->
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 6C13.66 6 15 7.34 15 8.4C15 9.46 13.66 10.8 12 10.8C10.34 10.8 9 9.46 9 8.4C9 7.34 10.34 6 12 6ZM12 19.2C9.5 19.2 7.29 17.92 6 15.75C6.03 13.75 10 12.66 12 12.66C13.99 12.66 17.97 13.75 18 15.75C16.71 17.92 14.5 19.2 12 19.2Z" fill="white"/>
        </svg>
      </div>
      <span class="brand-text">研发猫</span>
    </div>

    <!-- 2. 滚动菜单区 (白色背景) -->
    <div class="menu-scroll-area">
      <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical-demo"
        :collapse="layoutStore.isCollapse"
        :collapse-transition="false"
        unique-opened
        router
      >
        <el-menu-item index="/home">
          <el-icon><HomeFilled /></el-icon>
          <template #title>首页</template>
        </el-menu-item>

        <!-- 模拟原型图中的层级 -->
        <el-sub-menu index="1">
          <template #title>
            <el-icon><OfficeBuilding /></el-icon>
            <span>我的企业</span>
          </template>
          <el-menu-item index="/org/info">企业信息</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="2">
          <template #title>
            <el-icon><User /></el-icon>
            <span>人事管理</span>
          </template>
          <el-menu-item index="/hr/staff">员工列表</el-menu-item>
        </el-sub-menu>

        <!-- 核心功能区 -->
        <el-sub-menu index="ai">
          <template #title>
            <el-icon><Cpu /></el-icon>
            <span>AI 助手</span>
          </template>
          <el-menu-item index="/ai/chat">
            <template #title>AI 问答</template>
          </el-menu-item>
          <!-- 新增入口 -->
          <el-menu-item index="/ai/kb">
            <template #title>知识库管理</template>
          </el-menu-item>
          <el-menu-item index="/ai/test-tree">
            <template #title>结构测试</template>
          </el-menu-item>
        </el-sub-menu>

      </el-menu>
    </div>

    <!-- 3. 底部收起按钮区 -->
    <div class="collapse-footer" @click="layoutStore.toggleCollapse">
      <el-icon size="16">
        <Expand v-if="layoutStore.isCollapse" />
        <Fold v-else />
      </el-icon>
      <span class="collapse-text" v-if="!layoutStore.isCollapse">收起导航</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { 
  HomeFilled, 
  OfficeBuilding, 
  User, 
  Cpu, 
  Fold, 
  Expand 
} from '@element-plus/icons-vue'
import { useLayoutStore } from '@/stores/layout'

const route = useRoute()
const layoutStore = useLayoutStore()
const activeMenu = computed(() => route.path)
</script>

<style scoped lang="less">
/* 全局布局变量 */
@header-bg: #4080FF; /* 原型图蓝色 */
@menu-bg: #ffffff;
@text-color: #333333;
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

/* 1. 顶部品牌区 */
.brand-header {
  height: 56px;
  background: @header-bg;
  display: flex;
  align-items: center;
  padding: 0 20px;
  color: white;
  flex-shrink: 0;
  transition: padding 0.3s;
  overflow: hidden;

  &.collapsed {
    padding: 0;
    justify-content: center;
    .brand-text {
      display: none;
    }
  }

  .logo-icon {
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .brand-text {
    margin-left: 12px;
    font-size: 16px;
    font-weight: 600;
    white-space: nowrap;
  }
}

/* 2. 菜单区 */
.menu-scroll-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;

  /* 隐藏滚动条但保留功能 */
  &::-webkit-scrollbar {
    width: 0; 
  }
}

/* 覆盖 Element Plus 样式以匹配原型 */
:deep(.el-menu) {
  border-right: none;
}

:deep(.el-menu-item), :deep(.el-sub-menu__title) {
  height: 50px;
  line-height: 50px;
  margin: 4px 8px; /* 悬浮留白效果 */
  border-radius: 4px;
  
  &:hover {
    background-color: #f5f5f5;
  }
}

:deep(.el-menu-item.is-active) {
  background-color: @active-bg;
  color: @active-text;
  font-weight: 500;
}

/* 3. 底部折叠区 */
.collapse-footer {
  height: 48px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  padding-left: 24px;
  cursor: pointer;
  color: #666;
  font-size: 14px;
  flex-shrink: 0;
  
  &:hover {
    color: @active-text;
  }

  .collapse-text {
    margin-left: 12px;
    white-space: nowrap;
  }
}

/* 针对折叠状态的特殊处理 */
:deep(.el-menu--collapse) {
  .el-menu-item, .el-sub-menu__title {
    margin: 4px 0;
    padding: 0 !important;
    display: flex;
    justify-content: center;
  }
}
</style>
