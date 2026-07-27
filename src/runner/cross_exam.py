"""交叉质询（cross-examination）协议核心。

这个模块负责三件事：
1. 从各人格已产出的评审意见里挑出真正有分歧的争议点，并把对立双方配成匿名论据；
2. 渲染反驳提示词（**提示词里不出现任何人格名**，只用论据编号 A1/B1/…）；
3. 执行反驳轮，然后**在代码里**比较反驳前后的 (立场, 置信度) 判定改票。

三种 mode，含义必须与实际发生的事严格一致：
  derived_summary      —— 没有发生任何反驳调用，只是把既有对立意见并排摆出（历史行为）
  moderated_rebuttal   —— 一次仲裁式反驳轮：1 次模型调用，主持人代双方各写一轮反驳
  multi_agent_rebuttal —— 真多智能体反驳：每位涉事人格各被重新调用一次

`is_live_debate` 只在后两种模式下为 True。反驳调用失败会回落成 derived_summary
并在 limitation 里写明原因 —— 绝不允许"跑失败了还说辩论过了"。
"""

import inspect
import json
import os
import re
from typing import Callable, List, Optional

import yaml
from jinja2 import Template

try:
    from .similarity import get_issue_similarity
except ImportError:
    from runner.similarity import get_issue_similarity


SEVERITY_MAP = {"low": 1, "medium": 2, "high": 3, "critical": 4}

# ---------------------------------------------------------------------------
# 模式常量与 limitation 文案
# ---------------------------------------------------------------------------

MODE_AUTO = "auto"  # 仅作为入参：有 llm_call 就走 moderated，没有就 derived
MODE_DERIVED = "derived_summary"
MODE_MODERATED = "moderated_rebuttal"
MODE_MULTI_AGENT = "multi_agent_rebuttal"
LIVE_MODES = (MODE_MODERATED, MODE_MULTI_AGENT)
VALID_MODES = (MODE_AUTO, MODE_DERIVED, MODE_MODERATED, MODE_MULTI_AGENT)

# 派生摘要的文案保持与历史版本逐字一致：docs/ 与 README 里引用了这句原文，
# 改字面会让"文档与代码一致"这件事重新破掉。真跑了反驳时不会用这句。
LIMITATION_DERIVED = (
    "This cross-examination block is derived from existing persona outputs; "
    "no live multi-agent rebuttal was executed."
)

# ---------------------------------------------------------------------------
# θ（置信度变化阈值）从 aggregation-rules.yaml 读
#
# 这个值以前只存在于 yaml 和提示词文本里，全仓库零读取点——也就是说没有任何代码
# 执行过它。改票判定必须真的读它，否则"可配置阈值"又是一句空话。
# ---------------------------------------------------------------------------

DEFAULT_RULES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "aggregation-rules.yaml",
)
FALLBACK_CONFIDENCE_CHANGE_THRESHOLD = 0.15


def _coerce_str(value) -> str:
    """任意类型降成字符串。模型/上游偶尔吐 None、数字、甚至 dict，
    而下游要拼提示词、要做 str 比较，非字符串会直接炸。"""
    if isinstance(value, str):
        return value.strip()
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "content", "point", "title", "value"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        return "; ".join(f"{k}: {_coerce_str(v)}" for k, v in value.items() if _coerce_str(v))
    if isinstance(value, (list, tuple, set)):
        return "; ".join(t for t in (_coerce_str(v) for v in value) if t)
    return str(value)


def _coerce_confidence(value, default: Optional[float] = None) -> Optional[float]:
    """置信度归一到 0-1 的 float。

    与 persona_agent._coerce_ratio 同一套口径（"0.8" / "80%" / 8 都收），这里独立
    实现是为了不让协议核心依赖 persona_agent（aggregator 对 SEVERITY_MAP 也是这么做的）。
    取不到时返回 default（默认 None，表示"模型没给"，由调用方决定当作不变还是失败）。
    """
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        text = value.strip().rstrip("%")
        try:
            num = float(text)
        except ValueError:
            return default
        if value.strip().endswith("%"):
            num /= 100.0
    else:
        return default
    if 1.0 < num <= 10.0:
        # 模型有时按十分制/百分制给：按比例还原，而不是直接夹到 1.0（夹会伪造出巨大 delta）
        num /= 10.0
    elif num > 10.0:
        num /= 100.0
    return max(0.0, min(1.0, num))


def load_cross_exam_rules(rules: Optional[dict] = None, rules_path: Optional[str] = None) -> dict:
    """取交叉质询相关配置：θ 与 allow_stance_update。

    优先用调用方已经加载好的 rules dict（cli / web 后端都已经读过这份 yaml，
    没必要再读一遍）；没有就按 rules_path（默认 src/config/aggregation-rules.yaml）读。
    读不到时回落到内置默认值，并把这件事写进 source —— 不静默假装配置生效了。
    """
    section = None
    source = ""

    if isinstance(rules, dict) and isinstance(rules.get("cross_exam"), dict):
        section = rules["cross_exam"]
        source = "rules-dict"
    else:
        path = rules_path or DEFAULT_RULES_PATH
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            if isinstance(loaded.get("cross_exam"), dict):
                section = loaded["cross_exam"]
                source = path
            else:
                source = f"fallback-default(配置文件 {path} 缺少 cross_exam 段)"
        except (OSError, yaml.YAMLError) as e:
            source = f"fallback-default(读取 {path} 失败: {e})"

    threshold = None
    allow_stance_update = True
    if section is not None:
        threshold = _coerce_confidence(section.get("confidence_change_threshold"))
        if threshold is None:
            source = f"fallback-default({source} 里 confidence_change_threshold 不是有效数值)"
        allow = section.get("allow_stance_update", True)
        allow_stance_update = bool(allow) if isinstance(allow, (bool, int)) else True

    if threshold is None:
        threshold = FALLBACK_CONFIDENCE_CHANGE_THRESHOLD

    return {
        "threshold": threshold,
        "allow_stance_update": allow_stance_update,
        "source": source,
    }


