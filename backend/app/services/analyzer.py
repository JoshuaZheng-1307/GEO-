"""指标分析引擎：用 pandas 计算 SHEEP 五维评分 + GEM 综合评分。

评分体系对齐 SheepGEO 模板：
  S  语义覆盖   Semantic Coverage       —— AI 识别率 / 内容质量 / 语义完整性
  H  人类可信度 Human Credibility      —— 权威信号 / 专业背书 / 社会证明
  E1 证据结构化 Evidence Structuring   —— 内容完整度 / 语义丰富度 / 结构质量
  E2 生态集成   Ecosystem Integration  —— 推荐覆盖率 / 行业集成度 / 平台覆盖
  P  性能监测   Performance Monitoring —— Core Web Vitals / AI 采纳效率 / 转化潜力
"""
import hashlib

import numpy as np
import pandas as pd

from app.config import settings
from app.services.eeat import compute_eeat
from app.services.parser import PageFeatures, keyword_hits

# ---------------------------------------------------------------------------
# 维度与子指标权重
# ---------------------------------------------------------------------------
DIMENSION_WEIGHTS = {
    "S": 0.20,   # 语义覆盖
    "H": 0.15,   # 人类可信度
    "E1": 0.20,  # 证据结构化
    "E2": 0.15,  # 生态集成
    "P": 0.30,   # 性能监测
}

SUBMETRIC_WEIGHTS = {
    "S": {"ai_recognition_rate": 0.4, "content_quality": 0.3, "semantic_completeness": 0.3},
    "H": {"authority_signals": 0.4, "endorsement": 0.3, "social_proof": 0.3},
    "E1": {"content_completeness": 0.35, "semantic_richness": 0.3, "structure_quality": 0.35},
    "E2": {"recommendation_coverage": 0.4, "industry_integration": 0.3, "platform_coverage": 0.3},
    "P": {"vitals_score": 0.5, "ai_adoption_efficiency": 0.25, "conversion_potential": 0.25},
}

DIMENSION_META = {
    "S": {"name": "语义覆盖", "name_en": "Semantic Coverage", "desc": "AI 模型识别和理解能力"},
    "H": {"name": "人类可信度", "name_en": "Human Credibility", "desc": "权威性和信任建设"},
    "E1": {"name": "证据结构化", "name_en": "Evidence Structuring", "desc": "内容组织和结构质量"},
    "E2": {"name": "生态集成", "name_en": "Ecosystem Integration", "desc": "AI 推荐系统覆盖度"},
    "P": {"name": "性能监测", "name_en": "Performance Monitoring", "desc": "转化能力和效率"},
}

DIMENSION_CODE_MAP = {"S": "GV", "H": "CR", "E1": "SH", "E2": "EI", "P": "AE"}

GRADE_TABLE = [(90, "S级"), (80, "A级"), (70, "B级"), (60, "C级"), (0, "D级")]


def _grade(score: float) -> str:
    for threshold, grade in GRADE_TABLE:
        if score >= threshold:
            return grade
    return "D级"


def _clamp(value: float, low=0.0, high=100.0) -> float:
    return float(np.clip(value, low, high))


