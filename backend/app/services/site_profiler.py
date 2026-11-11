"""企业画像与关键词自动生成。

用户只需要给官网 URL（可选给一个行业方向），系统自己回答三个问题：
  1. 这家企业是干什么的？   -> 品牌 / 行业 / 主营产品 / 应用场景 / 资质背书
  2. 应该用哪些关键词监测？ -> 品牌词 / 产品词 / 行业词 / 场景词 / 资质词
  3. 每个词属于哪一类？     -> 供前端分类展示、用户增删

实现思路（无外部 NLP 依赖）：
  - 抓首页：品牌取自站点标题；导航链接按 URL/文案特征分类
  - 抓若干关键子页（产品/解决方案/关于）：子页的二级导航往往就是
    产品体系与行业应用场景，是最高价值的候选来源
  - 用行业词典从标题+小标题+关于页正文中识别行业方向
  - 合并去重、过滤无效词、按类别配额输出 12~18 个关键词
"""
from __future__ import annotations

import re
import urllib.request
from typing import Optional
from urllib.parse import urljoin, urlparse

import lxml.html as LH
from lxml.html import HtmlElement

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# ---------------------------------------------------------------------------
# 词典
# ---------------------------------------------------------------------------
# 行业核心词（尽量具体，避免"工程/服务"这类过于宽泛的词造成误判）
INDUSTRY_CORES = [
    "建材", "石膏板", "矿棉板", "龙骨", "卫浴", "厨卫", "家居", "家具", "家电",
    "电器", "照明", "灯具", "门窗", "陶瓷", "瓷砖", "涂料", "油漆", "玻璃",
    "钢材", "水泥", "管道", "五金", "锁具", "机械", "装备", "机床", "电子",
    "半导体", "芯片", "元器件", "软件", "互联网", "人工智能", "大数据", "云计算",
    "新能源", "光伏", "储能", "锂电", "电池", "汽车", "汽配", "化工", "材料",
    "新材料", "塑料", "橡胶", "纺织", "服装", "食品", "饮料", "医药", "生物",
    "医疗", "医疗器械", "物流", "仓储", "地产", "建筑", "装饰", "环保", "节能",
    "电力", "电气", "能源", "农业", "饲料", "包装", "印刷", "珠宝", "教育",
    "旅游", "酒店", "餐饮", "金融", "保险", "证券", "传媒", "广告", "咨询",
    "安防", "通信", "机器人", "无人机", "仪器", "仪表", "自动化", "模具",
    "轴承", "泵阀", "激光", "皮具", "箱包", "玩具", "化妆品", "体育", "健康",
]
INDUSTRY_MODIFIERS = ["智能", "新型", "高端", "绿色", "节能", "环保", "数字",
                      "工业", "建筑", "装配式", "整体", "全屋", "定制", "商用"]

