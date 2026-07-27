import json
import re
from typing import List, Optional

import jsonschema


def load_schema(schema_path: str) -> dict:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(output: dict, schema: dict) -> dict:
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(output), key=lambda e: list(e.path))
    error_messages = [f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]
    return {"valid": len(error_messages) == 0, "errors": error_messages}


def _dict_entries(value) -> List[dict]:
    """只留 dict 元素。正常链路上 normalize_persona_output 已经把形状规整过了，
    但直接调 validator 的路径（老数据回放、单测、外部集成）没过那一道，
    第三方模型吐的 ["文案不清晰"] 会让 e.get(...) 炸 AttributeError——
    而 cli.py 的人格循环没有 try 包住这里，一个人格就能让整个 run_panel 崩掉。"""
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    return [e for e in value if isinstance(e, dict)]


def validate_role_consistency(output: dict, persona: dict) -> dict:
    issues = []
    must_comment_on_check = output.get("must_comment_on_check", {})
    if not isinstance(must_comment_on_check, dict):
        # 模型把它吐成数组时无法判断覆盖情况，按"无必答项"处理而不是崩掉
        must_comment_on_check = {}
    total = len(must_comment_on_check)
    if total == 0:
        coverage = 1.0
    else:
        covered = sum(1 for v in must_comment_on_check.values() if v is True)
        coverage = covered / total
    if coverage < 0.8:
        issues.append(f"角色漂移: must_comment_on覆盖率{coverage:.0%}低于80%")

    evidence = _dict_entries(output.get("evidence", []))
    inferred_count = sum(1 for e in evidence if e.get("inference_level") == "inferred")
    if len(evidence) == 0:
        inferred_ratio = 0.0
    else:
        inferred_ratio = inferred_count / len(evidence)
    if inferred_ratio > 0.4:
        issues.append(f"推断过度: inferred比例{inferred_ratio:.0%}超过40%")

    consistent = len(issues) == 0
    return {
        "consistent": consistent,
        "must_comment_on_coverage": coverage,
        "inferred_ratio": inferred_ratio,
        "issues": issues,
    }


def validate_evidence_grounding(output: dict, artifact_texts: List[str]) -> dict:
    evidence = _dict_entries(output.get("evidence", []))
    direct_entries = [e for e in evidence if e.get("inference_level") == "direct"]
    ungrounded = []

    for entry in direct_entries:
        content = entry.get("content", "")
        tokens = [t for t in re.split(r"[\s,，。.!！?？、：:；;()（）\[\]【】]+", content) if len(t) > 1]
        found = False
        for token in tokens:
            for text in artifact_texts:
                if token in text:
                    found = True
                    break
            if found:
                break
        if not found:
            ungrounded.append(content)

    total_direct = len(direct_entries)
    if total_direct == 0:
        hallucination_risk = 0.0
    else:
        hallucination_risk = len(ungrounded) / total_direct

    grounded = hallucination_risk < 0.3
    return {
        "grounded": grounded,
        "ungrounded_evidence": ungrounded,
        "hallucination_risk": hallucination_risk,
    }


def validate_output(
    output: dict,
    persona: dict,
    schema: dict,
    artifact_texts: Optional[List[str]] = None,
) -> dict:
    schema_result = validate_schema(output, schema)
    role_result = validate_role_consistency(output, persona)

    schema_valid = schema_result["valid"]
    role_consistent = role_result["consistent"]

    if artifact_texts is not None:
        evidence_result = validate_evidence_grounding(output, artifact_texts)
        evidence_grounded = evidence_result["grounded"]
    else:
        evidence_grounded = True

    passed = schema_valid and role_consistent and evidence_grounded

    return {
        "schema_valid": schema_valid,
        "role_consistent": role_consistent,
        "evidence_grounded": evidence_grounded,
        "passed": passed,
        "details": {
            "schema": schema_result,
            "role": role_result,
            "evidence": validate_evidence_grounding(output, artifact_texts) if artifact_texts is not None else None,
        },
    }


# 这条规则要抓的是"因为某人是某身份、所以会有某行为"的刻板推理。
# 旧正则 (?:作为[男女女性男性]|她|他).*?(?:所以|因此) 有三处错，实测会把正常中文判违规：
#   1. 字符类 [男女女性男性] 去重后其实只是 {男,女,性}，本意的"男性/女性"整词没写对，
#      还顺带让单个"性"字也能触发；改成显式 (?:男性|女性|男|女) 整词。
#   2. 裸 "他" 会命中「其他」「他们」「他人」「吉他」里的那个字。中文里"其他…所以"
#      密度极高，「其他玩家很容易困惑，所以建议加提示」这种纯 UX 建议直接被判违规；
#      aggregator 每条违规扣 10 分，5 条就把 ethics_score 打到 50 以下 →
#      compliance 变"驳回" + "全部评审结果需要人工复核"，正常报告被误杀。
#      用否定环视把这些词形排掉，只留独立的人称指代。
#      「他们」放行：中文里它是性别中立的泛指复数，「他们看不懂教程所以流失」说的是
#      群体行为而非身份刻板推理。「她们」保留：显式带性别，属于性别泛化。
#   3. ".*?" 会跨句子连结两件无关的事（「她提到教程。另外价格高，所以…」），
#      改成句内匹配（中间不允许出现句末标点），耦合本来就是句内现象。
_IDENTITY_BEHAVIOR_PATTERN = re.compile(
    r"(?:作为(?:男性|女性|男|女)|(?<![其吉])他(?![们人])|她)"
    r"[^。！？!?；;\n]*?"
    r"(?:所以|因此)"
)


def _walk_texts(value, label: str):
    """递归摊出结构里所有字符串，附带 "字段路径" 标签。

    伦理检查不能按固定形状取字段：模型换个形状（evidence 吐成字符串数组、
    key_issues 整体吐成一句话、问题写成 {维度: 描述}），违规文本就从缝里漏过去了。
    宁可多查几个字段——inference_basis 恰恰是刻板推理最爱藏的地方。"""
    if isinstance(value, str):
        if value:
            yield label, value
    elif isinstance(value, dict):
        for key, inner in value.items():
            yield from _walk_texts(inner, f"{label}.{key}")
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_texts(item, label)


def check_identity_behavior_decoupling(output: dict) -> dict:
    pattern = _IDENTITY_BEHAVIOR_PATTERN
    violations = []

    if isinstance(output, dict):
        for field in ("evidence", "key_issues"):
            for label, text in _walk_texts(output.get(field), field):
                for m in pattern.findall(text):
                    violations.append(f"{label}: {m}")

    return {
        "decoupled": len(violations) == 0,
        "violations": violations,
    }
