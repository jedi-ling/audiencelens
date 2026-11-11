import json
import os
import re
import unicodedata
from typing import List, Optional

import jsonschema
import yaml


def load_schema(schema_path: str) -> dict:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


# evidence / key_issues 必须是对象数组。模型的工具输入损坏时，这里会变成一段字符串，
# 里面是工具调用标记（<invoke …>、<parameter name="content">…）而不是数据。
MALFORMED_LIST_FIELDS = ("evidence", "key_issues")
_TOOL_MARKUP_RE = re.compile(r"</?\s*(?:antml:)?(?:invoke|parameter|function_calls|tool_use|tool_call)\b", re.IGNORECASE)


def is_tool_markup_string(value) -> bool:
    """这个值是不是"本该是列表、却是一段工具调用标记字符串"。

    只认带标记的字符串：模型把整个字段写成一句普通的话（"整体就一句话"）是另一回事，
    归一化会把它包成一条证据，信息没丢。带标记的字符串里没有可用的内容，包成一条
    inferred 证据只会把"工具输入坏了"伪装成"推断过度"（2026-11-11 实测：P15 因此被判
    role_drift，而 role_drift 不重试）。
    """
    return isinstance(value, str) and bool(_TOOL_MARKUP_RE.search(value))


def malformed_list_field_errors(output: dict) -> List[str]:
    """给 MALFORMED_LIST_FIELDS 里形状损坏的字段各出一条具体的 schema 错误。"""
    errors = []
    for field in MALFORMED_LIST_FIELDS:
        if is_tool_markup_string((output or {}).get(field)):
            errors.append(
                f"{field}: 收到的是一段含工具调用标记的字符串，不是对象数组——工具输入格式损坏，"
                "请把它作为 JSON 数组重新提交，字段值里不要出现 <invoke> / <parameter> 之类的标签"
            )
    return errors


def validate_schema(output: dict, schema: dict) -> dict:
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(output), key=lambda e: list(e.path))
    error_messages = [f"{'.'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors]
    specific = malformed_list_field_errors(output) if isinstance(output, dict) else []
    if specific:
        # jsonschema 对这些字段报的是 "evidence: '<整段标记>' is not of type 'array'"——把原串
        # 回显一遍对谁都没用；换成一句说清楚发生了什么的话，放在最前面。
        damaged = {m.split(":", 1)[0] for m in specific}
        error_messages = specific + [m for m in error_messages if m.split(":", 1)[0] not in damaged]
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


# 推断占比的硬上限。单一事实源：validator 用它拦人格（超了记 role_drift），
# aggregator 用它给整份报告算证据构成（evidence_profile.threshold），
# 前端展示的"40%"也来自报告里的这个值——三处引用一个常量，改档只改这里。
MAX_INFERRED_RATIO = 0.4


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
    if inferred_ratio > MAX_INFERRED_RATIO:
        issues.append(f"推断过度: inferred比例{inferred_ratio:.0%}超过{MAX_INFERRED_RATIO:.0%}")

    consistent = len(issues) == 0
    return {
        "consistent": consistent,
        "must_comment_on_coverage": coverage,
        "inferred_ratio": inferred_ratio,
        "issues": issues,
    }


GROUNDING_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "grounding.yaml"
)
# 人格级门槛，未改动：direct 证据里"未落地"的占比达到 30% 即判该人格未通过。
MAX_UNGROUNDED_DIRECT_SHARE = 0.3

_grounding_config_cache: Optional[dict] = None


