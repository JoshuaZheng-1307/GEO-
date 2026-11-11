<template>
  <div class="layout">
    <header class="header">
      <div class="header-inner">
        <router-link to="/" class="logo">
          <span class="logo-mark">G<span class="dot">·</span>E<span class="dot">·</span>O</span>
          <div class="logo-text">
            <h1>监测量化模拟系统</h1>
            <p>Generative Engine Optimization · SHEEP 五维框架</p>
          </div>
        </router-link>
        <nav>
          <router-link to="/" class="nav-link">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M3 12l2-2 4 4 8-8 4 4" />
            </svg>
            监测任务
          </router-link>
          <router-link v-if="auth.isAdmin.value" to="/admin" class="nav-link admin-link">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z" />
            </svg>
            管理控制台
          </router-link>

          <!-- 登录态：余额 + 用户菜单 -->
          <template v-if="auth.isLoggedIn.value">
            <div class="balance" :class="{ low: isLow }"
                 title="每次监测消耗 10 token">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 7v10M9.5 9.5c0-1 1-1.8 2.5-1.8s2.5.8 2.5 1.8-1 1.6-2.5 1.9c-1.5.3-2.5 1-2.5 2s1 1.8 2.5 1.8 2.5-.8 2.5-1.8" />
              </svg>
              {{ auth.isAdmin.value ? '∞' : auth.balance.value.toLocaleString() }}
              <i>token</i>
            </div>
            <div class="user-chip" @click="menuOpen = !menuOpen">
              <span class="avatar">{{ auth.state.user?.username?.slice(0, 1).toUpperCase() }}</span>
              <span class="uname">{{ auth.state.user?.username }}</span>
              <span v-if="auth.isAdmin.value" class="role-badge">管理员</span>
              <transition name="drop">
                <div v-if="menuOpen" class="menu" @click.stop>
                  <button @click="goAdmin">管理控制台</button>
                  <button class="danger" @click="logout">退出登录</button>
                </div>
              </transition>
            </div>
          </template>

          <!-- 未登录 -->
          <router-link v-else to="/login" class="nav-link login-btn">登录 / 注册</router-link>
        </nav>
      </div>
    </header>

    <main class="main">
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <footer class="footer">
      <span>参照 SheepGEO 量化指标模板 · GEM 评分体系 · 模拟数据仅供研究</span>
    </footer>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { auth } from './store/auth'

const router = useRouter()
const menuOpen = ref(false)
const isLow = computed(() => !auth.isAdmin.value && auth.balance.value < 10)

function logout() {
  menuOpen.value = false
  auth.logout()
  router.push('/login')
}
function goAdmin() {
  menuOpen.value = false
  router.push('/admin')
}
function closeMenu() { menuOpen.value = false }
onMounted(() => document.addEventListener('click', closeMenu))
onBeforeUnmount(() => document.removeEventListener('click', closeMenu))
</script>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ============ Header ============ */
.header {
  position: sticky; top: 0; z-index: 50;
  background: rgba(10, 14, 31, 0.72);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  border-bottom: 1px solid var(--border);
}
.header-inner {
  max-width: 1180px; margin: 0 auto;
  padding: 14px 24px;
  display: flex; align-items: center; justify-content: space-between;
  gap: 24px;
}
.logo {
  display: flex; align-items: center; gap: 14px;
  text-decoration: none; color: inherit;
  transition: opacity var(--t-fast) var(--ease);
}
.logo:hover { opacity: 0.85; }

.logo-mark {
  font-weight: 800; font-size: 14px; color: #fff;
  background: var(--accent-grad);
  padding: 9px 12px; border-radius: 10px;
  letter-spacing: 0.5px;
  box-shadow: var(--accent-glow);
  position: relative;
  overflow: hidden;
}
.logo-mark::after {
  content: '';
  position: absolute; inset: 0;
  background: linear-gradient(135deg, transparent 30%, rgba(255,255,255,0.25) 50%, transparent 70%);
  transform: translateX(-100%);
  transition: transform 600ms var(--ease-out);
}
.logo:hover .logo-mark::after { transform: translateX(100%); }
.logo-mark .dot { opacity: 0.55; padding: 0 1px; }