def _variance(values: List[float]) -> float:
    if len(values) == 0:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def extract_controversy_points(
    persona_outputs: List[dict], top_n: int = 3, similarity=None
) -> List[dict]:
    # similarity 可注入便于测试；默认优先语义 embedding，缺依赖时回退字符串相似度
    sim = similarity if similarity is not None else get_issue_similarity()
    all_issues = []
    for output in persona_outputs:
        persona_id = output.get("persona_id", "")
        for issue in output.get("key_issues", []):
            all_issues.append(
                {
                    "persona_id": persona_id,
                    "title": issue.get("title", ""),
                    "severity": issue.get("severity", "low"),
                }
            )

    unique_issues = []
    for issue in all_issues:
        merged = False
        for ui in unique_issues:
            if sim.is_same_issue(issue["title"], ui["title"]):
                ui["views"].append(
                    {
                        "persona_id": issue["persona_id"],
                        "severity": issue["severity"],
                        "title": issue["title"],
                    }
                )
                merged = True
                break
        if not merged:
            unique_issues.append(
                {
                    "title": issue["title"],
                    "views": [
                        {
                            "persona_id": issue["persona_id"],
                            "severity": issue["severity"],
                            "title": issue["title"],
                        }
                    ],
                }
            )

    results = []
    for ui in unique_issues:
        severity_values = [
            SEVERITY_MAP.get(v["severity"], 1) for v in ui["views"]
        ]
        var = _variance(severity_values)
        results.append(
            {
                "title": ui["title"],
                "severity_variance": var,
                "persona_views": ui["views"],
                "dedup_method": sim.method,
            }
        )

    results.sort(key=lambda x: x["severity_variance"], reverse=True)
    return results[:top_n]


def find_opposing_stances(
    controversy_point: dict, persona_outputs: List[dict], similarity=None
) -> dict:
    # similarity 可注入便于测试；默认优先语义 embedding，缺依赖时回退字符串相似度
    sim = similarity if similarity is not None else get_issue_similarity()
    views = controversy_point.get("persona_views", [])
    severity_scores = [
        SEVERITY_MAP.get(v["severity"], 1) for v in views
    ]

    if len(views) < 2:
        return {
            "pro": {"persona_id": views[0]["persona_id"], "argument": ""},
            "con": {"persona_id": views[0]["persona_id"], "argument": ""},
        }

    max_idx = severity_scores.index(max(severity_scores))
    min_idx = severity_scores.index(min(severity_scores))

    if max_idx == min_idx:
        stance_map = {}
        for output in persona_outputs:
            pid = output.get("persona_id", "")
            stance = output.get("primary_stance", "")
            stance_map[pid] = stance

        stance_values = {}
        for v in views:
            stance = stance_map.get(v["persona_id"], "")
            stance_values[v["persona_id"]] = stance

        pro_view = views[0]
        con_view = views[-1]
    else:
        pro_view = views[max_idx]
        con_view = views[min_idx]

    issue_title = controversy_point.get("title", "")

    pro_argument = ""
    con_argument = ""
    for output in persona_outputs:
        for issue in output.get("key_issues", []):
            if sim.is_same_issue(issue.get("title", ""), issue_title):
                if output.get("persona_id") == pro_view["persona_id"]:
                    pro_argument = issue.get("why_it_matters", "")
                if output.get("persona_id") == con_view["persona_id"]:
                    con_argument = issue.get("why_it_matters", "")

    return {
        "pro": {"persona_id": pro_view["persona_id"], "argument": pro_argument},
        "con": {"persona_id": con_view["persona_id"], "argument": con_argument},
    }


# ---------------------------------------------------------------------------
# 匿名化：把论据和人格身份解绑
#
# 提示词里出现人格名会让模型按身份结盟或让位（"这是资深策划说的，那我改立场"），
# 反驳就不再是对论据的检验。所以：
#   1. 模板里没有 persona name 槽位，只有论据编号 A1 / B1；
#   2. 论据正文里若不小心带了人格名（人格自称、互相点名），这里洗成"某位评审"。
# ---------------------------------------------------------------------------

ANONYMOUS_PLACEHOLDER = "某位评审"


def _persona_names(persona_outputs: List[dict]) -> List[str]:
    """收集需要从提示词里洗掉的人格名。单字名不洗——单字太容易命中正常词，
    洗掉反而把论据改得不知所云（宁可漏一个也不毁原文）。"""
    names = set()
    for output in persona_outputs:
        name = _coerce_str(output.get("persona_name", ""))
        if len(name) >= 2:
            names.add(name)
    # 长名先替换，避免"周策"先被换掉导致"周策同学"里残留"同学"
    return sorted(names, key=len, reverse=True)


