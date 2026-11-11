import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import ReportDetail from './views/ReportDetail.vue'
import Login from './views/Login.vue'
import Admin from './views/Admin.vue'
import { auth } from './store/auth'
import api from './api'
import './styles/theme.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/login', component: Login, meta: { public: true } },
    { path: '/admin', component: Admin, meta: { admin: true } },
    { path: '/reports/:id', component: ReportDetail, props: true },
  ],
  scrollBehavior() { return { top: 0 } },
})

/* 路由守卫：未登录跳登录页；管理页仅 admin 可入 */
router.beforeEach(async (to) => {
  if (to.meta.public) return true
  if (!auth.isLoggedIn.value) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.admin && !auth.isAdmin.value) return { path: '/' }
  // 刷新后拉最新余额
  if (auth.isLoggedIn.value) {
    api.me().then(({ data }) => auth.setUser(data)).catch(() => {})
  }
  return true
})

createApp(App).use(router).mount('#app')
