"""
关键词建议器：从目标页面抽取候选 GEO 关键词。

原理（无外部 NLP 依赖）：
  - 抓取页面 HTML，提取 title / meta description / h1 / h2 / h3
  - 按中文标点与分隔符切短语，2~15 字符的片段视为有效关键词
  - 按"来源"赋权（title 最高、h2/h3 居中、meta 补充），返回 Top N

为什么这样做：
  - 真实 GEO 关键词必须与目标页面内容高度相关；AI 引擎只在页面"看得见"
    关键词时才会把它作为推荐答案的引用来源
  - 用户往往不知道该填什么词；用页面自身的标题层级是最安全、最贴切的选择
"""
from __future__ import annotations
import re
import urllib.request
from typing import Iterable

import lxml.html as LH
from lxml.html import HtmlElement


_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# 常见无意义短语（中文 + 英文），命中直接丢弃
_STOPWORDS = {
    "首页", "网站", "官网", "官方", "欢迎您", "欢迎", "登录", "注册", "首页",
    "返回", "更多", "查看", "详情", "点击", "进入", "了解", "关于", "联系",
    "home", "login", "register", "more", "view", "click", "about", "contact",
    "copyright", "版权所有", "rights", "reserved", "all", "rights reserved",
    "中文", "英文", "简体", "繁体", "english", "chinese",
}

_SPLIT_RE = re.compile(r"[\s\-_/|,，。；：、（）()【】\[\]<>《》!?:：\"'`]")
_KEEP_RE = re.compile(r"[一-鿿A-Za-z0-9]")


def _fetch(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(2_000_000)  # 最多 2MB，避免被巨型页面拖死
        charset = r.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="ignore")
        except LookupError:
            return raw.decode("utf-8", errors="ignore")


def _split_phrases(text: str) -> list[str]:
    """按中英文标点切，保留 2~15 字符的短语。"""
    if not text:
        return []
    out: list[str] = []
    for chunk in _SPLIT_RE.split(text):
        chunk = chunk.strip()
        if 2 <= len(chunk) <= 15 and _KEEP_RE.search(chunk):
            out.append(chunk)
    return out


def _headings(doc: HtmlElement, tag: str, limit: int) -> list[str]:
    items: list[str] = []
    for el in doc.xpath(f".//{tag}"):
        txt = (el.text_content() or "").strip()
        if 2 <= len(txt) <= 60:
            items.append(txt)
        if len(items) >= limit:
            break
    return items


def _meta(doc: HtmlElement) -> str:
    for m in doc.xpath(".//meta"):
        key = (m.get("name") or m.get("property") or "").lower()
        if key in ("description", "og:description", "keywords"):
            content = (m.get("content") or "").strip()
            if content:
                return content
    return ""


def suggest_keywords(url: str, top: int = 12) -> dict:
    """从目标 URL 抓取页面并生成关键词建议。"""
    html = _fetch(url)
    doc = LH.fromstring(html)

    title = (doc.findtext(".//title") or "").strip()
    meta = _meta(doc)
    h1_list = _headings(doc, "h1", 3)
    h2_list = _headings(doc, "h2", 6)
    h3_list = _headings(doc, "h3", 8)

    seen: set[str] = set()
    bag: list[dict] = []

    def add(items: Iterable[str], weight: int, source: str) -> None:
        for item in items:
            for phrase in _split_phrases(item):
                # 过滤纯数字 / 纯单字符英文（如 "Pro"/"Duo" 单独出现时）
                if phrase.isdigit():
                    continue
                if len(phrase) <= 2 and phrase.isascii() and phrase.isalpha():
                    continue
                key = phrase.lower()
                if key in seen:
                    # 已存在则提升权重
                    for b in bag:
                        if b["keyword"] == phrase:
                            b["weight"] = min(b["weight"] + weight // 3, 12)
                            break
                    continue
                if phrase in _STOPWORDS or key in _STOPWORDS:
                    continue
                seen.add(key)
                bag.append({"keyword": phrase, "weight": weight, "source": source})

    add([title], 10, "title")
    add([meta], 6, "meta")
    add(h1_list, 9, "h1")
    add(h2_list, 8, "h2")
    add(h3_list, 6, "h3")

    bag.sort(key=lambda x: (-x["weight"], len(x["keyword"])))
    suggestions = [b for b in bag[:top] if b["weight"] >= 5]

    # 兜底：title 整体作为一个关键词（如果太短被切没了）
    if not suggestions and 2 <= len(title) <= 15:
        suggestions = [{"keyword": title, "weight": 10, "source": "title"}]

    return {
        "url": url,
        "title": title,
        "suggestions": suggestions,
    }
