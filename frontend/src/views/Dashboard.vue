<template>
  <div class="dashboard">
    <!-- Hero -->
    <section class="hero reveal" :style="{ '--delay': '0ms' }">
      <div>
        <h1>为官网做 <span class="grad">AI 引擎</span> 体检</h1>
        <p>填一个网址，系统自动识别业务并生成监测关键词，跑出五维评分报告。</p>
      </div>
      <div class="hero-stats">
        <div><b>{{ tasks.length }}</b><span>总任务</span></div>
        <div><b>{{ doneCount }}</b><span>已完成</span></div>
        <div><b>{{ runningCount }}</b><span>运行中</span></div>
      </div>
    </section>

    <!-- 新建任务 -->
    <section class="card reveal" :style="{ '--delay': '80ms' }">
      <header class="card-head">
        <h2>新建监测任务</h2>
        <div class="steps">
          <span :class="{ on: step >= 1, done: step > 1 }">1 命名</span>
          <i></i>
          <span :class="{ on: step >= 2, done: step > 2 }">2 解析官网</span>
          <i></i>
          <span :class="{ on: step >= 3 }">3 确认关键词</span>
        </div>
      </header>

      <form @submit.prevent="submit" class="form">
        <!-- Step 1: 任务名 -->
        <div class="field" :class="{ filled: form.name }">
          <label>任务名称</label>
          <input v-model.trim="form.name" placeholder="例：北新建材官网 GEO 监测" required />
        </div>

        <!-- Step 2: URL + 一键分析 -->
        <div class="field" :class="{ filled: form.url }">
          <label>
            目标 URL
            <span class="hint">填官网地址即可——系统会自动抓页面、识别业务</span>
          </label>
          <div class="url-row">
            <input v-model.trim="form.url" placeholder="https://www.example.com" required />
            <button type="button" class="btn ghost analyze" :disabled="!form.url || profiling"
                    @click="analyzeSite">
              <span v-if="!profiling">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4">
                  <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
                </svg>
                分析官网
              </span>
              <span v-else class="spin-wrap">
                <span class="spin"></span>分析中…
              </span>
            </button>
          </div>
        </div>

        <!-- 企业画像 -->
        <transition name="slide">
          <div v-if="profile" class="profile">
            <div class="profile-head">
              <span class="badge">企业画像</span>
              <b>{{ profile.brand }}</b>
              <span class="ind">{{ profile.industry }}</span>
              <span class="muted">已扫描 {{ profile.pages_analyzed.length }} 页</span>
            </div>
            <p class="summary">{{ profile.summary }}</p>
            <div class="pages">
              <span v-for="p in profile.pages_analyzed.slice(1, 6)" :key="p" class="page-chip">
                {{ shortUrl(p) }}
              </span>
            </div>
          </div>
        </transition>
        <p v-if="profileError" class="err-msg">⚠ {{ profileError }}</p>

        <!-- Step 3: 关键词（系统自动 + 用户补充） -->
        <transition name="slide">
          <div v-if="profile" class="field kw-field">
            <label>
              监测关键词
              <span class="hint">已选 <b>{{ selectedCount }}</b> / {{ totalKeywords }} · 点击 chip 切换</span>
            </label>
            <div class="kw-groups">
              <div v-for="g in groupedKeywords" :key="g.category" class="kw-group">
                <span class="kw-cat" :class="'cat-' + g.category">{{ g.category }}</span>
                <span v-for="(k, i) in g.items" :key="k"
                      class="chip"
                      :class="{ off: !selected[k] }"
                      :style="{ '--i': i }"
                      @click="toggle(k)">
                  <i class="dot"></i>{{ k }}
                </span>
              </div>
            </div>
          </div>
        </transition>

        <!-- 补充（可折叠） -->
        <details class="advanced">
          <summary>高级设置</summary>
          <div class="adv-body">
            <div class="field">
              <label>行业方向（选填）</label>
              <input v-model.trim="form.hint" placeholder="例：建材 / 智能卫浴" />
            </div>
            <div class="field">
              <label>补充关键词（选填，逗号分隔）</label>
              <input v-model.trim="form.manual" placeholder="例：石膏板, 轻钢龙骨" />
            </div>
          </div>
        </details>

        <div class="submit-row">
          <p class="submit-tip">留空也能直接创建——运行时系统会自动补齐关键词。</p>
          <button class="btn primary" :disabled="submitting">
            <span v-if="!submitting">创建任务</span>
            <span v-else class="spin-wrap"><span class="spin"></span>创建中…</span>
          </button>
        </div>
      </form>
    </section>

    <!-- 任务列表 -->
    <section class="card reveal" :style="{ '--delay': '160ms' }">
      <header class="card-head">
        <h2>监测任务</h2>
        <span v-if="tasks.length" class="count">{{ tasks.length }}</span>
      </header>

      <transition-group tag="ul" name="task" class="task-list">
        <li v-for="t in tasks" :key="t.id" class="task">
          <div class="task-main">
            <div class="task-head">
              <strong>{{ t.name }}</strong>
              <span class="status" :class="t.status">
                <i class="dot"></i>{{ statusText(t.status) }}
              </span>
            </div>
            <div class="task-url">{{ t.url }}</div>
            <div class="task-meta">
              <span class="tag-id">#{{ t.id }}</span>
              <span class="tag-time">{{ formatTime(t.created_at) }}</span>
              <span v-if="t.hint" class="tag-hint">行业：{{ t.hint }}</span>
            </div>
            <div v-if="t.keywords.length" class="task-kws">
              <span v-for="k in t.keywords.slice(0, 6)" :key="k" class="kw">{{ k }}</span>
              <span v-if="t.keywords.length > 6" class="kw more">+{{ t.keywords.length - 6 }}</span>
            </div>
            <div v-else class="task-kws">
              <span class="kw auto">运行时自动生成</span>
            </div>
            <div v-if="progressMap[t.id]?.percent < 100" class="progress-track">
              <div class="progress-bar"
                   :style="{ width: (progressMap[t.id]?.percent || 0) + '%' }">
                <span class="bar-glow"></span>
              </div>
            </div>
            <div v-if="progressMap[t.id]?.message" class="progress-msg">
              {{ progressMap[t.id].message }}
            </div>
            <div v-else-if="t.last_message" class="progress-msg">{{ t.last_message }}</div>
          </div>
          <div class="task-actions">
            <button class="btn small" :disabled="t.status === 'running'" @click="run(t)">
              {{ t.status === 'running' ? '运行中' : '运行' }}
            </button>
            <button v-if="t.status === 'done'" class="btn small ghost" @click="openReport(t)">
              报告
            </button>
            <button class="btn small danger" @click="remove(t)">删除</button>
          </div>
        </li>
      </transition-group>

      <div v-if="!tasks.length" class="empty">
        <div class="empty-icon">
          <svg viewBox="0 0 64 64" width="48" height="48" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="32" cy="32" r="26" stroke-dasharray="4 5" opacity="0.45" />
            <path d="M22 32h20M32 22v20" opacity="0.65" />
          </svg>
        </div>
        <p>暂无任务 — 在上方创建第一个监测任务吧</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { auth } from '../store/auth'

