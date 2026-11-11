<template>
  <div class="admin">
    <header class="page-head reveal">
      <h1>管理控制台</h1>
      <p>用户管理 · token 充值 · 消费审计</p>
    </header>

    <!-- 总览 -->
    <div class="stats reveal" :style="{ '--delay': '60ms' }">
      <div class="stat">
        <span class="label">注册用户</span>
        <span class="value">{{ stats.total_users ?? '—' }}</span>
      </div>
      <div class="stat">
        <span class="label">当前流通余额</span>
        <span class="value green">{{ (stats.total_balance ?? 0).toLocaleString() }}</span>
      </div>
      <div class="stat">
        <span class="label">累计发放</span>
        <span class="value">{{ (stats.total_recharged ?? 0).toLocaleString() }}</span>
      </div>
      <div class="stat">
        <span class="label">累计消耗</span>
        <span class="value orange">{{ Math.abs(stats.total_consumed ?? 0).toLocaleString() }}</span>
      </div>
      <div class="stat">
        <span class="label">单价 / 次监测</span>
        <span class="value">{{ stats.task_cost ?? 10 }} token</span>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar reveal" :style="{ '--delay': '120ms' }">
      <input v-model.trim="q" class="search" placeholder="按用户名搜索…" @input="loadUsers" />
      <button class="btn primary" @click="openCreate">＋ 创建用户</button>
    </div>

    <!-- 用户表 -->
    <div class="table-card reveal" :style="{ '--delay': '180ms' }">
      <table>
        <thead>
          <tr>
            <th>用户</th>
            <th>角色</th>
            <th>token 余额</th>
            <th>状态</th>
            <th>注册时间</th>
            <th class="ops-col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>
              <div class="cell-user">
                <span class="avatar" :class="{ admin: u.role === 'admin' }">{{ u.username.slice(0, 1).toUpperCase() }}</span>
                <b>{{ u.username }}</b>
              </div>
            </td>
            <td>
              <span class="tag" :class="u.role">
                {{ u.role === 'admin' ? '管理员 · 无限' : '普通用户' }}
              </span>
            </td>
            <td class="num">{{ u.role === 'admin' ? '∞' : u.token_balance.toLocaleString() }}</td>
            <td>
              <span class="tag" :class="u.is_active ? 'on' : 'off'">
                {{ u.is_active ? '正常' : '已禁用' }}
              </span>
            </td>
            <td class="mute">{{ fmtDate(u.created_at) }}</td>
            <td class="ops-col">
              <div class="ops">
                <button v-if="u.role !== 'admin'" class="op charge" @click="openRecharge(u)">充值</button>
                <button v-if="u.role !== 'admin'" class="op" @click="toggleRole(u)">{{ u.role === 'admin' ? '降为用户' : '设为管理员' }}</button>
                <button v-if="u.id !== meId" class="op" @click="toggleActive(u)">{{ u.is_active ? '禁用' : '启用' }}</button>
                <button class="op tx" @click="openTx(u)">流水</button>
                <button v-if="u.id !== meId" class="op danger" @click="resetPwd(u)">改密</button>
                <button v-if="u.id !== meId" class="op danger" @click="removeUser(u)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!users.length" class="empty">没有匹配的用户</p>
    </div>

    <!-- 充值弹窗 -->
    <transition name="fade">
      <div v-if="dlg === 'recharge'" class="mask" @click.self="dlg = null">
        <div class="dialog">
          <h3>充值 · {{ target?.username }}</h3>
          <p class="dlg-sub">当前余额 {{ target?.token_balance.toLocaleString() }} token</p>
          <div class="quick">
            <button v-for="n in [100, 500, 1000, 5000]" :key="n" @click="amount = n">+{{ n }}</button>
          </div>
          <label class="dlg-field">
            <span>数量（正充值 / 负扣减）</span>
            <input v-model.number="amount" type="number" />
          </label>
          <label class="dlg-field">
            <span>备注</span>
            <input v-model.trim="note" placeholder="如：月度套餐 / 手动调整" />
          </label>
          <p v-if="dlgError" class="dlg-error">{{ dlgError }}</p>
          <div class="dlg-actions">
            <button class="btn" @click="dlg = null">取消</button>
            <button class="btn primary" :disabled="busy" @click="doRecharge">{{ busy ? '处理中…' : '确认' }}</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 创建用户弹窗 -->
    <transition name="fade">
      <div v-if="dlg === 'create'" class="mask" @click.self="dlg = null">
        <div class="dialog">
          <h3>创建用户</h3>
          <label class="dlg-field">
            <span>用户名</span>
            <input v-model.trim="newName" minlength="2" />
          </label>
          <label class="dlg-field">
            <span>初始密码（≥6 位）</span>
            <input v-model="newPwd" type="password" minlength="6" />
          </label>
          <p class="dlg-sub">创建后赠送 {{ pricing.signup_bonus }} token</p>
          <p v-if="dlgError" class="dlg-error">{{ dlgError }}</p>
          <div class="dlg-actions">
            <button class="btn" @click="dlg = null">取消</button>
            <button class="btn primary" :disabled="busy" @click="doCreate">{{ busy ? '创建中…' : '创建' }}</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 流水弹窗 -->
    <transition name="fade">
      <div v-if="dlg === 'tx'" class="mask" @click.self="dlg = null">
        <div class="dialog wide">
          <h3>token 流水 · {{ target?.username }}</h3>
          <div class="tx-list">
            <div v-for="t in txList" :key="t.id" class="tx" :class="{ minus: t.amount < 0 }">
              <span class="tx-amount">{{ t.amount > 0 ? '+' : '' }}{{ t.amount }}</span>
              <span class="tx-reason">{{ reasonLabel(t.reason) }}</span>
              <span class="tx-note">{{ t.note || '—' }}</span>
              <span class="tx-balance">余 {{ t.balance_after.toLocaleString() }}</span>
              <span class="tx-date">{{ fmtDate(t.created_at) }}</span>
            </div>
          </div>
          <p v-if="!txList.length" class="empty">暂无流水</p>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'
