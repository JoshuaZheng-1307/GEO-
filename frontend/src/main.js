import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import ReportDetail from './views/ReportDetail.vue'
import Login from './views/Login.vue'
import Admin from './views/Admin.vue'
import Onboarding from './views/Onboarding.vue'
import { auth } from './store/auth'
import api from './api'
import './styles/theme.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/onboarding', component: Onboarding, meta: { onboarding: true } },
    { path: '/admin', component: Admin, meta: { admin: true } },
    { path: '/reports/:id', component: ReportDetail, props: true },
  ],
  scrollBehavior() { return { top: 0 } },
})

/* 路由守卫：未登录跳登录 → 未完成引导强制引导页 → 管理页仅 admin */
router.beforeEach(async (to) => {
  if (to.meta.public) return true
  if (!auth.isLoggedIn.value) return { path: '/login', query: { redirect: to.fullPath } }

  // 拉取最新用户信息（余额 / 引导状态），旧 localStorage 也能补全
  try {
    const { data } = await api.me()
    auth.setUser(data)
  } catch (e) {
    if (e?.response?.status === 401) return { path: '/login' }
  }

  if (to.meta.admin && !auth.isAdmin.value) return { path: '/' }

  const isAdmin = auth.isAdmin.value
  const needOnboarding = !isAdmin && auth.state.user?.onboarded === false

  // 新用户必须先完成引导（免费体检）
  if (needOnboarding && !to.meta.onboarding) return { path: '/onboarding' }
  // 已完成的普通用户不再进入引导页（免费额度只一次）
  if (!needOnboarding && to.meta.onboarding && !isAdmin) return { path: '/' }

  return true
})

createApp(App).use(router).mount('#app')