def _strip_persona_names(text: str, names: List[str]) -> str:
    result = _coerce_str(text)
    for name in names:
        if name and name in result:
            result = result.replace(name, ANONYMOUS_PLACEHOLDER)
    return result


def _find_issue(persona_output: dict, title: str, sim) -> dict:
    for issue in persona_output.get("key_issues", []) or []:
        if isinstance(issue, dict) and sim.is_same_issue(_coerce_str(issue.get("title", "")), title):
            return issue
    return {}


def build_debate_sides(
    controversy_points: List[dict], persona_outputs: List[dict], similarity=None
) -> List[dict]:
    """把争议点变成匿名的双方论据，作为提示词渲染和改票判定的**唯一**数据来源。

    返回 list，每项：
      {point_id, title, debatable, skip_reason,
       sides: [{argument_id, role, persona_id, persona_name, severity,
                argument, suggested_fix, stance, confidence}, ...]}

    role="pro" 是认为问题更严重的一方，"con" 是认为更轻的一方（沿用
    find_opposing_stances 的口径）。argument_id 形如 A1 / B1，数字是争议点序号。
    """
    sim = similarity if similarity is not None else get_issue_similarity()
    names = _persona_names(persona_outputs)
    by_id = {}
    for output in persona_outputs:
        by_id[_coerce_str(output.get("persona_id", ""))] = output

    debates = []
    for idx, cp in enumerate(controversy_points or [], start=1):
        point_id = f"C{idx}"
        title = _coerce_str(cp.get("title", ""))
        views = cp.get("persona_views", []) or []

        if not views:
            # 没有任何人格观点的议题没法反驳；find_opposing_stances 在这种输入下会
            # IndexError，所以在这里就短路掉。
            debates.append({
                "point_id": point_id,
                "title": _strip_persona_names(title, names),
                "sides": [],
                "debatable": False,
                "skip_reason": "该议题没有记录任何人格观点",
            })
            continue

        opposing = find_opposing_stances(cp, persona_outputs, similarity=sim)
        sides = []
        for role, letter in (("pro", "A"), ("con", "B")):
            pid = _coerce_str(opposing[role]["persona_id"])
            output = by_id.get(pid, {})
            issue = _find_issue(output, title, sim)
            severity = ""
            for v in views:
                if _coerce_str(v.get("persona_id", "")) == pid:
                    severity = _coerce_str(v.get("severity", ""))
                    break
            argument = _coerce_str(opposing[role].get("argument", "")) or _coerce_str(
                issue.get("why_it_matters", "")
            )
            sides.append({
                "argument_id": f"{letter}{idx}",
                "role": role,
                "persona_id": pid,
                "persona_name": _coerce_str(output.get("persona_name", "")) or pid,
                "severity": severity,
                "argument": _strip_persona_names(argument, names),
                "suggested_fix": _strip_persona_names(_coerce_str(issue.get("suggested_fix", "")), names),
                "stance": _coerce_str(output.get("primary_stance", "")),
                "confidence": _coerce_confidence(output.get("confidence"), 0.5),
            })

        pro, con = sides[0], sides[1]
        skip_reason = ""
        if pro["persona_id"] == con["persona_id"]:
            skip_reason = "该议题只有一位人格提出，没有对立方可反驳"
        elif not pro["argument"] or not con["argument"]:
            skip_reason = "原始评审输出里缺少可反驳的论据正文"

        debates.append({
            "point_id": point_id,
            "title": _strip_persona_names(title, names),
            "sides": sides,
            "debatable": not skip_reason,
            "skip_reason": skip_reason,
        })

    return debates


# ---------------------------------------------------------------------------
# 提示词渲染
# ---------------------------------------------------------------------------

_SECTION_MARKER_RE = re.compile(r"^<!--\s*SECTION:\s*(\w+)\s*-->[ \t]*$", re.M)


def load_prompt_sections(template_path: str) -> dict:
    """把提示词文件按 `<!-- SECTION:名字 -->` 切成多段。

    没有任何分段标记时，整份文件当作 moderated 段——这样即使有人换回旧模板，
    仲裁式反驳仍然能跑（多智能体反驳会因为缺 rebutter 段而如实报失败）。
    """
    with open(template_path, "r", encoding="utf-8") as f:
        text = f.read()

    parts = _SECTION_MARKER_RE.split(text)
    if len(parts) == 1:
        return {"moderated": text.strip()}

    sections = {}
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i]] = parts[i + 1].strip()
    return sections


