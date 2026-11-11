"""解析层：用 BeautifulSoup(lxml) 把 HTML 解析为结构化页面特征。

输出 PageFeatures 供 pandas 分析引擎计算 SHEEP 五维指标。
"""
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# 常见社媒/内容平台（用于 E2 生态集成度判断）
SOCIAL_PLATFORMS = {
    "weixin.qq.com": "微信公众号",
    "mp.weixin.qq.com": "微信公众号",
    "weibo.com": "微博",
    "zhihu.com": "知乎",
    "xiaohongshu.com": "小红书",
    "douyin.com": "抖音",
    "bilibili.com": "B站",
    "linkedin.com": "LinkedIn",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "facebook.com": "Facebook",
    "youtube.com": "YouTube",
    "github.com": "GitHub",
}

AUTHORITY_KEYWORDS = ["认证", "ISO", "专利", "资质", "奖项", "证书", "荣誉", "备案", "权威"]
ENDORSEMENT_KEYWORDS = ["专家", "研究院", "实验室", "学术", "论文", "博士", "教授", "标准制定"]
SOCIAL_PROOF_KEYWORDS = ["客户案例", "成功案例", "评价", "口碑", "用户反馈", "合作伙伴", "案例展示", "testimonials"]
CTA_KEYWORDS = ["咨询", "联系", "立即", "免费", "获取", "预约", "试用", "下单", "购买", "热线", "400", "留言"]

# --- EEAT 信号词表（Google 质量评估框架四维）---------------------------------
# Experience 经验：是否展示"亲手做过"的第一手证据
EXPERIENCE_KEYWORDS = [
    "案例", "客户案例", "成功案例", "工程案例", "应用案例", "项目案例",
    "项目经验", "实例", "落地", "实拍", "现场", "已服务", "服务客户",
    "客户见证", "用户评价", "使用反馈", "项目展示", "业绩",
]
# Expertise 专业性：内容是否体现专业深度与可核验的技术细节
EXPERTISE_KEYWORDS = [
    "技术", "工艺", "研发", "参数", "规格", "型号", "尺寸", "指标",
    "技术方案", "解决方案", "白皮书", "检测报告", "测试报告", "施工方案",
    "工程师", "原理", "流程", "标准规范",
]
# Trustworthiness 可信度：是否有可追责的服务承诺与合规披露
TRUST_KEYWORDS = [
    "质保", "保修", "售后", "退换", "承诺", "保障", "正品", "授权",
    "服务承诺", "三包", "免费维修", "终身维护", "隐私政策", "用户协议",
]
# Authority 权威性中的"外部认可"部分（媒体/行业曝光）
MEDIA_KEYWORDS = ["媒体报道", "新闻报道", "新闻中心", "行业报道", "媒体关注", "权威媒体", "央视"]

# 年限表述：用于判断"做了多久"（Experience 的强信号）
_YEAR_PATTERNS = [
    re.compile(r"(专注|深耕|从事|成立|创立|服务|经验|积累)[^。；，\n]{0,6}?(\d{2,3})\s*年"),
    re.compile(r"(\d{2,3})\s*年(专业|行业|制造|研发|经验|深耕|专注)"),
    re.compile(r"(since|est\.?)\s*(19|20)\d{2}", re.I),
    re.compile(r"(19|20)\d{2}\s*年成立"),
]

# 品牌别名表：解决"苹果手机 vs Apple/iPhone"这类跨语言/品牌词匹配
BRAND_ALIASES = {
    "苹果": ["apple", "iphone", "ipad", "mac", "macbook", "airpods", "ios"],
    "iphone": ["苹果"],
    "apple": ["苹果"],
    "华为": ["huawei", "harmonyos", "鸿蒙", "mate", "pura"],
    "小米": ["xiaomi", "redmi", "米家", "su7"],
    "腾讯": ["tencent", "qq", "微信", "weixin", "wechat"],
    "阿里": ["alibaba", "aliyun", "淘宝", "天猫", "taobao"],
    "京东": ["jd.com", "jingdong"],
    "百度": ["baidu", "bilibili"],  # bilibili 单列
    "微软": ["microsoft", "windows", "azure", "office"],
    "谷歌": ["google", "android", "youtube"],
    "亚马逊": ["amazon", "aws"],
    "字节": ["bytedance", "抖音", "douyin", "tiktok"],
    "美团": ["meituan", "dianping", "大众点评"],
    "新东方": ["xdf", "koolearn"],
    "网易": ["netease", "163.com"],
}


