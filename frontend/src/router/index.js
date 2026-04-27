import { createRouter, createWebHistory } from "vue-router";
import Layout from '@/views/main/Layout.vue'

const routes = [
  {
    path: '/',
    redirect: '/ai/chat'
  },
  {
    path: '/',
    component: Layout,
    children: [
      {
        path: "",
        redirect: "/ai/chat"
      },
      {
        path: "/ai/chat",
        component: () => import("@/views/main/ai/LLMChat.vue"),
        meta: { title: 'AI问答', hideBreadcrumb: true, fullWidth: true }
      },
      {
        path: "/admin/history",
        component: () => import("@/views/main/ai/HistoryManagement.vue"),
        meta: { title: '对话日志', parent: 'AI后台' }
      },
      {
        path: "/admin/feedback",
        component: () => import("@/views/main/ai/FeedbackManagementPage.vue"),
        meta: { title: '反馈列表', parent: 'AI后台 / 反馈管理', mode: 'all' }
      },
      {
        path: "/admin/feedback-negative",
        component: () => import("@/views/main/ai/FeedbackManagementPage.vue"),
        meta: { title: '待优化回答', parent: 'AI后台 / 反馈管理', mode: 'negative' }
      },
      {
        path: "/admin/feedback-positive",
        component: () => import("@/views/main/ai/FeedbackManagementPage.vue"),
        meta: { title: '回答良好', parent: 'AI后台 / 反馈管理', mode: 'positive' }
      },
      {
        path: "/admin/kb",
        component: () => import("@/views/main/ai/KBManagement.vue"),
        meta: { title: '知识库', parent: 'AI后台' }
      },
      {
        path: "/admin/database",
        component: () => import("@/views/main/ai/DatabaseLink.vue"),
        meta: { title: '链接数据库', parent: 'AI后台' }
      },
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/ai/chat'
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

export default router;