def render_cross_exam_prompt(
    controversy_points: List[dict],
    persona_outputs: List[dict],
    template_path: str,
    similarity=None,
    debates: Optional[List[dict]] = None,
) -> str:
    """渲染仲裁式反驳提示词（standard 档，一次调用覆盖全部争议点）。

    不可反驳的议题（只有一位人格提出 / 缺论据正文）不进提示词：既省 token，
    也避免模型对着"未提取到论证"这类占位文案编出一场假辩论。
    **如果一个可反驳议题都没有，返回空串——调用方必须先判空再决定是否发调用。**
    """
    sections = load_prompt_sections(template_path)
    template_str = sections.get("moderated") or ""
    if not template_str:
        raise ValueError(f"提示词模板缺少 moderated 段：{template_path}")

    if debates is None:
        debates = build_debate_sides(controversy_points, persona_outputs, similarity=similarity)

    rendered_points = []
    for d in debates:
        if not d.get("debatable"):
            continue
        pro, con = d["sides"][0], d["sides"][1]
        rendered_points.append({
            "point_id": d["point_id"],
            "title": d["title"],
            "pro_argument_id": pro["argument_id"],
            "pro_severity": pro["severity"],
            "pro_stance": pro["stance"],
            "pro_confidence": f"{pro['confidence']:.2f}",
            "pro_argument": pro["argument"],
            "pro_fix": pro["suggested_fix"],
            "con_argument_id": con["argument_id"],
            "con_severity": con["severity"],
            "con_stance": con["stance"],
            "con_confidence": f"{con['confidence']:.2f}",
            "con_argument": con["argument"],
            "con_fix": con["suggested_fix"],
        })

    if not rendered_points:
        return ""

    template = Template(_convert_handlebars_to_jinja2(template_str))
    return template.render(controversy_points=rendered_points)


def render_rebuttal_prompt(debate: dict, side: dict, template_path: str) -> str:
    """渲染单个人格的反驳提示词（full 档，每位涉事人格各一次调用）。

    人格自己知道自己是谁（调用方会带上它的人格提示词），但**看不到对手是谁**，
    只看到"论据 B1"。缺 rebutter 段时直接抛错，由 run_cross_exam_protocol
    记成失败并如实回落——不静默降级成仲裁式。
    """
    sections = load_prompt_sections(template_path)
    template_str = sections.get("rebutter") or ""
    if not template_str:
        raise ValueError(
            f"提示词模板缺少 rebutter 段（{template_path}），无法执行多智能体反驳"
        )

    opponent = None
    for other in debate.get("sides", []):
        if other["argument_id"] != side["argument_id"]:
            opponent = other
            break
    if opponent is None:
        raise ValueError(f"论据 {side['argument_id']} 没有对立论据，无法反驳")

    template = Template(_convert_handlebars_to_jinja2(template_str))
    return template.render(
        point_id=debate.get("point_id", ""),
        topic=debate.get("title", ""),
        own_argument_id=side["argument_id"],
        own_severity=side["severity"],
        own_stance=side["stance"],
        own_confidence=f"{side['confidence']:.2f}",
        own_argument=side["argument"],
        own_fix=side["suggested_fix"],
        opponent_argument_id=opponent["argument_id"],
        opponent_severity=opponent["severity"],
        opponent_argument=opponent["argument"],
        opponent_fix=opponent["suggested_fix"],
    )


def _convert_handlebars_to_jinja2(template_str: str) -> str:
    result = []
    i = 0
    in_each = False
    while i < len(template_str):
        match = re.match(r"\{\{#each\s+(\w+)\}\}", template_str[i:])
        if match:
            var_name = match.group(1)
            result.append("{% for _item in " + var_name + " %}")
            i += match.end()
            in_each = True
            continue
        if template_str[i:].startswith("{{/each}}"):
            result.append("{% endfor %}")
            i += len("{{/each}}")
            in_each = False
            continue
        if in_each:
            index_match = re.match(r"\{\{@index\}\}", template_str[i:])
            if index_match:
                result.append("{{ loop.index0 }}")
                i += index_match.end()
                continue
            this_match = re.match(r"\{\{this\}\}", template_str[i:])
            if this_match:
                result.append("{{ _item }}")
                i += this_match.end()
                continue
            var_match = re.match(r"\{\{(\w+)\}\}", template_str[i:])
            if var_match:
                prop = var_match.group(1)
                result.append("{{ _item." + prop + " }}")
                i += var_match.end()
                continue
        result.append(template_str[i])
        i += 1
    return "".join(result)


# ---------------------------------------------------------------------------
# 模型输出归一化
#
# 第三方模型能理解任务但不肯照抄 schema：字段改名、形状不对、整体吐成字符串。
# 这个仓库在 persona_agent 里已经有一整套经验，这里按同样思路做三道保险：
# 字段别名 → 形状归一 → 防御性取值。任何一条不成立都记成失败，不崩、不编数据。
# ---------------------------------------------------------------------------

_REBUTTAL_LIST_KEYS = (
    "rebuttals", "arguments", "responses", "persona_evaluations",
    "evaluations", "sides", "results", "items",
)
_ARG_ID_KEYS = ("argument_id", "arg_id", "id", "label")
_REBUTTAL_TEXT_KEYS = (
    "rebuttal", "rebuttal_text", "counter_argument", "counterargument",
    "response", "text", "point", "reason_if_changed", "reason",
)
_STANCE_KEYS = ("stance_after", "new_stance", "updated_stance", "stance", "position")
_CONF_KEYS = (
    "confidence_after", "new_confidence", "updated_confidence",
    "confidence", "confidence_score",
)
_PERSONA_KEYS = ("persona_id", "evaluator_id", "reviewer_id", "agent_id")