# 纯栏目导航词，直接丢弃
NOISE_EXACT = {
    "首页", "官网", "官方网站", "中文", "english", "en", "cn", "日语", "韩语",
    "更多", "了解更多", "查看更多", "更多资讯", "查看地图", "网站地图", "返回",
    "上一页", "下一页", "登录", "注册", "下载", "服务", "客户服务", "关于",
    "关于我们", "关于北新", "公司简介", "企业简介", "联系我们", "法律声明",
    "隐私政策", "加入我们", "人才招聘", "招聘", "投资者关系", "党的建设",
    "党建工作", "党建", "纪检监察", "职工之家", "学习园地", "社会责任",
    "企业公民", "企业文化", "发展历程", "光辉历程", "管理团队", "公司战略",
    "营销网络", "人力资源", "人才战略", "人才培养", "视频中心", "广告欣赏",
    "展会活动", "招商加盟", "在线反馈", "常见问题", "维护保养", "选购须知",
    "保修规定", "深度验厂", "faq", "新闻", "新闻中心", "新闻动态", "企业新闻",
    "行业资讯", "中标项目", "销售与服务", "可持续发展", "公司治理", "环境生态",
    "健康安全", "和谐社会", "品牌文化", "品牌建设", "品牌与创新", "技术创新",
    "管理创新", "国家技术攻关项目", "工程实例", "案例", "工程案例", "产品中心",
    "产品与应用", "精选产品", "探索产品", "产品", "全部产品", "其他", "综合",
    "行业应用", "技术支持", "工程解决方案", "解决方案", "官方微信", "官方微博",
    "首页 >", "cn", "all", "others", "品牌荣誉", "公司荣誉", "企业荣誉",
}
# 只要包含这些片段，就认为是栏目而非关键词（资质类词除外）
NOISE_MARKERS = ("关于", "联系", "招聘", "投资者", "党建", "纪检", "职工", "学习园地",
                 "社会责任", "企业文化", "发展历程", "历程", "简介", "地图", "声明",
                 "隐私", "反馈", "登录", "注册", "更多", "查看", "人才", "展会",
                 "广告", "English", "FAQ", "首页", "网站", "荣誉")

TRUST_MARKERS = ("认证", "专利", "标准", "资质", "检测", "验厂", "起草",
                 "证书", "奖项", "名牌", "示范", "技术攻关")

# 应用场景标识（用于把子页二级导航里的"行业应用"条目识别为场景词）
SCENARIO_MARKERS = ("建筑", "装饰", "改造", "厂房", "隧道", "桥梁", "住宅", "办公",
                    "商业", "医院", "学校", "酒店", "宾馆", "公寓", "车站", "机场",
                    "场馆", "工厂", "车间", "园区", "楼宇", "家装", "公装", "翻新",
                    "维修", "厨房", "卫生间", "公共", "食堂", "宿舍", "地铁", "高铁")

_SPLIT_TITLE = re.compile(r"[-–—_|·/]+")
_SPLIT_PHRASE = re.compile(r"[\s,，。；：、（）()【】\[\]<>《》!?:：\"'`*+]+")
_KEEP_RE = re.compile(r"[一-鿿A-Za-z0-9]")
_ASCII_RUN = re.compile(r"^[A-Za-z][A-Za-z0-9\.\-&]{1,14}")

# 通用后缀：去掉后更接近真实查询词
_GENERIC_SUFFIXES = ("解决方案", "方案", "系统", "系列", "产品", "服务", "中心")
# 型号特征（如 G33604 / GBL-6197D / 9166），型号不是好的 GEO 关键词，排在后面或过滤
_MODEL_RE = re.compile(r"[A-Za-z]+\d{2,}|\d{3,}")


def _strip_suffix(word: str) -> str:
    for suffix in _GENERIC_SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix) + 1:
            return word[:-len(suffix)]
    return word


def _clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _valid(word: str) -> bool:
    word = _clean(word)
    if not (2 <= len(word) <= 16):
        return False
    if not _KEEP_RE.search(word):
        return False
    if word.isdigit():
        return False
    low = word.lower()
    if low in NOISE_EXACT:
        return False
    # 栏目词过滤（资质类保留）
    if any(m in word for m in NOISE_MARKERS) and not any(t in word for t in TRUST_MARKERS):
        return False
    # 重复词/拼接噪声 如 "娱乐 娱乐 +"
    parts = _SPLIT_PHRASE.split(word)
    if len(parts) >= 2 and len(set(parts)) < len(parts):
        return False
    if low.isascii() and low.isalpha() and len(low) <= 2:
        return False
    return True


def _fetch(url: str, timeout: int = 12) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(3_000_000)
        final = r.geturl()
        charset = r.headers.get_content_charset() or "utf-8"
        try:
            return raw.decode(charset, errors="ignore"), final
        except LookupError:
            return raw.decode("utf-8", errors="ignore"), final


