import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useUserStore = defineStore('user', () => {
  // 状态
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || '{}'))
  const tenantList = ref([])
  const selectedTenant = ref(localStorage.getItem('selectedTenant') || '')
  const filePrefix = ref(localStorage.getItem('filePrefix') || '')

  // 计算属性
  const isLoggedIn = computed(() => !!token.value)
  const hasMultipleTenants = computed(() => tenantList.value.length > 1)

  // 方法
  // 设置token
  const setToken = (newToken) => {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  // 设置用户信息
  const setUserInfo = (info) => {
    userInfo.value = info
    localStorage.setItem('userInfo', JSON.stringify(info))
  }

  // 设置租户列表
  const setTenantList = (list) => {
    tenantList.value = list
    // 缓存到localStorage
    localStorage.setItem('tenantList', JSON.stringify(list))
  }

  // 设置选中的租户
  const setSelectedTenant = (tenant) => {
    selectedTenant.value = tenant
    // 缓存到localStorage
    localStorage.setItem('selectedTenant', tenant)
  }

  // 设置文件前缀
  const setFilePrefix = (prefix) => {
    filePrefix.value = prefix
    localStorage.setItem('filePrefix', prefix)
  }

  // 登录成功后的处理
  const handleLoginSuccess = (loginResult) => {
    console.log('handleLoginSuccess 接收到的数据:', loginResult)
    
    // 直接使用data.token
    const tokenValue = loginResult.token
    
    console.log('提取的token值:', tokenValue)
    
    if (!tokenValue) {
      console.error('未找到有效的token字段')
      return false
    }
    
    // 保存token
    setToken(tokenValue)
    
    // 保存用户信息
    if (loginResult.userInfo) {
      setUserInfo(loginResult.userInfo)
    } else if (loginResult.user) {
      setUserInfo(loginResult.user)
    }
    
    console.log('Token保存后的验证:', localStorage.getItem('token'))
    return true
  }

  // 设置租户列表
  const handleTenantListSuccess = (tenantListData) => {
    console.log('handleTenantListSuccess 接收到的数据:', tenantListData)
    
    // 确保数据是数组格式
    let processedData = []
    if (Array.isArray(tenantListData)) {
      processedData = tenantListData
    } else if (tenantListData && Array.isArray(tenantListData.data)) {
      processedData = tenantListData.data
    } else if (tenantListData && tenantListData.data) {
      processedData = [tenantListData.data]
    }
    
    console.log('处理后的租户数据:', processedData)
    setTenantList(processedData)
  }

  // 选择租户
  const handleSelectTenant = (tenantId) => {
    setSelectedTenant(tenantId)
  }

  // 登出处理
  const handleLogout = () => {
    clearUserData()
  }

  // 清除用户数据
  const clearUserData = () => {
    token.value = ''
    userInfo.value = {}
    tenantList.value = []
    selectedTenant.value = ''
    filePrefix.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    localStorage.removeItem('tenantList')
    localStorage.removeItem('selectedTenant')
    localStorage.removeItem('filePrefix')
  }

  // 初始化用户信息
  const initUserInfo = (userInfoData) => {
    if (userInfoData) {
      setUserInfo(userInfoData)
    }
  }

  return {
    // 状态
    token,
    userInfo,
    tenantList,
    selectedTenant,
    filePrefix,
    
    // 计算属性
    isLoggedIn,
    hasMultipleTenants,
    
    // 方法
    setToken,
    setUserInfo,
    setTenantList,
    setSelectedTenant,
    setFilePrefix,
    handleLoginSuccess,
    handleTenantListSuccess,
    handleSelectTenant,
    handleLogout,
    clearUserData,
    initUserInfo
  }
}) 