# 模型表示"我不改"的各种写法：立场原样照抄拿不到时，这些也算不变。
_UNCHANGED_MARKERS = (
    "不变", "保持", "维持", "无变化", "同上", "不改",
    "unchanged", "no change", "same", "keep", "n/a", "none",
)


def _pick(data: dict, keys) -> Optional[object]:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _normalize_argument_id(raw, valid_ids) -> str:
    """把模型给的编号归一回我们发出去的编号。

    实测模型会写成 "论据A1"、"a1"、"A 1"，也会有把 argument_id 填成 persona_id 的。
    对不上就返回空串，由调用方记成"未匹配"，绝不猜。
    """
    text = _coerce_str(raw).upper()
    if not text:
        return ""
    if text in valid_ids:
        return text
    if len(text) > 24:
        # 明显是正文而不是编号：在长文本里正则捞 "B1" 会把反驳里提到的对手编号
        # 误当成作者编号，宁可匹配不上
        return ""
    match = re.search(r"([AB])\s*(\d+)", text)
    if match:
        candidate = f"{match.group(1)}{int(match.group(2))}"
        if candidate in valid_ids:
            return candidate
    return ""


def _is_unchanged_marker(text: str) -> bool:
    lowered = _coerce_str(text).lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in _UNCHANGED_MARKERS)


def _normalize_rebuttal_items(parsed, debates: List[dict]) -> dict:
    """把 parse_cross_exam_output 的结果摊平成 {argument_id: {...}}。

    接受两种嵌套：外层按争议点分组（point_id + rebuttals[]），或者直接一个扁平
    的论据列表。两种都见过，模型不会稳定选一种。
    """
    valid_ids = set()
    persona_to_arg = {}
    for d in debates:
        for side in d.get("sides", []):
            valid_ids.add(side["argument_id"])
            # 同一人格可能在多个议题里有论据；只在唯一时才允许按 persona_id 回退匹配，
            # 否则会把 C2 的反驳错记到 C1 上。
            persona_to_arg.setdefault(side["persona_id"], []).append(side["argument_id"])

    updates = {}

    def absorb(item):
        if not isinstance(item, dict):
            return
        arg_id = _normalize_argument_id(_pick(item, _ARG_ID_KEYS), valid_ids)
        if not arg_id:
            pid = _coerce_str(_pick(item, _PERSONA_KEYS) or "")
            candidates = persona_to_arg.get(pid, [])
            if len(candidates) == 1:
                arg_id = candidates[0]
        if not arg_id:
            return
        stance_raw = _coerce_str(_pick(item, _STANCE_KEYS) or "")
        updates[arg_id] = {
            "rebuttal": _coerce_str(_pick(item, _REBUTTAL_TEXT_KEYS) or ""),
            "stance_after_raw": stance_raw,
            "confidence_after": _coerce_confidence(_pick(item, _CONF_KEYS)),
        }

    for entry in parsed or []:
        if not isinstance(entry, dict):
            continue
        nested = None
        for key in _REBUTTAL_LIST_KEYS:
            value = entry.get(key)
            if isinstance(value, list):
                nested = value
                break
        if nested is not None:
            for item in nested:
                absorb(item)
            # 有的模型把 point_id 和单条反驳混在同一层，两种都吸收
            absorb(entry)
        else:
            absorb(entry)

    return updates


# ---------------------------------------------------------------------------
# LLM 调用适配
# ---------------------------------------------------------------------------


def _accepts_persona_id(fn) -> bool:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    for name, param in sig.parameters.items():
        if param.kind == param.VAR_KEYWORD or name == "persona_id":
            return True
    return False


def _normalize_llm_result(result):
    """llm_call 允许三种返回形状，统一成 (text, in_tokens, out_tokens, tokens_known)。

    - str                          → 拿不到 token 数（tokens_known=False）
    - (text, in_tokens, out_tokens) → llm_client.chat_completion 的原生形状
    - {"text":..., "input_tokens":..., "output_tokens":...}

    token 必须能带出去：这是新增的付费调用，不计进账就是计费漏洞。
    """
    if isinstance(result, str):
        return result, 0, 0, False
    if isinstance(result, (tuple, list)):
        text = _coerce_str(result[0]) if result else ""
        if len(result) >= 3:
            try:
                return text, int(result[1] or 0), int(result[2] or 0), True
            except (TypeError, ValueError):
                return text, 0, 0, False
        return text, 0, 0, False
    if isinstance(result, dict):
        text = _coerce_str(_pick(result, ("text", "content", "output", "raw", "message")) or "")
        in_tok = _pick(result, ("input_tokens", "prompt_tokens"))
        out_tok = _pick(result, ("output_tokens", "completion_tokens"))
        if in_tok is None and out_tok is None:
            return text, 0, 0, False
        try:
            return text, int(in_tok or 0), int(out_tok or 0), True
        except (TypeError, ValueError):
            return text, 0, 0, False
    return _coerce_str(result), 0, 0, False


def _invoke_llm(llm_call: Callable, prompt: str, usage: dict, persona_id: str = ""):
    """发一次调用并把用量计进 usage。异常原样抛给调用方，由它记成失败。"""
    usage["calls"] += 1
    if persona_id and _accepts_persona_id(llm_call):
        result = llm_call(prompt, persona_id=persona_id)
    else:
        result = llm_call(prompt)
    text, in_tok, out_tok, tokens_known = _normalize_llm_result(result)
    usage["input_tokens"] += in_tok
    usage["output_tokens"] += out_tok
    if not tokens_known:
        # 有一次调用拿不到 token 数，整份用量就不能当成完整的账
        usage["token_counts_available"] = False
    return text


