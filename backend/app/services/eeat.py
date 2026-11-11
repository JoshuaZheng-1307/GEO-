"""EEAT 评估：Google 质量评估框架的四维量化。

  EXP  Experience        经验       —— 是否展示"亲手做过"的第一手证据
  EPT  Expertise         专业性     —— 内容是否体现专业深度与可核验的技术细节
  AUT  Authoritativeness 权威性     —— 是否获得行业/媒体的外部认可
  TRU  Trustworthiness   可信度     —— 是否可被追责与核验

设计原则：**每一分都可追溯**。每个维度由若干"检查项"构成，每项有权重，
命中即得分、未命中即记为"缺失项"。前端据此渲染"证据 vs 缺失"，
用户看到的不是黑箱分数，而是一份可执行清单。
"""
from __future__ import annotations

import numpy as np

from app.config import settings
from app.services.parser import PageFeatures, _YEAR_PATTERNS

EEAT_META = {
    "EXP": {
        "name": "经验", "name_en": "Experience", "short": "E",
        "desc": "展示第一手实操经验：真实案例、项目落地、年限积累",
        "color": "#5b8cff",
    },
    "EPT": {
        "name": "专业性", "name_en": "Expertise", "short": "E",
        "desc": "内容具备专业深度：技术参数、规格数据、解决方案",
        "color": "#9d5bff",
    },
    "AUT": {
        "name": "权威性", "name_en": "Authoritativeness", "short": "A",
        "desc": "获得外部认可：资质认证、专利标准、媒体报道",
        "color": "#f0a46a",
    },
    "TRU": {
        "name": "可信度", "name_en": "Trustworthiness", "short": "T",
        "desc": "可被追责与核验：备案、隐私政策、联系方式、服务承诺",
        "color": "#5ee6a8",
    },
}

GRADE_TABLE = [(90, "S级"), (80, "A级"), (70, "B级"), (60, "C级"), (0, "D级")]


def _grade(score: float) -> str:
    for threshold, g in GRADE_TABLE:
        if score >= threshold:
            return g
    return "D级"


def _level(score: float) -> str:
    return "strong" if score >= 75 else ("medium" if score >= 50 else "weak")


def _has_any(text: str, words) -> list:
    """返回在 text 中命中的词。

    按词表顺序（由长到短）匹配，已被更长命中词包含的短词不再重复计入
    ——避免同时输出『客户案例』和『案例』这种冗余。
    """
    hits = []
    for w in words:
        if w in text and not any(w in h for h in hits):
            hits.append(w)
    return hits


def _join(words, limit=4) -> str:
    shown = words[:limit]
    tail = f" 等 {len(words)} 处" if len(words) > limit else ""
    return "、".join(shown) + tail


# ---------------------------------------------------------------------------
# 检查项构造器
# ---------------------------------------------------------------------------
def _check(label: str, weight: float, hit: bool, hit_detail: str, miss_detail: str) -> dict:
    return {
        "label": label,
        "weight": round(weight, 1),
        "hit": bool(hit),
        "detail": hit_detail if hit else miss_detail,
    }


