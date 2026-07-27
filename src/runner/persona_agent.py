import json
import re

import yaml
from jinja2 import Template


CORE_FIELDS = [
    "id",
    "name",
    "archetype",
    "identity_summary",
    "behavior_profile",
    "motivations",
    "decision_rules",
    "quit_triggers",
    "continue_triggers",
    "first_scan_focus",
    "review_output",
]


def _minify_persona(persona: dict) -> str:
    minified = {k: persona[k] for k in CORE_FIELDS if k in persona}
    return yaml.dump(minified, allow_unicode=True, default_flow_style=False).strip()


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


def render_prompt(
    persona: dict, task_type: str, artifact_summary: str, template_path: str, artifact_bundle: dict = None
):
    """返回纯文本 str，除非 artifact_bundle 里带了图片材料——那种情况下返回 OpenAI Vision
    格式的内容块列表 [{"type":"text",...}, {"type":"image_url",...}]，交给
    src/runner/llm_client.py 按目标 provider 转换成各自认的格式（见该模块 chat_completion）。
    文字材料（type=="text"）照旧渲染进模板正文；图片材料（type=="image"，
    image_data 是 data URI）单独拼成内容块，不进模板文本。"""
    with open(template_path, "r", encoding="utf-8") as f:
        template_str = f.read()

    template_str = _convert_handlebars_to_jinja2(template_str)

    persona_yaml_minified = _minify_persona(persona)
    mbti = persona.get("mbti", "")
    persona_name = persona.get("name", "")
    must_comment_on_items = persona.get("review_output", {}).get(
        "must_comment_on", []
    )
    decision_rules = persona.get("decision_rules", [])
    primary_decision_rule = decision_rules[0] if decision_rules else ""

    all_materials = []
    if artifact_bundle:
        all_materials = artifact_bundle.get("materials", [])
    artifact_materials = [m for m in all_materials if m.get("type") != "image"]
    image_materials = [m for m in all_materials if m.get("type") == "image" and m.get("image_data")]

    template = Template(template_str)
    text_prompt = template.render(
        persona_yaml_minified=persona_yaml_minified,
        mbti=mbti,
        persona_name=persona_name,
        persona_id=persona.get("id", ""),
        must_comment_on_items=must_comment_on_items,
        primary_decision_rule=primary_decision_rule,
        task_type=task_type,
        artifact_summary=artifact_summary,
        artifact_materials=artifact_materials,
    )

    if not image_materials:
        return text_prompt

    content = [{"type": "text", "text": text_prompt}]
    for m in image_materials:
        content.append({"type": "image_url", "image_url": {"url": m["image_data"]}})
    return content


def parse_persona_output(raw_output: str) -> dict:
    json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
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

    for obj_str in reversed(json_objects):
        try:
            return json.loads(obj_str)
        except json.JSONDecodeError:
            continue

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return {"parse_error": True, "raw_output": raw_output}


# 第三方模型常见的"同义字段名"——它们能理解任务但不肯照抄 schema 的字段名
# （实测 MiniMax-M3 会吐 evaluator_id / stance_rationale / dimension_analysis…）。
# prompt 里已经给了逐字骨架，这里是第二道保险：把变体名归一回规范名，
# 让报告不至于因为"名字没对上"就丢掉模型真正产出的内容。
_FIELD_ALIASES = {
    "persona_id": ("evaluator_id", "reviewer_id", "agent_id", "id"),
    "persona_name": ("evaluator_name", "reviewer_name", "agent_name", "name"),
    "primary_stance": ("stance", "overall_stance", "verdict"),
    "key_issues": ("issues", "problems", "concerns", "key_problems", "dimension_analysis"),
    "voice_sample": ("quote", "voice", "comment"),
    "missing_information": ("missing_info", "information_gaps", "gaps"),
    "evidence_sufficiency": ("evidence_score", "evidence_confidence"),
}

# key_issues 每项内部的字段变体
_ISSUE_ALIASES = {
    "title": ("issue", "problem", "name", "summary", "point"),
    "severity": ("level", "priority", "impact"),
    "why_it_matters": ("reason", "rationale", "why", "impact_description", "detail"),
    "suggested_fix": ("fix", "suggestion", "recommendation", "how_to_fix", "advice"),
}


