<template>
  <div class="ob">
    <!-- 进度步骤 -->
    <div class="ob-head">
      <div class="brand">
        <span class="logo-mark">G<span class="dot">·</span>E<span class="dot">·</span>O</span>
        <span class="brand-name">监测量化模拟系统</span>
      </div>
      <button class="logout" @click="logout">
        <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />
        </svg>
        退出登录
      </button>
    </div>

    <div class="ob-body">
      <!-- 左：介绍 -->
      <aside class="intro">
        <span class="badge">首次免费 · 不消耗 token</span>
        <h1>先给你的官网做一次<br /><em>AI 可见度体检</em></h1>
        <p class="lead">
          填写公司名称、业务项目和官网链接，系统会抓取整站内容，
          按 SHEEP 五维 + EEAT 四维给出量化诊断与整改清单。
        </p>

        <ul class="points">
          <li>
            <span class="ico">◆</span>
            <div><b>自动识别业务</b><i>从官网正文提炼关键词，无需手工输入</i></div>
          </li>
          <li>
            <span class="ico">◆</span>
            <div><b>五维 + 四维量化</b><i>语义覆盖 / 可信度 / 结构化 / 生态 / 性能</i></div>
          </li>
          <li>
            <span class="ico">◆</span>
            <div><b>可执行的整改清单</b><i>每条建议对应到具体缺口，不是套话</i></div>
          </li>
        </ul>

        <div class="gift">
          <span class="gift-num">{{ pricing.signup_bonus }}</span>
          <div>
            <b>token 已到账</b>
            <i>本次体检免费，之后每次监测消耗 {{ pricing.task_cost }} token</i>
          </div>
        </div>
      </aside>

      <!-- 右：表单 / 运行态 -->
      <section class="panel">
        <transition name="swap" mode="out-in">
          <!-- 表单 -->
          <form v-if="step === 'form'" key="form" @submit.prevent="submit">
            <h2>填写你的公司信息</h2>
            <p class="sub">用于生成第一份分析报告，之后可在任务页随时复测</p>

            <label class="field">
              <span>公司名称 <em>*</em></span>
              <input v-model.trim="form.company_name" placeholder="如：北新集团建材股份有限公司"
                     required maxlength="200" />
            </label>

            <label class="field">
              <span>业务项目 <em>*</em></span>
              <textarea v-model.trim="form.business" rows="3" maxlength="500"
                        placeholder="如：石膏板、矿棉板、防水材料等绿色建筑材料的研发与生产"></textarea>
              <small>一句话说明主打业务，有助于关键词校准</small>
            </label>

            <label class="field">
              <span>官网链接 <em>*</em></span>
              <input v-model.trim="form.url" type="url" placeholder="https://www.example.com/"
                     required />
            </label>

            <p v-if="error" class="err">{{ error }}</p>

            <button class="go" :disabled="submitting">
              <span v-if="submitting" class="spin"></span>
              {{ submitting ? '正在创建分析任务…' : '开始免费体检' }}
            </button>
            <p class="tip">提交后将自动跳转到任务进度页，约 1~3 分钟出报告</p>
          </form>

          <!-- 运行中 -->
          <div v-else key="running" class="running">
            <div class="pulse-ring">
              <span class="pulse-core">GEO</span>
            </div>
            <h2>正在体检你的官网…</h2>
            <p class="sub">{{ runMsg }}</p>
            <div class="bar"><i :style="{ width: percent + '%' }"></i></div>
            <ul class="steps">
              <li v-for="(s, i) in steps" :key="s" :class="{ done: i < stepIdx, now: i === stepIdx }">
                <span class="dot"></span>{{ s }}
              </li>
            </ul>
            <button v-if="done" class="go" @click="toReport">查看分析报告 →</button>
          </div>
        </transition>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { auth } from '../store/auth'

const router = useRouter()
const step = ref('form')
const submitting = ref(false)
const error = ref('')
const pricing = ref({ task_cost: 10, signup_bonus: 50 })

const form = reactive({
  company_name: auth.state.user?.company_name || '',
  business: auth.state.user?.business || '',
  url: '',
})

