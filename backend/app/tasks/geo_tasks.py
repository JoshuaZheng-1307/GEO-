"""GEO 监测 Celery 任务：采集 -> 解析 -> 分析 -> 落库。

进度通过 Redis 发布（key: geo:progress:{task_id}），前端轮询获取。
"""
import json

import redis

from app.config import settings
from app.database import SessionLocal
from app.models import MonitorReport, MonitorTask, User
from app.services.analyzer import analyze
from app.services.auth import TASK_COST, charge_tokens
from app.services.crawler import crawl_sync
from app.services.parser import parse_page
from app.services.site_profiler import profile_site
from app.tasks.celery_app import celery_app

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

STAGES = [
    (5, "queued", "任务已入队"),
    (12, "profiling", "分析官网：识别企业业务并自动生成关键词"),
    (25, "crawling", "Playwright 采集中：加载页面并测量 Core Web Vitals"),
    (45, "parsing", "解析页面结构（BeautifulSoup/lxml）"),
    (65, "analyzing", "计算 SHEEP 五维指标（pandas）"),
    (85, "saving", "生成报告并写入 PostgreSQL"),
    (100, "done", "监测完成"),
]


def _publish(task_id: int, percent: int, stage: str, message: str, status: str = "running"):
    payload = {"task_id": task_id, "status": status, "stage": stage,
               "percent": percent, "message": message}
    redis_client.set(f"geo:progress:{task_id}", json.dumps(payload), ex=3600)


@celery_app.task(bind=True, name="geo.run_monitor")
def run_monitor(self, task_id: int):
    db = SessionLocal()
    try:
        task = db.get(MonitorTask, task_id)
        if not task:
            _publish(task_id, 0, "failed", "任务不存在", "failed")
            return {"error": "task not found"}

        task.status = "running"
        db.commit()

        try:
            _pct, _stage, _msg = STAGES[1]
            _publish(task_id, _pct, _stage, _msg)

            # 0. 关键词：用户没给就自动分析官网生成（用户只看结果，不需要懂 GEO 关键词）
            keywords = list(task.keywords or [])
            site_text, scope_pages = "", 1
            try:
                prof = profile_site(task.url, hint=task.hint or "", include_corpus=True)
                site_text = prof.get("corpus", "")
                scope_pages = max(1, len(prof.get("pages_analyzed", [])))
                if not keywords:
                    keywords = [k["keyword"] for k in prof["keywords"]]
                    if keywords:
                        task.keywords = keywords      # 回写，任务列表可见
                        db.commit()
            except Exception as exc:  # noqa: BLE001 画像失败不阻断监测
                _publish(task_id, _pct, _stage,
                         f"官网分析失败，改用任务名作为关键词：{exc}"[:200])
            if not keywords:
                keywords = [task.name[:30]]

            # 1. 采集
            _pct, _stage, _msg = STAGES[2]
            _publish(task_id, _pct, _stage, _msg)
            crawled = crawl_sync(task.url)
            if crawled.errors and not crawled.html:
                raise RuntimeError(f"采集失败: {'; '.join(crawled.errors[:3])}")

            # 2. 解析
            _pct, _stage, _msg = STAGES[3]
            _publish(task_id, _pct, _stage, _msg)
            features = parse_page(crawled.html, crawled.final_url or task.url)

            # 3. 分析
            _pct, _stage, _msg = STAGES[4]
            _publish(task_id, _pct, _stage, _msg)
            engines = task.engines or settings.SIMULATED_ENGINES
            perf = {
                "ttfb_ms": crawled.ttfb_ms, "fcp_ms": crawled.fcp_ms, "lcp_ms": crawled.lcp_ms,
                "resources": {
                    "request_count": crawled.request_count,
                    "page_size_mb": round(crawled.page_size_mb, 3),
                    "js_size_kb": round(crawled.js_size_kb, 1),
                    "css_size_kb": round(crawled.css_size_kb, 1),
                    "image_size_mb": round(crawled.image_size_mb, 3),
                },
            }
            report_data = analyze(features, perf, keywords, engines,
                                  site_text=site_text, scope_pages=scope_pages)

            # 4. 落库
            _pct, _stage, _msg = STAGES[5]
            _publish(task_id, _pct, _stage, _msg)
            report = MonitorReport(
                task_id=task.id,
                url=report_data["url"],
                overall_score=report_data["overall_score"],
                grade=report_data["grade"],
                dimensions=report_data["dimensions"],
                core_metrics=report_data["core_metrics"],
                eeat=report_data.get("eeat"),
                findings=report_data["findings"],
                performance=report_data["performance"],
                keyword_matrix=report_data["keyword_matrix"],
                suggestions=report_data["suggestions"],
                snapshot=report_data["snapshot"],
                signature=report_data["signature"],
            )
            db.add(report)
            task.status = "done"
            task.last_message = (
                f"综合评分 {report_data['overall_score']}/100（{report_data['grade_label']}），"
                f"最强维度 {report_data['findings']['strongest']['dimension']}，"
                f"最弱维度 {report_data['findings']['weakest']['dimension']}")
            db.commit()

            _pct, _stage, _msg = STAGES[6]
            _publish(task_id, _pct, _stage, _msg, status="done")
            return {"report_id": report.id, "overall_score": report_data["overall_score"]}

        except Exception as exc:  # noqa: BLE001
            db.rollback()
            task = db.get(MonitorTask, task_id)
            task.status = "failed"
            task.last_message = str(exc)[:500]
            # 计费保障：任务失败退还预扣的 token（admin 无额度概念，不退）
            if task.user_id:
                owner = db.get(User, task.user_id)
                if owner and owner.role != "admin":
                    charge_tokens(db, owner, TASK_COST, "refund",
                                  note=f"任务「{task.name[:60]}」失败退款", task_id=task.id)
            db.commit()
            _publish(task_id, 100, "failed", str(exc)[:200], status="failed")
            raise

    finally:
        db.close()
