# GEO 监测量化模拟系统

基于 **SHEEP 五维框架**（参照 SheepGEO 量化指标模板 / GEM 评分体系）的生成式引擎优化（GEO）监测与量化模拟平台。

## 评分体系（对齐 SheepGEO 模板）

| 维度 | 短码 | 子指标 |
|---|---|---|
| S 语义覆盖 Semantic Coverage | GV | AI 识别率 / 内容质量 / 语义完整性 |
| H 人类可信度 Human Credibility | CR | 权威信号 / 专业背书 / 社会证明 |
| E 证据结构化 Evidence Structuring | SH | 内容完整度 / 语义丰富度 / 结构质量 |
| E 生态集成 Ecosystem Integration | EI | 推荐覆盖率 / 行业集成度 / 平台覆盖 |
| P 性能监测 Performance Monitoring | AE | Core Web Vitals / AI 采纳效率 / 转化潜力 |

综合评分 = 五维加权（S 0.20 / H 0.15 / E1 0.20 / E2 0.15 / P 0.30），等级 S/A/B/C/D，
并输出核心指标汇总、关键发现、改进优先级矩阵与优化建议，结构对齐模板报告。

## 技术栈

- **采集**：Playwright（无头浏览器，抓取 HTML + TTFB/FCP/LCP + 资源统计）
- **解析**：BeautifulSoup + lxml（标题层级、JSON-LD、社媒外链、可信度信号等）
- **分析**：pandas（子指标加权 -> 五维得分 -> GEM 综合分）
- **业务层**：Python + FastAPI（任务 CRUD / 进度查询 / 报告查询 / 历史趋势）
- **调度**：Celery + Redis（异步监测任务，Redis 存实时进度）
- **存储**：PostgreSQL（任务与报告）+ Redis（进度缓存）
- **前端**：Vue3 + Vite + ECharts（任务管理、五维雷达图、识别矩阵、报告详情）

## 目录结构

```
backend/
  app/
    config.py           # 配置（环境变量 GEO_ 前缀）
    database.py         # SQLAlchemy 引擎/会话
    models.py           # MonitorTask / MonitorReport
    schemas.py          # Pydantic 模型
    main.py             # FastAPI 入口
    api/routes.py       # REST 路由
    services/
      crawler.py        # Playwright 采集
      parser.py         # BeautifulSoup/lxml 解析
      analyzer.py       # pandas SHEEP 分析引擎
    tasks/
      celery_app.py     # Celery 配置
      geo_tasks.py      # 监测任务流水线
frontend/
  src/
    views/Dashboard.vue     # 任务创建/列表/进度
    views/ReportDetail.vue  # GEM 评分 + 雷达图 + 识别矩阵
docker-compose.yml        # PostgreSQL + Redis
```

## 快速启动

### 1. 基础设施

```bash
docker compose up -d
```

### 2. 后端

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements.txt
playwright install chromium

# 启动 API（默认 8000 端口）
uvicorn app.main:app --reload

# 另开终端，启动 Celery Worker
celery -A app.tasks.celery_app worker --loglevel=info -P solo
```

> Windows 下 Celery 建议加 `-P solo`；Linux/macOS 可用默认 prefork 池。

### 3. 前端

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

### 4. 使用流程

1. 在首页创建监测任务：填入任务名、目标 URL、关键词（逗号分隔，支持多关键词）
2. 点击「运行」，观察实时进度（采集 -> 解析 -> 分析 -> 落库）
3. 完成后点击「报告」查看量化报告：GEM 综合评分、五维雷达图（含行业基准对比）、
   多引擎 × 多关键词识别矩阵、Core Web Vitals、优先级矩阵与优化建议

## 扩展方向

- **多模型**：`config.SIMULATED_ENGINES` 当前为确定性模拟；接入真实 LLM API 时
  替换 `analyzer.simulate_engines` 即可
- **定时监测**：为 Celery 增加 `beat` 周期任务，调用 `run_monitor.delay`
- **历史趋势**：`GET /api/reports/{id}/history` 已返回时序数据，前端可加折线图