def load_grounding_config(path: Optional[str] = None) -> dict:
    """读 src/config/grounding.yaml（逐条 direct 证据的覆盖率规则参数）。

    参数是在 tests/fixtures/grounding_eval 的 dev 划分上选的，不写死在代码里；
    缺文件或缺键直接报错——静默回落到某个默认值等于换了一条没人测过的规则。
    """
    global _grounding_config_cache
    if path is None and _grounding_config_cache is not None:
        return _grounding_config_cache
    with open(path or GROUNDING_CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    for key in ("min_span_cjk_chars", "min_span_latin_words", "coverage_threshold",
                "require_numbers_covered", "framing"):
        if key not in config:
            raise KeyError(f"grounding config 缺少 {key}")
    if path is None:
        _grounding_config_cache = config
    return config


_QUOTE_CHARS = "“”„‟«»「」『』﹁﹂﹃﹄‘’‚‛'`´"
_DASH_CHARS = "‐‑‒–—―−﹣"
_NORMALIZE_TABLE = {ord(c): '"' for c in _QUOTE_CHARS}
_NORMALIZE_TABLE.update({ord(c): "-" for c in _DASH_CHARS})

_CJK = r"぀-ヿ㐀-䶿一-鿿豈-﫿"
# 数字（含 8,000 / 19.99 这种带分隔符的写法）| 单个 CJK 字 | 非 CJK 的词
_TOKEN_RE = re.compile(rf"(\d+(?:[.,]\d+)*)|([{_CJK}])|((?:(?![{_CJK}])[^\W\d_])+)")


def normalize_grounding_text(text: str) -> str:
    """NFKC（全角→半角）、统一引号与破折号、大小写折叠、空白压成单个空格。"""
    text = unicodedata.normalize("NFKC", text or "").translate(_NORMALIZE_TABLE)
    # NFKC 之后才出现的全角引号也并进来
    text = text.replace("＂", '"').replace("＇", '"')
    return re.sub(r"\s+", " ", text.casefold()).strip()


def _grounding_tokens(normalized: str) -> List[tuple]:
    """[(token, kind, start, end)]，kind ∈ n(数字) / c(CJK 字) / w(词)。标点与空白不产生 token。"""
    out = []
    for m in _TOKEN_RE.finditer(normalized):
        kind = "n" if m.group(1) else ("c" if m.group(2) else "w")
        out.append((m.group(0), kind, m.start(), m.end()))
    return out


def _token_units(kind: str, config: dict) -> float:
    if kind == "c":
        return 1.0 / float(config["min_span_cjk_chars"])
    return 1.0 / float(config["min_span_latin_words"])


def _framing_token_count(normalized: str, tokens: List[tuple], config: dict) -> int:
    """entry 开头那段"页面写着：/ The page says \""引导语占了几个 token；不是引导语则 0。"""
    framing = config.get("framing") or {}
    # 词内撇号（devlog's）规范化后也是 "，但它不是引号：两侧都是拉丁字母的不算分隔符。
    m = re.search(r':|"(?!(?<=[a-z\u00c0-\u024f]")[a-z\u00c0-\u024f])', normalized)
    cut = m.start() if m else -1
    if cut <= 0:
        return 0
    prefix = normalized[:cut]
    prefix_tokens = [t for t in tokens if t[3] <= cut]
    if not prefix_tokens or len(prefix_tokens) == len(tokens):
        return 0
    cjk = sum(1 for t in prefix_tokens if t[1] == "c")
    latin = len(prefix_tokens) - cjk
    size = cjk / float(framing.get("max_cjk_chars") or 1) + latin / float(framing.get("max_latin_words") or 1)
    if size > 1.0:
        return 0
    if any(cue in prefix for cue in framing.get("cues_cjk") or []):
        return len(prefix_tokens)
    for cue in framing.get("cues_latin") or []:
        if re.search(rf"(?<![^\W\d_]){re.escape(cue)}(?![^\W\d_])", prefix):
            return len(prefix_tokens)
    return 0


class _MaterialIndex:
    def __init__(self, artifact_texts: List[str]):
        self.tokens: List[Optional[str]] = []
        for text in artifact_texts:
            if not isinstance(text, str):
                continue
            self.tokens.extend(t[0] for t in _grounding_tokens(normalize_grounding_text(text)))
            self.tokens.append(None)  # 材料之间的哨兵：匹配不能跨材料
        self.positions: dict = {}
        for i, tok in enumerate(self.tokens):
            if tok is not None:
                self.positions.setdefault(tok, []).append(i)

    def longest_match(self, tokens: List[tuple], start: int) -> int:
        best = 0
        n = len(tokens)
        for p in self.positions.get(tokens[start][0], ()):
            length = 1
            while (start + length < n and p + length < len(self.tokens)
                   and self.tokens[p + length] == tokens[start + length][0]):
                length += 1
            if length > best:
                best = length
        return best


def check_entry_grounding(content, material, config: Optional[dict] = None) -> dict:
    """单条 direct 证据的覆盖率判定。material：材料文本列表，或一个已建好的 _MaterialIndex。

    返回 grounded / coverage / uncovered（没在材料里找到的片段，规范化后的文本）/
    uncovered_numbers（落在未覆盖部分的数字）。覆盖率衡量的是"这条有多少是材料原文"，
    不是"这条说得对不对"。
    """
    config = config or load_grounding_config()
    index = material if isinstance(material, _MaterialIndex) else _MaterialIndex(list(material or []))
    normalized = normalize_grounding_text(content if isinstance(content, str) else "")
    tokens = _grounding_tokens(normalized)
    tokens = tokens[_framing_token_count(normalized, tokens, config):]
    if not tokens:
        return {"grounded": False, "coverage": 0.0, "uncovered": [normalized] if normalized else [],
                "uncovered_numbers": []}

    covered = [False] * len(tokens)
    i = 0
    while i < len(tokens):
        length = index.longest_match(tokens, i)
        if length and sum(_token_units(t[1], config) for t in tokens[i:i + length]) >= 1.0:
            for j in range(i, i + length):
                covered[j] = True
            i += length
        else:
            i += 1

    total = sum(_token_units(t[1], config) for t in tokens)
    hit = sum(_token_units(t[1], config) for t, c in zip(tokens, covered) if c)
    coverage = hit / total if total else 0.0

    uncovered, numbers = [], []
    i = 0
    while i < len(tokens):
        if covered[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(tokens) and not covered[j + 1]:
            j += 1
        uncovered.append(normalized[tokens[i][2]:tokens[j][3]])
        numbers.extend(t[0] for t in tokens[i:j + 1] if t[1] == "n")
        i = j + 1

    grounded = coverage >= float(config["coverage_threshold"])
    if config.get("require_numbers_covered") and numbers:
        grounded = False
    return {"grounded": grounded, "coverage": round(coverage, 4), "uncovered": uncovered,
            "uncovered_numbers": numbers}


def check_direct_entry(entry: dict, material, config: Optional[dict] = None,
                       allow_content_fallback: bool = False) -> dict:
    """一条 direct 证据是否落地：只核对 `quote`（材料原文的逐字片段），`content` 是人格
    自己的观察/解读，不核对。

    - 有 quote：对 quote 跑覆盖率规则（check_entry_grounding，参数同一份 grounding.yaml）。
    - 没有 / 为空：未落地，reason = "quote_missing"。
    - allow_content_fallback=True：没有 quote 时退回去核对 content。只给 quote 字段出现
      之前存下来的旧输出用（examples/ 里 2026-11-04 的样例、评测集里的旧形状条目），
      引擎的校验路径不开。

    返回 check_entry_grounding 的字段，外加 checked（"quote" / "content" / "none"）
    和 reason（None / "quote_missing" / "quote_not_found"）。
    """
    quote = entry.get("quote") if isinstance(entry, dict) else None
    if isinstance(quote, str) and quote.strip():
        result = check_entry_grounding(quote, material, config)
        result["checked"] = "quote"
    elif allow_content_fallback:
        result = check_entry_grounding(entry.get("content", ""), material, config)
        result["checked"] = "content"
    else:
        return {"grounded": False, "coverage": 0.0, "uncovered": [], "uncovered_numbers": [],
                "checked": "none", "reason": "quote_missing"}
    result["reason"] = None if result["grounded"] else "quote_not_found"
    return result


def validate_evidence_grounding(output: dict, artifact_texts: List[str], config: Optional[dict] = None,
                                allow_content_fallback: bool = False) -> dict:
    """逐条核对 direct 证据的 `quote` 是否落在材料原文上（覆盖率规则，参数见
    src/config/grounding.yaml）。direct 条目缺 quote = 未落地。

    两次改动的来由：
    1. 旧规则是"按标点/空白切开后，任意一个长度 > 1 的片段是材料子串就算落地"——
       「一句真引用 + 一句编造」整条通过，英文任何一个词（the、is）都能让整条通过。
       外部评审指出后改成覆盖率规则。
    2. 覆盖率规则直接套在 content 上时，已发布样例里 12 位人格只有 1 位能过：模型把引用和
       自己的评论写在同一个字段里。所以把数据形状拆开——quote 放原文、content 放解读——
       而不是放宽规则。实测见 docs/evaluation/grounding-check.md。

    中文引号、破折号、全半角、空白差异在规范化阶段抹平（Balatro 材料下曾 4/6 人格被误伤）。

    allow_content_fallback：见 check_direct_entry，只用于复核 quote 字段出现之前的旧输出。

    返回里的 `hallucination_risk` 键名为兼容保留，含义是 **direct 证据中未落地条目的占比**
    （0–1），不是"幻觉概率"。content 里说了什么不在这项检查之内。
    """
    config = config or load_grounding_config()
    evidence = _dict_entries(output.get("evidence", []))
    index = _MaterialIndex(list(artifact_texts or []))
    ungrounded = []
    details = []
    total_direct = 0

    for position, entry in enumerate(evidence):
        if entry.get("inference_level") != "direct":
            continue
        total_direct += 1
        content = entry.get("content", "")
        result = check_direct_entry(entry, index, config, allow_content_fallback)
        if not result["grounded"]:
            ungrounded.append(content)
            details.append({"index": position, "content": content,
                            "quote": entry.get("quote") if isinstance(entry.get("quote"), str) else None,
                            "checked": result["checked"], "reason": result["reason"],
                            "coverage": result["coverage"],
                            "uncovered": result["uncovered"],
                            "uncovered_numbers": result["uncovered_numbers"]})

    if total_direct == 0:
        hallucination_risk = 0.0
    else:
        hallucination_risk = len(ungrounded) / total_direct

    grounded = hallucination_risk < MAX_UNGROUNDED_DIRECT_SHARE
    return {
        "grounded": grounded,
        "ungrounded_evidence": ungrounded,
        "ungrounded_details": details,
        # 兼容键名；含义 = direct 证据中未落地条目的占比，不是幻觉概率。
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