# ---------------------------------------------------------------------------
# 改票判定（在代码里算，不信模型自报）
# ---------------------------------------------------------------------------


def _decide_change(side: dict, update: dict, threshold: float, allow_stance_update: bool) -> dict:
    """比较反驳前后的 (立场, 置信度)，判定这是不是一次改票。

    模型自己说 "stance_changed": true 一律不采信——它高兴时能给每个人都改一次票。
    唯一依据是：立场文字真的变了，**且**置信度变化的绝对值达到 θ。
    """
    stance_before = side["stance"]
    conf_before = side["confidence"] if side["confidence"] is not None else 0.5

    conf_after = update.get("confidence_after")
    if conf_after is None:
        conf_after = conf_before  # 模型没给就当没变，不编数字

    stance_raw = update.get("stance_after_raw", "")
    if not stance_raw or _is_unchanged_marker(stance_raw):
        stance_after = stance_before
    else:
        stance_after = stance_raw

    delta = round(conf_after - conf_before, 4)
    stance_moved = stance_after.strip() != stance_before.strip()
    # 浮点减法会把"恰好等于 θ"算成 0.1499999…，所以留一个比 θ 小几个数量级的容差
    meets_threshold = abs(delta) >= threshold - 1e-9

    changed = bool(stance_moved and meets_threshold and allow_stance_update)
    if stance_moved and not allow_stance_update:
        suppressed = "配置 allow_stance_update=false，不接受立场更新"
    elif stance_moved and not meets_threshold:
        suppressed = (
            f"置信度变化 {abs(delta):.2f} 未达阈值 {threshold:.2f}，立场更新不予采纳"
        )
    else:
        suppressed = ""

    return {
        "stance_before": stance_before,
        "stance_after": stance_after if changed else stance_before,
        "stance_claimed": stance_after,
        "confidence_before": round(conf_before, 4),
        "confidence_after": round(conf_after, 4),
        "delta": delta,
        "changed": changed,
        "suppressed_reason": suppressed,
    }


# ---------------------------------------------------------------------------
# 协议主入口
# ---------------------------------------------------------------------------


def _legacy_args(debate: dict, role: str, updates: dict) -> List[dict]:
    """报告模板读的 disputes[].pro_args / con_args 形状（persona_id 位置放的是
    展示名，历史如此，不动它），额外挂上反驳正文供新版报告渲染。"""
    args = []
    for side in debate.get("sides", []):
        if side["role"] != role:
            continue
        update = updates.get(side["argument_id"]) or {}
        placeholder = (
            "未从原始 persona 输出中提取到支持方论证"
            if role == "pro"
            else "未从原始 persona 输出中提取到反对方论证"
        )
        args.append({
            "argument_id": side["argument_id"],
            "point": side["argument"] or placeholder,
            "persona_id": side["persona_name"],
            "persona_key": side["persona_id"],
            "severity": side["severity"],
            "rebuttal": _coerce_str(update.get("rebuttal", "")),
        })
    if not args:
        args.append({
            "argument_id": "",
            "point": "该议题没有记录任何人格观点",
            "persona_id": "",
            "persona_key": "",
            "severity": "",
            "rebuttal": "",
        })
    return args


