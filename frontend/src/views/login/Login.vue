<template>
  <div class="login-page">
    <div class="login-form-area">
      <el-card class="login-form-card" shadow="always">
        <!-- 标题和tab始终保留 -->
        <div class="login-title">欢迎使用研发猫</div>
        <div class="login-tabs">
          <span class="tab" @click="activeTab = 'phone'">手机号登录</span>
        </div>
        <!-- 表单区域切换 -->
        <div v-if="!showEnterpriseSelect">
          <el-form :model="form" :rules="rules" ref="formRef" label-width="0" class="login-el-form">
            <el-form-item prop="username">
              <el-input v-model="form.username" :placeholder="activeTab === 'phone' ? '请输入手机号' : '请输入账号'" clearable
                class="login-input" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password clearable
                class="login-input" />
            </el-form-item>
            <el-form-item class="login-btn-item">
              <el-button type="primary" class="login-btn" :disabled="!canLogin" @click="onLogin" block>登录</el-button>
            </el-form-item>
          </el-form>
          <div class="forgot-link">忘记密码</div>
          <div class="login-tip">
            登录视为您已同意
            <a href="javascript:;">用户协议</a>
            和
            <a href="javascript:;">隐私政策</a>
          </div>
        </div>
        <div v-else class="enterprise-area">
          <div class="enterprise-title">选择您的企业</div>
          <div class="enterprise-subtitle">请选择要登录的企业账号</div>
          <!-- 调试信息 -->
          <div style="font-size: 12px; color: #999; margin-bottom: 10px;">
          </div>
          <el-select v-model="selectedEnterprise" placeholder="请选择企业" class="enterprise-select" filterable>
            <el-option v-for="item in enterpriseList" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-button type="primary" class="enterprise-btn" @click="onEnterpriseLogin" :disabled="!selectedEnterprise"
            block>确认登录</el-button>
          <el-button class="enterprise-back" @click="onBack" block>返回上一步</el-button>
        </div>
      </el-card>
    </div>
    <div class="login-banner-area">
      <div class="banner-img-box">
        <!-- <img src="@/assets/login-banner.png" alt="R&D" /> -->
      </div>
      <div class="banner-title">研发猫 — 科研系统引领者</div>
      <div class="banner-desc">智能统计 合法合规</div>
    </div>
  </div>
</template>
<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { loginByPwd, getTenantList, tenantLogin } from '@/api/user'
import { getPrefixAddress } from '@/api/hr'
import { useRouter } from 'vue-router'
const router = useRouter()