# ---------------------------------------------------------------------------
# 多生成式引擎模拟
# ---------------------------------------------------------------------------
def simulate_engines(f: PageFeatures, keywords: list, engines: list,
                     site_text: str = "") -> tuple[dict, float]:
    """模拟各生成式引擎对关键词的识别情况。

    规则（内容对齐、可解释）：
      - 关键词在页面强信号位（title/h1）命中 → 所有引擎识别
      - 在正文/标题层级命中 → 绝大多数引擎识别
      - 仅弱信号位（meta/URL）命中 → 宽松引擎识别、严格引擎存疑（形成梯度）
      - 完全未出现 → 所有引擎不识别（这是内容缺口，不是模型问题）
    返回 (keyword_matrix, ai_recognition_rate)。
    """
    engine_strictness = {}
    for eng in engines:
        seed = int(hashlib.md5(eng.encode()).hexdigest()[:8], 16)
        engine_strictness[eng] = 0.35 + (seed % 100) / 250.0  # 0.35 ~ 0.75

    POSITION_LABELS = [
        ("title", "标题"), ("h1", "主标题"), ("headings", "小标题"),
        ("body", "正文"), ("meta_description", "描述"), ("url", "URL"),
    ]
    rows = []
    diagnostics = []
    total, hits = 0, 0
    for kw in keywords:
        pos = keyword_hits(f, kw, site_text)
        # 信号强度：强信号位权重大；正文/小标题命中已足以被普遍识别
        strength = (pos["title"] * 3 + pos["h1"] * 3 +
                    pos["headings"] * 2 + pos["body"] * 2 +
                    pos["meta_description"] * 1.5 + pos["url"] * 1.5)
        for eng in engines:
            strict = engine_strictness[eng]
            # 阈值 0.77 ~ 1.65：强/正文信号(≥2.0)全员识别；
            # 仅弱信号(1.5)时严格引擎不识别；未出现(0)全员不识别。
            recognized = strength >= strict * 2.2
            rows.append({"keyword": kw, "engine": eng, "recognized": bool(recognized),
                         "strength": strength, "positions": pos})
            total += 1
            hits += int(recognized)

        # 每个关键词的命中诊断（与引擎无关，纯内容事实）
        hit_labels = [label for key, label in POSITION_LABELS if pos.get(key)]
        scope_desc = "官网首页与已分析的关键页面" if site_text else "该页面"
        if strength >= 2.0:
            level, advice = "strong", f"该关键词在{scope_desc}中命中，AI 引擎可将其与你的品牌关联。"
        elif strength > 0:
            level, advice = "weak", "该关键词仅出现在弱信号位（meta/URL）。建议将其自然融入标题或正文段落。"
        else:
            level, advice = ("none",
                             f"该关键词未出现在{scope_desc}中——AI 引擎无法把它与你的品牌关联。"
                             "建议：在正文/H2 中补充相关内容，或把它从监测词里去掉。")
        diagnostics.append({"keyword": kw, "level": level, "strength": round(strength, 1),
                            "hit_positions": hit_labels, "advice": advice})

    rate = round(hits / total * 100, 1) if total else 0.0
    matrix = {
        "engines": engines,
        "keywords": keywords,
        "rows": rows,
        "recognition_rate": rate,
        "diagnostics": diagnostics,
    }
    return matrix, rate


# ---------------------------------------------------------------------------
# 各维度子指标计算
# ---------------------------------------------------------------------------
def _score_semantic(f: PageFeatures, recognition_rate: float) -> dict:
    """S 语义覆盖。"""
    # 内容质量：文本量 + 段落 + 多媒体
    length_score = min(f.text_length / settings.CONTENT_TARGET_CHARS, 1.0) * 50
    para_score = min(f.paragraph_count / 10, 1.0) * 25
    media_score = min((f.image_count + f.table_count * 2) / 10, 1.0) * 25
    content_quality = _clamp(length_score + para_score + media_score)

    # 语义完整性：title / description / og / lang / favicon
    sema = sum([
        bool(f.title) * 25, bool(f.meta_description) * 30, min(f.og_tags, 4) * 5,
        bool(f.lang) * 10, f.has_favicon * 10, bool(f.canonical) * 10,
    ])
    semantic_completeness = _clamp(sema)
    return {"ai_recognition_rate": recognition_rate, "content_quality": round(content_quality, 1),
            "semantic_completeness": round(semantic_completeness, 1)}


def _score_credibility(f: PageFeatures) -> dict:
    """H 人类可信度。

    以客观站点信号为主（HTTPS/备案/官方标识/结构化数据/外链），
    字眼命中（认证/ISO 等）仅作辅助——避免 Apple 这类不写"认证"二字
    的权威站点被误判为低可信。

    合法企业基线：HTTPS + ICP 备案 + 版权声明的站点是可验证的实体，
    直接给各子指标一个底分（首页通常不含认证/隐私政策/社媒链接，
    不加基线会把头部品牌误判为 D 级）。
    """
    legit = bool(f.is_https and (f.has_icp or f.has_copyright))
    base = 12 if legit else 0

    authority = sum([
        f.is_https * 12,
        f.official_in_title * 18,                      # 标题"官方/官网"
        f.has_icp * 18,                                # ICP 备案号
        f.has_copyright * 10,
        f.has_privacy_policy * 12,
        min(len(f.authority_hits) * 6, 18),            # 认证类字眼（辅助）
        min(f.external_links, 10) * 1,                 # 对外引用
    ]) + base
    endorsement = sum([
        min(f.jsonld_count, 3) * 12,                   # Organization/Brand 结构化数据
        min(len(f.endorsement_hits) * 12, 36),
        min(f.external_links, 6) * 4,
        f.has_contact_info * 12,
        bool(f.lang) * 6,
    ]) + base
    social = sum([
        min(len(f.social_platforms) * 12, 36),
        min(len(f.social_proof_hits) * 12, 36),
        f.has_contact_info * 14,
        f.has_copyright * 8,
    ]) + base
    return {"authority_signals": round(_clamp(authority), 1),
            "endorsement": round(_clamp(endorsement), 1),
            "social_proof": round(_clamp(social), 1)}