def run_cross_exam_protocol(
    persona_outputs: List[dict],
    controversy_points: List[dict],
    llm_call: Optional[Callable] = None,
    mode: str = MODE_AUTO,
    template_path: Optional[str] = None,
    rules: Optional[dict] = None,
    rules_path: Optional[str] = None,
    similarity=None,
    num_rounds: int = 1,
) -> dict:
    """执行交叉质询，返回可直接进报告的 cross_examination 区块。

    参数
      llm_call: 由调用方注入的模型调用封装，签名 `(prompt: str, persona_id: str = "") -> str
                | (str, int, int) | dict`。**不传就回落派生摘要**（历史行为，向后兼容）。
      mode:     auto（有 llm_call 就仲裁式）/ derived_summary / moderated_rebuttal
                / multi_agent_rebuttal。
      num_rounds: 保留参数，今天只执行 1 轮反驳；返回的 rounds 反映**实际**执行的轮次，
                不按这个参数虚构轮数。

    失败处理：反驳全部失败 → mode 回落 derived_summary，limitation 写明原因，
    failures 列出每次失败；报告其余部分照出。绝不静默吞掉，也绝不谎称辩论过。
    """
    if mode not in VALID_MODES:
        raise ValueError(f"未知的交叉质询模式：{mode}（可选 {', '.join(VALID_MODES)}）")

    # 老签名第三个位置参数是 num_rounds；万一有旧调用方按位置传整数，别把它当 llm_call
    if isinstance(llm_call, int):
        num_rounds = llm_call
        llm_call = None

    if template_path is None:
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "templates",
            "cross-exam-prompt.md",
        )

    cfg = load_cross_exam_rules(rules=rules, rules_path=rules_path)
    threshold = cfg["threshold"]

    debates = build_debate_sides(controversy_points, persona_outputs, similarity=similarity)
    debatable = [d for d in debates if d.get("debatable")]

    requested_mode = mode
    if mode == MODE_AUTO:
        requested_mode = MODE_MODERATED if llm_call is not None else MODE_DERIVED

    usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "token_counts_available": True}
    failures: List[dict] = []
    updates: dict = {}
    skip_note = ""

    if requested_mode in LIVE_MODES and llm_call is None:
        # 调用方明确要求实时反驳却没给 llm_call：这是接线错误，如实降级并说清楚
        skip_note = f"调用方请求 {requested_mode} 但未注入 llm_call，未执行任何反驳调用"
        failures.append({"stage": "setup", "error": skip_note})
    elif requested_mode in LIVE_MODES and not debatable:
        skip_note = "本次没有可反驳的对立论据（争议点不足或缺少论据正文），未执行反驳调用"
    elif requested_mode == MODE_MODERATED:
        try:
            prompt = render_cross_exam_prompt(
                controversy_points, persona_outputs, template_path,
                similarity=similarity, debates=debates,
            )
            if not prompt:
                raise ValueError("渲染出的反驳提示词为空")
            raw = _invoke_llm(llm_call, prompt, usage)
            parsed = parse_cross_exam_output(raw)
            if not parsed:
                raise ValueError("模型输出无法解析为 JSON")
            updates = _normalize_rebuttal_items(parsed, debates)
            if not updates:
                raise ValueError("模型输出里没有任何可匹配的论据编号")
        except Exception as e:
            # 反驳失败不吞：记进 failures，下面会据此回落 mode 并写进 limitation
            failures.append({"stage": "moderated_rebuttal", "error": f"{type(e).__name__}: {e}"})
    elif requested_mode == MODE_MULTI_AGENT:
        for d in debatable:
            for side in d["sides"]:
                try:
                    prompt = render_rebuttal_prompt(d, side, template_path)
                    raw = _invoke_llm(llm_call, prompt, usage, persona_id=side["persona_id"])
                    parsed = parse_cross_exam_output(raw)
                    if not parsed:
                        raise ValueError("模型输出无法解析为 JSON")
                    # 单人格调用只该谈自己那条论据：解析不到编号时按当前论据兜底
                    single = _normalize_rebuttal_items(parsed, [{"sides": [side]}])
                    if side["argument_id"] not in single:
                        first = next((p for p in parsed if isinstance(p, dict)), None)
                        if first is None:
                            raise ValueError("模型输出里没有对象结构")
                        single = {side["argument_id"]: {
                            "rebuttal": _coerce_str(_pick(first, _REBUTTAL_TEXT_KEYS) or ""),
                            "stance_after_raw": _coerce_str(_pick(first, _STANCE_KEYS) or ""),
                            "confidence_after": _coerce_confidence(_pick(first, _CONF_KEYS)),
                        }}
                    updates.update(single)
                except Exception as e:
                    failures.append({
                        "stage": "multi_agent_rebuttal",
                        "point_id": d["point_id"],
                        "argument_id": side["argument_id"],
                        "error": f"{type(e).__name__}: {e}",
                    })

    # ---- 按实际结果定 mode，绝不无条件置 True ----
    live_ran = bool(updates)
    final_mode = requested_mode if (requested_mode in LIVE_MODES and live_ran) else MODE_DERIVED

    # ---- 逐条判定改票 / 置信度变化 ----
    vote_changes = []
    suppressed_changes = []
    persona_final_conf = {}
    for d in debates:
        rebutted_sides = 0
        for side in d["sides"]:
            update = updates.get(side["argument_id"])
            if not update:
                continue
            rebutted_sides += 1
            decision = _decide_change(side, update, threshold, cfg["allow_stance_update"])
            persona_final_conf[side["persona_id"]] = decision["confidence_after"]
            record = {
                "point_id": d["point_id"],
                "topic": d["title"],
                "argument_id": side["argument_id"],
                "persona_id": side["persona_id"],
                "persona_name": side["persona_name"],
                "from_stance": decision["stance_before"],
                "to_stance": decision["stance_claimed"],
                "confidence_before": decision["confidence_before"],
                "confidence_after": decision["confidence_after"],
                "delta": decision["delta"],
                "threshold": threshold,
                "reason": _coerce_str(update.get("rebuttal", "")),
                # 旧报告模板读的字段名，保持能渲染
                "before": decision["stance_before"],
                "after": decision["stance_claimed"],
            }
            if decision["changed"]:
                vote_changes.append(record)
            elif decision["suppressed_reason"]:
                suppressed_changes.append({**record, "suppressed_reason": decision["suppressed_reason"]})

        if not d.get("debatable"):
            d["rebuttal_status"] = "skipped"
            d["rebuttal_error"] = d.get("skip_reason", "")
        elif rebutted_sides >= len(d["sides"]):
            d["rebuttal_status"] = "ok"
            d["rebuttal_error"] = ""
        elif rebutted_sides:
            # 只有一方反驳成功也不能算 ok：报告里必须看得出这场对质是单边的
            d["rebuttal_status"] = "partial"
            d["rebuttal_error"] = "只有一方产出了反驳，另一方未能完成"
        elif final_mode == MODE_DERIVED:
            d["rebuttal_status"] = "skipped" if not failures else "failed"
            d["rebuttal_error"] = skip_note or (failures[0]["error"] if failures else "")
        else:
            d["rebuttal_status"] = "failed"
            d["rebuttal_error"] = "模型未返回该争议点的反驳"

    confidence_changes = []
    for p in persona_outputs:
        pid = _coerce_str(p.get("persona_id", ""))
        before = _coerce_confidence(p.get("confidence"), 0.5)
        after = persona_final_conf.get(pid, before)
        before_pct = round(before * 100)
        after_pct = round(after * 100)
        confidence_changes.append({
            # 历史上这个字段放的是展示名，报告模板直接当标签渲染；真 id 放 persona_key
            "persona_id": _coerce_str(p.get("persona_name", "")) or pid,
            "persona_key": pid,
            "before": before_pct,
            "after": after_pct,
            "delta": after_pct - before_pct,
            "confidence_before": round(before, 4),
            "confidence_after": round(after, 4),
        })

    # ---- disputes（报告模板的既有形状）----
    disputes = []
    for d in debates:
        disputes.append({
            "point_id": d["point_id"],
            "topic": d["title"],
            "pro_args": _legacy_args(d, "pro", updates),
            "con_args": _legacy_args(d, "con", updates),
            "rebuttal_status": d.get("rebuttal_status", "skipped"),
            "rebuttal_error": d.get("rebuttal_error", ""),
        })

    # ---- rounds 反映实际发生的轮次：没跑就是 0 轮 ----
    rounds = [{"round_num": 1, "is_current": True}] if final_mode in LIVE_MODES else []

    return {
        "mode": final_mode,
        "is_live_debate": final_mode in LIVE_MODES,
        "requested_mode": requested_mode,
        "limitation": _build_limitation(
            final_mode, requested_mode, threshold, failures, skip_note, disputes, usage
        ),
        "threshold": threshold,
        "threshold_source": cfg["source"],
        "allow_stance_update": cfg["allow_stance_update"],
        "rounds": rounds,
        "disputes": disputes,
        "vote_changes": vote_changes,
        "suppressed_changes": suppressed_changes,
        "confidence_changes": confidence_changes,
        "failures": failures,
        "usage": usage,
    }


