import base64
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader

from runner.validator import MAX_INFERRED_RATIO, check_identity_behavior_decoupling

# 导出件（HTML/Markdown）里的 logo，读一次缓存住——每次渲染都重新读文件+base64
# 编码是纯浪费，这张图片在进程生命周期里不会变。用 data URI 而不是外链路径，
# 是因为导出件要脱离本站单独存在（下载后发给同事、离线打开），链接到本站资源
# 在那种场景下就是死链。
_LOGO_DATA_URI: Optional[str] = None


def _logo_data_uri() -> str:
    global _LOGO_DATA_URI
    if _LOGO_DATA_URI is None:
        logo_path = os.path.join(os.path.dirname(__file__), "..", "templates", "assets", "logo.png")
        try:
            with open(logo_path, "rb") as f:
                _LOGO_DATA_URI = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
        except OSError:
            # 图片没打包进来也不该让整份报告渲染失败——退回空串，模板按空值不出图。
            _LOGO_DATA_URI = ""
    return _LOGO_DATA_URI

try:
    from .similarity import get_issue_similarity
except ImportError:
    from runner.similarity import get_issue_similarity


# severity 合并用的强弱序：多个人格对同一议题报了不同 severity 时取最高。
# 与 cross_exam.SEVERITY_MAP 同一套口径，这里独立定义避免 aggregator 依赖 cross_exam。
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _severity_rank(severity: str) -> int:
    return SEVERITY_RANK.get(severity, SEVERITY_RANK["medium"])


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_BUILD_VERSION_CACHE = []  # 用列表当"算过没有"的标记，None 也是合法结果，不能用 None 判空


def resolve_build_version() -> Optional[str]:
    """报告里的 build_version 必须能追溯到真实的包版本，取不到就返回 None。

    以前这里写死 "0.1.0"，而 pyproject 早已是 0.3.0：用户按版本号复现结论
    会追到完全不存在的那一版。宁可这一行不显示，也不能显示一个可被证伪的值。

    两条取值路径：装成包时走 importlib.metadata；仓库内直接跑（开发/CI/服务端
    以源码方式引入）时读 pyproject.toml。两条都取不到就是 None——不猜、不兜底。
    """
    if _BUILD_VERSION_CACHE:
        return _BUILD_VERSION_CACHE[0]

    version = None
    try:
        from importlib.metadata import PackageNotFoundError, version as _pkg_version

        try:
            version = _pkg_version("audiencelens")
        except PackageNotFoundError:
            version = None
    except ImportError:  # Python 3.7 及更早没有 importlib.metadata
        version = None

    if not version:
        pyproject = os.path.join(_repo_root(), "pyproject.toml")
        try:
            with open(pyproject, "r", encoding="utf-8") as f:
                text = f.read()
            # 只认 [project] 段里的 version：依赖串里也有 version= 字样
            project_section = text.split("[project]", 1)[-1].split("\n[", 1)[0]
            match = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', project_section, re.M)
            if match:
                version = match.group(1)
        except OSError:
            version = None

    _BUILD_VERSION_CACHE.append(version)
    return version