def _score_evidence(f: PageFeatures) -> dict:
    """E1 证据结构化。"""
    completeness = min(f.text_length / settings.CONTENT_TARGET_CHARS, 1.0) * 60 + \
        min(f.paragraph_count / 8, 1.0) * 20 + min(f.table_count, 3) * 5 + min(f.list_item_count / 10, 1.0) * 10
    richness = min(len(f.heading_text) / 12, 1.0) * 40 + \
        min(f.image_with_alt / 5, 1.0) * 20 + min(f.jsonld_count * 15, 30) + \
        (min(f.external_links, 5) * 2)
    structure = 0.0
    structure += 30 if len(f.h1_list) == 1 else (10 if len(f.h1_list) == 0 else 0)  # H1 唯一性
    structure += min(f.h2_count, 6) / 6 * 30       # H2 模块划分
    structure += min(f.h3_count, 8) / 8 * 15        # H3 层级
    structure += min(f.jsonld_count * 10, 15)       # 结构化数据
    structure += 10 if f.canonical else 0
    return {"content_completeness": round(_clamp(completeness), 1),
            "semantic_richness": round(_clamp(richness), 1),
            "structure_quality": round(_clamp(structure), 1)}


def _score_ecosystem(f: PageFeatures, recognition_rate: float, engines: list) -> dict:
    """E2 生态集成。

    加基准分：任何正规运营的站点都不会是 0 分孤岛——
    有备案/结构化数据/联系方式的站点被视为"具备被收录的基础"。
    """
    recommendation = 20 + recognition_rate * 0.5 + min(f.jsonld_count * 10, 30)
    industry = 25 + min(f.external_links, 10) * 3 + \
        (10 if f.has_privacy_policy else 0) + \
        min(len(f.social_proof_hits) * 10, 35)
    platform = 25 + min(len(f.social_platforms) * 18, 75)
    return {"recommendation_coverage": round(_clamp(recommendation), 1),
            "industry_integration": round(_clamp(industry), 1),
            "platform_coverage": round(_clamp(platform), 1)}


def _vitals_grade_score(ttfb, fcp, lcp) -> float:
    """Core Web Vitals -> 0-100（对应模板 P100/A+ 逻辑）。"""
    def one_metric(v, good, poor, weight):
        if v is None:
            return weight * 0.5  # 未检测按一半分
        if v <= good:
            return weight
        if v >= poor:
            return 0.0
        return weight * (poor - v) / (poor - good)

    return _clamp(one_metric(ttfb, 200, 800, 30) + one_metric(fcp, 1800, 3000, 30) +
                  one_metric(lcp, 2500, 4000, 40))


def _score_performance(f: PageFeatures, vitals: float, content_quality: float,
                        structure_quality: float) -> dict:
    """P 性能监测。"""
    ai_adoption = content_quality * 0.4 + structure_quality * 0.4 + \
        min(f.jsonld_count * 5, 20)
    conversion = sum([
        min(len(f.cta_hits) * 8, 40), f.has_contact_info * 20,
        min(len(f.social_platforms) * 8, 20), min(f.table_count * 5, 20),
    ])
    return {"vitals_score": round(vitals, 1),
            "ai_adoption_efficiency": round(_clamp(ai_adoption), 1),
            "conversion_potential": round(_clamp(conversion), 1)}


# ---------------------------------------------------------------------------
# 报告生成
# ---------------------------------------------------------------------------
SUGGESTION_TEMPLATES = {
    "H": "补充权威认证（ISO、专利、行业奖项）并在页面展示证书；新增客户案例/评价页面，强化社会证明。",
    "E1": "确保每个页面唯一 H1；用 H2/H3 划分内容模块并以表格呈现规格数据；扩充正文至 1500-2000 字符。",
    "E2": "主动发布内容至微信公众号/知乎等平台并保证与官网信息一致；接入行业报告数据提升行业关联性。",
    "P": "优化 CTA 文案（如『立即咨询』→『免费获取方案』）；压缩资源体积，保持 Core Web Vitals 优秀。",
    "S": "针对低识别率关键词补充上下文语义（术语解释、案例数据），提升 AI 抓取效率。",
}