# ---------------------------------------------------------------------------
# 四个维度的检查项
# ---------------------------------------------------------------------------
def _checks_experience(f: PageFeatures, text: str, years: list) -> list:
    """EXP 经验：有没有"我做过"的证据。

    text 为整站语料（首页 + 关键子页），因为案例/年限这类内容
    通常挂在「关于我们」「客户案例」子页，只扫首页会严重低估。
    """
    # 案例/实证词在整站范围内重新检索（f.experience_hits 仅来自首页）
    case_words = _has_any(text, ["客户案例", "成功案例", "工程案例", "应用案例",
                                 "项目案例", "案例展示", "案例"])
    proof_words = _has_any(text, ["实拍", "现场实景", "实例", "项目落地", "落地项目",
                                  "项目经验", "项目展示"])
    scale_words = _has_any(text, ["已服务", "服务客户", "服务过", "覆盖", "累计", "万家", "余家"])
    review_words = _has_any(text, ["用户评价", "客户见证", "使用反馈", "口碑", "客户评价"])

    return [
        _check("客户案例", 25, bool(case_words),
               f"命中：{_join(case_words)}",
               "页面未出现案例类内容"),
        _check("案例入口", 12, f.case_link_count >= 3,
               f"检测到 {f.case_link_count} 个案例/项目入口链接",
               "缺少指向案例或项目页的导航入口"),
        _check("年限积累", 18, bool(years),
               f"命中：{_join(years, 2)}",
               "未找到年限表述（如『专注 20 年』）"),
        _check("服务规模", 12, bool(scale_words),
               f"命中：{_join(scale_words)}",
               "未量化服务规模（客户数/项目数）"),
        _check("用户见证", 15, bool(review_words),
               f"命中：{_join(review_words)}",
               "缺少用户评价或客户见证"),
        _check("项目实证", 10, bool(proof_words),
               f"命中：{_join(proof_words)}",
               "缺少实拍/现场/落地类实证内容"),
        _check("图片实证", 8, f.image_count >= 8 and f.image_with_alt >= 5,
               f"{f.image_count} 张图片（{f.image_with_alt} 张带 alt）",
               f"图片偏少或缺少 alt 描述（{f.image_count} 张 / {f.image_with_alt} 带 alt）"),
    ]


def _checks_expertise(f: PageFeatures, text: str) -> list:
    """EPT 专业性：内容是不是"懂行的人写的"。"""
    tech_words = _has_any(text, ["技术工艺", "核心技术", "工艺", "技术研发", "研发", "技术", "原理", "工程师"])
    spec_words = _has_any(text, ["技术参数", "产品参数", "参数", "规格型号", "规格", "型号", "尺寸", "指标"])
    doc_words = _has_any(text, ["白皮书", "检测报告", "测试报告", "技术方案", "施工方案", "解决方案"])
    # 内容深度按整站语料衡量（子页的技术长文也算数）
    scope_len = max(f.text_length, len(text))
    depth_ratio = min(scope_len / settings.CONTENT_TARGET_CHARS, 1.0)

    return [
        _check("技术表述", 20, len(tech_words) >= 2,
               f"命中：{_join(tech_words)}",
               "技术/工艺类表述不足，内容偏营销化"),
        _check("参数规格", 18, len(spec_words) >= 2,
               f"命中：{_join(spec_words)}",
               "缺少可核验的参数、规格、型号数据"),
        _check("结构化数据表", 15, f.table_count >= 1,
               f"检测到 {f.table_count} 个数据表",
               "未用表格呈现规格/参数对比"),
        _check("内容深度", 20, depth_ratio >= 0.6 and f.paragraph_count >= 6,
               f"正文 {scope_len} 字 / {f.paragraph_count} 段",
               f"正文偏薄（{scope_len} 字 / {f.paragraph_count} 段），建议扩充至 1500 字以上"),
        _check("层级划分", 12, f.h2_count >= 3,
               f"{f.h2_count} 个 H2 / {f.h3_count} 个 H3",
               f"标题层级过浅（H2 仅 {f.h2_count} 个），不利于 AI 分段理解"),
        _check("专业文档", 10, bool(doc_words),
               f"命中：{_join(doc_words)}",
               "缺少白皮书/检测报告等专业文档"),
        _check("作者署名", 5, f.author_signal,
               "检测到作者或来源署名",
               "未标注作者/来源，专业性难以溯源"),
    ]


