"""人格分化消融实验。

回答核心问题：人格 prompt 是否真的让输出分化（而不是同一模型换语气）？
分化的贡献来自行为向量还是身份描述？

三个实验条件，同一份输入材料：
    full         完整人格 prompt（身份 + 行为向量 + 决策规则）
    no_behavior  去掉行为向量与决策/退出/继续规则，仅保留身份描述
    bare         无人格，通用评审者 prompt

分化度指标（每个条件内跨人格计算）：
    issue_divergence   议题集合分化度 = 1 - 平均成对议题相似度（语义/词法）
    severity_js        严重度分布的平均成对 Jensen-Shannon 散度
    stance_entropy     立场分布的归一化香农熵
"""

import json
import math
import os
import re
from itertools import combinations
from typing import List, Optional

try:
    from runner.similarity import get_issue_similarity
    from runner.persona_agent import parse_persona_output, render_prompt
except ImportError:
    from src.runner.similarity import get_issue_similarity
    from src.runner.persona_agent import parse_persona_output, render_prompt

CONDITIONS = ["full", "no_behavior", "bare"]

# 行为向量条件下要剥离的字段
BEHAVIOR_FIELDS = [
    "behavior_profile",
    "decision_rules",
    "quit_triggers",
    "continue_triggers",
]

SEVERITY_LEVELS = ["low", "medium", "high", "critical"]

BARE_PROMPT_TEMPLATE = """你是一名游戏评审员。请评审以下材料并输出 JSON（字段：primary_stance, confidence, key_issues[{{title, severity, why_it_matters, suggested_fix}}], voice_sample）。severity 取值 low/medium/high/critical。

任务类型：{task_type}

评审材料：
{artifact_summary}

只输出 JSON。"""


# ---------------- 指标（纯函数，离线可测） ----------------

def issue_set_similarity(titles_a: List[str], titles_b: List[str], sim) -> float:
    """两个议题集合的对称平均最大相似度。"""
    if not titles_a or not titles_b:
        return 0.0

    def _directed(src, dst):
        return sum(max(sim.similarity(a, b) for b in dst) for a in src) / len(src)

    return (_directed(titles_a, titles_b) + _directed(titles_b, titles_a)) / 2


def issue_divergence(outputs: List[dict], sim=None) -> float:
    """议题分化度：1 - 跨人格平均成对议题相似度。越高越分化。"""
    if sim is None:
        sim = get_issue_similarity()
    title_sets = [
        [i.get("title", "") for i in o.get("key_issues", []) if i.get("title")]
        for o in outputs
    ]
    pairs = list(combinations(range(len(title_sets)), 2))
    if not pairs:
        return 0.0
    total = sum(
        issue_set_similarity(title_sets[i], title_sets[j], sim) for i, j in pairs
    )
    return 1 - total / len(pairs)


def _severity_distribution(output: dict) -> List[float]:
    counts = [0.0] * len(SEVERITY_LEVELS)
    for issue in output.get("key_issues", []):
        sev = issue.get("severity", "low")
        if sev in SEVERITY_LEVELS:
            counts[SEVERITY_LEVELS.index(sev)] += 1
    total = sum(counts)
    if total == 0:
        return [1.0 / len(SEVERITY_LEVELS)] * len(SEVERITY_LEVELS)
    return [c / total for c in counts]


def _js_divergence(p: List[float], q: List[float]) -> float:
    def _kl(a, b):
        return sum(
            ai * math.log2(ai / bi) for ai, bi in zip(a, b) if ai > 0 and bi > 0
        )

    m = [(pi + qi) / 2 for pi, qi in zip(p, q)]
    return (_kl(p, m) + _kl(q, m)) / 2


def severity_js(outputs: List[dict]) -> float:
    """严重度分布的平均成对 JS 散度（0~1，越高越分化）。"""
    dists = [_severity_distribution(o) for o in outputs]
    pairs = list(combinations(range(len(dists)), 2))
    if not pairs:
        return 0.0
    return sum(_js_divergence(dists[i], dists[j]) for i, j in pairs) / len(pairs)


def stance_entropy(outputs: List[dict]) -> float:
    """立场分布的归一化香农熵（0~1，越高越分化）。"""
    stances = [o.get("primary_stance", "") for o in outputs if o.get("primary_stance")]
    if len(stances) <= 1:
        return 0.0
    counts = {}
    for s in stances:
        counts[s] = counts.get(s, 0) + 1
    n = len(stances)
    entropy = -sum((c / n) * math.log2(c / n) for c in counts.values())
    max_entropy = math.log2(len(stances))
    return entropy / max_entropy if max_entropy > 0 else 0.0


def compute_condition_metrics(outputs: List[dict], sim=None) -> dict:
    return {
        "persona_count": len(outputs),
        "issue_divergence": round(issue_divergence(outputs, sim), 4),
        "severity_js": round(severity_js(outputs), 4),
        "stance_entropy": round(stance_entropy(outputs), 4),
    }


# ---------------- 条件构造 ----------------

def strip_behavior_fields(persona: dict) -> dict:
    return {k: v for k, v in persona.items() if k not in BEHAVIOR_FIELDS}


def build_condition_prompt(
    condition: str,
    persona: dict,
    task_type: str,
    artifact_summary: str,
    persona_prompt_path: str,
    artifact_bundle: Optional[dict] = None,
) -> str:
    if condition == "bare":
        return BARE_PROMPT_TEMPLATE.format(
            task_type=task_type, artifact_summary=artifact_summary
        )
    if condition == "no_behavior":
        persona = strip_behavior_fields(persona)
    return render_prompt(
        persona, task_type, artifact_summary, persona_prompt_path, artifact_bundle
    )


# ---------------- 实验执行 ----------------

def _call_llm(client, model: str, prompt: str) -> Optional[dict]:
    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        try:
            return parse_persona_output(raw)
        except Exception:
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return None
    except Exception:
        return None


def run_ablation(
    personas: List[dict],
    task_type: str,
    artifact_bundle: dict,
    persona_prompt_path: str,
    model: str = "claude-haiku-4-5-20251001",
    conditions: Optional[List[str]] = None,
    client=None,
    progress=None,
) -> dict:
    """对同一材料在多个条件下运行人格面板并计算分化度指标。

    需要可用的 anthropic client（实验无模拟档——模拟数据测分化没有意义）。
    """
    if conditions is None:
        conditions = CONDITIONS
    if client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "消融实验需要 ANTHROPIC_API_KEY：模拟数据上测分化度没有意义"
            )
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

    artifact_summary = artifact_bundle.get("title", "")
    sim = get_issue_similarity()

    results = {}
    for condition in conditions:
        outputs = []
        failures = 0
        for persona in personas:
            prompt = build_condition_prompt(
                condition,
                persona,
                task_type,
                artifact_summary,
                persona_prompt_path,
                artifact_bundle,
            )
            output = _call_llm(client, model, prompt)
            if output is None:
                failures += 1
                continue
            output.setdefault("persona_id", persona.get("id", "bare"))
            outputs.append(output)
            if progress:
                progress(condition, persona.get("id", "?"))
        metrics = compute_condition_metrics(outputs, sim)
        metrics["failures"] = failures
        results[condition] = metrics

    return {
        "task_type": task_type,
        "model": model,
        "similarity_method": sim.method,
        "conditions": results,
    }