@dataclass
class PageFeatures:
    url: str = ""
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    lang: str = ""
    is_https: bool = False
    has_favicon: bool = False
    h1_list: list = field(default_factory=list)
    h2_count: int = 0
    h3_count: int = 0
    heading_text: list = field(default_factory=list)
    text: str = ""
    text_length: int = 0
    paragraph_count: int = 0
    list_item_count: int = 0
    table_count: int = 0
    image_count: int = 0
    image_with_alt: int = 0
    internal_links: int = 0
    external_links: int = 0
    jsonld_count: int = 0
    jsonld_types: list = field(default_factory=list)
    og_tags: int = 0
    social_platforms: list = field(default_factory=list)
    has_contact_info: bool = False
    has_copyright: bool = False
    has_privacy_policy: bool = False
    authority_hits: list = field(default_factory=list)
    endorsement_hits: list = field(default_factory=list)
    social_proof_hits: list = field(default_factory=list)
    cta_hits: list = field(default_factory=list)
    # 客观权威信号（不依赖特定字眼）
    official_in_title: bool = False   # 标题含"官方/官网"
    has_icp: bool = False             # 页面含 ICP 备案号

    # --- EEAT 信号 ---------------------------------------------------------
    experience_hits: list = field(default_factory=list)   # 案例/实例/项目经验
    expertise_hits: list = field(default_factory=list)    # 技术/参数/方案专业词
    trust_hits: list = field(default_factory=list)        # 质保/售后/承诺
    media_hits: list = field(default_factory=list)        # 媒体报道
    years_mentioned: list = field(default_factory=list)   # 年限表述原文
    case_link_count: int = 0                              # 指向案例/项目的链接数
    author_signal: bool = False                           # 作者/署名信息


def parse_page(html: str, url: str) -> PageFeatures:
    """主入口：HTML -> PageFeatures。"""
    soup = BeautifulSoup(html, "lxml")
    f = PageFeatures(url=url)
    host = urlparse(url).netloc

    f.title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    if not f.title and soup.title:
        f.title = soup.title.get_text(strip=True)

    # <head> 元信息
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    f.meta_description = (meta_desc.get("content", "") if meta_desc else "").strip()
    canonical_tag = soup.find("link", attrs={"rel": re.compile(r"canonical", re.I)})
    f.canonical = canonical_tag.get("href", "") if canonical_tag else ""
    html_tag = soup.find("html")
    f.lang = (html_tag.get("lang", "") if html_tag else "") or ""
    f.is_https = url.startswith("https://")
    f.has_favicon = soup.find("link", attrs={"rel": re.compile(r"(shortcut )?icon", re.I)}) is not None
    f.og_tags = len(soup.find_all("meta", attrs={"property": re.compile(r"^og:", re.I)}))

    # 标题层级
    f.h1_list = [h.get_text(strip=True) for h in soup.find_all("h1") if h.get_text(strip=True)]
    f.h2_count = len(soup.find_all("h2"))
    f.h3_count = len(soup.find_all("h3"))
    f.heading_text = [
        h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3", "h4"])
        if h.get_text(strip=True)
    ]

    # 正文
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    f.text = soup.get_text(" ", strip=True)
    f.text_length = len(f.text)
    f.paragraph_count = len([p for p in soup.find_all("p") if p.get_text(strip=True)])
    f.list_item_count = len(soup.find_all("li"))
    f.table_count = len(soup.find_all("table"))

    # 图片
    imgs = soup.find_all("img")
    f.image_count = len(imgs)
    f.image_with_alt = len([i for i in imgs if (i.get("alt") or "").strip()])

    # 链接（内链/外链 + 社媒平台）
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        link_host = urlparse(href).netloc
        if not link_host:
            continue
        if link_host.endswith(host) or host.endswith(link_host):
            f.internal_links += 1
        else:
            f.external_links += 1
            for domain, name in SOCIAL_PLATFORMS.items():
                if domain in link_host and name not in f.social_platforms:
                    f.social_platforms.append(name)

    # JSON-LD 结构化数据
    for s_tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        f.jsonld_count += 1
        for m in re.finditer(r'"@type"\s*:\s*"([^"]+)"', s_tag.string or ""):
            if m.group(1) not in f.jsonld_types:
                f.jsonld_types.append(m.group(1))

    # 可信度信号
    lower_text = f.text.lower()
    f.official_in_title = any(w in f.title for w in ("官方", "官网")) or "official" in f.title.lower()
    # ICP 备案：标准格式「京ICP备12345678号」，也兼容「ICP备」+数字的简写
    f.has_icp = bool(re.search(
        r"(?:京|沪|粤|浙|苏|鲁|川|渝|津|冀|晋|蒙|辽|吉|黑|皖|闽|赣|豫|鄂|湘|桂|琼|"
        r"贵|云|藏|陕|甘|青|宁|新)?\s*ICP\s*[备证]\s*(?:第)?\s*\d{4,}", f.text, re.I)
    ) or ("icp" in lower_text and "备" in f.text)
    # 联系方式：手机号需前后为非数字，避免把订单号/时间戳误判为电话
    f.has_contact_info = bool(re.search(
        r"(400[-\s]?\d{3}[-\s]?\d{3,4})|(?<!\d)1[3-9]\d{9}(?!\d)|(mailto:)|(@\w+\.(?:com|cn|net))",
        html, re.I)
    ) or "联系我们" in f.text or "联系电话" in f.text or "contact" in lower_text
    f.has_copyright = "©" in f.text or "版权" in f.text or "copyright" in lower_text
    f.has_privacy_policy = "隐私" in f.text or "privacy" in lower_text
    for kw in AUTHORITY_KEYWORDS:
        if kw.lower() in lower_text:
            f.authority_hits.append(kw)
    for kw in ENDORSEMENT_KEYWORDS:
        if kw.lower() in lower_text:
            f.endorsement_hits.append(kw)
    for kw in SOCIAL_PROOF_KEYWORDS:
        if kw.lower() in lower_text:
            f.social_proof_hits.append(kw)
    for kw in CTA_KEYWORDS:
        if kw.lower() in lower_text or any(kw.lower() in h.lower() for h in f.heading_text):
            f.cta_hits.append(kw)

    # --- EEAT 信号抽取 -----------------------------------------------------
    for kw in EXPERIENCE_KEYWORDS:
        if kw.lower() in lower_text or any(kw in h for h in f.heading_text):
            f.experience_hits.append(kw)
    for kw in EXPERTISE_KEYWORDS:
        if kw.lower() in lower_text or any(kw in h for h in f.heading_text):
            f.expertise_hits.append(kw)
    for kw in TRUST_KEYWORDS:
        if kw.lower() in lower_text:
            f.trust_hits.append(kw)
    for kw in MEDIA_KEYWORDS:
        if kw.lower() in lower_text or any(kw in h for h in f.heading_text):
            f.media_hits.append(kw)

    # 年限表述："专注20年" / "since 1997" / "1997年成立"
    for pat in _YEAR_PATTERNS:
        for m in pat.finditer(f.text):
            snippet = m.group(0).strip()
            if snippet not in f.years_mentioned:
                f.years_mentioned.append(snippet)
        if len(f.years_mentioned) >= 3:
            break

    # 指向案例/项目/解决方案的链接数（Experience 的结构性证据）
    for a in soup.find_all("a", href=True):
        anchor = a.get_text(strip=True) + " " + a.get("href", "")
        if any(w in anchor for w in ("case", "案例", "项目", "project", "客户", "solution", "方案")):
            f.case_link_count += 1

    # 作者署名（Expertise/Trust 的辅助信号）
    f.author_signal = bool(
        soup.find(attrs={"itemprop": re.compile("author", re.I)})
        or soup.find(attrs={"rel": re.compile("author", re.I)})
        or re.search(r"(责任编辑|作者|撰稿|来源[:：])", f.text)
    )
    return f


