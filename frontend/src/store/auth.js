/* 账号状态：轻量 reactive store（不引 pinia），token 持久化到 localStorage */
import { computed, reactive } from 'vue'

const STORAGE_KEY = 'geo_auth'

function load() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}
  } catch {
    return {}
  }
}

const state = reactive(load())

export const auth = {
  state,
  isLoggedIn: computed(() => !!state.token),
  isAdmin: computed(() => state.user?.role === 'admin'),
  balance: computed(() => state.user?.token_balance ?? 0),

  setLogin(token, user) {
    state.token = token
    state.user = user
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, user }))
  },
  setBalance(balance) {
    if (state.user) {
      state.user.token_balance = balance
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: state.token, user: state.user }))
    }
  },
  setUser(user) {
    state.user = user
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: state.token, user }))
  },
  logout() {
    state.token = null
    state.user = null
    localStorage.removeItem(STORAGE_KEY)
  },
}