const router = useRouter()

const tasks = ref([])
const submitting = ref(false)
const progressMap = reactive({})
const form = reactive({ name: '', url: '', hint: '', manual: '' })
const profile = ref(null)
const profileError = ref('')
const profiling = ref(false)
const selected = reactive({})
const tipOpen = ref(false)
let timer = null

const selectedKeywords = computed(() => Object.keys(selected).filter((k) => selected[k]))
const selectedCount = computed(() => selectedKeywords.value.length)
const totalKeywords = computed(() => profile.value?.keywords.length || 0)

const step = computed(() => {
  if (profile.value && selectedCount.value) return 3
  if (profile.value) return 3
  if (form.url) return 2
  return 1
})

const doneCount = computed(() => tasks.value.filter((t) => t.status === 'done').length)
const runningCount = computed(() =>
  tasks.value.filter((t) => ['running', 'pending'].includes(t.status)).length
)

const groupedKeywords = computed(() => {
  const groups = []
  const map = {}
  for (const k of profile.value?.keywords || []) {
    if (!map[k.category]) {
      map[k.category] = { category: k.category, items: [] }
      groups.push(map[k.category])
    }
    map[k.category].items.push(k.keyword)
  }
  return groups
})

function statusText(s) {
  return { pending: '排队中', running: '运行中', done: '已完成', failed: '失败' }[s] || s
}
function formatTime(t) {
  return new Date(t).toLocaleString('zh-CN', { hour12: false })
}
function shortUrl(u) {
  try {
    const p = new URL(u)
    return p.pathname === '/' ? p.host : p.pathname
  } catch {
    return u
  }
}
function toggle(keyword) {
  selected[keyword] = !selected[keyword]
}