def _headings(doc: HtmlElement, tag: str, limit: int = 25) -> list[str]:
    out = []
    for el in doc.xpath(f".//{tag}"):
        txt = _clean(el.text_content())
        if 2 <= len(txt) <= 40:
            out.append(txt)
        if len(out) >= limit:
            break
    return out


def _meta_desc(doc: HtmlElement) -> str:
    for m in doc.xpath(".//meta"):
        key = (m.get("name") or m.get("property") or "").lower()
        if key in ("description", "og:description", "keywords"):
            val = _clean(m.get("content"))
            if val:
                return val
    return ""


def _links(doc: HtmlElement, base: str, host: str) -> list[dict]:
    seen, out = set(), []
    for a in doc.xpath("//a[@href]"):
        text = _clean(a.text_content())
        href = (a.get("href") or "").strip()
        if not text or not href or href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        abs_url = urljoin(base, href).split("#")[0]
        if urlparse(abs_url).netloc != host:
            continue
        if len(text) > 20 or (text, abs_url) in seen:
            continue
        seen.add((text, abs_url))
        out.append({"text": text, "url": abs_url})
    return out


def _link_kind(text: str, url: str) -> str:
    path = urlparse(url).path.lower()
    # 顺序重要：/img/list-xx 既是 list 也可能是场景页，优先判场景
    if any(k in path for k in ("/img/", "img/list", "/case", "project", "/scene")):
        return "scenario"
    if any(k in path for k in ("product", "chanpin", "/cp/")):
        return "product"
    if any(k in path for k in ("solution", "solve", "application", "fangan")):
        return "solution"
    if any(k in path for k in ("about", "profile", "company", "jianjie", "gywm", "corp")):
        return "about"
    if any(k in path for k in ("honor", "cert", "/ce/", "patent", "zizhi", "qualification")):
        return "trust"
    if any(k in path for k in ("news", "article", "info")):
        return "news"
    if any(k in text for k in ("产品中心", "产品与应用", "精选产品")):
        return "product_section"
    if any(k in text for k in TRUST_MARKERS):
        return "trust"
    if any(k in text for k in SCENARIO_MARKERS):
        return "scenario"
    return "other"


def _industry_terms(*texts: str) -> list[str]:
    found: list[str] = []
    for text in texts:
        if not text:
            continue
        for core in INDUSTRY_CORES:
            if core in text:
                term = core
                for mod in INDUSTRY_MODIFIERS:
                    if mod + core in text:
                        term = mod + core
                        break
                if term not in found:
                    found.append(term)
    # 更具体的词优先（长度降序）
    found.sort(key=len, reverse=True)
    return found


def _brands(title: str) -> list[str]:
    """品牌名：仅取自站点标题（跨页标题过于嘈杂）。"""
    out: list[str] = []
    segs = []
    for seg in _SPLIT_TITLE.split(title):
        seg = _clean(seg)
        seg = re.sub(r"(官方网站|官网|首页|主页|网站)$", "", seg).strip()
        if seg and seg.lower() not in NOISE_EXACT:
            segs.append(seg)

    for seg in segs:
        if not _valid(seg):
            continue
        if seg not in out:
            out.append(seg)
        # 去掉结尾的行业词，得到更干净的品牌词（GIBO洁博利智能卫浴 -> GIBO洁博利）
        for core in INDUSTRY_CORES:
            if seg.endswith(core) and len(seg) > len(core) + 1:
                stripped = seg[:-len(core)]
                for mod in INDUSTRY_MODIFIERS:
                    if stripped.endswith(mod) and len(stripped) > len(mod) + 1:
                        stripped = stripped[:-len(mod)]
                        break
                if _valid(stripped) and stripped not in out:
                    out.append(stripped)
                break
        # 附带纯英文品牌词（GIBO洁博利 -> GIBO）
        m = _ASCII_RUN.match(seg)
        if m and m.group(0) != seg and len(m.group(0)) >= 2 and m.group(0) not in out:
            out.append(m.group(0))
    return out[:4]