def load_aggregation_rules(rules_path: str) -> dict:
    if not os.path.isfile(rules_path):
        raise FileNotFoundError(f"Rules file not found: {rules_path}")
    with open(rules_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_consensus(
    persona_outputs: List[dict], threshold: float = 0.7, similarity=None
) -> dict:
    """真正的议题级共识：多位人格各自独立提到的同一个问题才算"共识点"。

    旧实现算的根本不是"点"：它把每个人格的 primary_stance 做频次统计，占比过线的
    **立场名**（"加愿望单"这种词）塞进 agreed_points，其余塞进 questioned_points。
    两个后果都是直接骗人：
      1. threshold=0.7 > 0.5，一份分布里最多只有一个立场能过线，agreed_points 长度
         恒 ≤1；首屏"共识点 / 存疑点 = 1 / 3"被读成"找到 1 个共识、3 个疑点"，
         真相只是"有 1 种立场超过七成、另有 3 种少数派立场"。
      2. questioned_points 语义是反的——"少数人持有某立场"不等于"大家共同质疑它"。

    现在改成对 key_issues 做相似度聚类（复用 priority_fixes / compute_disagreements
    的同一个比较器，三处口径必须一致，否则同一批议题在不同 section 被切成不同组）：
      - agreed_points：被 >= threshold 比例的人格**各自**提到的议题标题，且至少 2 人
        （1 个人不构成共识，哪怕面板只有 1 人）。这是可核对的事实陈述。
      - questioned_points：其余议题，即只有少数人格提出的关切。语义如实：不是
        "大家共同质疑"，而是"个别人格单独提出"，模板/前端文案已同步改口径。
    算不出共识就返回空数组——空是诚实的，编一个立场词填进去不是。

    shared_concerns 是给渲染层用的明细（谁提的、几人提的、合并了哪些措辞），
    好让读者能自己核对"这几条真是同一件事吗"，而不是只看到一个光秃秃的数字。
    """
    if not persona_outputs:
        return {
            "agreed_points": [],
            "questioned_points": [],
            "shared_concerns": [],
            "stance_distribution": {},
            "persona_count": 0,
            "threshold": threshold,
            "min_personas_for_agreement": 0,
        }

    if similarity is None:
        similarity = get_issue_similarity()

    total = len(persona_outputs)
    distribution = dict(Counter(p.get("primary_stance", "观望") for p in persona_outputs))

    clusters = []  # [{"title", "personas": [pid], "variants": [title]}]
    for p in persona_outputs:
        persona_id = p.get("persona_id", "")
        for issue in p.get("key_issues", []):
            if not isinstance(issue, dict):
                continue
            title = issue.get("title", "")
            if not title:
                continue
            target = None
            for cluster in clusters:
                if similarity.is_same_issue(title, cluster["title"]):
                    target = cluster
                    break
            if target is None:
                clusters.append({"title": title, "personas": [persona_id], "variants": [title]})
                continue
            # 同一个人格把同一件事说两遍不算两个人认同，按人格去重
            if persona_id not in target["personas"]:
                target["personas"].append(persona_id)
            if title not in target["variants"]:
                target["variants"].append(title)

    # 面板只有 1 人时 ceil(1*0.7)=1，会把独角戏判成"共识"，所以另加 2 人下限
    min_personas = max(2, math.ceil(threshold * total))

    agreed_points = []
    questioned_points = []
    shared_concerns = []
    for cluster in clusters:
        count = len(cluster["personas"])
        is_agreed = count >= min_personas
        (agreed_points if is_agreed else questioned_points).append(cluster["title"])
        shared_concerns.append({
            "issue": cluster["title"],
            "personas": cluster["personas"],
            "persona_count": count,
            "is_consensus": is_agreed,
            "title_variants": cluster["variants"],
        })

    shared_concerns.sort(key=lambda c: c["persona_count"], reverse=True)

    return {
        "agreed_points": agreed_points,
        "questioned_points": questioned_points,
        "shared_concerns": shared_concerns,
        "stance_distribution": distribution,
        "persona_count": total,
        "threshold": threshold,
        "min_personas_for_agreement": min_personas,
    }


def compute_disagreements(persona_outputs: List[dict], similarity=None) -> List[dict]:
    if similarity is None:
        similarity = get_issue_similarity()

    stance_groups = {}
    for p in persona_outputs:
        stance = p.get("primary_stance", "观望")
        if stance not in stance_groups:
            stance_groups[stance] = []
        stance_groups[stance].append(p)

    unique_stances = list(stance_groups.keys())
    if len(unique_stances) <= 1:
        return []

    # 使用相似度合并议题，避免同一问题换措辞被分到不同组
    issue_clusters = []  # [{"title": str, "entries": [(pid, stance, issue)]}]
    for p in persona_outputs:
        for issue in p.get("key_issues", []):
            if not isinstance(issue, dict):
                continue
            title = issue.get("title", "")
            if not title:
                continue
            merged = False
            for cluster in issue_clusters:
                if similarity.is_same_issue(title, cluster["title"]):
                    cluster["entries"].append((p.get("persona_id",""), p.get("primary_stance","观望"), issue))
                    merged = True
                    break
            if not merged:
                issue_clusters.append({
                    "title": title,
                    "entries": [(p.get("persona_id",""), p.get("primary_stance","观望"), issue)],
                })

    issue_map = {c["title"]: c["entries"] for c in issue_clusters}

    disagreements = []

    controversial_issues = []
    for title, entries in issue_map.items():
        stances_for_issue = set(e[1] for e in entries)
        if len(stances_for_issue) > 1:
            controversial_issues.append(title)

    if controversial_issues:
        for title in controversial_issues:
            entries = issue_map[title]
            persona_stances = []
            for pid, stance, issue in entries:
                evidence_text = f"{issue.get('title', '')}: {issue.get('why_it_matters', '')}"
                persona_stances.append({
                    "persona_id": pid,
                    "stance": stance,
                    "evidence": evidence_text,
                })
            # 不写 resolution_suggestion：这里没有任何调解逻辑可跑。以前填的是
            # f"Further investigation needed on {title}"——把标题回填进一句英文套话，
            # 前端却以"建议："的口吻展示，读者会当成引擎算出来的调解方案。
            # 真正的仲裁结论在 cross_examination 里（跑了反驳才有），缺就该缺着。
            disagreements.append({
                "topic": title,
                "persona_stances": persona_stances,
                "dedup_method": similarity.method,
            })
    else:
        for i in range(len(unique_stances)):
            for j in range(i + 1, len(unique_stances)):
                stance_a = unique_stances[i]
                stance_b = unique_stances[j]
                persona_stances = []
                for p in stance_groups[stance_a]:
                    evidence_text = p.get("voice_sample", "")
                    persona_stances.append({
                        "persona_id": p.get("persona_id",""),
                        "stance": stance_a,
                        "evidence": evidence_text,
                    })
                for p in stance_groups[stance_b]:
                    evidence_text = p.get("voice_sample", "")
                    persona_stances.append({
                        "persona_id": p.get("persona_id",""),
                        "stance": stance_b,
                        "evidence": evidence_text,
                    })
                # 同上：原来的 "Mediate between A and B perspectives" 是套话不是建议
                disagreements.append({
                    "topic": f"{stance_a} vs {stance_b}",
                    "persona_stances": persona_stances,
                    "dedup_method": similarity.method,
                })

    return disagreements


def compute_priority_fixes(
    persona_outputs: List[dict], rules: dict, similarity=None
) -> List[dict]:
    """按"影响人数 × severity 加成"排优先级。

    去重口径必须和 compute_disagreements / extract_controversy_points 一致（同一套
    相似度聚类）：旧实现用 title 精确相等建 map，同一个问题换个措辞就裂成 N 条、
    每条 affected_count 都是 1，排序退化成只看 severity——"5 个人都说新手引导讲不清"
    这种最该先修的问题反而排不上去。

    severity 取参与人格里的最高值：旧实现记第一个报出该 title 的人格的值，
    A 说 low、B/C 说 critical 时会被永久记作 low，等于把最严重的判断吞掉。
    """
    if similarity is None:
        similarity = get_issue_similarity()

    severity_boost = rules.get("severity_boost", {})

    clusters = []  # [{"title", "severity", "why_it_matters", "suggested_fix", "affected_personas", "title_variants"}]
    for p in persona_outputs:
        persona_id = p.get("persona_id", "")
        for issue in p.get("key_issues", []):
            if not isinstance(issue, dict):
                continue
            title = issue.get("title", "")
            if not title:
                continue
            severity = issue.get("severity", "medium")

            target = None
            for cluster in clusters:
                if similarity.is_same_issue(title, cluster["title"]):
                    target = cluster
                    break

            if target is None:
                clusters.append({
                    "title": title,
                    "severity": severity,
                    "why_it_matters": issue.get("why_it_matters", ""),
                    "suggested_fix": issue.get("suggested_fix", ""),
                    "affected_personas": [persona_id],
                    "title_variants": [title],
                })
                continue

            target["affected_personas"].append(persona_id)
            if title not in target["title_variants"]:
                target["title_variants"].append(title)
            if _severity_rank(severity) > _severity_rank(target["severity"]):
                target["severity"] = severity
                # 描述跟着最严重的那份走，免得出现"critical 配一句无关痛痒的理由"
                if issue.get("why_it_matters"):
                    target["why_it_matters"] = issue["why_it_matters"]
                if issue.get("suggested_fix"):
                    target["suggested_fix"] = issue["suggested_fix"]

    results = []
    for cluster in clusters:
        boost = severity_boost.get(cluster["severity"], 1.0)
        weight = 1.0
        affected = list(dict.fromkeys(cluster["affected_personas"]))  # 去重且保序（确定性）
        score = boost * weight * len(affected)
        results.append({
            "priority": 0,
            "issue": cluster["title"],
            "severity": cluster["severity"],
            "why_it_matters": cluster["why_it_matters"],
            "affected_personas": affected,
            "suggested_fix": cluster["suggested_fix"],
            "score": score,
            # 声明去重精度 + 被合并掉的措辞，方便人工核对"这几条真是同一个问题吗"
            "dedup_method": similarity.method,
            "title_variants": cluster["title_variants"],
        })

    # 同分时让更严重的排前面（原来只按 score 排，同分顺序取决于出现次序）
    results.sort(key=lambda x: (x["score"], _severity_rank(x["severity"])), reverse=True)
    for i, item in enumerate(results):
        item["priority"] = i + 1

    return results


def _panel_audience_profiles(panel_personas: List[dict]) -> List[str]:
    """把人格档案里的**真实字段**拼成可用于筛真人受访者的特征串。

    只用 YAML 里确实写了的字段（年龄段 / 地区 / 游戏经验 / 平台 / 品类），
    一个字段都没有的人格直接跳过——宁可少一条，也不能补一个"泛用玩家"充数。
    去重且保序，保证同一份输入两次跑出同样的顺序（报告要可复现）。
    """
    profiles = []
    for persona in panel_personas:
        if not isinstance(persona, dict):
            continue
        gaming = persona.get("gaming_profile") or {}
        parts = []
        for value in (
            persona.get("age_range"),
            persona.get("region"),
            gaming.get("experience"),
        ):
            if value:
                parts.append(str(value))
        for key in ("platforms", "genres"):
            values = gaming.get(key)
            if isinstance(values, list) and values:
                parts.append("/".join(str(v) for v in values[:3]))
        if parts:
            profiles.append(" · ".join(parts))
    return list(dict.fromkeys(profiles))


def collect_caveats(persona_outputs: List[dict]) -> List[str]:
    """汇总各人格自己声明的限制条件。

    人格提示词（src/templates/persona-prompt.md:89）要求每个人格 meta.caveats 至少
    写一条，output-schema 也把它列为必填，但 aggregate_report 从来没收集过，于是
    导出 Markdown 的「Limitations & Caveats」永远是个空章节——最该出现的免责内容
    恰好一条都没有，读者会以为这份合成评审没有已知局限。
    去重且保序（可复现），空白项丢弃。
    """
    caveats = []
    for p in persona_outputs:
        meta = p.get("meta")
        if not isinstance(meta, dict):
            continue
        items = meta.get("caveats")
        if isinstance(items, str):
            items = [items]
        if not isinstance(items, list):
            continue
        for item in items:
            text = str(item).strip()
            if text and text not in caveats:
                caveats.append(text)
    return caveats


def aggregate_report(
    persona_outputs: List[dict],
    task_type: str,
    target: str,
    rules: dict,
    cross_exam_data: Optional[dict] = None,
    similarity=None,
    panel_personas: Optional[List[dict]] = None,
    persona_pack: Optional[dict] = None,
) -> dict:
    """panel_personas：本次实际参与的人格 YAML 定义（不是 LLM 输出）。
    next_human_test.recruit_types 需要人格的真实受众特征（年龄段/地区/平台/品类），
    只有 YAML 里有；persona_outputs 里没有这些字段。传 None 时该项如实留空。

    persona_pack：{"pack_id", "version"}，来自人格包 YAML 顶部的 panel_id/version。
    meta.persona_pack_version 必须来自它，不能写死。
    """
    # 一份报告只建一个相似度比较器：共识聚类、分歧聚类、修复项去重必须同口径
    # （否则同一批议题在三个 section 里被切成不同组），顺带避免重复加载 embedding 模型。
    if similarity is None:
        similarity = get_issue_similarity()
    consensus = compute_consensus(
        persona_outputs,
        threshold=rules.get("consensus_threshold", 0.7),
        similarity=similarity,
    )
    disagreements = compute_disagreements(persona_outputs, similarity=similarity)
    priority_fixes = compute_priority_fixes(persona_outputs, rules, similarity=similarity)

    stance_counter = Counter(p.get("primary_stance", "观望") for p in persona_outputs)
    primary_recommendation = stance_counter.most_common(1)[0][0] if stance_counter else ""

    # 风险等级数的是**去重后的**问题数（priority_fixes 的聚类结果），不是扁平 issue 列表。
    # 旧实现在 all_issues 上数 severity in (critical, high)、>=2 即判 critical：
    # 只要 2 位人格用不同措辞说同一个 high 问题，首屏就打"critical / 极高风险"，
    # 用户会以为有两个互相独立的严重问题。priority_fixes 早就按相似度合并过了，
    # 这里不跟着合并纯粹是漏改，两处口径不一致本身就是 bug。
    distinct_severities = [f["severity"] for f in priority_fixes]
    critical_high_count = sum(1 for s in distinct_severities if s in ("critical", "high"))
    if critical_high_count >= 2:
        release_risk = "critical"
    elif critical_high_count == 1:
        release_risk = "high"
    elif any(s == "medium" for s in distinct_severities):
        release_risk = "medium"
    else:
        release_risk = "low"

    # 缺 evidence_sufficiency 的人格排除出分母，而不是按 0 计入。
    # 旧实现拿 .get(..., 0)：8 位人格里 2 位漏了这个字段，均值就从 0.8 被拖到 0.6，
    # 执行摘要上的"证据充分度"从"充分"掉成"中等"——把"字段缺失"当成"证据很差"
    # 展示，用户完全分不出是哪一种。全都缺时返回 None，渲染层显示「—」，不猜。
    graded = [
        p["evidence_sufficiency"]
        for p in persona_outputs
        if isinstance(p.get("evidence_sufficiency"), (int, float))
    ]
    if graded:
        avg_evidence = sum(graded) / len(graded)
        if avg_evidence >= 0.8:
            evidence_quality = "strong"
        elif avg_evidence >= 0.6:
            evidence_quality = "medium"
        elif avg_evidence >= 0.4:
            evidence_quality = "weak"
        else:
            evidence_quality = "insufficient"
    else:
        evidence_quality = None

    information_gaps = []
    seen_gaps = set()
    for p in persona_outputs:
        for gap in p.get("missing_information", []):
            if gap not in seen_gaps:
                information_gaps.append(gap)
                seen_gaps.add(gap)

    # 三个"下一步"清单：只允许由真实产出推导，推不出就留空。
    # 旧实现无数据时硬回落成 "General playtest validation" / "General players" /
    # "Current build"——中文界面里冒出的英文常量，看起来像引擎给的建议，实际是
    # 写死的占位串，用户照着它准备下一轮真人测试等于什么都没拿到。
    suggested_tasks = [f"用真人验证争议点：{d['topic']}" for d in disagreements]
    next_materials = [f"补充材料：{gap}" for gap in information_gaps]

    # recruit_types 曾经直接抄本次跑过的 AI 人格名（"林岚"这种代号），而章节标题写的是
    # "建议招募的真人玩家类型"——把合成人格清单当真人受众画像给出去，和报告顶部的
    # 合成声明、ETHICS.md 直接冲突。现在改成从人格 YAML 的真实受众字段聚合出
    # 可用于筛人的特征串，并在 basis 里写明它的口径是"本次面板覆盖了哪些受众特征"，
    # 不是"引擎推断出你下一步该找谁"——后者引擎根本没算。
    recruit_types = _panel_audience_profiles(panel_personas or [])
    recruit_types_basis = (
        "本次面板覆盖的受众特征（取自人格档案的真实属性），可据此筛选同类真人受访者；"
        "这不是引擎推断出的招募建议"
        if recruit_types
        else ""
    )

    # ——— 证据构成（evidence_profile）———
    # 回答"这份报告的结论建立在什么之上"：多少条直接观察（direct）、多少条
    # 合理推断（inferred）、多少条信息缺口（gap）。口径与 validator 完全一致：
    # inferred_ratio = inferred / 全部证据条数，未标注等级的条目计入分母但
    # 不算 inferred。这是对**报告自身可信度**的度量，不是产品得分——
    # 合成面板给产品打一个综合分是假精确，给自己的证据构成记账是诚实的。
    _ep_personas = []
    _ep_d = _ep_i = _ep_g = _ep_total = 0
    for p in persona_outputs:
        _evs = [e for e in p.get("evidence", []) if isinstance(e, dict)]
        _d = sum(1 for e in _evs if e.get("inference_level") == "direct")
        _i = sum(1 for e in _evs if e.get("inference_level") == "inferred")
        _g = sum(1 for e in _evs if e.get("inference_level") == "gap")
        _ep_d += _d
        _ep_i += _i
        _ep_g += _g
        _ep_total += len(_evs)
        _ep_personas.append({
            "persona_id": p.get("persona_id", ""),
            "direct": _d,
            "inferred": _i,
            "gap": _g,
            "total": len(_evs),
            "inferred_ratio": round(_i / len(_evs), 3) if _evs else 0.0,
        })
    evidence_profile = {
        "total": _ep_total,
        "direct": _ep_d,
        "inferred": _ep_i,
        "gap": _ep_g,
        "inferred_ratio": round(_ep_i / _ep_total, 3) if _ep_total else 0.0,
        # 阈值随报告落库：历史报告要按**当时**的规则解读，规则改了不能追溯改写
        "threshold": MAX_INFERRED_RATIO,
        "per_persona": _ep_personas,
    }

    # ——— 维度均分（dimension_scores）———
    # 各人格 scores.base / scores.task_specific 的逐维度简单均分（1-5 制原样）。
    # 刻意不做加权综合分：权重没有任何校准依据，编一套就是 ARTi 式假精确。
    # min/max 一起给：均分 3.0 可能是"全员 3"也可能是"1 和 5 对半"，
    # 只报均值会把最有信息量的分歧抹掉。
    _dim_acc = {}
    for p in persona_outputs:
        _sc = p.get("scores", {}) or {}
        merged = {**(_sc.get("base") or {}), **(_sc.get("task_specific") or {})}
        for dim, val in merged.items():
            if isinstance(val, (int, float)):
                _dim_acc.setdefault(dim, []).append(float(val))
    dimension_scores = [
        {
            "dim": dim,
            "avg": round(sum(vals) / len(vals), 2),
            "min": min(vals),
            "max": max(vals),
            "count": len(vals),
        }
        for dim, vals in _dim_acc.items()
    ]

    persona_notes = []
    for p in persona_outputs:
        _top_entries = [e for e in p.get("evidence", []) if isinstance(e, dict)][:3]
        top_evidence = [e.get("content", "") for e in _top_entries]
        # 结构化版本：把 quote（材料原文）和 content（人格的解读）分开带进报告，
        # 渲染时先引用后评论。evidence_top3 保持字符串数组不变，老的读法不受影响。
        top_evidence_detail = []
        for e in _top_entries:
            _level = e.get("inference_level")
            _detail = {"content": e.get("content", ""),
                       "level": _level if _level in ("direct", "inferred", "gap") else "inferred"}
            if _level == "direct" and isinstance(e.get("quote"), str) and e["quote"].strip():
                _detail["quote"] = e["quote"]
            top_evidence_detail.append(_detail)
        top_issues = [
            i.get("title", "") for i in p.get("key_issues", []) if isinstance(i, dict)
        ]
        persona_notes.append({
            "persona_id": p.get("persona_id", ""),
            "persona_name": p.get("persona_name", p.get("persona_id", "")),
            "stance": p.get("primary_stance", "观望"),
            "evidence_top3": top_evidence,
            "evidence_top3_detail": top_evidence_detail,
            "top_issues": top_issues,
            "continue_triggers": p.get("continue_triggers", []),
            "quit_triggers": p.get("quit_triggers", []),
        })

    decoupling_issues = []
    for p in persona_outputs:
        result = check_identity_behavior_decoupling(p)
        if not result["decoupled"]:
            decoupling_issues.extend(result["violations"])

    ethics_score = 100
    if decoupling_issues:
        ethics_score -= len(decoupling_issues) * 10
    ethics_score = max(0, min(100, ethics_score))

    if ethics_score >= 80:
        compliance_status = "通过"
        compliance_status_class = "pass"
        score_class = "high"
    elif ethics_score >= 50:
        compliance_status = "需修订"
        compliance_status_class = "needs-revision"
        score_class = "medium"
    else:
        compliance_status = "驳回"
        compliance_status_class = "rejected"
        score_class = "low"

    recommended_steps = []
    if ethics_score < 100:
        recommended_steps.append("检查 AI 人格是否存在身份-行为耦合违规")
    if ethics_score < 80:
        recommended_steps.append("对违规人格进行修正后重新评审")
    if ethics_score < 50:
        recommended_steps.append("全部评审结果需要人工复核")
    if not recommended_steps:
        recommended_steps = ["结果可供参考，但仍建议人工抽检"]

    # 三个版本号原来全写死 "0.1.0"，还被渲染进 .md 头部和 HTML 页脚的「📦 v0.1.0」。
    # 用户拿它做复现/追溯会追到一个不存在的版本（包版本早就是 0.3.0），而且两份用
    # 不同人格包跑出来的报告版本号一模一样。规则：取得到真值才写这个键，取不到
    # 就整键不写，渲染层看不到就不显示——显示一个假版本号比不显示危险得多。
    meta = {
        "task_type": task_type,
        "target": target,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "is_synthetic": True,
        "caveats": collect_caveats(persona_outputs),
    }
    build_version = resolve_build_version()
    if build_version:
        meta["build_version"] = build_version
    if persona_pack:
        pack_id = persona_pack.get("pack_id")
        pack_version = persona_pack.get("version")
        if pack_version:
            # 带上包名：只写 "0.1.0" 无法区分 game-core 和 mobile-f2p，
            # 而所有人格包目前恰好都是 0.1.0，跨包对比时等于没有版本信息
            meta["persona_pack_version"] = (
                f"{pack_id}@{pack_version}" if pack_id else str(pack_version)
            )
        elif pack_id:
            meta["persona_pack"] = pack_id
    # prompt_version 直接去掉：仓库里没有任何东西给提示词模板打版本号，
    # 没有事实源就不该有这个字段。需要它的话得先给 src/templates/*.md 建立版本机制。

    return {
        "meta": meta,
        "executive_summary": {
            "primary_recommendation": primary_recommendation,
            "release_risk": release_risk,
            "evidence_quality": evidence_quality,
        },
        # 整份 consensus 原样透出：stance_distribution 以前被丢弃，前端只好自己
        # 从 persona_notes 再算一遍，两套口径并存——引擎侧改了阈值前端不会跟着变。
        "consensus": consensus,
        "major_disagreements": disagreements,
        "priority_fixes": priority_fixes,
        "persona_notes": persona_notes,
        "evidence_profile": evidence_profile,
        "dimension_scores": dimension_scores,
        "information_gaps": information_gaps,
        "next_human_test": {
            "suggested_tasks": suggested_tasks,
            "recruit_types": recruit_types,
            "recruit_types_basis": recruit_types_basis,
            "next_materials": next_materials,
        },
        "cross_examination": cross_exam_data,
        "compliance": {
            "status": compliance_status,
            "status_class": compliance_status_class,
            "ethics_score": ethics_score,
            "score_class": score_class,
            "recommended_steps": recommended_steps,
            # 这个分数的唯一输入是 check_identity_behavior_decoupling 的违规条数
            # （100 - 10×条数），与隐私、刻板印象、材料合规等其它伦理维度无关。
            # 不写清楚口径的话，"100 分"会被读成"通过了一整套伦理审查"。
            "scope": "identity_behavior_decoupling",
            "scope_label": "身份-行为解耦检查",
            "violation_count": len(decoupling_issues),
        },
    }


def render_markdown_report(report: dict, template_path: str) -> str:
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")

    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)
    # trim_blocks/lstrip_blocks：模板里的 {% if %}/{% for %} 标签独占一行，不开这两个
    # 选项的话每个标签都会在导出的 .md 里留下一个空行，一份报告下来到处是大段空白。
    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)
    template = env.get_template(template_name)

    meta = report.get("meta", {})
    summary = report.get("executive_summary", {})
    context = {
        "task_type": meta.get("task_type"),
        "target": meta.get("target"),
        # 三个版本号取不到就是 None，模板按 {% if %} 决定要不要出这一行
        "build_version": meta.get("build_version"),
        "persona_pack_version": meta.get("persona_pack_version"),
        "generated_at": meta.get("generated_at"),
        "primary_recommendation": summary.get("primary_recommendation"),
        "release_risk": summary.get("release_risk"),
        "evidence_quality": summary.get("evidence_quality"),
        "consensus": report.get("consensus", {}),
        "major_disagreements": report.get("major_disagreements", []),
        "priority_fixes": report.get("priority_fixes", []),
        "persona_notes": report.get("persona_notes", []),
        "information_gaps": report.get("information_gaps", []),
        "next_human_test": report.get("next_human_test", {}),
        "meta": meta,
        # 下面三项 HTML 模板一直有、Markdown 模板一直没有，而绝大多数人是把 .md
        # 发给同事看的：少了 cross_examination 的口径说明，读者会把 derived_summary
        # （根本没发生过反驳）当成一场真辩论；少了 compliance，AI 生成声明和整改
        # 建议也一起丢了。两份导出件必须说同样的话。
        "cross_examination": report.get("cross_examination"),
        "compliance": report.get("compliance"),
        "validation": report.get("validation"),
        "degradation": report.get("degradation"),
        "budget": report.get("budget"),
        "panel_selection": report.get("panel_selection"),
        # 证据构成 / 弃权 / 维度均分：网页版有的账目导出件必须同样有——
        # .md 是发给同事看的那一份，少了这三块等于账目只对本人公开。
        "evidence_profile": report.get("evidence_profile"),
        "abstentions": report.get("abstentions", []),
        "dimension_scores": report.get("dimension_scores", []),
        "triage": report.get("triage"),
        "predictions": report.get("predictions", []),
        "project_memory": report.get("project_memory"),
        # logo **只给 HTML**，不进 Markdown：这张图是 ~21KB 的 base64 data URI，
        # 塞进 .md 等于给每一行 reviews.report_markdown 和每一次导出都加 21KB
        # 死重量；而 Markdown 渲染器（GitHub、多数编辑器）出于安全普遍拒绝
        # data: 图片，加了也是个破图。HTML 导出件要脱站离线打开，那里才需要它。
    }

    return template.render(**context)