# ---------------------------------------------------------------------------
# 子结构"形状"归一化
#
# 改名只是第一层问题。第三方模型连子结构的形状也不按 schema 给，实测三种：
#   {"evidence": ["文案不清晰"]}      → validator 里 e.get(...) 炸 AttributeError
#   {"key_issues": "无重大问题"}      → calibration 里 issue["title"] 炸 TypeError
#   {"missing_information": [{...}]}  → aggregator 的 seen_gaps.add(gap) 炸 unhashable
# 而 cli.py 的人格循环没有把 validator 调用包在 try 里，所以**一个**人格吐错形状
# 就让整个 run_panel 崩掉——前面 N 个人格的 API 钱已经花掉了，报告一个字都拿不到。
#
# 因此形状归一化只做在这一个边界上（模型输出刚解析完、还没进任何下游），
# 而不是去下游 20 个调用点各加一遍 isinstance：后者每新增一个调用点就会漏一次，
# 且 aggregator.py / cross_exam.py 也各有自己的形状假设，补不干净。
#
# 原则：归一化只改形状，不丢内容——字符串塞进该子结构语义上最贴的键里。
# ---------------------------------------------------------------------------

# 模型把文本塞进子结构时常用的键名，按"越可能是正文"排序
_TEXT_KEYS = (
    "content", "text", "description", "detail", "quote", "observation",
    "title", "name", "item", "gap", "info", "question", "summary", "value",
)


def _coerce_text(value) -> str:
    """把任意类型降成字符串，尽量不丢原文。

    下游有两类硬要求：一是 str 方法/正则（validator 的正则、模板渲染），
    二是 hashable（aggregator 用 set 给 missing_information 去重、
    用 primary_stance 当 dict 键）。dict/list 元素在这两处都会直接炸。
    """
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    if isinstance(value, dict):
        # 先找语义正文键；找不到就把整个 dict 摊平成 "键: 值"，宁可难看也不丢信息
        for key in _TEXT_KEYS:
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        return "; ".join(
            f"{k}: {_coerce_text(v)}" for k, v in value.items() if _coerce_text(v)
        )
    if isinstance(value, (list, tuple, set)):
        return "; ".join(t for t in (_coerce_text(v) for v in value) if t)
    return str(value)