def _dynamic_suggestion(dim: str, f: PageFeatures, sub: dict, eeat: dict) -> str:
    """基于实际缺失信号拼装建议，而不是套用固定模板。

    同一个维度（如 S 语义覆盖）在不同站点上的短板完全不同：
    有的缺内容量，有的缺结构化数据。这里逐条检测具体缺口，
    只输出"这个站真正缺什么"，避免建议千篇一律。
    """
    gaps = []
    if dim == "S":
        if (sub["S"]["content_quality"] or 0) < 60:
            gaps.append(f"正文仅 {f.text_length} 字、{f.paragraph_count} 段，建议扩充到 1500 字以上并分段")
        if not f.meta_description:
            gaps.append("缺少 meta description，AI 无法快速摘要页面")
        if (sub["S"]["semantic_completeness"] or 0) < 60:
            gaps.append("补全 og 标签、lang、canonical 等语义标识")
        if eeat["dimensions"]["EPT"]["score"] < 60:
            gaps.append("补充术语解释与技术参数，强化专业性语义")
    elif dim == "H":
        if not f.has_icp:
            gaps.append("页面未展示 ICP 备案号")
        if not f.official_in_title:
            gaps.append("标题未含『官方/官网』标识")
        if not f.authority_hits:
            gaps.append("未展示任何资质认证或专利")
        if not f.has_privacy_policy:
            gaps.append("缺少隐私政策入口")
        if not f.social_proof_hits:
            gaps.append("无客户案例或用户评价类社会证明")
    elif dim == "E1":
        if len(f.h1_list) != 1:
            gaps.append(f"H1 数量为 {len(f.h1_list)}，应保持全站唯一")
        if f.h2_count < 3:
            gaps.append(f"H2 仅 {f.h2_count} 个，内容未做模块划分")
        if f.table_count == 0:
            gaps.append("未用表格呈现规格/参数数据")
        if f.jsonld_count == 0:
            gaps.append("无 JSON-LD 结构化数据")
        if f.text_length < settings.CONTENT_TARGET_CHARS:
            gaps.append(f"正文 {f.text_length} 字，低于 {settings.CONTENT_TARGET_CHARS} 字目标")
    elif dim == "E2":
        if not f.social_platforms:
            gaps.append("未接入微信公众号/知乎等外部内容平台")
        if f.external_links < 3:
            gaps.append(f"外链仅 {f.external_links} 个，缺少第三方引用")
        if not f.media_hits:
            gaps.append("无媒体报道或新闻中心，行业曝光不足")
    elif dim == "P":
        if not f.cta_hits:
            gaps.append("页面无明确 CTA（咨询/获取/预约）")
        if not f.has_contact_info:
            gaps.append("缺少电话/邮箱等联系方式")
        if (sub["P"]["vitals_score"] or 0) < 60:
            gaps.append("Core Web Vitals 未达标，优先压缩 JS/CSS 与图片体积")
    return "；".join(gaps[:3]) if gaps else SUGGESTION_TEMPLATES.get(dim, "")