const activeTab = ref('phone')
const formRef = ref()
const form = ref({
  username: '',
  password: ''
})
const canLogin = computed(() => {
  return form.value.username && form.value.password
})
const rules = {
  username: [
    { required: true, message: '请输入手机号/账号', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

// 使用用户store
const userStore = useUserStore()

// 企业选择相关
const showEnterpriseSelect = ref(false)
const enterpriseList = computed(() => {
  console.log('enterpriseList computed - userStore.tenantList:', userStore.tenantList)
  const mappedList = userStore.tenantList.map(item => ({
    label: item.tenantName,
    value: item.tenantId
  })).filter(option => option.label && option.value)
  console.log('enterpriseList mapped result:', mappedList)
  return mappedList
})
const selectedEnterprise = ref('')
// 切换tab时清空表单
watch(activeTab, () => {
  form.value.username = ''
  form.value.password = ''
})

async function onLogin() {
  console.log('表单数据:', form.value)
  console.log('canLogin状态:', canLogin.value)

  try {
    await formRef.value.validate();

    let params = {
      username: form.value.username,
      password: form.value.password
    };

    // 调用登录接口
    const res = await loginByPwd(params);
  
    console.log('登录响应:', res)

    // 检查登录响应是否成功
    if (!res || res.code !== 0) {
      ElMessage.error(res?.msg || '登录失败，请检查用户名和密码')
      return
    }

    // 检查token是否存在
    if (!res.data || !res.data.token) {
      console.error('登录响应中没有token:', res.data)
      ElMessage.error('登录失败：未获取到有效的登录凭证')
      return
    }

    // 登录成功后，保存token和用户信息到store
    const saveSuccess = userStore.handleLoginSuccess(res.data);

    if (!saveSuccess) {
      console.error('Token保存失败')
      ElMessage.error('登录失败：无法保存登录凭证')
      return
    }

    // 获取文件前缀
    try {
      const prefixRes = await getPrefixAddress()
      if (prefixRes.code === 0 && prefixRes.data) {
        userStore.setFilePrefix(prefixRes.data)
      }
    } catch (prefixErr) {
    }
    
    // 验证token是否成功保存
    const savedToken = localStorage.getItem('token')
    console.log('保存的token:', savedToken)
    
    if (!savedToken) {
      console.error('Token保存失败')
      ElMessage.error('登录失败：无法保存登录凭证')
      return
    }

    // 判断企业数量 - 修改判断条件
    if (res.data.tenantCode > 1 || (res.data.tenantList && res.data.tenantList.length > 1)) {
      // 获取租户列表
      try {
        const tenantListRes = await getTenantList();
        console.log('租户列表API响应:', tenantListRes)
        
        // 检查API返回的数据结构
        const tenantData = tenantListRes.data || tenantListRes
        
        userStore.handleTenantListSuccess(tenantData);
        
        // 确保有租户数据才显示选择界面
        if (userStore.tenantList && userStore.tenantList.length > 0) {
          showEnterpriseSelect.value = true;
        } else {
          // 如果没有租户数据，直接跳转
          setTimeout(() => {
            ElMessage.success('登录成功')
            router.push('/home')
          }, 1000)
        }
      } catch (tenantErr) {
        console.error('获取企业列表失败:', tenantErr)
        ElMessage.error('获取企业列表失败')
        // 获取失败时也直接跳转
        setTimeout(() => {
          ElMessage.success('登录成功')
          router.push('/home')
        }, 1000)
      }
    } else {
      // 直接登录成功逻辑
      setTimeout(() => {
        ElMessage.success('登录成功')
        router.push('/home')
      }, 1000)
    }
  } catch (err) {
    console.error('登录失败:', err)
    ElMessage.error('登录失败，请检查用户名和密码')
  }
}
// 选择企业后登录逻辑
async function onEnterpriseLogin() {
  if (selectedEnterprise.value) {
    try {
      console.log('选择的企业ID:', selectedEnterprise.value);

      // 调用租户登录接口
      const tenantRes = await tenantLogin(selectedEnterprise.value);
      
      console.log('租户登录响应:', tenantRes)
      
      // 检查租户登录是否成功
      if (!tenantRes || tenantRes.code !== 0) {
        ElMessage.error(tenantRes?.msg || '企业登录失败')
        return
      }

      // 保存选中的租户到store
      userStore.handleSelectTenant(selectedEnterprise.value);
      
      // 验证token是否仍然存在
      const currentToken = localStorage.getItem('token')
      console.log('企业登录后的token:', currentToken)
      
      if (!currentToken) {
        console.error('企业登录后token丢失')
        ElMessage.error('企业登录失败：登录凭证已失效')
        return
      }
      
      setTimeout(() => {
        ElMessage.success('登录成功');
        router.push('/home')
      }, 500);
    } catch (error) {
      console.error('企业登录失败:', error)
      ElMessage.error('企业登录失败，请重试')
    }
  }
}
function onBack() {
  showEnterpriseSelect.value = false
  selectedEnterprise.value = ''
  // 清除租户列表
  userStore.setTenantList([])
}
</script>
<style scoped>
.login-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  background: #e9edf5;
}

.login-form-area {
  width: 50%;
  min-width: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-form-card {
  width: 380px;
  border-radius: 12px;
  box-shadow: 0 4px 24px 0 rgba(0, 0, 0, 0.08);
  padding: 40px 32px 24px 32px;
  border: none;
  position: relative;
  min-height: 420px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

.login-title {
  font-size: 22px;
  font-weight: bold;
  margin-bottom: 32px;
  text-align: center;
}

.login-tabs {
  display: flex;
  justify-content: center;
  margin-bottom: 24px;

  .tab {
    font-size: 18px;
    color: #1976d2;
    font-weight: 700;
    cursor: pointer;
    padding: 0 12px 8px 12px;
    border-bottom: 2px solid transparent;
  }

  .tab.active {
    border-bottom: 2px solid #1976d2;
  }
}

.enterprise-area {
  margin-top: 12px;
  box-sizing: border-box;
}

.enterprise-title {
  font-size: 24px;
  font-weight: bold;
  text-align: center;
  margin-bottom: 8px;
  box-sizing: border-box;
}

.enterprise-subtitle {
  text-align: center;
  color: #888;
  margin-bottom: 20px;
  box-sizing: border-box;
  font-size: 15px;
}

.enterprise-select {
  width: 100%;
  margin-bottom: 24px;
  box-sizing: border-box;
}

.enterprise-btn {
  width: 100%;
  margin-bottom: 12px;
  box-sizing: border-box;
  font-size: 16px;
  height: 44px;
}

.enterprise-back {
  width: 100%;
  background: #f5f6fa;
  color: #666;
  border: none;
  font-size: 16px;
  height: 44px;
  border-radius: 8px;
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

.login-el-form {
  margin-bottom: 0;
  box-sizing: border-box;
}

.login-input {
  height: 44px;
  font-size: 15px;
  border-radius: 8px;
  box-sizing: border-box;
}

.login-btn-item {
  margin-bottom: 0;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: 18px;
  border-radius: 8px;
  margin-top: 8px;
  background: #1976d2;
  border: none;
  box-sizing: border-box;
}

.login-btn[disabled] {
  background: #d3d6db !important;
  color: #fff !important;
  border: none !important;
}

.forgot-link {
  color: #bdbdbd;
  font-size: 14px;
  cursor: pointer;
  text-align: right;
  margin-top: 8px;
  margin-bottom: 0;
  box-sizing: border-box;
}

.login-tip {
  position: absolute;
  left: 32px;
  bottom: 18px;
  color: #999;
  font-size: 12px;
  text-align: left;

  a {
    color: #1976d2;
    text-decoration: underline;
    margin: 0 2px;
  }
}

.login-banner-area {
  flex: 1;
  background: #fff;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.banner-img-box {
  width: 420px;
  margin-bottom: 18px;
}

.banner-img-box img {
  width: 100%;
  display: block;
}

.banner-title {
  font-size: 22px;
  color: #1677ff;
  font-weight: bold;
  margin-bottom: 8px;
  text-align: center;
}

.banner-desc {
  color: #666;
  font-size: 15px;
  text-align: center;
}
</style>