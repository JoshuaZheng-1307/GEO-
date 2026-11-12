import axios from 'axios'
import { auth } from './store/auth'

const api = axios.create({ baseURL: '/api' })

/* 请求拦截：自动带上 Bearer token */
api.interceptors.request.use((config) => {
  if (auth.state.token) {
    config.headers.Authorization = `Bearer ${auth.state.token}`
  }
  return config
})

/* 响应拦截：401 清会话跳登录；错误统一挂上 message 方便组件读取 */
api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const status = err.response?.status
    if (status === 401 && auth.isLoggedIn) {
      auth.logout()
      if (!location.hash.includes('login')) {
        location.href = '/login?expired=1'
      }
    }
    err.message = err.response?.data?.detail || err.message || '请求失败'
    return Promise.reject(err)
  }
)

export default {
  // 任务
  listTasks: () => api.get('/tasks'),
  createTask: (data) => api.post('/tasks', data),
  deleteTask: (id) => api.delete(`/tasks/${id}`),
  runTask: (id) => api.post(`/tasks/${id}/run`),
  getProgress: (id) => api.get(`/tasks/${id}/progress`),
  listReports: (taskId) => api.get(`/tasks/${taskId}/reports`),
  getReport: (id) => api.get(`/reports/${id}`),
  getHistory: (id) => api.get(`/reports/${id}/history`),
  suggestKeywords: (url, top = 12) => api.get('/keyword-suggestions', { params: { url, top } }),
  siteProfile: (url, hint = null) => api.post('/site-profile', { url, hint }),

  // 账号
  pricing: () => api.get('/auth/pricing'),
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
  myTransactions: (limit = 50) => api.get('/auth/transactions', { params: { limit } }),

  // 注册引导（首次免费分析）
  onboardingStatus: () => api.get('/onboarding/status'),
  onboardingStart: (data) => api.post('/onboarding/start', data),

  // 管理员
  adminStats: () => api.get('/admin/stats'),
  adminUsers: (q = '') => api.get('/admin/users', { params: { q } }),
  adminReports: (q = '', limit = 100) => api.get('/admin/reports', { params: { q, limit } }),
  adminUserTx: (userId, limit = 100) => api.get(`/admin/users/${userId}/transactions`, { params: { limit } }),
  adminRecharge: (userId, amount, note) => api.post(`/admin/users/${userId}/recharge`, { amount, note }),
  adminCreateUser: (data) => api.post('/admin/users', data),
  adminSetRole: (userId, role) => api.post(`/admin/users/${userId}/role`, { role }),
  adminSetActive: (userId, isActive) => api.post(`/admin/users/${userId}/active`, { is_active: isActive }),
  adminResetPassword: (userId, password) => api.post(`/admin/users/${userId}/password`, { password }),
  adminDeleteUser: (userId) => api.delete(`/admin/users/${userId}`),
}