def render_html_report(report: dict, template_path: str) -> str:
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"HTML template file not found: {template_path}")

    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)
    env = Environment(loader=FileSystemLoader(template_dir))
    env.filters["mul"] = lambda value, factor: int(value) * factor
    template = env.get_template(template_name)

    positive_stances = {
        "加愿望单", "继续试玩", "值得推进", "会买", "会转发",
        "增强信心", "会支持", "会加入", "增强期待", "文化适配良好",
        "正面", "推荐", "认可", "支持", "赞同",
    }
    negative_stances = {
        "不加", "退出", "不值得", "不买", "不会",
        "降低信心", "不会支持", "不会加入", "降低期待", "存在问题",
        "负面", "不推荐", "反对", "拒绝", "批评",
    }

    persona_notes_enriched = []
    for pn in report.get("persona_notes", []):
        pid = pn.get("persona_id", "")
        pname = pn.get("persona_name", pid)
        stance = pn.get("stance", "")

        avatar_hue = hash(pid) % 360
        avatar_color = f"hsl({avatar_hue}, 65%, 55%)"
        avatar_letter = pname[0] if pname else "?"

        if stance in positive_stances:
            stance_class = "positive"
        elif stance in negative_stances:
            stance_class = "negative"
        else:
            stance_class = "neutral"

        persona_output = next(
            (p for p in report.get("_persona_outputs", []) if p.get("persona_id") == pid),
            None,
        )

        scores = []
        if persona_output:
            base = persona_output.get("scores", {}).get("base", {})
            task_specific = persona_output.get("scores", {}).get("task_specific", {})
            for dim, val in {**base, **task_specific}.items():
                scores.append({"dim": dim, "val": val})

        evidence_top3 = []
        if persona_output:
            for ev in persona_output.get("evidence", [])[:3]:
                evidence_top3.append({
                    "content": ev.get("content", ""),
                    "level": ev.get("inference_level", "inferred"),
                    "quote": ev.get("quote", "") if ev.get("inference_level") == "direct" else "",
                })
        elif isinstance(pn.get("evidence_top3_detail"), list) and pn["evidence_top3_detail"]:
            # 没有原始人格输出（从已存报告重渲染）时，结构化版本里带着 quote
            evidence_top3.extend(ev for ev in pn["evidence_top3_detail"] if isinstance(ev, dict))
        elif isinstance(pn.get("evidence_top3"), list):
            for ev in pn["evidence_top3"]:
                if isinstance(ev, dict):
                    evidence_top3.append(ev)
                else:
                    evidence_top3.append({"content": str(ev), "level": "inferred"})

        top_issues = []
        if persona_output:
            for iss in persona_output.get("key_issues", [])[:3]:
                top_issues.append({
                    "severity": iss.get("severity", "medium"),
                    "title": iss.get("title", ""),
                    "why_it_matters": iss.get("why_it_matters", ""),
                    "suggested_fix": iss.get("suggested_fix", ""),
                })

        voice_sample = ""
        if persona_output:
            voice_sample = persona_output.get("voice_sample", "")

        persona_notes_enriched.append({
            **pn,
            "avatar_color": avatar_color,
            "avatar_letter": avatar_letter,
            "stance_class": stance_class,
            "scores": scores,
            "evidence_top3": evidence_top3,
            "top_issues": top_issues,
            "voice_sample": voice_sample,
        })

    context = {
        "meta": report["meta"],
        "executive_summary": report["executive_summary"],
        "consensus": report["consensus"],
        "major_disagreements": report["major_disagreements"],
        "priority_fixes": report["priority_fixes"],
        "persona_notes": persona_notes_enriched,
        "information_gaps": report["information_gaps"],
        "next_human_test": report["next_human_test"],
        "persona_count": len(persona_notes_enriched),
        "cross_examination": report.get("cross_examination"),
        "compliance": report.get("compliance"),
        "validation": report.get("validation"),
        "panel_selection": report.get("panel_selection"),
        # 与 Markdown 导出同批补齐：网页版有的账目，两份导出件必须同样有。
        "evidence_profile": report.get("evidence_profile"),
        "abstentions": report.get("abstentions", []),
        "dimension_scores": report.get("dimension_scores", []),
        "triage": report.get("triage"),
        "predictions": report.get("predictions", []),
        "project_memory": report.get("project_memory"),
        "logo_data_uri": _logo_data_uri(),
    }

    return template.render(**context)
