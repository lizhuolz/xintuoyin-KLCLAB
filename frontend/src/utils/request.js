import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const DEEPSEEK_BASE_URL = import.meta.env.VITE_DEEPSEEK_BASE_URL || 'https://api.deepseek.com'

const service = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json;charset=UTF-8',
  },
})

service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers = {
        ...config.headers,
        accessToken: token,
      }
    }

    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }

    if (config.method === 'get') {
      config.params = {
        ...config.params,
        _t: Date.now(),
      }
    }

    return config
  },
  (error) => Promise.reject(error),
)

service.interceptors.response.use(
  (response) => {
    const payload = response.data
    const code = payload?.code
    const message = payload?.msg || payload?.message || '请求失败'

    if (code === 401 || code === -3) {
      ElMessage.error(message || '登录已过期，请重新登录')
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      router.push('/login')
      return Promise.reject(new Error(message))
    }

    if (code === 403) {
      ElMessage.error(message || '没有权限访问该资源')
      return Promise.reject(new Error(message))
    }

    return payload
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      const message = data?.msg || data?.message
      switch (status) {
        case 400:
          ElMessage.error(message || '请求参数错误')
          break
        case 401:
          ElMessage.error(message || '登录已过期，请重新登录')
          localStorage.removeItem('token')
          localStorage.removeItem('userInfo')
          router.push('/login')
          break
        case 403:
          ElMessage.error(message || '没有权限访问该资源')
          break
        case 404:
          ElMessage.error(message || '请求的资源不存在')
          break
        case 500:
          ElMessage.error(message || '系统繁忙，请稍后尝试')
          break
        default:
          ElMessage.error(message || '网络错误，请稍后重试')
      }
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请检查网络连接')
    } else {
      ElMessage.error(error.message || '网络连接失败，请检查网络')
    }
    return Promise.reject(error)
  },
)

export default service
export { API_BASE, DEEPSEEK_BASE_URL }