def _coerce_list(value) -> list:
    """整体被吐成单个值（字符串/对象）时包成单元素列表；None 归一成空列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _coerce_text_list(value) -> list:
    """schema 里声明为 array of string 的字段：逐项降成非空字符串。"""
    return [t for t in (_coerce_text(item) for item in _coerce_list(value)) if t]


def _coerce_ratio(value, default: float = 0.5) -> float:
    """0-1 的比例字段。模型爱吐 "0.8" / "80%" / 8（十分制），
    而 aggregator 直接 sum(...)、cross_exam 直接 *100，字符串会 TypeError。"""
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
        num /= 10.0  # 十分制口径，按比例还原而不是直接夹到 1.0
    return max(0.0, min(1.0, num))


_EVIDENCE_TEXT_ALIASES = ("content", "text", "quote", "observation", "detail",
                          "description", "evidence", "fact")
_EVIDENCE_LEVEL_ALIASES = ("inference_level", "level", "inference", "type", "kind")
_EVIDENCE_LEVELS = ("direct", "inferred", "gap")
# 中文/变体写法映射回 schema 枚举
_LEVEL_SYNONYMS = {
    "直接": "direct", "直接证据": "direct", "原文": "direct", "quoted": "direct",
    "推断": "inferred", "推测": "inferred", "间接": "inferred", "inference": "inferred",
    "缺口": "gap", "缺失": "gap", "missing": "gap",
}
# 归一化补出来的 inference_level 要说明来源，否则报告读者会以为是模型自己标的。
# 用 inference_basis 承载（schema 允许该键），不新造 schema 外的字段。
_LEVEL_BACKFILL_NOTE = "模型未标注推断层级，归一化时按保守口径记为 inferred"


def _normalize_level(value) -> str:
    text = _coerce_text(value).lower()
    if text in _EVIDENCE_LEVELS:
        return text
    return _LEVEL_SYNONYMS.get(_coerce_text(value), "")


def _normalize_evidence(value) -> list:
    """evidence 归一成 [{"content": str, "inference_level": 枚举, ...}]。

    元素是字符串时包成 {"content": 原文}——保留原文，不丢证据。
    层级缺失/写错一律记 inferred 而不是 direct：direct 会让 validator 的
    grounding 检查和 calibration 的幻觉率去核对"原文出处"，而我们并不知道
    这句到底是不是原文照抄，谎报 direct 会让整份报告的幻觉率虚高。
    """
    normalized = []
    for item in _coerce_list(value):
        if isinstance(item, dict):
            content = ""
            for alias in _EVIDENCE_TEXT_ALIASES:
                if isinstance(item.get(alias), str) and item[alias].strip():
                    content = item[alias].strip()
                    break
            if not content:
                # 没有任何已知正文键：整个 dict 摊平进 content，信息不丢
                content = _coerce_text(item)
            level = ""
            for alias in _EVIDENCE_LEVEL_ALIASES:
                if alias in item:
                    level = _normalize_level(item[alias])
                    if level:
                        break
            source = _coerce_text(item.get("source_location") or item.get("source"))
            basis = _coerce_text(item.get("inference_basis") or item.get("basis"))
        else:
            content = _coerce_text(item)
            level, source, basis = "", "", ""

        if not content:
            continue

        # 只保留 schema 允许的键，顺手把 additionalProperties 违规也一并清掉
        entry = {"content": content, "inference_level": level or "inferred"}
        if not level and not basis:
            basis = _LEVEL_BACKFILL_NOTE
        if source:
            entry["source_location"] = source
        if basis:
            entry["inference_basis"] = basis
        normalized.append(entry)
    return normalized


def _normalize_key_issues(value) -> list:
    """key_issues 归一成 [{"title": str, "severity": ..., ...}]。

    整体是字符串（"无重大问题"）→ 包成单元素列表；元素是字符串 → 塞进 title。
    """
    if isinstance(value, dict):
        # 有的模型把 issues 写成 {维度: 描述} 的字典而非数组
        value = [
            {"title": _coerce_text(k), "why_it_matters": _coerce_text(v)}
            for k, v in value.items()
        ]

    normalized = []
    for item in _coerce_list(value):
        if not isinstance(item, dict):
            # 字符串/数字/嵌套列表：原文进 title，不静默丢弃
            item = {"title": _coerce_text(item)}
        else:
            item = dict(item)
            for canonical, aliases in _ISSUE_ALIASES.items():
                if item.get(canonical):
                    continue
                for alias in aliases:
                    if item.get(alias):
                        item[canonical] = item[alias]
                        break
            if not item.get("title"):
                # 一个键都对不上（比如 {"维度": "描述"}）：整条摊平进 title
                item["title"] = _coerce_text(item)

        # 下游（aggregator 拼 evidence_text、cross_exam 取 severity）都按 str 用
        item["title"] = _coerce_text(item.get("title"))
        item["severity"] = _coerce_text(item.get("severity")) or "medium"
        item["why_it_matters"] = _coerce_text(item.get("why_it_matters"))
        item["suggested_fix"] = _coerce_text(item.get("suggested_fix"))
        if item["title"]:
            normalized.append(item)
    return normalized


# 模型把"我已覆盖了哪些必答项"写成数组时的真值/假值词
_FALSEY_CHECK_TEXTS = {"", "false", "no", "n", "0", "否", "未覆盖", "未提及", "未涉及", "无"}


def _normalize_must_comment_check(value) -> dict:
    """must_comment_on_check 必须是 {项: bool}——validator 调 .values()、
    calibration 调 len()/.values()，列表进来就 AttributeError。
    模型常吐成"已覆盖项"的数组，那种情况按已覆盖处理。"""
    if isinstance(value, dict):
        return {
            _coerce_text(k): (
                bool(v) if not isinstance(v, str)
                else v.strip().lower() not in _FALSEY_CHECK_TEXTS
            )
            for k, v in value.items()
            if _coerce_text(k)
        }
    return {item: True for item in _coerce_text_list(value)}


def _normalize_scores(value) -> dict:
    """scores 归一成 {"base": {...}, "task_specific": {...}}——
    aggregator 对这两层是 .get() 链式取值，形状错了会 AttributeError。"""
    if not isinstance(value, dict):
        return {"base": {}, "task_specific": {}}
    scores = dict(value)
    base = scores.get("base")
    task_specific = scores.get("task_specific")
    if not isinstance(base, dict) or not isinstance(task_specific, dict):
        # 模型把维度分数直接平铺在 scores 顶层（没分 base/task_specific 两层）
        flat = {k: v for k, v in scores.items() if isinstance(v, (int, float))}
        base = base if isinstance(base, dict) else {
            k: flat[k] for k in ("clarity", "trust") if k in flat
        }
        task_specific = task_specific if isinstance(task_specific, dict) else {
            k: v for k, v in flat.items() if k not in ("clarity", "trust")
        }
    return {"base": base, "task_specific": task_specific}


# 声明为 array of string、下游按字符串用（去重/渲染/join）的字段
_TEXT_LIST_FIELDS = (
    "missing_information",      # aggregator: seen_gaps.add(gap) 要求 hashable
    "continue_triggers",
    "quit_triggers",
    "first_scan_observations",
)
# 声明为 string、下游拿去当 dict 键或直接拼字符串的字段
_TEXT_FIELDS = ("persona_id", "persona_name", "persona_version",
                "primary_stance", "voice_sample", "task_type")
# 声明为 0-1 number、下游直接参与算术的字段
_RATIO_FIELDS = ("confidence", "evidence_sufficiency")


def normalize_persona_output(output: dict) -> dict:
    """把模型吐回来的输出归一成 output-schema 的规范"名字"和规范"形状"。

    两层归一：
      1. 字段改名——只在规范名缺失时才从别名回填；
      2. 子结构形状——evidence / key_issues / missing_information 等按 schema
         声明的形状重建，元素类型不对时把原文塞进语义最贴的键。

    模型老实照抄骨架时此函数等于空操作，所以对 Claude 这类守规矩的模型零影响。
    """
    if not isinstance(output, dict) or output.get("parse_error"):
        return output

    for canonical, aliases in _FIELD_ALIASES.items():
        if output.get(canonical):
            continue
        for alias in aliases:
            if output.get(alias):
                output[canonical] = output[alias]
                break

    if "evidence" in output:
        output["evidence"] = _normalize_evidence(output["evidence"])
    if "key_issues" in output:
        output["key_issues"] = _normalize_key_issues(output["key_issues"])
    if "must_comment_on_check" in output:
        output["must_comment_on_check"] = _normalize_must_comment_check(
            output["must_comment_on_check"]
        )
    if "scores" in output:
        output["scores"] = _normalize_scores(output["scores"])

    for field in _TEXT_LIST_FIELDS:
        if field in output:
            output[field] = _coerce_text_list(output[field])
    for field in _TEXT_FIELDS:
        if field in output and not isinstance(output[field], str):
            output[field] = _coerce_text(output[field])
    for field in _RATIO_FIELDS:
        if field in output and not isinstance(output[field], (int, float)):
            output[field] = _coerce_ratio(output[field])

    meta = output.get("meta")
    if isinstance(meta, dict) and "caveats" in meta:
        meta["caveats"] = _coerce_text_list(meta["caveats"])

    return output


def estimate_cost(
    input_tokens: int, output_tokens: int, model: str, budget_config: dict = None
) -> float:
    if budget_config is None:
        with open(
            "src/config/budget.yaml", "r", encoding="utf-8"
        ) as f:
            budget_config = yaml.safe_load(f)

    pricing = budget_config.get("model_pricing", {}).get(model, {})
    input_price = pricing.get("input_per_mtok", 0.0)
    output_price = pricing.get("output_per_mtok", 0.0)

    cost = (input_tokens / 1_000_000) * input_price + (
        output_tokens / 1_000_000
    ) * output_price
    return cost


def select_model(persona: dict, budget_config: dict) -> str:
    """按人格的 model_hint 分级选真实 Anthropic 模型 ID（不是 "claude-sonnet" 这种占位别名——
    那种字符串传给 Anthropic API 会直接 404，见 budget.yaml 历史遗留的写法）。"""
    model_hint = persona.get("model_hint")
    if model_hint:
        model_map = {
            "haiku": budget_config.get("fallback_model", "claude-haiku-4-5-20251001"),
            "sonnet": budget_config.get("default_model", "claude-sonnet-4-20250514"),
            "opus": budget_config.get("premium_model", "claude-opus-4-20250514"),
        }
        return model_map.get(model_hint, f"claude-{model_hint}")
    return budget_config.get("default_model", "claude-sonnet-4-20250514")