.logo-text h1 {
  font-size: 16px; font-weight: 600; margin: 0;
  letter-spacing: 0.3px;
}
.logo-text p {
  font-size: 11.5px; color: var(--text-mute);
  margin: 2px 0 0; letter-spacing: 0.2px;
}

nav { display: flex; align-items: center; gap: 6px; }
.nav-link {
  display: inline-flex; align-items: center; gap: 6px;
  color: var(--text-soft); text-decoration: none;
  font-size: 13.5px; padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid transparent;
  transition: all var(--t-fast) var(--ease);
}
.nav-link:hover { color: var(--text); background: rgba(255,255,255,0.04); }
.nav-link.router-link-exact-active {
  color: #fff;
  background: rgba(91, 140, 255, 0.16);
  border-color: rgba(91, 140, 255, 0.35);
}
.admin-link.router-link-exact-active {
  color: #ffe3ad;
  background: rgba(240, 164, 106, 0.14);
  border-color: rgba(240, 164, 106, 0.35);
}
.login-btn { border: 1px solid rgba(91, 140, 255, 0.4); color: #a9c4ff; }

/* 余额徽标 */
.balance {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 6px 12px; border-radius: 999px;
  font-size: 12.5px; font-weight: 700;
  color: #7be0a2;
  background: rgba(80, 200, 120, 0.12);
  border: 1px solid rgba(80, 200, 120, 0.3);
  font-feature-settings: 'tnum';
  transition: all var(--t-fast) var(--ease);
}
.balance i { font-style: normal; font-weight: 400; font-size: 10.5px; opacity: 0.8; }
.balance.low {
  color: #ff8a8a;
  background: rgba(255, 120, 120, 0.12);
  border-color: rgba(255, 120, 120, 0.35);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  50% { box-shadow: 0 0 0 4px rgba(255, 120, 120, 0.08); }
}

/* 用户菜单 */
.user-chip {
  position: relative;
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 12px 5px 6px;
  border-radius: 999px;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--t-fast) var(--ease);
}
.user-chip:hover { background: rgba(255,255,255,0.08); }
.avatar {
  width: 26px; height: 26px; border-radius: 50%;
  background: var(--accent-grad);
  color: #fff; font-size: 12px; font-weight: 800;
  display: inline-flex; align-items: center; justify-content: center;
}
.uname { font-size: 13px; color: var(--text); max-width: 90px; overflow: hidden; text-overflow: ellipsis; }
.role-badge {
  font-size: 10px; font-weight: 700; color: #ffd08a;
  background: rgba(240, 164, 106, 0.15);
  border: 1px solid rgba(240, 164, 106, 0.35);
  padding: 2px 7px; border-radius: 999px;
}
.menu {
  position: absolute; top: calc(100% + 8px); right: 0;
  min-width: 150px;
  background: rgba(16, 20, 40, 0.96);
  border: 1px solid var(--border-2);
  border-radius: var(--r-sm);
  box-shadow: 0 16px 40px -12px rgba(0,0,0,0.6);
  overflow: hidden;
  z-index: 60;
}
.menu button {
  display: block; width: 100%;
  padding: 10px 16px;
  background: none; border: none;
  color: var(--text-soft); font-size: 13px;
  text-align: left; cursor: pointer;
  transition: all var(--t-fast) var(--ease);
}
.menu button:hover { background: rgba(255,255,255,0.06); color: var(--text); }
.menu button.danger:hover { color: #ff8a8a; }
.drop-enter-active, .drop-leave-active { transition: all 180ms var(--ease-out); }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-6px); }

/* ============ Main ============ */
.main {
  flex: 1;
  max-width: 1180px; width: 100%;
  margin: 0 auto;
  padding: 28px 24px 40px;
}

/* ============ Footer ============ */
.footer {
  text-align: center;
  padding: 20px 16px 28px;
  font-size: 11.5px; color: var(--text-mute);
  border-top: 1px solid var(--border);
  margin-top: 40px;
}

/* ============ Page transitions ============ */
.page-enter-active, .page-leave-active {
  transition: opacity 300ms var(--ease-out), transform 300ms var(--ease-out);
}
.page-enter-from { opacity: 0; transform: translateY(8px); }
.page-leave-to   { opacity: 0; transform: translateY(-4px); }
</style>