def _pages_to_visit(links: list[dict], limit: int = 5) -> list[dict]:
    """挑选子页：产品中心 1 + 产品页 2 + 解决方案 1 + 关于 1。"""
    buckets: dict[str, list[dict]] = {k: [] for k in
                                      ("product_section", "product", "solution", "about")}
    for link in links:
        kind = _link_kind(link["text"], link["url"])
        if kind in buckets:
            buckets[kind].append(link)
    quota = {"product_section": 1, "product": 2, "solution": 1, "about": 1}
    picked, seen_paths = [], {"/", "", "/index.html"}
    for kind in ("product_section", "product", "solution", "about"):
        taken = 0
        for link in buckets[kind]:
            path = urlparse(link["url"]).path
            if path in seen_paths:
                continue
            seen_paths.add(path)
            picked.append(link)
            taken += 1
            if taken >= quota[kind] or len(picked) >= limit:
                break
        if len(picked) >= limit:
            break
    return picked[:limit]


def profile_site(url: str, hint: str = "", max_pages: int = 5,
                 include_corpus: bool = False) -> dict:
    """抓取官网并生成企业画像 + 分类关键词。

    include_corpus=True 时额外返回站点语料（首页+关键子页正文），
    供监测阶段在整站范围内检索关键词，而不是只看首页。
    """
    html, final_url = _fetch(url)
    host = urlparse(final_url).netloc
    doc = LH.fromstring(html)

    title = _clean(doc.findtext(".//title"))
    meta = _meta_desc(doc)
    home_h1 = _headings(doc, "h1", 6)
    home_h2 = _headings(doc, "h2", 20)
    links = _links(doc, final_url, host)

    pages_analyzed = [final_url]
    products: list[str] = []
    scenarios: list[str] = []
    trust: list[str] = []
    sub_headings: list[str] = []
    sub_titles: list[str] = []
    home_texts = {link["text"] for link in links}   # 首页全局导航，用于剔除子页里的全站菜单
    corpus_parts = [_clean(doc.text_content())[:20000]]   # 站点语料：首页 + 关键子页正文

    # 首页导航分类候选（顺序靠前 = 优先级更高：更通用、更稳定）
    for link in links:
        text = link["text"]
        if not _valid(text):
            continue
        kind = _link_kind(text, link["url"])
        if kind == "product":
            products.append(text)
        elif kind == "scenario":
            scenarios.append(text)
        elif kind == "trust" or any(t in text for t in TRUST_MARKERS):
            trust.append(text)

    for h in home_h2:
        if any(t in h for t in TRUST_MARKERS) and _valid(h):
            trust.append(h)
        elif any(m in h for m in SCENARIO_MARKERS) and _valid(h):
            scenarios.append(h)

    for link in _pages_to_visit(links, limit=max_pages - 1):
        try:
            sub_html, sub_url = _fetch(link["url"], timeout=10)
            sub_doc = LH.fromstring(sub_html)
        except Exception:
            continue
        pages_analyzed.append(sub_url)
        kind = _link_kind(link["text"], link["url"])
        sub_titles.append(_clean(sub_doc.findtext(".//title")))
        corpus_parts.append(_clean(sub_doc.text_content())[:20000])

        for tag in ("h1", "h2", "h3"):
            sub_headings.extend(_headings(sub_doc, tag, 20))

        # 子页"二级导航"= 产品体系 / 行业应用场景（剔除全站菜单后剩下的才是新增信息）
        for sl in _links(sub_doc, sub_url, host):
            text = sl["text"]
            if not _valid(text) or text in home_texts:
                continue
            k = _link_kind(text, sl["url"])
            if k == "trust" or any(t in text for t in TRUST_MARKERS):
                trust.append(text)
            elif k == "scenario" or any(m in text for m in SCENARIO_MARKERS):
                scenarios.append(text)
            elif k == "product" or kind in ("product_section", "product"):
                products.append(text)

    # 子页小标题补充
    for h in sub_headings:
        if any(t in h for t in TRUST_MARKERS) and _valid(h):
            trust.append(h)
        elif any(m in h for m in SCENARIO_MARKERS) and _valid(h):
            scenarios.append(h)

    # 行业方向：只从高信号文本里识别，避免正文误伤
    industries = _industry_terms(title, meta, " ".join(home_h1), " ".join(home_h2),
                                 " ".join(sub_titles), " ".join(sub_headings))
    if hint:
        hint = _clean(hint)
        if hint and hint not in industries:
            industries.insert(0, hint)

    brands = _brands(title)

    def dedupe(items: list[str], limit: int, drop_brand_dup: bool = True,
               drop_model: bool = False) -> list[str]:
        out, seen = [], set()
        for item in items:
            item = _strip_suffix(_clean(item))
            key = item.lower()
            if key in seen or not _valid(item):
                continue
            if drop_model and _MODEL_RE.search(item):
                continue
            # 产品/场景词里不该出现品牌名本身（行业词例外，如"建材"属于"北新建材"）
            if drop_brand_dup and any(item == b or (item in b and len(item) < len(b))
                                     or (b in item and len(item) <= len(b) + 6)
                                     for b in brands):
                continue
            if any(item in existing for existing in out):
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= limit:
                break
        return out

    # 产品词：通用词优先、型号补充（排到后面）
    products = dedupe(products, 12)
    products = sorted(products, key=lambda w: (bool(_MODEL_RE.search(w)), len(w)))[:8]
    # 场景词：剔除型号（那是产品而非场景）
    scenarios = dedupe(scenarios, 5, drop_model=True)
    trust = dedupe(trust, 3)
    industries = dedupe(industries, 2, drop_brand_dup=False)

    # ------------------------------------------------------------------
    keywords: list[dict] = []
    used: set[str] = set()

    def push(word: str, category: str, score: int):
        word = _clean(word)
        if not word or word.lower() in used or not _valid(word):
            return
        used.add(word.lower())
        keywords.append({"keyword": word, "category": category, "score": score})

    for i, b in enumerate(brands):
        push(b, "品牌", 100 - i)
    for i, p in enumerate(products):
        push(p, "产品", 80 - i)
    for i, ind in enumerate(industries):
        push(ind, "行业", 70 - i)
    for i, s in enumerate(scenarios):
        push(s, "场景", 60 - i)
    for i, t in enumerate(trust):
        push(t, "资质", 50 - i)

    if not keywords:
        for seg in _SPLIT_PHRASE.split(title):
            push(seg, "品牌", 60)

    brand_main = brands[0] if brands else host
    industry_main = industries[0] if industries else "未识别"
    summary_parts = [f"{brand_main} 的行业方向为「{industry_main}」"]
    if products:
        summary_parts.append(f"主营产品/业务：{'、'.join(products[:5])}")
    if scenarios:
        summary_parts.append(f"应用场景：{'、'.join(scenarios[:4])}")
    if trust:
        summary_parts.append(f"资质背书：{'、'.join(trust[:3])}")
    summary = "；".join(summary_parts) + "。"

    counts: dict[str, int] = {}
    for k in keywords:
        counts[k["category"]] = counts.get(k["category"], 0) + 1

    result = {
        "url": final_url,
        "brand": brand_main,
        "industry": industry_main,
        "products": products,
        "scenarios": scenarios,
        "trust": trust,
        "summary": summary,
        "keywords": keywords,
        "category_counts": counts,
        "pages_analyzed": pages_analyzed,
    }
    if include_corpus:
        # 站点语料：供监测阶段在"首页 + 关键子页"范围内检索关键词
        result["corpus"] = "\n".join(p for p in corpus_parts if p)
    return result