def _checks_authority(f: PageFeatures, text: str) -> list:
    """AUT 权威性：别人是不是认可你。

    资质/专利/标准这类背书几乎都在「关于我们」「资质荣誉」子页，
    因此必须在整站语料里检索，否则会把头部品牌误判为无权威。
    """
    cert_words = _has_any(text, ["ISO", "体系认证", "资质认证", "认证", "资质", "证书"])
    award_words = _has_any(text, ["获奖", "行业奖项", "奖项", "荣誉", "权威"])
    std_words = _has_any(text, ["国家标准", "标准起草", "标准制定", "研究院",
                                "专家", "实验室", "学术", "论文", "博士", "教授"])
    has_patent = "专利" in text
    has_org_jsonld = any(t in ("Organization", "Corporation", "LocalBusiness", "Brand", "Company")
                         for t in f.jsonld_types)

    return [
        _check("资质认证", 20, len(cert_words) >= 2,
               f"命中：{_join(cert_words)}",
               "未展示 ISO / 行业认证等资质"),
        _check("专利", 12, has_patent,
               "内容提及专利",
               "全站未提及专利信息"),
        _check("标准与专家背书", 12, bool(std_words),
               f"命中：{_join(std_words)}",
               "无标准起草/专家/研究院类背书"),
        _check("媒体报道", 10, bool(f.media_hits),
               f"命中：{_join(f.media_hits)}",
               "缺少媒体报道或新闻中心入口"),
        _check("官方标识", 10, f.official_in_title,
               f"标题含官方标识：{f.title[:24]}",
               "标题未含『官方/官网』标识"),
        _check("ICP 备案", 10, f.has_icp,
               "页面含 ICP 备案号",
               "未找到 ICP 备案号"),
        _check("结构化实体声明", 10, has_org_jsonld,
               f"JSON-LD 类型：{_join(f.jsonld_types, 3)}" if f.jsonld_types else "含结构化数据",
               "缺少 Organization/Brand 结构化数据"),
        _check("外部引用", 8, f.external_links >= 3,
               f"{f.external_links} 个外链",
               f"外链偏少（{f.external_links} 个），缺少第三方引用"),
        _check("荣誉奖项", 8, bool(award_words),
               f"命中：{_join(award_words)}",
               "未展示行业奖项或荣誉"),
    ]


def _checks_trust(f: PageFeatures, text: str) -> list:
    """TRU 可信度：出事了能不能找得到人。"""
    promise_words = _has_any(text, ["质量保证", "质保", "保修", "售后服务", "售后", "退换货",
                                    "退换", "服务承诺", "承诺", "保障", "正品", "授权",
                                    "三包", "免费维修", "终身维护"])
    identity_complete = bool(f.title) and bool(f.meta_description)

    return [
        _check("HTTPS", 16, f.is_https,
               "站点启用 HTTPS",
               "未启用 HTTPS，传输可被篡改"),
        _check("服务承诺", 18, bool(promise_words),
               f"命中：{_join(promise_words)}",
               "缺少质保/售后/退换等服务承诺"),
        _check("联系方式", 14, f.has_contact_info,
               "检测到电话 / 邮箱 / 联系入口",
               "未找到明确的联系方式"),
        _check("备案信息", 12, f.has_icp,
               "含 ICP 备案号",
               "未展示 ICP 备案，主体身份不可核验"),
        _check("隐私政策", 12, f.has_privacy_policy,
               "含隐私政策入口",
               "缺少隐私政策，合规性存疑"),
        _check("页面身份完整", 12, identity_complete and bool(f.canonical),
               f"标题 + 描述 + canonical 齐全",
               "缺少 meta 描述或 canonical，身份信息不完整"),
        _check("作者/来源署名", 8, f.author_signal,
               "检测到作者或来源署名",
               "内容无署名，可信度难以判断"),
        _check("版权声明", 8, f.has_copyright,
               "含版权声明",
               "未找到版权声明"),
    ]


ADVICE = {
    "EXP": "新增『客户案例』栏目：每个案例写清场景、方案、结果，配现场实拍图；在首页露出『专注 XX 年 / 已服务 XX 家客户』等可验证的年限与规模数据。",
    "EPT": "把营销文案替换为技术内容：补齐参数表（型号/规格/尺寸/指标）、发布白皮书与检测报告、用 H2/H3 划分技术模块，并为内容标注作者与来源。",
    "AUT": "在页面集中展示资质证书与专利号；补充『国家标准起草单位』『XX 研究院合作』类背书；建立新闻中心沉淀媒体报道；接入 Organization JSON-LD 声明主体实体。",
    "TRU": "补齐 ICP 备案号、隐私政策与明确的联系方式（400 电话/邮箱）；增加质保与售后承诺；为文章添加作者署名，并在页脚声明版权。",
}


