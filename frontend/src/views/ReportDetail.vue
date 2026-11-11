<template>
  <div v-if="report" class="report">
    <!-- 综合评分头部 -->
    <section class="card hero reveal" :style="{ '--delay': '0ms' }">
      <div class="hero-left">
        <div class="overall" :class="'grade-' + report.grade">
          <svg viewBox="0 0 120 120" class="gauge">
            <defs>
              <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%"  stop-color="#5b8cff" />
                <stop offset="100%" stop-color="#9d5bff" />
              </linearGradient>
            </defs>
            <circle cx="60" cy="60" r="52" class="gauge-bg" />
            <circle cx="60" cy="60" r="52" class="gauge-fg" :style="gaugeStyle" />
          </svg>
          <div class="gauge-text">
            <span class="score">{{ displayScore }}</span>
            <span class="label">GEM 综合评分</span>
          </div>
        </div>
        <div class="hero-info">
          <h2 class="url" :title="report.url">{{ report.url }}</h2>
          <p class="grade-line">
            评分等级：<strong :class="'grade-' + report.grade">{{ report.grade }}级</strong>
            <span class="sep">·</span>
            报告签名 <code>{{ report.signature }}</code>
          </p>
          <p class="meta">基于 SHEEP 框架评估 · 生成时间 {{ formatTime(report.created_at) }}</p>
        </div>
      </div>
      <div class="hero-codes">
        <div v-for="d in dimensionList" :key="d.code" class="code-chip" :style="{ '--i': d.code }">
          <span class="code">{{ d.short_code }}</span>
          <span class="val" :class="'grade-' + gradeLetter(d.score)">
            {{ displayVal(d.code) }}
          </span>
          <span class="name">{{ d.name }}</span>
        </div>
      </div>
    </section>

    <!-- EEAT 核心指标 -->
    <section v-if="eeat" class="card eeat reveal" :style="{ '--delay': '60ms' }">
      <header class="card-head">
        <h2>EEAT 核心指标</h2>
        <div class="eeat-head">
          <span class="scope-tag">
            {{ eeat.scope === 'site' ? '整站范围评估' : '单页评估' }}
          </span>
          <span class="eeat-total" :class="'grade-' + eeatGradeLetter(eeat.overall)">
            {{ displayEEATScore }}
            <i>/100</i>
          </span>
          <span class="eeat-grade" :class="'grade-' + eeatGradeLetter(eeat.overall)">
            {{ eeat.grade }}
          </span>
        </div>
      </header>
      <p class="eeat-summary">{{ eeat.summary }}</p>

      <div class="eeat-grid">
        <div v-for="(d, i) in eeatList" :key="d.code"
             class="eeat-card" :class="'lv-' + d.level"
             :style="{ '--c': d.color, '--i': i }">
          <div class="eeat-card-head">
            <div class="eeat-ring">
              <svg viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" class="ring-bg" />
                <circle cx="50" cy="50" r="42" class="ring-fg" :style="eeatRing(d)" />
              </svg>
              <div class="ring-text">
                <span class="num">{{ displayEEAT(d.code) }}</span>
              </div>
            </div>
            <div class="eeat-meta">
              <div class="eeat-name">
                <b>{{ d.name }}</b>
                <span class="short">{{ d.short }}</span>
              </div>
              <span class="en">{{ d.name_en }}</span>
              <span class="grade-pill" :class="'grade-' + eeatGradeLetter(d.score)">
                {{ d.grade }}
              </span>
            </div>
          </div>

          <!-- 得分占比条 -->
          <div class="eeat-bar">
            <span class="eeat-bar-fill" :style="{ width: eeatEarnedPct(d) + '%' }"></span>
            <span class="eeat-bar-txt">{{ d.earned }} / {{ d.total }} 分</span>
          </div>

          <p class="eeat-desc">{{ d.desc }}</p>

          <!-- 信号明细 -->
          <div class="eeat-signals">
            <div v-for="ev in d.evidence" :key="'e' + ev.label" class="sig ok">
              <i class="mk">✓</i>
              <span class="lb">{{ ev.label }}</span>
              <span class="dt">{{ ev.detail }}</span>
              <span class="wt">+{{ ev.weight }}</span>
            </div>
            <div v-for="ms in d.missing" :key="'m' + ms.label" class="sig no">
              <i class="mk">✗</i>
              <span class="lb">{{ ms.label }}</span>
              <span class="dt">{{ ms.detail }}</span>
              <span class="wt">{{ ms.weight }}</span>
            </div>
          </div>

          <p class="eeat-advice">{{ d.advice }}</p>
        </div>
      </div>

      <!-- 高性价比整改清单 -->
      <div class="gap-panel">
        <h3>整改优先级 · 按可得分排序</h3>
        <div class="gap-list">
          <div v-for="(g, i) in eeatGaps" :key="g.code + g.label" class="gap-item"
               :style="{ '--i': i }">
            <span class="gap-rank">{{ i + 1 }}</span>
            <span class="gap-name" :style="{ '--c': eeat.dimensions[g.code].color }">
              {{ g.name }}
            </span>
            <span class="gap-weight">+{{ g.weight }}</span>
            <span class="gap-label">{{ g.label }}</span>
            <span class="gap-detail">{{ g.detail }}</span>
          </div>
        </div>
      </div>
    </section>

    <div class="grid">
      <!-- 雷达图 + 行业基准 -->
      <section class="card reveal" :style="{ '--delay': '80ms' }">
        <header class="card-head">
          <h2>SHEEP 五维分析</h2>
          <span class="legend">
            <i class="dot me"></i>本站 <i class="dot base"></i>行业基准
          </span>
        </header>
        <div ref="radarEl" class="chart"></div>
        <table class="dim-table">
          <thead>
            <tr><th>维度</th><th>得分</th><th>等级</th><th>行业基准</th><th>说明</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in dimensionList" :key="d.code">
              <td>
                <span class="dim-tag" :class="'dim-' + d.code">{{ d.short_code }}</span>
                {{ d.name }}
              </td>
              <td>
                <span class="score-bar" :class="'grade-' + gradeLetter(d.score)">
                  <span class="score-num" :style="{ '--target': d.score + '%' }"></span>
                </span>
                <strong :class="'grade-' + gradeLetter(d.score)">
                  {{ displayVal(d.code) }}
                </strong>
              </td>
              <td>
                <span class="grade-tag" :class="'grade-' + d.grade">{{ d.grade }}级</span>
              </td>
              <td>
                {{ findings.comparisons[d.code].benchmark }}
                <span :class="findings.comparisons[d.code].diff >= 0 ? 'up' : 'down'">
                  {{ findings.comparisons[d.code].diff >= 0 ? '+' : '' }}{{ findings.comparisons[d.code].diff }}
                </span>
              </td>
              <td class="sub">{{ d.desc }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- 核心指标汇总 -->
      <section class="card reveal" :style="{ '--delay': '160ms' }">
        <header class="card-head"><h2>核心指标汇总</h2></header>
        <div class="metric-grid">
          <div v-for="(v, k, i) in report.core_metrics" :key="k" class="metric"
               :style="{ '--i': i }">
            <div class="metric-val" :data-val="v + '%'">
              {{ displayMetric(k, v) }}<small>%</small>
            </div>
            <div class="metric-name">{{ metricNames[k] }}</div>
          </div>
        </div>

        <h3 class="section-h">关键发现</h3>
        <p class="finding">
          最强维度：<strong class="up">{{ findings.strongest.dimension }}（{{ findings.strongest.score }}分）</strong>
          最弱维度：<strong class="down">{{ findings.weakest.dimension }}（{{ findings.weakest.score }}分）</strong>
        </p>
        <p class="finding">改进优先级：
          <span v-for="p in findings.priority" :key="p.order" class="pri-tag">
            {{ p.order }}. {{ p.dimension }}
          </span>
        </p>
        <p class="finding">
          短期提升空间 <strong class="up">+{{ findings.short_term_uplift }}</strong> 分 ·
          中期提升空间 <strong class="up">+{{ findings.mid_term_uplift }}</strong> 分
        </p>
      </section>
    </div>

    <!-- 关键词 × 引擎识别矩阵 -->
    <section class="card reveal" :style="{ '--delay': '240ms' }">
      <header class="card-head">
        <h2>多引擎 × 多关键词识别矩阵</h2>
        <span class="recognition">
          AI 识别率
          <b>{{ displayRecognition }}</b>
          <span v-if="report.keyword_matrix.scope_pages > 1" class="scope">
            · 范围 {{ report.keyword_matrix.scope_pages }} 页
          </span>
        </span>
      </header>
      <p class="sub">
        各生成式引擎对每个关键词的识别模拟结果——识别率低通常意味着关键词与页面内容不匹配。
      </p>
      <div class="matrix-wrap">
        <table>
          <thead>
            <tr>
              <th>关键词</th>
              <th>页面命中位置</th>
              <th v-for="e in report.keyword_matrix.engines" :key="e">{{ e }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in diagnostics" :key="d.keyword">
              <td class="kw">{{ d.keyword }}</td>
              <td>
                <span v-if="d.hit_positions.length" class="pos-badges">
                  <i v-for="p in d.hit_positions" :key="p" class="pos-badge">{{ p }}</i>
                </span>
                <span v-else class="pos-none">未出现</span>
              </td>
              <td v-for="e in report.keyword_matrix.engines" :key="e" class="center">
                <span :class="cellClass(d.keyword, e)">
                  <i class="cell-dot"></i>{{ cellText(d.keyword, e) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="kw-diagnosis">
        <h3>关键词诊断</h3>
        <p v-for="d in diagnostics" :key="d.keyword" class="diag" :class="'diag-' + d.level">
          <b>{{ d.keyword }}</b>
          <span class="lv">{{ { strong: '✓ 命中良好', weak: '△ 命中偏弱', none: '✗ 未出现' }[d.level] }}</span>
          {{ d.advice }}
        </p>
      </div>
    </section>

    <!-- 性能 -->
    <section class="card reveal" :style="{ '--delay': '320ms' }">
      <header class="card-head"><h2>性能监测 · Core Web Vitals</h2></header>
      <div class="vitals">
        <div v-for="(v, k, i) in vitalsList" :key="k" class="vital" :style="{ '--i': i }">
          <div class="vital-label">{{ v.label }}</div>
          <div class="vital-val" :class="v.cls">
            {{ v.value }}<small>{{ v.unit }}</small>
          </div>
          <div class="vital-bar">
            <span class="vital-bar-fill" :style="{ '--pct': v.pct + '%' }"></span>
          </div>
        </div>
      </div>
      <details class="more-vitals">
        <summary>查看更多</summary>
        <table class="dim-table">
          <tbody>
            <tr><td>请求数量</td><td>{{ report.performance.resources.request_count }} 个</td></tr>
            <tr><td>页面大小</td><td>{{ report.performance.resources.page_size_mb }} MB</td></tr>
            <tr><td>JS / CSS 体积</td><td>{{ report.performance.resources.js_size_kb }} KB / {{ report.performance.resources.css_size_kb }} KB</td></tr>
          </tbody>
        </table>
      </details>
    </section>

    <!-- 优先级矩阵与优化建议 -->
    <section class="card reveal" :style="{ '--delay': '400ms' }">
      <header class="card-head"><h2>优化建议</h2></header>
      <div class="suggestion-list">
        <div v-for="p in findings.priority" :key="p.order" class="suggestion"
             :style="{ '--i': p.order }">
          <div class="suggestion-head">
            <span class="badge">P{{ p.order }}</span>
            <strong>{{ p.dimension }}</strong>
            <span class="score">{{ p.score }} 分</span>
          </div>
          <p>{{ p.suggestion }}</p>
        </div>
      </div>
    </section>

    <router-link to="/" class="back-link">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2">
        <path d="M15 6l-6 6 6 6" />
      </svg>
      返回任务列表
    </router-link>
  </div>
  <div v-else class="loading">
    <div class="loading-spin"></div>
    <p>报告加载中…</p>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import * as echarts from 'echarts'
import api from '../api'

const props = defineProps({ id: String })
const report = ref(null)
const radarEl = ref(null)
let chart = null

/* ============ 动画数字 ============ */
const animated = reactive({})   // key -> 当前显示值
const displayScore = ref(0)
const displayRecognition = ref('0.0')
const displayEEATScore = ref(0)

function animateTo(key, target, duration = 1100, fmt = (v) => v.toFixed(0)) {
  const start = performance.now()
  const from = animated[key] || 0
  const tick = (t) => {
    const p = Math.min(1, (t - start) / duration)
    // easeOutCubic
    const e = 1 - Math.pow(1 - p, 3)
    animated[key] = from + (target - from) * e
    if (p < 1) requestAnimationFrame(tick)
    else animated[key] = target
  }
  requestAnimationFrame(tick)
}

watch(() => report.value, (r) => {
  if (!r) return
  // 主分数
  displayScore.value = '0'
  animateTo('__score', r.overall_score, 1300, (v) => v.toFixed(1))
  // 识别率
  displayRecognition.value = '0.0'
  animateTo('__rec', r.keyword_matrix.recognition_rate, 1100, (v) => v.toFixed(1))
  // 维度
  for (const d of Object.values(r.dimensions || {})) {
    animateTo(d.code, d.score, 1100, (v) => v.toFixed(1))
  }
  // 指标
  for (const [k, v] of Object.entries(r.core_metrics || {})) {
    animateTo('m_' + k, v, 1100, (x) => x.toFixed(1))
  }
  // EEAT
  if (r.eeat) {
    displayEEATScore.value = '0'
    animateTo('__eeat', r.eeat.overall, 1300, (v) => v.toFixed(1))
    for (const d of Object.values(r.eeat.dimensions || {})) {
      animateTo('eeat_' + d.code, d.score, 1100, (v) => v.toFixed(1))
    }
  }
})

function displayVal(code) {
  const v = animated[code]
  return v == null ? '0.0' : v.toFixed(1)
}
function displayMetric(k, target) {
  const v = animated['m_' + k]
  return v == null ? '0.0' : v.toFixed(1)
}

// 同步 displayScore / displayRecognition / displayEEATScore
setInterval(() => {
  if (animated.__score != null) displayScore.value = animated.__score.toFixed(1)
  if (animated.__rec != null) displayRecognition.value = animated.__rec.toFixed(1)
  if (animated.__eeat != null) displayEEATScore.value = animated.__eeat.toFixed(1)
}, 32)

/* ============ 派生数据 ============ */
const diagnostics = computed(() => report.value?.keyword_matrix?.diagnostics || [])

/* ============ EEAT ============ */
const eeat = computed(() => report.value?.eeat || null)
const eeatList = computed(() => {
  if (!eeat.value) return []
  return Object.values(eeat.value.dimensions || {})
})
const eeatGaps = computed(() => eeat.value?.gap_actions || [])

function displayEEAT(code) {
  const v = animated['eeat_' + code]
  return v == null ? '0.0' : v.toFixed(1)
}

// 环形进度：半径 42 的圆周长
function eeatRing(d) {
  const pct = (d?.score || 0) / 100
  const c = 2 * Math.PI * 42
  return {
    strokeDasharray: `${c * pct} ${c}`,
    transform: 'rotate(-90deg)',
    transformOrigin: '50px 50px',
  }
}
// 得分占比条（命中权重 / 总权重）
function eeatEarnedPct(d) {
  return d?.total ? Math.round((d.earned / d.total) * 100) : 0
}
const metricNames = {
  ai_recognition_rate: 'AI 识别率',
  authority_score: '权威信号强度',
  content_completeness: '内容完整度',
  ecosystem_coverage: '生态推荐覆盖',
  conversion_potential: '转化潜力',
}
const findings = computed(() => report.value?.findings || {})
const dimensionList = computed(() => {
  const dims = report.value?.dimensions || {}
  return Object.entries(dims).map(([code, d]) => ({ code, ...d }))
})

/* ============ 仪表盘 SVG 动画 ============ */
const gaugeStyle = computed(() => {
  const pct = (report.value?.overall_score || 0) / 100
  const c = 2 * Math.PI * 52
  return {
    strokeDasharray: `${c * pct} ${c}`,
    transform: 'rotate(-90deg)',
    transformOrigin: '60px 60px',
  }
})

const vitalsList = computed(() => {
  const v = report.value?.performance?.vitals || {}
  const r = report.value?.performance?.resources || {}
  return [
    { label: 'TTFB 首字节', value: v.ttfb_ms != null ? Math.round(v.ttfb_ms) : '—',
      unit: 'ms', pct: pctFromMs(v.ttfb_ms, 800), cls: perfCls(v.ttfb_ms, 800) },
    { label: 'FCP 首次内容', value: v.fcp_ms != null ? Math.round(v.fcp_ms) : '—',
      unit: 'ms', pct: pctFromMs(v.fcp_ms, 1800), cls: perfCls(v.fcp_ms, 1800) },
    { label: 'LCP 最大内容', value: v.lcp_ms != null ? Math.round(v.lcp_ms) : '—',
      unit: 'ms', pct: pctFromMs(v.lcp_ms, 2500), cls: perfCls(v.lcp_ms, 2500) },
    { label: '页面大小', value: r.page_size_mb ?? '—', unit: 'MB',
      pct: Math.min(100, ((r.page_size_mb || 0) / 5) * 100), cls: '' },
  ]
})

function pctFromMs(v, bad) {
  if (v == null) return 0
  return Math.max(4, Math.min(100, 100 - (v / bad) * 100))
}
function perfCls(v, bad) {
  if (v == null) return ''
  if (v <= bad * 0.5) return 'good'
  if (v <= bad) return 'ok'
  return 'bad'
}

function gradeLetter(score) {
  return score >= 90 ? 'S' : score >= 80 ? 'A' : score >= 70 ? 'B' : score >= 60 ? 'C' : 'D'
}
function eeatGradeLetter(score) {
  return gradeLetter(score)
}
function formatTime(t) {
  return new Date(t).toLocaleString('zh-CN', { hour12: false })
}
function fmtMs(v) {
  if (v === null || v === undefined) return '未检测'
  return `${Math.round(v)} ms`
}

function cell(kw, engine) {
  const rows = report.value?.keyword_matrix?.rows || []
  return rows.find((r) => r.keyword === kw && r.engine === engine)
}
function cellClass(kw, engine) {
  return cell(kw, engine)?.recognized ? 'hit' : 'miss'
}
function cellText(kw, engine) {
  return cell(kw, engine)?.recognized ? '识别' : '未识别'
}

function renderRadar() {
  if (!radarEl.value || !report.value) return
  chart = chart || echarts.init(radarEl.value)
  const dims = report.value.dimensions
  chart.setOption({
    radar: {
      indicator: Object.entries(dims).map(([, d]) => ({ name: d.name, max: 100 })),
      splitArea: { areaStyle: { color: ['rgba(91,140,255,0.04)', 'rgba(157,91,255,0.06)'] } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } },
      axisName: { color: '#aab4d8', fontSize: 12 },
    },
    animationDuration: 900,
    animationEasing: 'cubicOut',
    series: [{
      type: 'radar',
      symbol: 'circle',
      symbolSize: 5,
      data: [
        {
          name: '本站得分', value: Object.values(dims).map((d) => d.score),
          areaStyle: { color: 'rgba(91,140,255,0.35)' },
          lineStyle: { color: '#5b8cff', width: 2 },
          itemStyle: { color: '#5b8cff' },
        },
        {
          name: '行业基准', value: Object.values(dims).map(() => findings.value.benchmark),
          areaStyle: { color: 'rgba(255,200,87,0.10)' },
          lineStyle: { color: '#ffc857', type: 'dashed', width: 1.5 },
        },
      ],
    }],
    legend: { data: ['本站得分', '行业基准'], textStyle: { color: '#aab4d8' }, bottom: 0 },
  })
}

async function load() {
  const { data } = await api.getReport(props.id)
  report.value = data
  await nextTick()
  renderRadar()
}

watch(() => props.id, load)
onMounted(load)
onBeforeUnmount(() => chart?.dispose())
</script>

<style scoped>
.report { display: flex; flex-direction: column; gap: 22px; }

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
.section-h { font-size: 13px; color: var(--text); margin: 22px 0 10px; font-weight: 600; }

/* ============ Hero ============ */
.hero { padding: 26px 28px; }
.hero-left { display: flex; gap: 26px; align-items: center; flex: 1; min-width: 0; }

.overall {
  position: relative; width: 132px; height: 132px;
  flex-shrink: 0;
}
.gauge-bg {
  fill: none; stroke: rgba(255,255,255,0.05); stroke-width: 9;
}
.gauge-fg {
  fill: none; stroke: url(#g); stroke-width: 9; stroke-linecap: round;
  transition: stroke-dasharray 1.3s var(--ease-out);
}
.overall.grade-S .gauge-fg { stroke: var(--grade-S); }
.overall.grade-A .gauge-fg { stroke: var(--grade-A); }
.overall.grade-B .gauge-fg { stroke: var(--grade-B); }
.overall.grade-C .gauge-fg { stroke: var(--grade-C); }
.overall.grade-D .gauge-fg { stroke: var(--grade-D); }
.overall.grade-S .score { color: var(--grade-S); }
.overall.grade-A .score { color: var(--grade-A); }
.overall.grade-B .score { color: var(--grade-B); }
.overall.grade-C .score { color: var(--grade-C); }
.overall.grade-D .score { color: var(--grade-D); }

.gauge-text {
  position: absolute; inset: 0;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.gauge-text .score {
  font-size: 36px; font-weight: 800;
  line-height: 1; letter-spacing: -0.5px;
  font-feature-settings: 'tnum';
}
.gauge-text .label { font-size: 10px; color: var(--text-mute); margin-top: 4px; }

.hero-info { min-width: 0; }
.url {
  font-size: 17px; font-weight: 600; margin: 0 0 6px;
  word-break: break-all; line-height: 1.3;
  letter-spacing: 0.2px;
}
.grade-line { font-size: 13px; color: var(--text-soft); margin: 6px 0 4px; }
.grade-line .sep { color: var(--text-mute); margin: 0 6px; }
.grade-line code {
  font-family: 'SFMono-Regular', Consolas, monospace;
  font-size: 11.5px; color: var(--text-mute);
  background: rgba(255,255,255,0.05); padding: 1px 6px; border-radius: 4px;
}
.meta { font-size: 11.5px; color: var(--text-mute); margin: 0; }

.grade-S, .grade-A { color: var(--grade-A); }
.grade-B { color: var(--grade-B); }
.grade-C, .grade-D { color: var(--grade-C); }

.hero-codes { display: flex; gap: 8px; flex-wrap: wrap; }
.code-chip {
  background: rgba(8, 11, 26, 0.5);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: 10px 14px;
  text-align: center;
  min-width: 76px;
  transition: all var(--t-fast) var(--ease);
  animation: pop 400ms var(--ease-out) backwards;
  animation-delay: calc(var(--i) * 60ms + 200ms);
}
.code-chip:hover {
  transform: translateY(-2px);
  border-color: var(--border-2);
  background: rgba(8, 11, 26, 0.7);
}
.code-chip .code {
  display: block; font-size: 10.5px;
  color: var(--accent); font-weight: 700; letter-spacing: 0.5px;
}
.code-chip .val {
  display: block; font-size: 20px; font-weight: 700;
  font-feature-settings: 'tnum';
  margin: 2px 0;
}
.code-chip .name { display: block; font-size: 10.5px; color: var(--text-mute); }

/* ============ EEAT ============ */
.eeat { padding: 26px 28px; }
.eeat-head { display: flex; align-items: center; gap: 10px; }
.scope-tag {
  font-size: 11px; padding: 3px 9px; border-radius: 999px;
  background: rgba(91, 140, 255, 0.14);
  border: 1px solid rgba(91, 140, 255, 0.3);
  color: #a9c4ff;
}
.eeat-total {
  font-size: 26px; font-weight: 800; line-height: 1;
  font-feature-settings: 'tnum';
}
.eeat-total i { font-size: 12px; font-style: normal; font-weight: 400; color: var(--text-mute); }
.eeat-grade {
  font-size: 11.5px; font-weight: 700; padding: 3px 10px; border-radius: 6px;
}
.eeat-grade.grade-S, .eeat-grade.grade-A { background: rgba(80, 200, 120, 0.16); color: #6fd68f; }
.eeat-grade.grade-B { background: rgba(255, 200, 87, 0.16); color: #ffc857; }
.eeat-grade.grade-C, .eeat-grade.grade-D { background: rgba(255, 120, 120, 0.16); color: #ff8a8a; }

.eeat-summary {
  margin: 0 0 18px; font-size: 13px; color: var(--text-soft); line-height: 1.75;
  padding: 12px 16px; border-radius: var(--r-md);
  background: rgba(8, 11, 26, 0.4); border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
}

.eeat-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px;
}
.eeat-card {
  padding: 16px 18px;
  border-radius: var(--r-md);
  background: rgba(8, 11, 26, 0.45);
  border: 1px solid var(--border);
  border-top: 2px solid var(--c);
  transition: all var(--t-med) var(--ease);
  animation: fadeUp 500ms var(--ease-out) backwards;
  animation-delay: calc(var(--i) * 90ms + 260ms);
  display: flex; flex-direction: column;
}
.eeat-card:hover {
  transform: translateY(-3px);
  border-color: var(--border-2);
  border-top-color: var(--c);
  background: rgba(8, 11, 26, 0.62);
  box-shadow: 0 12px 32px -12px rgba(0, 0, 0, 0.5);
}

.eeat-card-head { display: flex; align-items: center; gap: 14px; }
.eeat-ring { position: relative; width: 74px; height: 74px; flex-shrink: 0; }
.ring-bg { fill: none; stroke: rgba(255, 255, 255, 0.06); stroke-width: 8; }
.ring-fg {
  fill: none; stroke: var(--c); stroke-width: 8; stroke-linecap: round;
  transition: stroke-dasharray 1.2s var(--ease-out);
}
.ring-text {
  position: absolute; inset: 0;
  display: flex; align-items: center; justify-content: center;
}
.ring-text .num {
  font-size: 20px; font-weight: 800; color: var(--c);
  font-feature-settings: 'tnum';
}

.eeat-meta { min-width: 0; }
.eeat-name { display: flex; align-items: center; gap: 7px; }
.eeat-name b { font-size: 15px; color: var(--text); }
.eeat-name .short {
  display: inline-flex; align-items: center; justify-content: center;
  width: 19px; height: 19px; border-radius: 5px;
  font-size: 11px; font-weight: 800;
  background: var(--c); color: #0a0e1f;
}
.eeat-meta .en {
  display: block; font-size: 11px; color: var(--text-mute);
  letter-spacing: 0.3px; margin-top: 1px;
}
.grade-pill {
  display: inline-block; margin-top: 5px;
  font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 4px;
}
.grade-pill.grade-S, .grade-pill.grade-A { background: rgba(80, 200, 120, 0.16); color: #6fd68f; }
.grade-pill.grade-B { background: rgba(255, 200, 87, 0.16); color: #ffc857; }
.grade-pill.grade-C, .grade-pill.grade-D { background: rgba(255, 120, 120, 0.16); color: #ff8a8a; }

/* 得分占比条 */
.eeat-bar {
  position: relative; height: 5px; border-radius: 3px;
  background: rgba(255, 255, 255, 0.05);
  margin: 12px 0 10px; overflow: visible;
}
.eeat-bar-fill {
  display: block; height: 100%; border-radius: 3px;
  background: var(--c);
  transition: width 1s var(--ease-out);
  box-shadow: 0 0 10px -2px var(--c);
}
.eeat-bar-txt {
  position: absolute; right: 0; top: 8px;
  font-size: 10.5px; color: var(--text-mute);
}

.eeat-desc {
  margin: 16px 0 12px; font-size: 12px; color: var(--text-mute); line-height: 1.6;
}

/* 信号明细 */
.eeat-signals { display: flex; flex-direction: column; gap: 5px; flex: 1; }
.sig {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  gap: 6px; align-items: baseline;
  font-size: 11.5px; line-height: 1.5;
  padding: 5px 8px; border-radius: 6px;
  transition: background var(--t-fast) var(--ease);
}
.sig:hover { background: rgba(255, 255, 255, 0.03); }
.sig .mk {
  font-style: normal; font-weight: 800; font-size: 11px;
  grid-row: span 2;
}
.sig.ok .mk { color: #6fd68f; }
.sig.no .mk { color: #ff8a8a; }
.sig .lb { color: var(--text); font-weight: 600; white-space: nowrap; }
.sig .wt {
  font-size: 10.5px; font-weight: 700;
  font-feature-settings: 'tnum';
}
.sig.ok .wt { color: #6fd68f; }
.sig.no .wt { color: #ff8a8a; }
.sig .dt {
  grid-column: 2; font-size: 11px; color: var(--text-mute);
  line-height: 1.45;
}
.sig.ok .dt { color: var(--text-soft); }

.eeat-advice {
  margin: 12px 0 0; padding-top: 10px;
  border-top: 1px dashed var(--border);
  font-size: 11.5px; color: var(--text-soft); line-height: 1.7;
}

/* 整改清单 */
.gap-panel {
  margin-top: 20px; padding-top: 16px;
  border-top: 1px solid var(--border);
}
.gap-panel h3 { margin: 0 0 12px; font-size: 13.5px; color: var(--text); }
.gap-list { display: flex; flex-direction: column; gap: 7px; }
.gap-item {
  display: grid;
  grid-template-columns: 22px 76px 48px 1fr;
  grid-template-areas: "rank name weight label" "rank name weight detail";
  gap: 2px 10px; align-items: baseline;
  padding: 9px 12px; border-radius: var(--r-sm);
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border);
  border-left: 3px solid rgba(255, 120, 120, 0.45);
  animation: fadeUp 400ms var(--ease-out) backwards;
  animation-delay: calc(var(--i) * 60ms + 500ms);
  transition: all var(--t-fast) var(--ease);
}
.gap-item:hover { background: rgba(255, 255, 255, 0.06); transform: translateX(2px); }
.gap-rank {
  grid-area: rank;
  display: inline-flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; border-radius: 50%;
  font-size: 11px; font-weight: 800;
  background: rgba(255, 120, 120, 0.18); color: #ff9a9a;
}
.gap-name {
  grid-area: name;
  font-size: 12px; font-weight: 700; color: var(--c);
}
.gap-weight {
  grid-area: weight;
  font-size: 12px; font-weight: 800; color: #6fd68f;
  font-feature-settings: 'tnum';
}
.gap-label { grid-area: label; font-size: 12.5px; color: var(--text); font-weight: 600; }
.gap-detail { grid-area: detail; font-size: 11.5px; color: var(--text-mute); line-height: 1.5; }

/* ============ Grid ============ */
.grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 22px; }

.chart { height: 320px; margin-bottom: 16px; }

table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; color: var(--text-mute); font-weight: 500; padding: 10px 8px; border-bottom: 1px solid var(--border); }
td { padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.dim-table td.sub { color: var(--text-mute); font-size: 12px; }

/* Dimension table */
.dim-tag {
  display: inline-block;
  font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px;
  padding: 2px 6px; border-radius: 4px;
  margin-right: 8px;
  background: rgba(91, 140, 255, 0.18);
  color: #a9c4ff;
}
.dim-tag.dim-S { background: rgba(91, 140, 255, 0.18); color: #8db4ff; }
.dim-tag.dim-H { background: rgba(157, 91, 255, 0.18); color: #c3a4ff; }
.dim-tag.dim-E1 { background: rgba(80, 200, 120, 0.18); color: #7fd7a0; }
.dim-tag.dim-E2 { background: rgba(240, 150, 90, 0.18); color: #f0a46a; }
.dim-tag.dim-P { background: rgba(91, 220, 220, 0.18); color: #7fd7d7; }

.score-bar {
  display: inline-block;
  width: 60px; height: 6px; border-radius: 3px;
  background: rgba(255,255,255,0.05);
  position: relative; vertical-align: middle;
  margin-right: 8px;
  overflow: hidden;
}
.score-num {
  position: absolute; left: 0; top: 0; bottom: 0;
  width: 0;
  background: var(--accent-grad);
  border-radius: 3px;
  animation: fillBar 1.2s var(--ease-out) forwards;
  animation-delay: 200ms;
}
.score-bar.grade-S .score-num, .score-bar.grade-A .score-num { background: linear-gradient(90deg, #4dd0a4, #5ee6a8); }
.score-bar.grade-B .score-num { background: linear-gradient(90deg, #ffc857, #ffd97a); }
.score-bar.grade-C .score-num, .score-bar.grade-D .score-num { background: linear-gradient(90deg, #ff7d7d, #ff9a6a); }
@keyframes fillBar { to { width: var(--target); } }

.grade-tag {
  display: inline-block; font-size: 11px; font-weight: 600;
  padding: 2px 8px; border-radius: 4px;
}
.grade-tag.grade-S, .grade-tag.grade-A { background: rgba(80, 200, 120, 0.16); color: #6fd68f; }
.grade-tag.grade-B { background: rgba(255, 200, 87, 0.16); color: #ffc857; }
.grade-tag.grade-C, .grade-tag.grade-D { background: rgba(255, 120, 120, 0.16); color: #ff8a8a; }

.up { color: #6fd68f; }
.down { color: #ff8a8a; }

/* ============ Metrics ============ */
.metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.metric {
  background: rgba(8, 11, 26, 0.4);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: 14px 16px;
  position: relative; overflow: hidden;
  transition: all var(--t-fast) var(--ease);
  animation: pop 400ms var(--ease-out) backwards;
  animation-delay: calc(var(--i) * 50ms + 200ms);
}
.metric::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: var(--accent-grad);
  opacity: 0; transition: opacity var(--t-fast) var(--ease);
}
.metric:hover { transform: translateY(-2px); border-color: var(--border-2); }
.metric:hover::before { opacity: 1; }

.metric-val {
  font-size: 26px; font-weight: 700;
  background: var(--accent-grad);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  font-feature-settings: 'tnum';
}
.metric-val small { font-size: 12px; color: var(--text-mute); -webkit-text-fill-color: var(--text-mute); }
.metric-name { font-size: 12px; color: var(--text-mute); margin-top: 4px; }

.finding { font-size: 13px; color: var(--text-soft); margin: 8px 0; line-height: 1.75; }
.pri-tag {
  display: inline-block; background: rgba(91, 140, 255, 0.15);
  color: #a9c4ff; font-size: 11.5px;
  border-radius: 5px; padding: 2px 8px; margin: 2px 4px 2px 0;
  border: 1px solid rgba(91, 140, 255, 0.25);
}

/* ============ Matrix ============ */
.recognition {
  font-size: 12.5px; color: var(--text-mute);
  display: inline-flex; align-items: center; gap: 6px;
}
.recognition b {
  font-size: 18px; font-weight: 700;
  background: var(--accent-grad);
  -webkit-background-clip: text; background-clip: text; color: transparent;
  font-feature-settings: 'tnum';
}
.recognition .scope { color: var(--text-mute); font-size: 11.5px; }

.matrix-wrap { overflow-x: auto; margin: 0 -6px; }
.matrix-wrap table { min-width: 100%; }
.kw { font-weight: 600; color: var(--text); }
.pos-badges { display: flex; flex-wrap: wrap; gap: 4px; }
.pos-badge {
  font-style: normal; font-size: 10.5px; padding: 2px 7px; border-radius: 4px;
  background: rgba(91, 140, 255, 0.15); color: #8db4ff;
  border: 1px solid rgba(91, 140, 255, 0.3);
}
.pos-none { font-size: 12px; color: #ff8a8a; }
.center { text-align: center; }
.hit, .miss {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11.5px; padding: 2px 8px; border-radius: 999px;
}
.hit { color: #6fd68f; background: rgba(80, 200, 120, 0.12); border: 1px solid rgba(80, 200, 120, 0.25); }
.miss { color: #ff8a8a; background: rgba(255, 80, 80, 0.10); border: 1px solid rgba(255, 80, 80, 0.22); }
.cell-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }

.sub { font-size: 12px; color: var(--text-mute); margin: 0 0 12px; }

.kw-diagnosis {
  margin-top: 18px; padding-top: 14px;
  border-top: 1px solid var(--border);
}
.kw-diagnosis h3 { margin: 0 0 10px; font-size: 14px; color: var(--text); }
.diag { margin: 6px 0; font-size: 13px; color: var(--text-soft); line-height: 1.7; }
.diag b { color: var(--text); margin-right: 8px; }
.diag .lv {
  display: inline-block; margin-right: 8px; font-size: 11.5px;
  padding: 1px 8px; border-radius: 4px; font-weight: 600;
}
.diag-strong .lv { background: rgba(80, 200, 120, 0.15); color: #6fd68f; }
.diag-weak   .lv { background: rgba(240, 200, 80, 0.15); color: #e8c86a; }
.diag-none   .lv { background: rgba(224, 123, 123, 0.15); color: #e07b7b; }

/* ============ Vitals ============ */
.vitals { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.vital {
  padding: 14px 16px;
  border-radius: var(--r-md);
  background: rgba(8, 11, 26, 0.4);
  border: 1px solid var(--border);
  transition: all var(--t-fast) var(--ease);
  animation: pop 400ms var(--ease-out) backwards;
  animation-delay: calc(var(--i) * 60ms + 200ms);
}
.vital:hover { transform: translateY(-2px); border-color: var(--border-2); }
.vital-label { font-size: 11.5px; color: var(--text-mute); }
.vital-val {
  font-size: 24px; font-weight: 700; margin: 4px 0;
  font-feature-settings: 'tnum';
  color: var(--text);
}
.vital-val small { font-size: 12px; color: var(--text-mute); margin-left: 2px; font-weight: 400; }
.vital-val.good { color: #6fd68f; }
.vital-val.ok   { color: #ffc857; }
.vital-val.bad  { color: #ff8a8a; }
.vital-bar {
  margin-top: 8px;
  height: 4px; border-radius: 2px;
  background: rgba(255,255,255,0.05);
  overflow: hidden;
}
.vital-bar-fill {
  display: block; height: 100%; width: 0;
  background: var(--accent-grad);
  border-radius: 2px;
  animation: fillBar 1.2s var(--ease-out) forwards;
  animation-delay: 300ms;
}

.more-vitals {
  margin-top: 14px;
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: rgba(8, 11, 26, 0.3);
  overflow: hidden;
}
.more-vitals summary {
  list-style: none;
  cursor: pointer;
  padding: 10px 14px;
  font-size: 12.5px; color: var(--text-soft);
  display: flex; align-items: center; gap: 6px;
  transition: background var(--t-fast) var(--ease);
}
.more-vitals summary::-webkit-details-marker { display: none; }
.more-vitals summary::before {
  content: '▸';
  display: inline-block;
  transition: transform var(--t-fast) var(--ease);
  color: var(--text-mute);
}
.more-vitals[open] summary::before { transform: rotate(90deg); }
.more-vitals summary:hover { background: rgba(255,255,255,0.03); }
.more-vitals table { margin: 0 14px 14px; }

/* ============ Suggestions ============ */
.suggestion-list { display: grid; gap: 12px; }
.suggestion {
  background: rgba(8, 11, 26, 0.4);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  padding: 14px 18px;
  transition: all var(--t-fast) var(--ease);
  position: relative; overflow: hidden;
  animation: pop 400ms var(--ease-out) backwards;
  animation-delay: calc(var(--i) * 80ms + 300ms);
}
.suggestion::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 3px;
  background: var(--accent-grad);
}
.suggestion:hover { transform: translateX(2px); border-color: var(--border-2); }
.suggestion-head { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; }
.suggestion-head strong { font-size: 14px; color: var(--text); }
.suggestion-head .score { color: var(--text-mute); font-size: 12px; margin-left: auto; }
.badge {
  background: var(--accent-grad); color: #fff;
  font-size: 11px; font-weight: 700;
  border-radius: 5px; padding: 2px 8px;
  letter-spacing: 0.5px;
}
.suggestion p { font-size: 13px; color: var(--text-soft); line-height: 1.75; margin: 0; }

.legend {
  font-size: 11.5px; color: var(--text-mute);
  display: inline-flex; align-items: center; gap: 8px;
}
.legend .dot {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 3px; vertical-align: middle;
}
.legend .me   { background: #5b8cff; }
.legend .base { background: #ffc857; }

/* ============ Back link ============ */
.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  color: var(--text-mute); text-decoration: none;
  font-size: 13px;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  transition: all var(--t-fast) var(--ease);
  align-self: flex-start;
}
.back-link:hover { color: var(--text); background: rgba(255,255,255,0.08); transform: translateX(-2px); }

/* ============ Loading ============ */
.loading { text-align: center; padding: 80px 20px; color: var(--text-mute); }
.loading-spin {
  display: inline-block;
  width: 32px; height: 32px;
  border: 3px solid rgba(255,255,255,0.1);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 14px;
}
.loading p { margin: 0; font-size: 13px; }

/* ============ Responsive ============ */
@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; }
  .hero { flex-direction: column; align-items: flex-start; }
  .hero-codes { width: 100%; }
}
</style>