import { auth } from '../store/auth'

const meId = computed(() => auth.state.user?.id)
const stats = ref({})
const users = ref([])
const q = ref('')
const pricing = ref({ signup_bonus: 50 })

const dlg = ref(null)          // null | recharge | create | tx
const target = ref(null)
const amount = ref(500)
const note = ref('')
const newName = ref('')
const newPwd = ref('')
const txList = ref([])
const busy = ref(false)
const dlgError = ref('')

onMounted(async () => {
  loadStats()
  loadUsers()
  try { pricing.value = (await api.pricing()).data } catch { /* ignore */ }
})

async function loadStats() {
  try { stats.value = (await api.adminStats()).data } catch { /* ignore */ }
}
async function loadUsers() {
  try { users.value = (await api.adminUsers(q.value)).data } catch { /* ignore */ }
}

function fmtDate(s) {
  return new Date(s).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
function reasonLabel(r) {
  return { recharge: '充值', consume: '消费', refund: '退款', signup_bonus: '注册赠送', adjust: '调整' }[r] || r
}

/* ---- 充值 ---- */
function openRecharge(u) {
  target.value = u
  amount.value = 500
  note.value = ''
  dlgError.value = ''
  dlg.value = 'recharge'
}
async function doRecharge() {
  if (!amount.value || amount.value === 0) { dlgError.value = '数量不能为 0'; return }
  busy.value = true
  dlgError.value = ''
  try {
    const { data } = await api.adminRecharge(target.value.id, amount.value, note.value || undefined)
    target.value = data
    Object.assign(users.value.find(x => x.id === data.id) || {}, data)
    dlg.value = null
    loadStats()
  } catch (e) {
    dlgError.value = e.message
  } finally {
    busy.value = false
  }
}

/* ---- 创建 ---- */
function openCreate() {
  newName.value = ''
  newPwd.value = ''
  dlgError.value = ''
  dlg.value = 'create'
}
async function doCreate() {
  if (newName.value.length < 2 || newPwd.value.length < 6) {
    dlgError.value = '用户名 ≥2 位、密码 ≥6 位'
    return
  }
  busy.value = true
  try {
    await api.adminCreateUser({ username: newName.value, password: newPwd.value })
    dlg.value = null
    loadUsers()
    loadStats()
  } catch (e) {
    dlgError.value = e.message
  } finally {
    busy.value = false
  }
}

/* ---- 其它操作 ---- */
async function toggleRole(u) {
  const role = u.role === 'admin' ? 'user' : 'admin'
  if (!confirm(`将「${u.username}」设为${role === 'admin' ? '管理员（额度无限）' : '普通用户'}？`)) return
  try {
    Object.assign(u, (await api.adminSetRole(u.id, role)).data)
  } catch (e) { alert(e.message) }
}
async function toggleActive(u) {
  try {
    Object.assign(u, (await api.adminSetActive(u.id, !u.is_active)).data)
  } catch (e) { alert(e.message) }
}
async function resetPwd(u) {
  const pwd = prompt(`设置「${u.username}」的新密码（≥6 位）：`)
  if (!pwd) return
  try {
    await api.adminResetPassword(u.id, pwd)
    alert('密码已重置')
  } catch (e) { alert(e.message) }
}
async function removeUser(u) {
  if (!confirm(`确定删除用户「${u.username}」？其任务与流水将一并删除。`)) return
  try {
    await api.adminDeleteUser(u.id)
    users.value = users.value.filter(x => x.id !== u.id)
    loadStats()
  } catch (e) { alert(e.message) }
}
async function openTx(u) {
  target.value = u
  txList.value = []
  dlg.value = 'tx'
  try { txList.value = (await api.adminUserTx(u.id)).data } catch { /* ignore */ }
}
</script>

<style scoped>
.admin { display: flex; flex-direction: column; gap: 18px; }
.page-head h1 { margin: 0; font-size: 22px; }
.page-head p { margin: 4px 0 0; font-size: 13px; color: var(--text-mute); }

/* 总览 */
.stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.stat {
  padding: 16px 18px;
  background: rgba(8, 11, 26, 0.45);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  display: flex; flex-direction: column; gap: 6px;
}
.stat .label { font-size: 11.5px; color: var(--text-mute); }
.stat .value { font-size: 22px; font-weight: 800; font-feature-settings: 'tnum'; }
.stat .value.green { color: #7be0a2; }
.stat .value.orange { color: #ffb27d; }

/* 工具栏 */
.toolbar { display: flex; gap: 10px; }
.search {
  flex: 1; max-width: 320px;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  color: var(--text);
  padding: 9px 14px; font-size: 13px;
}
.search:focus { outline: none; border-color: rgba(91, 140, 255, 0.55); }

.btn {
  padding: 9px 18px;
  border-radius: var(--r-sm);
  border: 1px solid var(--border-2);
  background: rgba(255,255,255,0.05);
  color: var(--text);
  font-size: 13px; cursor: pointer;
  transition: all var(--t-fast) var(--ease);
}
.btn:hover { background: rgba(255,255,255,0.09); }
.btn.primary {
  background: var(--accent-grad);
  border: none; color: #fff; font-weight: 700;
  box-shadow: var(--accent-glow);
}
.btn.primary:hover { filter: brightness(1.08); }
.btn:disabled { opacity: 0.55; cursor: not-allowed; }

/* 表格 */
.table-card {
  background: rgba(8, 11, 26, 0.45);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  overflow-x: auto;
}
table { width: 100%; border-collapse: collapse; min-width: 860px; }
th, td { padding: 12px 16px; text-align: left; font-size: 13px; }
th {
  color: var(--text-mute); font-weight: 600; font-size: 11.5px;
  border-bottom: 1px solid var(--border);
  letter-spacing: 0.4px;
}
tbody tr { border-bottom: 1px solid rgba(255,255,255,0.03); transition: background var(--t-fast) var(--ease); }
tbody tr:last-child { border-bottom: none; }
tbody tr:hover { background: rgba(255,255,255,0.03); }
.num { font-feature-settings: 'tnum'; font-weight: 700; }
.mute { color: var(--text-mute); font-size: 12px; }
.empty { padding: 30px; text-align: center; color: var(--text-mute); font-size: 13px; }

.cell-user { display: flex; align-items: center; gap: 10px; }
.avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: rgba(91, 140, 255, 0.2);
  color: #a9c4ff; font-size: 12px; font-weight: 800;
  display: inline-flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.avatar.admin { background: rgba(240, 164, 106, 0.2); color: #ffd08a; }

.tag {
  font-size: 11px; padding: 3px 9px; border-radius: 999px;
  border: 1px solid transparent;
}
.tag.admin { color: #ffd08a; background: rgba(240,164,106,0.12); border-color: rgba(240,164,106,0.3); }
.tag.user { color: #a9c4ff; background: rgba(91,140,255,0.12); border-color: rgba(91,140,255,0.3); }
.tag.on { color: #7be0a2; background: rgba(80,200,120,0.1); border-color: rgba(80,200,120,0.25); }
.tag.off { color: #ff8a8a; background: rgba(255,120,120,0.1); border-color: rgba(255,120,120,0.25); }

.ops-col { width: 320px; }
.ops { display: flex; gap: 6px; flex-wrap: wrap; }
.op {
  padding: 5px 11px;
  border-radius: 6px;
  border: 1px solid var(--border-2);
  background: rgba(255,255,255,0.04);
  color: var(--text-soft);
  font-size: 12px; cursor: pointer;
  transition: all var(--t-fast) var(--ease);
}
.op:hover { background: rgba(255,255,255,0.09); color: var(--text); }
.op.charge:hover { border-color: rgba(80,200,120,0.5); color: #7be0a2; }
.op.tx:hover { border-color: rgba(91,140,255,0.5); color: #a9c4ff; }
.op.danger:hover { border-color: rgba(255,120,120,0.5); color: #ff8a8a; }

/* 弹窗 */
.mask {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(4, 6, 16, 0.66);
  backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.dialog {
  width: 100%; max-width: 420px;
  background: rgba(16, 20, 40, 0.98);
  border: 1px solid var(--border-2);
  border-radius: var(--r-lg);
  padding: 24px 26px;
  box-shadow: 0 30px 80px -20px rgba(0,0,0,0.7);
  animation: fadeUp 240ms var(--ease-out);
}
.dialog.wide { max-width: 620px; }
.dialog h3 { margin: 0 0 4px; font-size: 16px; }
.dlg-sub { margin: 0 0 14px; font-size: 12px; color: var(--text-mute); }
.dlg-field { display: block; margin-bottom: 12px; }
.dlg-field span { display: block; font-size: 12px; color: var(--text-mute); margin-bottom: 5px; }
.dlg-field input {
  width: 100%;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  color: var(--text);
  padding: 9px 12px; font-size: 13px;
}
.dlg-field input:focus { outline: none; border-color: rgba(91, 140, 255, 0.55); }
.quick { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 14px; }
.quick button {
  padding: 8px 0;
  border-radius: var(--r-sm);
  border: 1px solid rgba(80, 200, 120, 0.3);
  background: rgba(80, 200, 120, 0.08);
  color: #7be0a2; font-size: 13px; font-weight: 700;
  cursor: pointer;
  transition: all var(--t-fast) var(--ease);
  font-feature-settings: 'tnum';
}
.quick button:hover { background: rgba(80, 200, 120, 0.16); }
.dlg-error {
  font-size: 12px; color: #ff8a8a;
  background: rgba(255, 120, 120, 0.1);
  border: 1px solid rgba(255, 120, 120, 0.25);
  border-radius: var(--r-sm);
  padding: 8px 12px; margin: 0 0 12px;
}
.dlg-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 6px; }

/* 流水 */
.tx-list { max-height: 380px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.tx {
  display: grid;
  grid-template-columns: 70px 74px 1fr 90px 76px;
  gap: 8px; align-items: baseline;
  padding: 9px 12px;
  border-radius: var(--r-sm);
  background: rgba(255,255,255,0.03);
  font-size: 12px;
}
.tx-amount { font-weight: 800; font-feature-settings: 'tnum'; color: #7be0a2; }
.tx.minus .tx-amount { color: #ff8a8a; }
.tx-reason { color: var(--text-soft); }
.tx-note { color: var(--text-mute); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tx-balance { color: var(--text-soft); font-feature-settings: 'tnum'; text-align: right; }
.tx-date { color: var(--text-mute); text-align: right; font-size: 11px; }

.fade-enter-active, .fade-leave-active { transition: opacity 200ms var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