def compute_eeat(f: PageFeatures, site_text: str = "") -> dict:
    """主入口：页面特征 -> EEAT 四维量化结果（含证据与缺失清单）。

    site_text：站点其它关键页（关于我们/产品/方案/案例）的正文语料。
    EEAT 关心的是"整个官网能不能证明自己"，而不是首页这一屏——
    只扫首页会把资质、专利、年限这些本就挂在子页的强信号全部漏掉。
    """
    # 整站语料：首页正文 + 关键子页正文
    scope_text = f.text if not site_text else f"{f.text}\n{site_text}"

    # 年限表述在整站范围内重新抽取
    years = list(f.years_mentioned)
    for pat in _YEAR_PATTERNS:
        for m in pat.finditer(scope_text):
            snip = m.group(0).strip()
            if snip not in years:
                years.append(snip)
        if len(years) >= 3:
            break

    builders = {
        "EXP": lambda: _checks_experience(f, scope_text, years),
        "EPT": lambda: _checks_expertise(f, scope_text),
        "AUT": lambda: _checks_authority(f, scope_text),
        "TRU": lambda: _checks_trust(f, scope_text),
    }

    dims = {}
    for code, builder in builders.items():
        checks = builder()
        total_w = sum(c["weight"] for c in checks)
        got_w = sum(c["weight"] for c in checks if c["hit"])
        score = round(float(np.clip(got_w / total_w * 100, 0, 100)), 1) if total_w else 0.0

        dims[code] = {
            "code": code,
            "name": EEAT_META[code]["name"],
            "name_en": EEAT_META[code]["name_en"],
            "short": EEAT_META[code]["short"],
            "desc": EEAT_META[code]["desc"],
            "color": EEAT_META[code]["color"],
            "score": score,
            "grade": _grade(score),
            "level": _level(score),
            "earned": round(got_w, 1),
            "total": round(total_w, 1),
            "evidence": [c for c in checks if c["hit"]],
            "missing": [c for c in checks if not c["hit"]],
            "advice": ADVICE[code],
        }

    overall = round(float(np.mean([d["score"] for d in dims.values()])), 1)
    sorted_dims = sorted(dims.items(), key=lambda kv: kv[1]["score"])

    # 全站缺失项汇总：按"未得分权重"排序，即性价比最高的整改项
    all_missing = []
    for code, d in dims.items():
        for m in d["missing"]:
            all_missing.append({"code": code, "name": d["name"],
                                "label": m["label"], "weight": m["weight"],
                                "detail": m["detail"]})
    all_missing.sort(key=lambda x: -x["weight"])

    return {
        "overall": overall,
        "grade": _grade(overall),
        "level": _level(overall),
        "scope": "site" if site_text else "page",
        "scope_chars": len(scope_text),
        "dimensions": dims,
        "strongest": {"code": sorted_dims[-1][0], "name": sorted_dims[-1][1]["name"],
                      "score": sorted_dims[-1][1]["score"]},
        "weakest": {"code": sorted_dims[0][0], "name": sorted_dims[0][1]["name"],
                    "score": sorted_dims[0][1]["score"]},
        "gap_actions": all_missing[:6],
        "summary": _summary(overall, sorted_dims),
    }


def _summary(overall: float, sorted_dims) -> str:
    weakest_name, weakest_score = sorted_dims[0][1]["name"], sorted_dims[0][1]["score"]
    strongest_name, strongest_score = sorted_dims[-1][1]["name"], sorted_dims[-1][1]["score"]
    if overall >= 80:
        tone = "EEAT 信号整体扎实，AI 引擎有充分依据将你列为可信来源。"
    elif overall >= 65:
        tone = "EEAT 基本达标，但仍有明显缺口会被竞拉开差距。"
    elif overall >= 50:
        tone = "EEAT 信号偏弱——页面更像宣传册，缺少 AI 可引用的实证与背书。"
    else:
        tone = "EEAT 信号严重不足：AI 引擎几乎找不到可以信任你的理由。"
    return (f"{tone}最强维度为{strongest_name}（{strongest_score}分），"
            f"最弱为{weakest_name}（{weakest_score}分）——优先补齐后者收益最大。")