async function analyzeSite() {
  if (!form.url) return
  profiling.value = true
  profileError.value = ''
  try {
    const { data } = await api.siteProfile(form.url, form.hint || null)
    profile.value = data
    Object.keys(selected).forEach((k) => delete selected[k])
    for (const k of data.keywords || []) selected[k.keyword] = true
  } catch (e) {
    profile.value = null
    profileError.value = e?.response?.data?.detail || e?.message || '分析官网失败'
  } finally {
    profiling.value = false
  }
}

function collectKeywords() {
  const all = [...selectedKeywords.value]
  for (const raw of form.manual.split(/[,，]/)) {
    const k = raw.trim()
    if (k && !all.includes(k)) all.push(k)
  }
  return all
}

function resetForm() {
  Object.assign(form, { name: '', url: '', hint: '', manual: '' })
  profile.value = null
  profileError.value = ''
  Object.keys(selected).forEach((k) => delete selected[k])
}

async function load() {
  const { data } = await api.listTasks()
  tasks.value = data
  pollRunning()
}

async function pollRunning() {
  const running = tasks.value.filter((t) => ['pending', 'running'].includes(t.status))
  if (!running.length && !Object.keys(progressMap).some(
      (id) => progressMap[id]?.percent < 100)) {
    return
  }
  for (const t of running) {
    const { data } = await api.getProgress(t.id)
    progressMap[t.id] = data
  }
  if (running.length) setTimeout(load, 1500)
}

function startTimer() {
  timer = setInterval(pollRunning, 2000)
}

async function submit() {
  submitting.value = true
  try {
    await api.createTask({
      name: form.name,
      url: form.url,
      keywords: collectKeywords(),
      hint: form.hint || null,
    })
    resetForm()
    await load()
  } catch (e) {
    alert(e.message || '创建任务失败')
  } finally {
    submitting.value = false
  }
}

async function run(t) {
  try {
    progressMap[t.id] = { percent: 5, message: '已提交到队列', stage: 'queued', status: 'running' }
    const { data } = await api.runTask(t.id)
    if (typeof data?.token_balance === 'number') auth.setBalance(data.token_balance)
    t.status = 'running'
    setTimeout(load, 1000)
  } catch (e) {
    delete progressMap[t.id]
    alert(e.message || '运行失败')
  }
}

async function remove(t) {
  await api.deleteTask(t.id)
  tasks.value = tasks.value.filter((x) => x.id !== t.id)
}

async function openReport(t) {
  const { data } = await api.listReports(t.id)
  if (data.length) router.push('/reports/' + data[0].id)
}

onMounted(() => { load(); startTimer() })
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 22px; }

/* ============ Hero ============ */
.hero {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 24px;
  padding: 8px 4px 4px;
}
.hero h1 {
  font-size: 26px; font-weight: 700; letter-spacing: 0.3px;
  margin: 0 0 6px; line-height: 1.3;
}
.hero p { color: var(--text-mute); font-size: 14px; margin: 0; }
.grad {
  background: var(--accent-grad);
  -webkit-background-clip: text; background-clip: text;
  color: transparent;
}
.hero-stats { display: flex; gap: 12px; }
.hero-stats > div {
  text-align: center;
  padding: 10px 18px;
  border-radius: var(--r-md);
  background: var(--surface);
  border: 1px solid var(--border);
  backdrop-filter: blur(10px);
  min-width: 84px;
  transition: transform var(--t-fast) var(--ease);
}
.hero-stats > div:hover { transform: translateY(-2px); }
.hero-stats b { display: block; font-size: 22px; font-weight: 700; color: var(--text); }
.hero-stats span { font-size: 11.5px; color: var(--text-mute); }

/* ============ Card ============ */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 22px 24px;
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  box-shadow: var(--shadow-md);
  transition: border-color var(--t-med) var(--ease);
}
.card:hover { border-color: var(--border-2); }

