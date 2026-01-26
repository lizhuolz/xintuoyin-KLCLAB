import { createRouter, createWebHistory } from "vue-router";
import First from '@/views/first/First.vue'
import Login from '@/views/login/Login.vue'
import Layout from '@/views/main/Layout.vue'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/first',
    name: 'First',
    component: First
  },
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/',
    component: Layout,
    children: [
      {
        path: "/home",
        component: () => import("../views/main/home/Home.vue"),
        alias: ["/home/"],
        meta: { title: '首页' }
      },
      {
        path: "",
        redirect: "/home"
      },
      {
        path: "/ai",
        component: () => import("../views/main/ai/index.vue"),
        meta: { title: 'ai' }
      },
      {
        path: "/ai/chat",
        component: () => import("../views/main/ai/LLMChat.vue"),
        meta: { title: 'AI 对话' }
      },
      {
        path: "/ai/kb",
        component: () => import("../views/main/ai/KBManagement.vue"),
        meta: { title: '知识库管理' }
      },
      {
        path: "/org/info",
        component: () => import("../views/main/org/OrgInfo.vue"),
        meta: { title: '企业信息' }
      },
      {
        path: "/hr/staff",
        component: () => import("../views/main/hr/StaffList.vue"),
        meta: { title: '员工列表' }
      },
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/not-found/NotFound.vue')
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

// 路由守卫
// router.beforeEach((to, from, next) => {
//   const token = localStorage.getItem('token')
//   const publicPages = ['/login', '/first']
//   const authRequired = !publicPages.includes(to.path)

//   if (authRequired && !token) {
//     console.log('未登录，重定向到登录页')
//     next('/login')
//   } else if (to.path === '/login' && token) {
//     console.log('已登录，重定向到首页')
//     next('/home')
//   } else {
//     next()
//   }
// })

export default router;
