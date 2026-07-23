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


def normalize_persona_output(output: dict) -> dict:
    """把模型吐回来的变体字段名归一成 output-schema 的规范名。

    只在规范名缺失时才从别名回填（模型老实照抄骨架时此函数等于空操作），
    所以对 Claude 这类守规矩的模型零影响。
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

    issues = output.get("key_issues")
    if isinstance(issues, dict):
        # 有的模型把 issues 写成 {维度: 描述} 的字典而非数组
        issues = [
            {"title": str(k), "why_it_matters": v if isinstance(v, str) else str(v)}
            for k, v in issues.items()
        ]
        output["key_issues"] = issues

    if isinstance(issues, list):
        normalized = []
        for item in issues:
            if isinstance(item, str):
                normalized.append({"title": item, "severity": "medium",
                                   "why_it_matters": "", "suggested_fix": ""})
                continue
            if not isinstance(item, dict):
                continue
            for canonical, aliases in _ISSUE_ALIASES.items():
                if item.get(canonical):
                    continue
                for alias in aliases:
                    if item.get(alias):
                        item[canonical] = item[alias]
                        break
            item.setdefault("severity", "medium")
            item.setdefault("why_it_matters", "")
            item.setdefault("suggested_fix", "")
            if item.get("title"):
                normalized.append(item)
        output["key_issues"] = normalized

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
