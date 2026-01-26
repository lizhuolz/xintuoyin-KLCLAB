<template>
  <div class="breadcrumb-container">
    <div class="breadcrumb-list">
      <span 
        v-for="(item, index) in breadcrumbList" 
        :key="item.path"
        class="breadcrumb-item"
        :class="{ 'active': item.path === currentPath }"
      >
        <span 
          class="breadcrumb-text"
          @click="handleBreadcrumbClick(item, index)"
        >
          {{ item.title }}
        </span>
        <!-- Close icon removed -->
      </span>
    </div>

    <!-- User Profile Area (Moved from Header) -->
    <div class="user-area">
      <el-dropdown trigger="click" @command="handleCommand">
        <span class="user-trigger">
          <el-avatar
            :size="28"
            :style="{ background: '#7c3aed', color: '#fff', fontSize: '12px' }"
          >
            {{ userName.charAt(0).toUpperCase() }}
          </el-avatar>
          <span class="username">{{ userName }}</span>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><ChatDotRound /></el-icon>
              基础资料
            </el-dropdown-item>
            <el-dropdown-item command="password">
              <el-icon><Edit /></el-icon>
              修改密码
            </el-dropdown-item>
            <el-dropdown-item command="message">
              <el-icon><Bell /></el-icon>
              系统消息
              <el-badge :value="9" is-dot class="badge" style="margin-left:4px;" />
            </el-dropdown-item>
            <el-dropdown-item command="manual">
              <el-icon><Document /></el-icon>
              使用手册
            </el-dropdown-item>
            <el-dropdown-item command="service">
              <el-icon><Service /></el-icon>
              客服咨询
            </el-dropdown-item>
            <el-dropdown-item command="logout" divided>
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Close, ChatDotRound, SwitchButton, Document, Bell, Service, Edit, Fold, Expand } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useBreadcrumbStore } from '@/stores/breadcrumb'
import { useUserStore } from '@/stores/user'
import { useLayoutStore } from '@/stores/layout'

const router = useRouter()
const route = useRoute()
const breadcrumbStore = useBreadcrumbStore()
const userStore = useUserStore()
const layoutStore = useLayoutStore()

// User Logic
const userName = computed(() => userStore.userInfo?.name || userStore.userInfo?.username || '用户')

function handleCommand(command) {
  switch (command) {
    case 'logout':
      userStore.userInfo = {} 
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      router.push('/login')
      ElMessage.success('已退出登录')
      break
    default:
      ElMessage.info('点击了 ' + command)
  }
}

// Breadcrumb Logic
const breadcrumbList = computed(() => breadcrumbStore.breadcrumbList)
const currentPath = computed(() => route.path)

watch(() => route.path, (newPath) => {
    updateBreadcrumb(newPath)
}, { immediate: true })

function updateBreadcrumb(path) {
    const breadcrumbs = generateBreadcrumbFromPath(path)
    const existingIndex = breadcrumbStore.breadcrumbList.findIndex(item => item.path === path)
    
    if (existingIndex === -1) {
        breadcrumbs.forEach(breadcrumb => {
            breadcrumbStore.addBreadcrumb(breadcrumb)
        })
    }
}

function generateBreadcrumbFromPath(path) {
    const breadcrumbs = []
    const matchedRoute = router.resolve(path)
    const title = matchedRoute.meta?.title || '未知页面'
    
    breadcrumbs.push({
        title: title,
        path: path
    })
    return breadcrumbs
}

function handleBreadcrumbClick(item, index) {
  router.push(item.path)
  nextTick(() => { })
}

function handleRemoveBreadcrumb(index) {
  breadcrumbStore.removeBreadcrumb(index)
  if (breadcrumbStore.breadcrumbList.length > 0) {
    const lastBreadcrumb = breadcrumbStore.breadcrumbList[breadcrumbStore.breadcrumbList.length - 1]
    router.push(lastBreadcrumb.path)
  } else {
    router.push('/')
  }
}
</script>

<style scoped>
.breadcrumb-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between; /* Push items apart */
  padding-right: 16px; /* Space for user profile */
}

.breadcrumb-list {
  display: flex;
  align-items: center;
  gap: 8px; /* Slightly more gap */
  flex-wrap: nowrap;
  height: 100%;
  padding: 0 4px;
  overflow-x: auto;
  overflow-y: hidden;
  flex: 1;
}

.breadcrumb-item {
  display: flex;
  align-items: center;
  position: relative;
  background-color: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 6px; /* Larger radius */
  height: 36px; /* Larger height */
  flex-shrink: 0;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
  overflow: hidden;
}

.breadcrumb-item:hover {
  border-color: #c0c4cc;
  background-color: #f5f7fa;
}

.breadcrumb-item.active {
  background-color: #ecf5ff; 
  border-color: #d9ecff;
  color: #409eff;
}

.breadcrumb-text {
  height: 100%;
  font-size: 12px;
  color: #606266;
  cursor: pointer;
  padding: 0 28px 0 12px;
  white-space: nowrap;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  user-select: none;
}

.breadcrumb-item.active .breadcrumb-text {
  color: #409eff; 
  font-weight: 500;
}

.breadcrumb-close {
  font-size: 12px;
  color: #909399;
  cursor: pointer;
  position: absolute;
  top: 50%;
  right: 6px;
  transform: translateY(-50%);
  width: 14px;
  height: 14px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.breadcrumb-close:hover {
  background-color: #c0c4cc;
  color: #fff;
}

.breadcrumb-item.active .breadcrumb-close:hover {
  background-color: #a0cfff;
}

/* User Area Styles */
.user-area {
  flex-shrink: 0;
  margin-left: 12px;
}

.user-trigger {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.2s;
}
.user-trigger:hover {
  background: #f5f5f5;
}

.user-area .el-dropdown .el-icon--right {
  display: none !important; /* Hide the default dropdown arrow icon */
}

.username {
  font-size: 13px;
  margin-left: 8px;
  color: #606266;
  font-weight: 500;
}
</style>