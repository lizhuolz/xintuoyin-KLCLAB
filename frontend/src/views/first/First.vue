<template>
  <div class="main-page">
    <!-- 顶部导航栏 -->
    <div class="main-header">
      <div class="main-header-title">系统操作界面截图</div>
      <div class="main-header-btns">
        <el-button type="warning" @click="showApplyDialog = true">申请试用</el-button>
        <el-button type="primary" @click="goLogin">企业登录</el-button>
      </div>
    </div>

    <!-- 主体内容 -->
    <div class="main-content">
      <!-- 左侧介绍 -->
      <div class="main-info">
        <h1>项目研发管理体系</h1>
        <p>企业自研项目数智化研发费管理体系</p>
        <div class="main-features">
          <div class="feature-item" v-for="item in features" :key="item.title">
            <img :src="item.icon" class="feature-icon" />
            <div class="feature-title">{{ item.title }}</div>
            <div class="feature-desc">{{ item.desc }}</div>
          </div>
        </div>
      </div>
      <!-- 右侧系统截图 -->
      <div class="main-screenshot">
        <!-- <img src="@/assets/screenshot.png" alt="系统截图" /> -->
      </div>
    </div>
  </div>
  <!-- 申请试用弹窗 -->
  <ApplyDialog v-if="showApplyDialog" @close="showApplyDialog = false" />
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ApplyDialog from '../login/components/ApplyDialog.vue'
const router = useRouter()
const showApplyDialog = ref(false)
function goLogin() {
  router.push('/login')
}

// 功能区数据
const features = [
  {
    icon: 'https://img.icons8.com/ios-filled/50/000000/atom-editor.png',
    title: '信息化与数字化改造',
    desc: ''
  },
  {
    icon: 'https://img.icons8.com/ios-filled/50/000000/process.png',
    title: '项目流程标准化',
    desc: ''
  },
  {
    icon: 'https://img.icons8.com/ios-filled/50/000000/table.png',
    title: '项目矩阵管理',
    desc: ''
  },
  {
    icon: 'https://img.icons8.com/ios-filled/50/000000/server.png',
    title: '项目文件可溯化',
    desc: ''
  }
]
</script>

<style scoped>
.main-page {
  width: 100vw;
  height: 100vh;
  background: #f6fbff;
  min-height: 100vh;
}

.main-header {
  background: #1677ff;
  color: #fff;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  height: 60px;
  padding: 0 40px;
  position: relative;
}

.main-header-title {
  position: absolute;
  left: 40px;
  font-size: 16px;
  font-weight: bold;
}

.main-header-btns {
  display: flex;
  gap: 16px;
}

.main-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 40px 80px 0 80px;
}

.main-info {
  flex: 1;
  min-width: 400px;
}

.main-info h1 {
  color: #1677ff;
  font-size: 32px;
  margin-bottom: 8px;
}

.main-info p {
  color: #6b7b8d;
  margin-bottom: 32px;
}

.main-features {
  display: flex;
  gap: 40px;
  flex-wrap: wrap;
}

.feature-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 120px;
  margin-bottom: 24px;
}

.feature-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 8px;
}

.feature-title {
  font-weight: bold;
  color: #1677ff;
  margin-bottom: 4px;
}

.feature-desc {
  color: #6b7b8d;
  font-size: 13px;
}

.main-screenshot {
  flex: 1;
  display: flex;
  justify-content: flex-end;
  align-items: flex-start;
}

.main-screenshot img {
  width: 480px;
  border-radius: 8px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
  margin-top: 20px;
}
</style>