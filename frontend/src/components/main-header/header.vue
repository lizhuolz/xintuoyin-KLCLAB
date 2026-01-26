<template>
  <div class="main-header">
    <div class="left">
      <!-- 删除了原有的 Menu 按钮和 Logo 文字 -->
      <span class="page-title"></span>
    </div>
    <div class="right">
      <el-dropdown trigger="click" @command="handleCommand">
        <span class="user-trigger">
          <el-avatar
            :size="32"
            :style="{ background: '#7c3aed', color: '#fff', fontSize: '14px' }"
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
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ChatDotRound, SwitchButton, Document, Bell, Service, Edit } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const userName = computed(() => userStore.userInfo?.name || userStore.userInfo?.username || '用户')

function handleCommand(command) {
  switch (command) {
    case 'logout':
      userStore.userInfo = {} // 清除 store
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      router.push('/login')
      ElMessage.success('已退出登录')
      break
    default:
      ElMessage.info('点击了 ' + command)
  }
}
</script>

<style scoped>
.main-header {
  width: 100%;
  height: 100%;
  background: #ffffff; /* 改为白色 */
  border-bottom: 1px solid #e0e0e0; /* 底部细线 */
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-sizing: border-box;
}

.left {
  display: flex;
  align-items: center;
}

.right {
  display: flex;
  align-items: center;
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

.username {
  font-size: 14px;
  margin-left: 8px;
  color: #333; /* 文字改黑 */
  font-weight: 500;
}

</style>