def _keyword_variants(keyword: str) -> list:
    """生成关键词的匹配变体：原词 + 分词 + 品牌别名。

    例："苹果手机" -> ["苹果手机", "苹果", "手机", "apple", "iphone", ...]
    匹配时任一变体命中该位点即算命中——模拟生成式引擎的语义联想能力。
    """
    kw = keyword.strip()
    variants = {kw.lower()}
    # 中文分词：按 2-3 字滑窗切常见词（轻量启发式，够用于模拟）
    if re.search(r"[\u4e00-\u9fff]", kw):
        if len(kw) >= 4:
            variants.add(kw[:2].lower())
            variants.add(kw[2:].lower())
            if len(kw) >= 6:
                variants.add(kw[:3].lower())
                variants.add(kw[3:].lower())
        elif len(kw) == 3:
            variants.add(kw[:2].lower())
            variants.add(kw[2:].lower())
    # 品牌别名（跨语言）
    for brand, aliases in BRAND_ALIASES.items():
        if brand.lower() in variants or any(v == brand.lower() for v in variants):
            variants.update(a.lower() for a in aliases)
        for v in list(variants):
            if v and v in brand.lower() or brand.lower() in (v or ""):
                variants.update(a.lower() for a in aliases)
    return [v for v in variants if v]


def _any_hit(variants: list, haystack: str) -> bool:
    low = (haystack or "").lower()
    return any(v in low for v in variants)


def keyword_hits(f: PageFeatures, keyword: str, site_text: str = "") -> dict:
    """关键词（含变体）在页面各信号位点的命中情况（供多引擎模拟使用）。

    site_text：站点其它关键页（产品/解决方案/关于）的正文语料。
    正文命中在"本页 + 站点关键页"范围内检索——GEO 关心的是 AI 能否在
    整个官网里找到该关键词，而不是只盯首页。
    """
    variants = _keyword_variants(keyword)
    body_scope = f.text if not site_text else f"{f.text}\n{site_text}"
    positions = {
        "title": _any_hit(variants, f.title),
        "meta_description": _any_hit(variants, f.meta_description),
        "h1": any(_any_hit(variants, h) for h in f.h1_list),
        "headings": any(_any_hit(variants, h) for h in f.heading_text),
        "body": _any_hit(variants, body_scope),
        "url": _any_hit(variants, f.url),
    }
    positions["hit_count"] = sum(1 for k in ("title", "meta_description", "h1", "headings", "body", "url")
                                 if positions[k])
    positions["variants"] = variants
    return positions