.card-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 18px; gap: 16px; flex-wrap: wrap;
}
.card h2 {
  font-size: 15px; font-weight: 600;
  margin: 0; color: var(--text);
  display: flex; align-items: center; gap: 8px;
}
.card h2::before {
  content: ''; display: inline-block;
  width: 3px; height: 14px; border-radius: 2px;
  background: var(--accent-grad);
}
.count {
  font-size: 12px; padding: 2px 9px; border-radius: 999px;
  background: rgba(91, 140, 255, 0.18);
  color: #a9c4ff;
  font-weight: 600;
}

/* ============ Steps ============ */
.steps {
  display: flex; align-items: center; gap: 8px;
  font-size: 12.5px; color: var(--text-mute);
}
.steps span {
  padding: 4px 10px; border-radius: 999px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  transition: all var(--t-med) var(--ease);
}
.steps span.on { color: var(--text); background: rgba(91,140,255,0.12); border-color: rgba(91,140,255,0.35); }
.steps span.done { color: #6fd68f; background: rgba(80,200,120,0.12); border-color: rgba(80,200,120,0.35); }
.steps i {
  display: block; width: 16px; height: 1px;
  background: var(--border);
}

/* ============ Form ============ */
.form { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.field { position: relative; }
.field.wide, .field.kw-field, .field.full, .advanced, .profile, .submit-row {
  grid-column: 1 / -1;
}

.field label {
  display: flex; align-items: baseline; justify-content: space-between;
  font-size: 12px; color: var(--text-soft);
  margin-bottom: 6px; letter-spacing: 0.2px;
}
.hint { font-size: 11.5px; color: var(--text-mute); font-weight: 400; }
.hint b { color: var(--text-soft); }

.field input {
  width: 100%;
  padding: 11px 14px;
  border-radius: var(--r-md);
  background: rgba(8, 11, 26, 0.6);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 14px;
  transition: all var(--t-fast) var(--ease);
}
.field input::placeholder { color: var(--text-mute); }
.field input:hover { border-color: var(--border-2); }
.field input:focus {
  outline: none;
  border-color: var(--accent);
  background: rgba(8, 11, 26, 0.8);
  box-shadow: 0 0 0 3px rgba(91, 140, 255, 0.15);
}
.field.filled label { color: var(--text); }

/* URL row */
.url-row { display: flex; gap: 8px; }
.url-row input { flex: 1; }

/* Buttons */
.btn {
  border: 1px solid transparent;
  border-radius: var(--r-md);
  cursor: pointer;
  font-size: 14px; font-weight: 500;
  padding: 11px 18px;
  background: rgba(255,255,255,0.06);
  color: var(--text);
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  transition: all var(--t-fast) var(--ease);
  position: relative; overflow: hidden;
}
.btn::after {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(120% 100% at 50% 0%, rgba(255,255,255,0.18), transparent 60%);
  opacity: 0; transition: opacity var(--t-fast) var(--ease);
}
.btn:hover { transform: translateY(-1px); background: rgba(255,255,255,0.1); }
.btn:hover::after { opacity: 1; }
.btn:active { transform: translateY(0); }
.btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.btn.ghost {
  background: transparent;
  border-color: var(--border-2);
}
.btn.ghost:hover { background: rgba(255,255,255,0.06); }

.btn.primary {
  background: var(--accent-grad);
  color: #fff; font-weight: 600;
  padding: 12px 24px;
  box-shadow: var(--accent-glow);
}
.btn.primary:hover { transform: translateY(-2px); box-shadow: 0 0 0 1px rgba(91,140,255,0.45), 0 10px 30px -8px rgba(91,140,255,0.5); }
.btn.primary::after { background: radial-gradient(120% 100% at 50% 0%, rgba(255,255,255,0.3), transparent 60%); }

.btn.small { padding: 7px 14px; font-size: 12.5px; }
.btn.danger { color: #ff9c9c; background: rgba(255, 80, 80, 0.08); border-color: rgba(255, 80, 80, 0.2); }
.btn.danger:hover { background: rgba(255, 80, 80, 0.16); border-color: rgba(255, 80, 80, 0.4); }

.spin-wrap { display: inline-flex; align-items: center; gap: 6px; }
.spin {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid currentColor; border-right-color: transparent;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}

/* Profile */
.profile {
  padding: 16px 18px;
  border-radius: var(--r-md);
  background: linear-gradient(135deg, rgba(91,140,255,0.10), rgba(157,91,255,0.10));
  border: 1px solid rgba(91, 140, 255, 0.25);
}
.profile-head {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
}
.profile-head b { font-size: 15px; }
.badge {
  font-size: 10.5px; padding: 2px 8px; border-radius: 999px;
  background: rgba(91, 140, 255, 0.25); color: #a9c4ff;
  border: 1px solid rgba(91, 140, 255, 0.4);
  font-weight: 600; letter-spacing: 0.3px;
}
.ind {
  font-size: 11.5px; padding: 2px 9px; border-radius: 999px;
  background: rgba(80, 200, 120, 0.16); color: #7fd7a0;
  border: 1px solid rgba(80, 200, 120, 0.3);
}
.profile-head .muted { margin-left: auto; font-size: 11.5px; color: var(--text-mute); }
.summary { margin: 10px 0 8px; font-size: 13px; color: #c4cbe5; line-height: 1.7; }
.pages { display: flex; flex-wrap: wrap; gap: 6px; }
.page-chip {
  font-size: 11px; color: var(--text-soft); padding: 2px 8px;
  border-radius: 5px;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  font-family: 'SFMono-Regular', Consolas, monospace;
}
.err-msg { margin: 4px 0 0; font-size: 12.5px; color: #ff8a8a; }

/* KW groups */
.kw-groups { display: flex; flex-direction: column; gap: 10px; }
.kw-group { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.kw-cat {
  font-size: 10.5px; padding: 3px 9px; border-radius: 5px;
  min-width: 36px; text-align: center;
  background: #232a48; color: #9aa4cc;
  border: 1px solid #333c66;
  font-weight: 600; letter-spacing: 0.5px;
}
.kw-cat.cat-品牌 { background: rgba(245, 213, 106, 0.14); color: #f5d56a; border-color: rgba(245, 213, 106, 0.32); }
.kw-cat.cat-产品 { background: rgba(91, 140, 255, 0.16); color: #8db4ff; border-color: rgba(91, 140, 255, 0.32); }
.kw-cat.cat-行业 { background: rgba(80, 200, 120, 0.14); color: #7fd7a0; border-color: rgba(80, 200, 120, 0.32); }
.kw-cat.cat-场景 { background: rgba(157, 91, 255, 0.16); color: #c3a4ff; border-color: rgba(157, 91, 255, 0.32); }
.kw-cat.cat-资质 { background: rgba(240, 150, 90, 0.14); color: #f0a46a; border-color: rgba(240, 150, 90, 0.32); }

.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px; border-radius: 999px;
  font-size: 12.5px;
  background: rgba(91, 140, 255, 0.15);
  color: #c8d6ff;
  border: 1px solid rgba(91, 140, 255, 0.3);
  cursor: pointer; user-select: none;
  transition: all var(--t-fast) var(--ease);
  animation: pop 280ms var(--ease-out) backwards;
  animation-delay: calc(var(--i, 0) * 30ms);
}
.chip .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent);
  transition: all var(--t-fast) var(--ease);
}
.chip:hover {
  background: rgba(91, 140, 255, 0.25);
  border-color: rgba(91, 140, 255, 0.5);
  transform: translateY(-1px);
}
.chip:active { transform: scale(0.97); }
.chip.off {
  background: transparent;
  border-color: var(--border);
  color: var(--text-mute);
}
.chip.off .dot { background: transparent; border: 1px solid var(--text-mute); }

/* Advanced */
.advanced {
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: rgba(8, 11, 26, 0.3);
  overflow: hidden;
}
.advanced summary {
  list-style: none;
  cursor: pointer;
  padding: 12px 16px;
  font-size: 12.5px;
  color: var(--text-soft);
  display: flex; align-items: center; gap: 8px;
  transition: background var(--t-fast) var(--ease);
}
.advanced summary::-webkit-details-marker { display: none; }
.advanced summary::before {
  content: '▸';
  display: inline-block;
  transition: transform var(--t-fast) var(--ease);
  color: var(--text-mute);
}
.advanced[open] summary::before { transform: rotate(90deg); }
.advanced summary:hover { background: rgba(255,255,255,0.03); }
.adv-body { padding: 4px 16px 16px; display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

/* Submit */
.submit-row {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; flex-wrap: wrap;
  margin-top: 4px;
}
.submit-tip { margin: 0; font-size: 12px; color: var(--text-mute); }

/* ============ Task list ============ */
.task-list {
  list-style: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 12px;
}
.task {
  display: flex; justify-content: space-between; gap: 16px;
  padding: 16px 18px;
  border-radius: var(--r-md);
  background: rgba(8, 11, 26, 0.45);
  border: 1px solid var(--border);
  transition: all var(--t-fast) var(--ease);
  position: relative;
  overflow: hidden;
}
.task::before {
  content: '';
  position: absolute; left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--accent-grad);
  opacity: 0;
  transition: opacity var(--t-med) var(--ease);
}
.task:hover {
  border-color: var(--border-2);
  transform: translateY(-1px);
  background: rgba(8, 11, 26, 0.6);
}
.task:hover::before { opacity: 1; }
.task.running { border-color: rgba(91, 140, 255, 0.35); }
.task.running::before { opacity: 1; }

.task-main { flex: 1; min-width: 0; }
.task-head {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin-bottom: 4px;
}
.task-head strong { font-size: 15px; font-weight: 600; }
.status {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11.5px; padding: 2px 9px; border-radius: 999px;
  font-weight: 600;
}
.status .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.status.done    { color: #5ee6a8; background: rgba(80, 200, 120, 0.14); }
.status.running { color: #ffc857; background: rgba(255, 200, 87, 0.14); }
.status.running .dot { animation: pulse 1.4s ease-in-out infinite; }
.status.failed  { color: #ff8a8a; background: rgba(255, 80, 80, 0.14); }
.status.pending { color: var(--text-soft); background: rgba(255, 255, 255, 0.05); }

.task-url {
  font-size: 12.5px; color: var(--text-soft);
  font-family: 'SFMono-Regular', Consolas, monospace;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  margin-bottom: 6px;
}
.task-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.tag-id, .tag-time, .tag-hint {
  font-size: 11px; color: var(--text-mute);
  padding: 1px 7px; border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
}

.task-kws { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 4px; }
.kw {
  font-size: 11.5px; padding: 2px 8px; border-radius: 5px;
  background: rgba(91, 140, 255, 0.12);
  color: #a9c4ff;
  border: 1px solid rgba(91, 140, 255, 0.22);
}
.kw.more { color: var(--text-soft); }
.kw.auto { background: transparent; border-style: dashed; color: var(--text-mute); }

.progress-track {
  width: 100%; height: 5px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 3px;
  margin-top: 10px;
  overflow: hidden;
  position: relative;
}
.progress-bar {
  height: 100%; border-radius: 3px;
  background: var(--accent-grad);
  transition: width 600ms var(--ease-out);
  position: relative;
  overflow: hidden;
}
.bar-glow {
  position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.5), transparent);
  animation: shimmer 1.6s linear infinite;
  background-size: 400px 100%;
}
.progress-msg { font-size: 11.5px; color: var(--text-mute); margin-top: 6px; }

.task-actions { display: flex; flex-direction: column; gap: 6px; align-items: stretch; }
.task-actions .btn { white-space: nowrap; }

/* Empty */
.empty {
  text-align: center;
  padding: 48px 20px;
  color: var(--text-mute);
}
.empty-icon {
  display: inline-flex; justify-content: center;
  margin-bottom: 10px;
  color: var(--text-mute);
  animation: fadeIn 800ms var(--ease-out);
}
.empty p { font-size: 13px; margin: 0; }

/* ============ Animations ============ */
.slide-enter-active, .slide-leave-active {
  transition: all 320ms var(--ease-out);
}
.slide-enter-from, .slide-leave-to {
  opacity: 0; transform: translateY(-8px);
}

.task-enter-active, .task-leave-active {
  transition: all 400ms var(--ease-out);
}
.task-enter-from { opacity: 0; transform: translateY(8px); }
.task-leave-to   { opacity: 0; transform: translateX(20px); }
.task-move { transition: transform 400ms var(--ease-out); }

/* Responsive */
@media (max-width: 720px) {
  .form { grid-template-columns: 1fr; }
  .adv-body { grid-template-columns: 1fr; }
  .task { flex-direction: column; }
  .task-actions { flex-direction: row; }
  .hero { text-align: center; }
  .hero-stats { width: 100%; justify-content: center; }
}
</style>