def analyze(f: PageFeatures, crawl_perf: dict, keywords: list, engines: list,
            site_text: str = "", scope_pages: int = 1) -> dict:
    """主入口：页面特征 + 性能数据 -> 完整量化报告（对齐 SheepGEO 模板结构）。

    site_text / scope_pages：关键词识别在"首页 + 站点关键页"范围内进行，
    使识别率反映整站内容覆盖度，而不是只看首页。
    """
    keyword_matrix, recognition_rate = simulate_engines(f, keywords, engines, site_text)
    keyword_matrix["scope_pages"] = scope_pages

    # EEAT 四维（Google 质量评估框架）：与 SHEEP 五维并列，单独成块。
    # 传入整站语料——资质/专利/年限通常在子页，只扫首页会严重低估。
    eeat = compute_eeat(f, site_text=site_text)

    sub = {
        "S": _score_semantic(f, recognition_rate),
        "H": _score_credibility(f),
        "E1": _score_evidence(f),
        "E2": _score_ecosystem(f, recognition_rate, engines),
    }
    vitals = _vitals_grade_score(
        crawl_perf.get("ttfb_ms"), crawl_perf.get("fcp_ms"), crawl_perf.get("lcp_ms"))
    sub["P"] = _score_performance(f, vitals,
                                   sub["S"]["content_quality"], sub["E1"]["structure_quality"])

    # pandas 计算五维加权得分与综合分
    records = []
    for dim, metrics in sub.items():
        for metric, value in metrics.items():
            records.append({"dimension": dim, "metric": metric,
                            "value": value, "weight": SUBMETRIC_WEIGHTS[dim][metric],
                            "dim_weight": DIMENSION_WEIGHTS[dim]})
    df = pd.DataFrame(records)

    dimension_scores = {}
    for dim in DIMENSION_WEIGHTS:
        sub_df = df[df["dimension"] == dim]
        dim_score = float((sub_df["value"] * sub_df["weight"]).sum() /
                          sub_df["weight"].sum())
        dimension_scores[dim] = round(dim_score, 1)

    overall = round(sum(dimension_scores[d] * w for d, w in DIMENSION_WEIGHTS.items()) /
                    sum(DIMENSION_WEIGHTS.values()), 1)

    # 与行业基准对比
    benchmark = settings.INDUSTRY_BENCHMARK
    comparisons = {
        dim: {"score": score, "benchmark": benchmark, "diff": round(score - benchmark, 1),
              "verdict": "优秀" if score - benchmark >= 15 else ("良好" if score >= benchmark else "落后")}
        for dim, score in dimension_scores.items()
    }

    # 关键发现与改进优先级
    sorted_dims = sorted(dimension_scores.items(), key=lambda kv: kv[1])
    findings = {
        "strongest": {"dimension": DIMENSION_META[sorted_dims[-1][0]]["name"],
                      "code": sorted_dims[-1][0], "score": sorted_dims[-1][1]},
        "weakest": {"dimension": DIMENSION_META[sorted_dims[0][0]]["name"],
                    "code": sorted_dims[0][0], "score": sorted_dims[0][1]},
        "priority": [
            {"order": i + 1, "dimension": DIMENSION_META[dim]["name"], "code": dim, "score": score,
             "suggestion": _dynamic_suggestion(dim, f, sub, eeat) or SUGGESTION_TEMPLATES.get(dim, "")}
            for i, (dim, score) in enumerate(sorted_dims[:3])
        ],
        "benchmark": benchmark,
        "comparisons": comparisons,
        "short_term_uplift": round(sum(max(0, 70 - s) for s in dimension_scores.values()) * 0.15, 0),
        "mid_term_uplift": round(sum(max(0, 70 - s) for s in dimension_scores.values()) * 0.3, 0),
    }

    core_metrics = {
        "ai_recognition_rate": round(recognition_rate, 1),
        "authority_score": sub["H"]["authority_signals"],
        "content_completeness": sub["E1"]["content_completeness"],
        "ecosystem_coverage": sub["E2"]["recommendation_coverage"],
        "conversion_potential": sub["P"]["conversion_potential"],
    }

    # EEAT 维度建议：同样用实际缺口驱动
    for code, dim in eeat["dimensions"].items():
        dim["next_actions"] = [m["detail"] for m in dim["missing"][:3]]

    dimensions_detail = {
        code: {
            "score": dimension_scores[code],
            "grade": _grade(dimension_scores[code]),
            "name": meta["name"], "name_en": meta["name_en"], "desc": meta["desc"],
            "short_code": DIMENSION_CODE_MAP[code],
            "metrics": sub[code],
        }
        for code, meta in DIMENSION_META.items()
    }

    performance = {
        "vitals": {
            "ttfb_ms": crawl_perf.get("ttfb_ms"),
            "fcp_ms": crawl_perf.get("fcp_ms"),
            "lcp_ms": crawl_perf.get("lcp_ms"),
        },
        "resources": crawl_perf.get("resources", {}),
        "score": round(vitals, 1),
    }

    signature = hashlib.md5(
        f"{f.url}|{overall}|{sorted(dimension_scores.items())}".encode()).hexdigest()[:16]

    return {
        "url": f.url,
        "overall_score": overall,
        "grade": _grade(overall).replace("级", ""),
        "grade_label": _grade(overall),
        "dimensions": dimensions_detail,
        "core_metrics": core_metrics,
        "eeat": eeat,
        "findings": findings,
        "performance": performance,
        "keyword_matrix": keyword_matrix,
        "suggestions": {
            code: _dynamic_suggestion(code, f, sub, eeat) or SUGGESTION_TEMPLATES.get(code, "")
            for code in DIMENSION_META
        },
        "snapshot": {
            "title": f.title, "text_length": f.text_length, "h1_list": f.h1_list[:5],
            "h2_count": f.h2_count, "h3_count": f.h3_count, "jsonld_types": f.jsonld_types,
            "social_platforms": f.social_platforms, "external_links": f.external_links,
            "internal_links": f.internal_links, "image_count": f.image_count,
            "authority_hits": f.authority_hits, "cta_hits": f.cta_hits[:10],
        },
        "signature": signature,
    }
