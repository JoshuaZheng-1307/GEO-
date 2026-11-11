"""Playwright 采集服务：抓取页面 HTML + Core Web Vitals + 资源统计。

对应模板中 P 维度的性能数据（TTFB/FCP/LCP、页面大小、请求数量等）。
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import async_playwright

from app.config import settings


@dataclass
class CrawlResult:
    html: str = ""
    final_url: str = ""
    status_code: int = 0
    # Core Web Vitals（毫秒）
    ttfb_ms: Optional[float] = None
    fcp_ms: Optional[float] = None
    lcp_ms: Optional[float] = None
    # 资源统计
    request_count: int = 0
    page_size_mb: float = 0.0
    js_size_kb: float = 0.0
    css_size_kb: float = 0.0
    image_size_mb: float = 0.0
    errors: list = field(default_factory=list)


# 注入到页面内采集 FCP / LCP 的脚本（PerformanceObserver + Navigation Timing）
_MEASURE_SCRIPT = """
() => new Promise((resolve) => {
    const out = { fcp: null, lcp: null };
    try {
        const nav = performance.getEntriesByType('navigation')[0];
        out.ttfb = nav ? nav.responseStart : null;
    } catch (e) { out.ttfb = null; }
    try {
        const paints = performance.getEntriesByType('paint');
        const fcp = paints.find(p => p.name === 'first-contentful-paint');
        out.fcp = fcp ? fcp.startTime : null;
    } catch (e) {}
    try {
        new PerformanceObserver((l) => {
            const entries = l.getEntries();
            if (entries.length) out.lcp = entries[entries.length - 1].startTime;
        }).observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) {}
    // 给 LCP 一点缓冲时间
    setTimeout(() => resolve(out), 1500);
})
"""


async def crawl(url: str) -> CrawlResult:
    """用 Playwright 无头浏览器采集页面，返回 HTML 与性能数据。"""
    result = CrawlResult(final_url=url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.HEADLESS)
        context = await browser.new_context(user_agent=settings.USER_AGENT)
        page = await context.new_page()

        # 资源统计：监听所有响应的 body 大小
        async def _on_response(resp):
            nonlocal result
            if resp.url.startswith("data:"):
                return
            try:
                body = await resp.body()
                size = len(body)
            except Exception:
                size = 0
            result.request_count += 1
            result.page_size_mb += size / (1024 * 1024)
            rtype = resp.request.resource_type
            if rtype == "script":
                result.js_size_kb += size / 1024
            elif rtype == "stylesheet":
                result.css_size_kb += size / 1024
            elif rtype == "image":
                result.image_size_mb += size / 1024

        page.on("response", lambda r: asyncio.ensure_future(_on_response(r)))

        t0 = time.perf_counter()
        try:
            resp = await page.goto(
                url, wait_until="domcontentloaded",
                timeout=settings.NAV_TIMEOUT_MS,
            )
            result.status_code = resp.status if resp else 0
            result.final_url = page.url
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass  # 部分站点长连接无法 idle，忽略

            vitals = await page.evaluate(_MEASURE_SCRIPT)
            if vitals.get("ttfb") is None:
                result.ttfb_ms = (time.perf_counter() - t0) * 1000
            else:
                result.ttfb_ms = float(vitals["ttfb"])
            if vitals.get("fcp") is not None:
                result.fcp_ms = float(vitals["fcp"])
            if vitals.get("lcp") is not None:
                result.lcp_ms = float(vitals["lcp"])

            result.html = await page.content()
        except Exception as exc:  # noqa: BLE001
            result.errors.append(str(exc))
        finally:
            await context.close()
            await browser.close()
    return result


def crawl_sync(url: str) -> CrawlResult:
    """Celery 同步任务入口。"""
    return asyncio.run(crawl(url))