def _build_limitation(
    final_mode: str,
    requested_mode: str,
    threshold: float,
    failures: List[dict],
    skip_note: str,
    disputes: List[dict],
    usage: dict,
) -> str:
    """limitation 按实际情况生成：跑成了就不许再说"未执行实时反驳"。"""
    if final_mode == MODE_DERIVED:
        if requested_mode in LIVE_MODES and failures:
            reason = failures[0].get("error", "未知原因")
            return (
                f"本次交叉质询未能完成（{reason}）。下面的正反论据仍是从各人格既有评审意见"
                f"派生的摘要，人格之间没有发生实际反驳，也没有人因此改票。"
            )
        if requested_mode in LIVE_MODES and skip_note:
            return f"本次交叉质询未执行：{skip_note}。下面只有争议点的派生摘要。"
        return LIMITATION_DERIVED

    broken = [d for d in disputes if d.get("rebuttal_status") in ("failed", "partial")]
    tail = ""
    if broken:
        ids = "、".join(d["point_id"] for d in broken)
        tail = f" 其中 {ids} 的反驳未完整完成（{broken[0].get('rebuttal_error', '')}）。"
    if not usage.get("token_counts_available", True):
        tail += " 本次反驳调用的 token 用量未由调用方回报，成本统计可能偏低。"

    if final_mode == MODE_MODERATED:
        return (
            f"本环节执行了**一次仲裁式反驳轮**（1 次模型调用）：由主持人视角代双方各写一轮"
            f"反驳并给出更新后的立场，**不是每个人格各自独立重新发言**。改票由代码比较反驳"
            f"前后的立场与置信度判定，置信度变化需达到阈值 θ={threshold:g}。" + tail
        )
    return (
        f"本环节对每个争议点的**双方各重新发起了一次独立调用**（共 {usage.get('calls', 0)} 次）："
        f"每位人格只看到自己的论据与匿名的对手论据，各自产出反驳与最终立场。改票由代码比较"
        f"反驳前后的立场与置信度判定，置信度变化需达到阈值 θ={threshold:g}。" + tail
    )


def parse_cross_exam_output(raw_output: str) -> List[dict]:
    raw_output = raw_output if isinstance(raw_output, str) else _coerce_str(raw_output)
    json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError:
            pass

    try:
        parsed = json.loads(raw_output)
        if isinstance(parsed, list):
            return parsed
        # 合法 JSON 但既不是对象也不是数组（裸字符串 / 数字）：等于没给结构化结果。
        # 以前会包成 [12345] 交给下游，白白多一个永远读不出字段的元素。
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    json_objects = []
    depth = 0
    start = None
    for i, ch in enumerate(raw_output):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                json_objects.append(raw_output[start : i + 1])
                start = None

    results = []
    for obj_str in json_objects:
        try:
            parsed = json.loads(obj_str)
            if isinstance(parsed, list):
                return parsed
            results.append(parsed)
        except json.JSONDecodeError:
            continue

    if results:
        return results

    return []
