"""两层评审的第一层：全包初筛（triage）。

背景：面板此前是"选人后直接截断"——truncate_panel 按档位切到 3/6/8，
包里其余人格的视角是被**扔掉**的，不是被便宜地用掉的。对外说 72 个人格，
单次评审用户只见到几个，落差迟早被问（实际已经被问了）。

这一层把流程改成：

    L1 全包初筛（本模块）      每位人格一次**廉价短调用**：只产出立场 +
                              严重度 + 一句话核心关切，不做完整评审
    ↓ 门禁（rank_for_advance）按严重度与立场分歧排序，保底异见者
    L2 深评（既有流程）        胜出者进完整评审 + 交叉质询

三条设计红线：

1. **初筛结论只用于选人，绝不混进正式结论。** 初筛是廉价模型 + 截断材料
   跑出来的粗筛信号，质量低于完整评审一个档位。报告里它放在独立的
   report["triage"] 块，标明"初筛意见，非正式评审结论"。

2. **材料截断必须留痕。** 初筛为控成本会截断超长材料（TRIAGE_MATERIAL_CHARS）。
   截没截、截到多少，写进 triage 块——"全包人格都看过材料"这句话的真实
   含义必须可查，否则就是那种"听起来全面"的假话。

3. **选择理由逐人可查。** 谁晋级、为什么（severity / 少数派立场 / 异见者
   保底），谁没晋级，全部写进报告。门禁是确定性排序，不是又一次模型调用
   ——用模型选人等于把"选谁"也变成不可复现的黑箱。
"""

import concurrent.futures
import json
import os
import re
from typing import Callable, Dict, List, Optional, Tuple

# 初筛时材料的最大字符数。超长材料截断到这个长度——初筛只需要"这是什么、
# 大概什么状况"的判断力，不需要逐字精读；逐字精读是 L2 深评的事。
TRIAGE_MATERIAL_CHARS = 4000

# 初筛输出里认可的严重度（与正式评审同一词表），排序权重越大越优先晋级。
SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}

TRIAGE_PROMPT_TEMPLATE = """你是评审团初筛环节中的一位评审员。你的人格设定：

{persona_brief}

待评审材料（{truncation_note}）：
---
{materials}
---

任务类型：{task_type}

这是**初筛**：不需要完整评审，只回答三件事。只输出一个 JSON 对象，不要其他文字：
{{"stance": "你的初步立场（一个词或短语）", "severity": "你最担心的问题的严重度，取 critical/high/medium/low 之一", "top_concern": "你最担心的一个问题，一句话"}}"""


def build_triage_prompt(persona: dict, task_type: str, artifact_bundle: dict) -> Tuple[str, bool]:
    """返回 (prompt, materials_truncated)。

    人格设定只带身份摘要与前两条决策规则——初筛调用的成本大头是输入 token，
    全量人格卡（行为轴、必答项、证据需求）是深评的事。
    """
    rules = persona.get("decision_rules", [])[:2]
    brief_parts = [
        f"{persona.get('name', persona.get('id', ''))}（{persona.get('archetype', '')}）",
        persona.get("identity_summary", ""),
    ]
    for r in rules:
        brief_parts.append(f"- 决策规则：{r}")
    persona_brief = "\n".join(p for p in brief_parts if p)

    texts = []
    for m in artifact_bundle.get("materials", []) or []:
        if m.get("type") == "image":
            continue
        # is_context 材料（项目历史等背景）不进初筛：初筛只判断本次材料本身
        if m.get("is_context") is True:
            continue
        body = m.get("description") or m.get("text") or ""
        if body:
            texts.append(f"[{m.get('type', 'text')}] {body}")
    materials = "\n\n".join(texts)

    truncated = len(materials) > TRIAGE_MATERIAL_CHARS
    if truncated:
        materials = materials[:TRIAGE_MATERIAL_CHARS] + "\n…（材料超长，初筛截断到此；深评阶段读完整材料）"

    prompt = TRIAGE_PROMPT_TEMPLATE.format(
        persona_brief=persona_brief,
        truncation_note="已截断，见末尾说明" if truncated else "完整",
        materials=materials or "（无文字材料）",
        task_type=task_type,
    )
    return prompt, truncated


def parse_triage_output(raw: str, persona: dict) -> Optional[dict]:
    """解析初筛 JSON。解析失败返回 None——失败的初筛不编造立场，
    该人格按"初筛失败"处理（不晋级也不进统计，报告里如实列出）。"""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    stance = str(data.get("stance", "")).strip()
    severity = str(data.get("severity", "")).strip().lower()
    concern = str(data.get("top_concern", "")).strip()
    if not stance:
        return None
    if severity not in SEVERITY_RANK:
        severity = "medium"  # 词表外的严重度按中档记，不猜高也不猜低
    return {
        "persona_id": persona.get("id", ""),
        "persona_name": persona.get("name", persona.get("id", "")),
        "stance": stance[:60],
        "severity": severity,
        "top_concern": concern[:200],
    }


def simulated_triage(persona: dict, index: int) -> dict:
    """模拟模式（无 API key）的占位初筛。立场按序号轮换，制造确定性的
    "分歧"让门禁逻辑可测——与 _build_simulated_output 同一思路。"""
    stances = ["看好", "观望", "不看好"]
    severities = ["low", "medium", "high", "critical"]
    return {
        "persona_id": persona.get("id", ""),
        "persona_name": persona.get("name", persona.get("id", "")),
        "stance": stances[index % len(stances)],
        "severity": severities[index % len(severities)],
        "top_concern": "模拟初筛意见（无 API key）",
    }