const steps = ['抓取官网首页与关键子页', '提取业务关键词与结构化信号', '多引擎模拟识别测试', '生成五维 + EEAT 量化报告']
const stepIdx = ref(0)
const percent = ref(0)
const runMsg = ref('已提交到队列…')
const done = ref(false)
const taskId = ref(null)
const reportId = ref(null)
let timer = null

onMounted(async () => {
  try { pricing.value = (await api.pricing()).data } catch { /* ignore */ }
})

function logout() {
  auth.logout()
  router.push('/login')
}

async function submit() {
  if (!form.company_name) { error.value = '请填写公司名称'; return }
  if (!form.business) { error.value = '请填写业务项目'; return }
  if (!/^https?:\/\//i.test(form.url)) { error.value = '官网链接必须以 http:// 或 https:// 开头'; return }
  error.value = ''
  submitting.value = true
  try {
    const { data } = await api.onboardingStart({
      company_name: form.company_name,
      business: form.business,
      url: form.url,
    })
    taskId.value = data.id
    step.value = 'running'
    startPolling()
  } catch (e) {
    error.value = e.message || '提交失败'
  } finally {
    submitting.value = false
  }
}

function startPolling() {
  let ticks = 0
  timer = setInterval(async () => {
    ticks += 1
    try {
      const { data } = await api.getProgress(taskId.value)
      percent.value = data.percent ?? Math.min(90, percent.value + 8)
      runMsg.value = data.message || runMsg.value
      stepIdx.value = Math.min(steps.length - 1, Math.floor((data.percent || 0) / 26))
      if (['done', 'failed'].includes(data.status)) {
        clearInterval(timer)
        timer = null
        percent.value = 100
        if (data.status === 'failed') {
          runMsg.value = data.message || '分析失败，请检查官网是否可访问'
          return
        }
        const { data: reports } = await api.listReports(taskId.value)
        reportId.value = reports?.[0]?.id || null
        done.value = true
        runMsg.value = '报告已生成'
      }
    } catch {
      // 轮询失败静默重试
      if (ticks > 150) { clearInterval(timer); timer = null }
    }
  }, 2000)
}

function toReport() {
  if (reportId.value) router.push(`/reports/${reportId.value}`)
  else router.push('/')
}

onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.ob { max-width: 1060px; margin: 0 auto; }
.ob-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 0 22px;
}
.brand { display: flex; align-items: center; gap: 10px; }
.logo-mark {
  font-weight: 800; font-size: 12px; color: #fff;
  background: var(--accent-grad);
  padding: 7px 10px; border-radius: 9px; letter-spacing: 0.5px;
}
.logo-mark .dot { opacity: 0.55; padding: 0 1px; }
.brand-name { font-size: 13px; color: var(--text-soft); }
.logout {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px; border-radius: 999px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  color: var(--text-soft); font-size: 12.5px; cursor: pointer;
  transition: all var(--t-fast) var(--ease);
}
.logout:hover { color: #ff8a8a; border-color: rgba(255,120,120,0.4); }

.ob-body {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 30px; align-items: start;
}

/* 左栏 */
.badge {
  display: inline-block;
  font-size: 11.5px; font-weight: 700; color: #7be0a2;
  background: rgba(80,200,120,0.1);
  border: 1px solid rgba(80,200,120,0.3);
  padding: 4px 12px; border-radius: 999px;
  margin-bottom: 16px;
}
.intro h1 {
  font-size: 30px; line-height: 1.35; margin: 0 0 14px; letter-spacing: -0.5px;
}
.intro h1 em {
  font-style: normal;
  background: var(--accent-grad);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.lead { font-size: 13.5px; line-height: 1.75; color: var(--text-soft); margin: 0 0 22px; }

.points { list-style: none; padding: 0; margin: 0 0 24px; display: flex; flex-direction: column; gap: 14px; }
.points li { display: flex; gap: 12px; }
.points .ico { color: #6f9cff; font-size: 11px; margin-top: 3px; }
.points b { display: block; font-size: 13.5px; font-weight: 600; }
.points i { font-style: normal; font-size: 12px; color: var(--text-mute); }

.gift {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px;
  background: linear-gradient(135deg, rgba(80,200,120,0.1), rgba(91,140,255,0.06));
  border: 1px solid rgba(80,200,120,0.22);
  border-radius: var(--r-md);
}
.gift-num {
  font-size: 26px; font-weight: 800; color: #7be0a2;
  font-feature-settings: 'tnum';
}
.gift b { display: block; font-size: 13px; }
.gift i { font-style: normal; font-size: 11.5px; color: var(--text-mute); }

/* 右栏 */
.panel {
  background: rgba(8, 11, 26, 0.55);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 28px 30px;
  backdrop-filter: blur(12px);
  box-shadow: 0 30px 80px -40px rgba(0,0,0,0.8);
}
.panel h2 { margin: 0 0 6px; font-size: 18px; }
.sub { margin: 0 0 20px; font-size: 12.5px; color: var(--text-mute); }

.field { display: block; margin-bottom: 16px; }
.field > span {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--text-mute); margin-bottom: 6px;
}
.field > span em { font-style: normal; color: #ff8a8a; }
.field input, .field textarea {
  width: 100%;
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border);
  border-radius: var(--r-sm);
  color: var(--text);
  padding: 10px 13px; font-size: 13.5px;
  font-family: inherit; resize: vertical;
  transition: all var(--t-fast) var(--ease);
}
.field input:focus, .field textarea:focus {
  outline: none;
  border-color: rgba(91,140,255,0.55);
  background: rgba(255,255,255,0.08);
}
.field small { display: block; margin-top: 5px; font-size: 11px; color: var(--text-mute); }

.err {
  font-size: 12px; color: #ff8a8a;
  background: rgba(255,120,120,0.1);
  border: 1px solid rgba(255,120,120,0.25);
  border-radius: var(--r-sm);
  padding: 8px 12px; margin: 0 0 14px;
}

.go {
  width: 100%; padding: 12px 0;
  border: none; border-radius: var(--r-sm);
  background: var(--accent-grad);
  color: #fff; font-size: 14px; font-weight: 700;
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  box-shadow: var(--accent-glow);
  transition: all var(--t-fast) var(--ease);
}
.go:hover:not(:disabled) { transform: translateY(-1px); filter: brightness(1.08); }
.go:disabled { opacity: 0.6; cursor: not-allowed; }
.tip { text-align: center; font-size: 11.5px; color: var(--text-mute); margin: 12px 0 0; }

.spin {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 运行态 */
.running { text-align: center; padding: 10px 0 4px; }
.pulse-ring {
  width: 92px; height: 92px; margin: 4px auto 20px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: radial-gradient(circle, rgba(91,140,255,0.22), transparent 70%);
  border: 1px solid rgba(91,140,255,0.35);
  animation: breathe 2s ease-in-out infinite;
}
.pulse-core {
  font-size: 13px; font-weight: 800; letter-spacing: 1px; color: #a9c4ff;
}
@keyframes breathe {
  50% { transform: scale(1.07); box-shadow: 0 0 40px rgba(91,140,255,0.25); }
}
.bar {
  height: 6px; border-radius: 999px; overflow: hidden;
  background: rgba(255,255,255,0.07);
  margin: 18px 0 20px;
}
.bar i {
  display: block; height: 100%; border-radius: 999px;
  background: var(--accent-grad);
  transition: width 600ms var(--ease-out);
}

.steps { list-style: none; padding: 0; margin: 0 0 20px; text-align: left; }
.steps li {
  display: flex; align-items: center; gap: 10px;
  font-size: 12.5px; color: var(--text-mute);
  padding: 7px 0;
  transition: color var(--t-base) var(--ease);
}
.steps .dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: rgba(255,255,255,0.15); flex-shrink: 0;
}
.steps li.done { color: var(--text-soft); }
.steps li.done .dot { background: #6b8cff; }
.steps li.now { color: #fff; }
.steps li.now .dot { background: #7be0a2; box-shadow: 0 0 0 4px rgba(80,200,120,0.15); }

.swap-enter-active, .swap-leave-active { transition: all 260ms var(--ease-out); }
.swap-enter-from { opacity: 0; transform: translateY(10px); }
.swap-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 860px) {
  .ob-body { grid-template-columns: 1fr; gap: 22px; }
  .intro h1 { font-size: 24px; }
}
</style>
