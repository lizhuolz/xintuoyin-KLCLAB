import axios from "axios";
import { ElMessage } from "element-plus";
import router from "@/router";

// 根据环境动态设置 baseURL
const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const DEEPSEEK_BASE_URL = import.meta.env.VITE_DEEPSEEK_BASE_URL || "https://api.deepseek.com";
let baseURL = API_BASE;

console.log("当前环境:", import.meta.env.MODE);
console.log("API BaseURL:", baseURL);
console.log("DEEPSEEK_BASE_URL:", DEEPSEEK_BASE_URL);

const service = axios.create({
  baseURL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json;charset=UTF-8",
  },
});

// 请求拦截器
service.interceptors.request.use(
  (config) => {
    // 添加 token - 支持多种token格式
    const token = localStorage.getItem("token");
    if (token) {
      config.headers = {
        ...config.headers,
        accessToken: token
      };
    }

    // 关键：如果是 FormData，删除 Content-Type，让 axios 自动处理
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }

    // 添加时间戳防止缓存
    if (config.method === "get") {
      config.params = {
        ...config.params,
        _t: Date.now(),
      };
    }

    return config;
  },
  (error) => {
    console.error("请求错误:", error);
    return Promise.reject(error);
  }
);

// 响应拦截器

service.interceptors.response.use(
  (response) => {
    const { code, message, msg } = response.data;

    // 全局处理登录失效
    if (code === 401 || code === -3) {
      const errorMsg = msg || message || "登录已过期，请重新登录";
      ElMessage.error(errorMsg);
      localStorage.removeItem("token");
      localStorage.removeItem("userInfo");
      router.push("/login");
      return Promise.reject(new Error(errorMsg));
    }

    // 全局处理无权限
    if (code === 403) {
      ElMessage.error(msg || message || "没有权限访问该资源");
      return Promise.reject(new Error(msg || message || "权限不足"));
    }

    // 其它错误不拦截，页面自己判断
    return response.data;
  },
  (error) => {
    // ... 你的原有错误处理保持不变
    if (error.response) {
      const { status, data } = error.response;
      switch (status) {
        case 400:
          ElMessage.error(data.message || "请求参数错误");
          break;
        case 401:
          ElMessage.error("登录已过期，请重新登录");
          localStorage.removeItem("token");
          localStorage.removeItem("userInfo");
          router.push("/login");
          break;
        case 403:
          ElMessage.error("没有权限访问该资源");
          break;
        case 404:
          ElMessage.error("请求的资源不存在");
          break;
        case 500:
          ElMessage.error("系统繁忙，请稍后尝试!");
          break;
        default:
          ElMessage.error("网络错误，请稍后重试");
      }
    } else if (error.code === "ECONNABORTED") {
      ElMessage.error("请求超时，请检查网络连接");
    } else {
      ElMessage.error("网络连接失败，请检查网络");
    }
    return Promise.reject(error);
  }
);


export default service;
export { DEEPSEEK_BASE_URL };