def rank_for_advance(
    triage_results: List[dict],
    max_advance: int,
    dissenter_id: Optional[str] = None,
) -> Tuple[List[dict], List[dict]]:
    """门禁：确定性排序，返回 (晋级, 未晋级)，两边都带 advanced_reason /
    not_advanced_reason。

    排序目标是**分歧信号最大化**，不是"选最悲观的"：
      1. 异见者保底（与 panel_selector.PACK_DISSENTERS 同一条纪律——
         全员和气的面板不值得付深评的钱）
      2. 严重度降序：喊 critical 的人格必须进深评把话说完
      3. 少数派立场加权：立场与多数不同的人格携带对质机制需要的燃料
      4. 同分按 persona_id 字典序——排序必须可复现，不引入随机性
    """
    if not triage_results:
        return [], []

    stance_counts: Dict[str, int] = {}
    for r in triage_results:
        stance_counts[r["stance"]] = stance_counts.get(r["stance"], 0) + 1
    majority = max(stance_counts.values())

    def score(r: dict) -> Tuple:
        sev = SEVERITY_RANK.get(r["severity"], 2)
        minority_bonus = 1 if stance_counts[r["stance"]] < majority else 0
        return (-sev, -minority_bonus, r["persona_id"])

    ranked = sorted(triage_results, key=score)

    advanced: List[dict] = []
    seen = set()

    # 异见者保底：占一个名额，且必须真的在初筛结果里（可能被证据预检跳过）
    if dissenter_id:
        for r in ranked:
            if r["persona_id"] == dissenter_id:
                advanced.append({**r, "advanced_reason": "dissenter_guarantee"})
                seen.add(dissenter_id)
                break

    for r in ranked:
        if len(advanced) >= max_advance:
            break
        if r["persona_id"] in seen:
            continue
        sev = SEVERITY_RANK.get(r["severity"], 2)
        minority = stance_counts[r["stance"]] < majority
        reason = (
            "severity_critical" if r["severity"] == "critical"
            else "minority_stance" if minority
            else "severity_rank"
        )
        advanced.append({**r, "advanced_reason": reason})
        seen.add(r["persona_id"])

    not_advanced = [
        {**r, "not_advanced_reason": "below_cutoff"}
        for r in ranked
        if r["persona_id"] not in seen
    ]
    return advanced, not_advanced


def run_triage(
    personas: List[dict],
    task_type: str,
    artifact_bundle: dict,
    call_llm: Optional[Callable[[str], Tuple[str, int, int]]] = None,
    max_concurrency: Optional[int] = None,
) -> dict:
    """跑全包初筛。call_llm=None 即模拟模式（与主流程的 simulation 判定一致，
    由调用方决定）。call_llm 接收 prompt，返回 (文本, input_tokens, output_tokens)
    ——模型选择、key、provider 全部由调用方闭包掉，本模块不碰凭据。

    max_concurrency：并发上限，与人格深评共用同一个旋钮（cli.run_panel 传进来，
    默认读 AUDIENCELENS_MAX_CONCURRENCY）。
    """
    results: List[dict] = []
    failures: List[dict] = []
    truncated_any = False
    total_in = total_out = 0

    # 模拟模式没有任何 I/O，原地串行生成，不为了对称白开线程池
    if call_llm is None:
        return {
            "results": [simulated_triage(p, i) for i, p in enumerate(personas)],
            "failures": failures,
            "materials_truncated": False,
            "material_char_limit": TRIAGE_MATERIAL_CHARS,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    prompts = []
    for persona in personas:
        prompt, truncated = build_triage_prompt(persona, task_type, artifact_bundle)
        truncated_any = truncated_any or truncated
        prompts.append(prompt)

    def _screen_one(persona: dict, prompt: str) -> dict:
        """单人初筛。**不碰任何共享状态**——token 数和成败都放进返回值，
        由主线程汇总。这样并发路径一把锁都不需要，也就不存在 `+=` 丢计数的问题。"""
        try:
            raw, tin, tout = call_llm(prompt)
        except Exception as e:  # 单个人格初筛失败不拖垮整层——如实记失败
            return {"ok": False, "error": str(e)[:200], "in": 0, "out": 0}
        parsed = parse_triage_output(raw, persona)
        if parsed is None:
            # token 照记：解析失败的这次调用钱是真花了
            return {"ok": False, "error": "unparseable_output", "in": tin, "out": tout}
        return {"ok": True, "parsed": parsed, "in": tin, "out": tout}

    # 初筛是每人一次独立的 I/O 等待型调用，串行跑等于 17 个人格排队等 17 次往返，
    # L2 深评要等到最后一个回来才能开始。与 cli._run_batch 同样用线程池并发，
    # 并**按提交顺序**收 future 结果——晋级排序虽然是确定性的，但输入顺序变了
    # 同分时的字典序兜底就未必稳定，报告里"谁晋级"这种事不能随线程调度漂。
    workers = max(1, min(int(max_concurrency or os.environ.get("AUDIENCELENS_MAX_CONCURRENCY", "6")),
                         len(personas))) if personas else 1
    if workers <= 1 or len(personas) <= 1:
        outcomes = [_screen_one(p, pr) for p, pr in zip(personas, prompts)]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_screen_one, p, pr) for p, pr in zip(personas, prompts)]
            outcomes = [f.result() for f in futures]

    for persona, outcome in zip(personas, outcomes):
        total_in += outcome["in"]
        total_out += outcome["out"]
        if outcome["ok"]:
            results.append(outcome["parsed"])
        else:
            failures.append({"persona_id": persona.get("id", ""), "error": outcome["error"]})

    return {
        "results": results,
        "failures": failures,
        "materials_truncated": truncated_any,
        "material_char_limit": TRIAGE_MATERIAL_CHARS,
        "input_tokens": total_in,
        "output_tokens": total_out,
    }
