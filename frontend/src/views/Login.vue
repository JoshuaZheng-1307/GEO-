<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <span class="logo-mark">G<span class="dot">·</span>E<span class="dot">·</span>O</span>
        <h1>监测量化模拟系统</h1>
        <p>登录以继续 · 每次监测消耗 {{ pricing.task_cost }} token</p>
      </div>

      <div class="tabs">
        <button :class="{ on: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ on: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <form @submit.prevent="submit">
        <label>
          <span>用户名</span>
          <input v-model.trim="username" autocomplete="username" required minlength="2" />
        </label>
        <label>
          <span>密码</span>
          <input v-model="password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
                 required minlength="6" placeholder="至少 6 位" />
        </label>
        <p v-if="mode === 'register'" class="hint">注册赠送 {{ pricing.signup_bonus }} token 体验额度</p>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="submit" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '请稍候…' : (mode === 'login' ? '登 录' : '注 册 并 登 录') }}
        </button>
      </form>

      <p v-if="expired" class="expired">登录已过期，请重新登录</p>
      <p class="admin-hint">
        管理员账号：<code>admin</code> / <code>123456</code>
        <span>（首次部署默认，登录后请尽快修改）</span>
      </p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { auth } from '../store/auth'

const route = useRoute()
const router = useRouter()

const mode = ref('login')
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const expired = ref(route.query.expired === '1')
const pricing = ref({ task_cost: 10, signup_bonus: 50 })

onMounted(async () => {
  try {
    const { data } = await api.pricing()
    pricing.value = data
  } catch { /* 用默认值 */ }
})

async function submit() {
  error.value = ''
  loading.value = true
  const isRegister = mode.value === 'register'
  try {
    if (isRegister) {
      await api.register({ username: username.value, password: password.value })
    }
    const { data } = await api.login({ username: username.value, password: password.value })
    auth.setLogin(data.access_token, data.user)
    // 新注册用户（或尚未完成引导）先去填写公司信息，免费生成首份报告
    if (isRegister || data.user?.onboarded === false) {
      router.push('/onboarding')
    } else {
      router.push(route.query.redirect || '/')
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: calc(100vh - 140px);
  display: flex; align-items: center; justify-content: center;
}
.login-card {
  width: 100%; max-width: 400px;
  background: rgba(8, 11, 26, 0.6);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 36px 34px 30px;
  backdrop-filter: blur(12px);
  animation: fadeUp 500ms var(--ease-out);
  box-shadow: 0 30px 80px -30px rgba(0, 0, 0, 0.6);
}
.login-logo { text-align: center; margin-bottom: 24px; }
.logo-mark {
  font-weight: 800; font-size: 13px; color: #fff;
  background: var(--accent-grad);
  padding: 8px 11px; border-radius: 10px;
  letter-spacing: 0.5px;
  display: inline-block;
}
.logo-mark .dot { opacity: 0.55; padding: 0 1px; }
.login-logo h1 { font-size: 17px; margin: 14px 0 4px; }
.login-logo p { font-size: 12px; color: var(--text-mute); margin: 0; }

.tabs {
  display: grid; grid-template-columns: 1fr 1fr; gap: 4px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  padding: 4px; margin-bottom: 20px;
}
.tabs button {
  padding: 8px 0; border: none; border-radius: 6px;
  background: transparent; color: var(--text-soft);
  font-size: 13px; cursor: pointer;
  transition: all var(--t-fast) var(--ease);
}
.tabs button.on {
  background: rgba(91, 140, 255, 0.2);
  color: #fff;
  border: 1px solid rgba(91, 140, 255, 0.35);
}

form label { display: block; margin-bottom: 14px; }
form label span {
  display: block; font-size: 12px; color: var(--text-mute); margin-bottom: 6px;
}
form input {
  width: 100%;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  color: var(--text);
  padding: 10px 12px; font-size: 14px;
  transition: border-color var(--t-fast) var(--ease), background var(--t-fast) var(--ease);
}
form input:focus {
  outline: none;
  border-color: rgba(91, 140, 255, 0.55);
  background: rgba(255,255,255,0.08);
}
.hint { font-size: 11.5px; color: var(--text-mute); margin: -6px 0 12px; }
.error {
  font-size: 12px; color: #ff8a8a;
  background: rgba(255, 120, 120, 0.1);
  border: 1px solid rgba(255, 120, 120, 0.25);
  border-radius: var(--r-sm);
  padding: 8px 12px; margin: 0 0 12px;
}
.expired { text-align: center; font-size: 12px; color: #ffc857; margin-top: 14px; }
.admin-hint {
  margin: 18px 0 0; padding-top: 14px;
  border-top: 1px dashed var(--border);
  text-align: center; font-size: 11.5px; color: var(--text-mute);
  line-height: 1.7;
}
.admin-hint code {
  color: #a9c4ff; background: rgba(91,140,255,0.12);
  padding: 1px 6px; border-radius: 4px; font-size: 11.5px;
}
.admin-hint span { display: block; opacity: 0.75; }

.submit {
  width: 100%; padding: 11px 0;
  border: none; border-radius: var(--r-sm);
  background: var(--accent-grad);
  color: #fff; font-size: 14px; font-weight: 700;
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  transition: all var(--t-fast) var(--ease);
  box-shadow: var(--accent-glow);
}
.submit:hover:not(:disabled) { transform: translateY(-1px); filter: brightness(1.08); }
.submit:disabled { opacity: 0.6; cursor: not-allowed; }

.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
