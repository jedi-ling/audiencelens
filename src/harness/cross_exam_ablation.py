"""交叉质询消融实验。

回答的问题**只有一个**：把交叉质询关掉，报告会变吗？

为什么需要单独一个模块，而不是复用 ablation.py：
    ablation.py 消融的是**人格 prompt**，它的三个指标（issue_divergence /
    severity_js / stance_entropy）全部算在 persona_outputs 上。而交叉质询发生在
    人格评审**之后**——它不改任何一位人格的原始输出，只改聚合出来的那份报告。
    拿分化度指标去测交叉质询，三档会得到完全相同的数字，因为输入根本没变。
    所以这里的指标全部算在 **report** 上。

三个实验条件（同一份材料、同一批人格输出）：
    none         不跑交叉质询（等价于 quick 档）
    moderated    一次仲裁式反驳（等价于 standard 档）
    multi_agent  每位涉事人格各一次反驳（等价于 full 档）

**为什么不能直接 run_panel(mode="quick"/"standard"/"full") 跑三遍**：
    REVIEW_MODE_CONFIG 里档位同时绑定了 max_personas（3/6/8）和 cross_examination，
    run_panel 会按档位调 truncate_panel 截人数。三档跑出来的差异里，人数和反驳
    各占多少无法分离——那是个混淆变量，实验做了也不能用。
    这里的做法：人格评审**只跑一次**，固定同一批 persona_outputs 当共同基线，
    再从基线分叉出三种反驳条件。交叉质询因此是唯一变量。顺带省掉 2/3 的人格评审开销。

**这个实验能证明什么、不能证明什么（先读这段再看数字）**：
    能证伪 —— 如果 delta_ratio 和 rank_churn 都是 0，交叉质询没有改变报告的任何
        结论，那它就是纯成本，这个结论是确定的。
    不能证实 —— 如果报告变了，本实验**不能**说明它变好了。change ≠ improvement。
        要回答"更好吗"，需要外部真值（建议采纳率 / 真人对照），见
        docs/product-validation.md 与 tools/benchmark_compare.py。
    结果 JSON 里的 `verdict` 字段严格按上面两条措辞，不会替你把"变了"读成"变好了"。
"""

import os
from typing import Callable, List, Optional

try:
    from runner.similarity import get_issue_similarity
    from runner.cross_exam import MODE_DERIVED, extract_controversy_points
except ImportError:
    from src.runner.similarity import get_issue_similarity
    from src.runner.cross_exam import MODE_DERIVED, extract_controversy_points

# 条件名 → 传给 run_cross_exam_stage 的 review mode。
# none 不发调用；moderated/multi_agent 分别对应 standard/full 档的反驳形态。
CONDITIONS = ["none", "moderated", "multi_agent"]

CONDITION_TO_REVIEW_MODE = {
    "moderated": "standard",
    "multi_agent": "full",
}

BASELINE_CONDITION = "none"


# ---------------- 指标（纯函数，离线可测，不需要 API Key） ----------------

def _fix_titles(report: dict) -> List[str]:
    return [
        f.get("issue", "")
        for f in report.get("priority_fixes", [])
        if f.get("issue")
    ]


def match_index(title: str, candidates: List[str], sim) -> Optional[int]:
    """在 candidates 里找与 title 最相似且过阈值的下标；找不到返回 None。

    用 sim.threshold 而不是另写一个阈值：修复项去重、共识聚类在报告里用的就是
    这一档，消融实验换一档会导致"同一条修复项在报告里算同一条、在实验里算两条"。
    """
    best_i, best_score = None, 0.0
    for i, cand in enumerate(candidates):
        score = sim.similarity(title, cand)
        if score >= sim.threshold and score > best_score:
            best_i, best_score = i, score
    return best_i


def fix_list_delta(baseline_titles: List[str], variant_titles: List[str], sim) -> dict:
    """两份优先修复项清单之间的增/删/位移。

    net_new    variant 里有、baseline 里匹配不到的条目数（交叉质询**新增**了什么）
    dropped    baseline 里有、variant 里匹配不到的条目数（交叉质询**删掉**了什么）
    rank_churn 两边都在的条目的平均排名位移，按清单长度归一化（0~1）
               —— 它单独拿出来，是为了把"重排"和"改变结论"分开：
               只重排说明反驳只动了优先级，没带来新议题。
    """
    matched_pairs = []
    unmatched_variant = 0
    for vi, title in enumerate(variant_titles):
        bi = match_index(title, baseline_titles, sim)
        if bi is None:
            unmatched_variant += 1
        else:
            matched_pairs.append((bi, vi))

    matched_baseline = {bi for bi, _ in matched_pairs}
    dropped = len(baseline_titles) - len(matched_baseline)

    if matched_pairs:
        span = max(len(baseline_titles), len(variant_titles), 2) - 1
        rank_churn = sum(abs(bi - vi) for bi, vi in matched_pairs) / len(matched_pairs) / span
    else:
        rank_churn = 0.0

    denom = max(len(baseline_titles), 1)
    return {
        "baseline_count": len(baseline_titles),
        "variant_count": len(variant_titles),
        "net_new": unmatched_variant,
        "dropped": dropped,
        "matched": len(matched_pairs),
        # 报告结论层面的改动幅度：新增 + 删除，按基线长度归一化
        "delta_ratio": round((unmatched_variant + dropped) / denom, 4),
        "rank_churn": round(min(rank_churn, 1.0), 4),
    }


def consensus_delta(baseline: dict, variant: dict, sim) -> dict:
    """共识 / 分歧划分的变化量。

    交叉质询若真的说服了谁，最该动的就是"这一点算共识还是算分歧"。
    """
    def _pts(report, key, sub):
        return [p for p in (report.get(key) or {}).get(sub, []) if isinstance(p, str)]

    b_agreed = _pts(baseline, "consensus", "agreed_points")
    v_agreed = _pts(variant, "consensus", "agreed_points")
    b_dis = [
        d.get("issue", "")
        for d in baseline.get("major_disagreements", [])
        if isinstance(d, dict) and d.get("issue")
    ]
    v_dis = [
        d.get("issue", "")
        for d in variant.get("major_disagreements", [])
        if isinstance(d, dict) and d.get("issue")
    ]

    def _unmatched(src, dst):
        return sum(1 for t in src if match_index(t, dst, sim) is None)

    return {
        "agreed_added": _unmatched(v_agreed, b_agreed),
        "agreed_removed": _unmatched(b_agreed, v_agreed),
        "disagreement_added": _unmatched(v_dis, b_dis),
        "disagreement_removed": _unmatched(b_dis, v_dis),
    }


def summarize_condition(baseline_report: dict, variant_report: dict,
                        cross_exam_data: Optional[dict], usage: dict, sim) -> dict:
    """把一个条件相对基线的全部差异汇成一行。"""
    fixes = fix_list_delta(_fix_titles(baseline_report), _fix_titles(variant_report), sim)
    ce = cross_exam_data or {}
    return {
        "cross_exam_mode": ce.get("mode", MODE_DERIVED),
        "is_live_debate": bool(ce.get("is_live_debate")),
        "controversy_points": len(ce.get("points", []) or []),
        "vote_changes": len(ce.get("vote_changes", []) or []),
        # 模型自称改票但没过 θ 阈值的，engine 会留在 suppressed_changes。
        # 它和 vote_changes 的比值直接反映 θ=0.15 这个猜测卡掉了多少——
        # 想校准 θ，看的就是这个数。
        "suppressed_changes": len(ce.get("suppressed_changes", []) or []),
        "failures": len(ce.get("failures", []) or []),
        "priority_fixes": fixes,
        "consensus": consensus_delta(baseline_report, variant_report, sim),
        "cost": {
            "calls": usage.get("calls", 0),
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": round(usage.get("cost", 0.0), 6),
        },
    }


def build_verdict(conditions: dict) -> dict:
    """把数字翻成一句不夸大的结论。

    措辞受限于本实验的设计（见模块 docstring）：只允许说"没变 / 变了"，
    不允许说"更好 / 更差"——那需要外部真值。
    """
    changed = []
    reshuffle_only = []
    unchanged = []
    for name, data in conditions.items():
        if name == BASELINE_CONDITION:
            continue
        fixes = data["priority_fixes"]
        cons = data["consensus"]
        content_changed = (
            fixes["net_new"] > 0
            or fixes["dropped"] > 0
            or any(v > 0 for v in cons.values())
        )
        if content_changed:
            changed.append(name)
        elif fixes["rank_churn"] > 0:
            reshuffle_only.append(name)
        else:
            unchanged.append(name)

    if changed:
        headline = (
            f"交叉质询改变了报告结论（{', '.join(changed)}）。"
            "注意：本实验只能证明**变了**，不能证明**变好了**——"
            "要回答后者需要建议采纳率或真人对照数据。"
        )
    elif reshuffle_only:
        headline = (
            f"交叉质询只改变了优先级排序（{', '.join(reshuffle_only)}），"
            "没有新增或删除任何结论。是否值这笔调用成本，取决于排序本身的价值。"
        )
    else:
        headline = (
            "交叉质询没有改变报告的任何结论。在本样本上它是纯成本——"
            "这一条是确定性结论，不需要外部真值即可成立。"
        )

    return {
        "headline": headline,
        "changed_conditions": changed,
        "reshuffle_only_conditions": reshuffle_only,
        "unchanged_conditions": unchanged,
        "caveat": (
            "单样本结果不可外推。改变率与成本需在多份材料上重复本实验后才有意义，"
            "且 change ≠ improvement。"
        ),
    }


# ---------------- 实验执行 ----------------

def run_cross_exam_ablation(
    task_type: str,
    artifact_bundle: dict,
    personas_path: Optional[str] = None,
    selected_personas: Optional[List[str]] = None,
    conditions: Optional[List[str]] = None,
    api_key: Optional[str] = None,
    progress: Optional[Callable[[str, str], None]] = None,
) -> dict:
    """人格评审跑一次，交叉质询跑 N 次，对比 N 份报告。

    需要真实 API Key：模拟模式下 run_cross_exam_stage 一次调用都不发，
    三个条件会退化成同一条派生摘要，实验没有意义。
    """
    try:
        from runner import cli as runner_cli
        from runner.task_types import default_personas_path
        from runner.aggregator import aggregate_report, load_aggregation_rules
    except ImportError:
        from src.runner import cli as runner_cli
        from src.runner.task_types import default_personas_path
        from src.runner.aggregator import aggregate_report, load_aggregation_rules

    effective_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not effective_key:
        raise RuntimeError(
            "交叉质询消融需要 ANTHROPIC_API_KEY："
            "模拟模式下一次反驳调用都不发，三个条件会退化成同一条派生摘要"
        )

    if conditions is None:
        conditions = CONDITIONS
    if BASELINE_CONDITION not in conditions:
        raise ValueError(
            f"条件列表必须含基线 '{BASELINE_CONDITION}'：所有指标都是相对基线算的"
        )

    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    personas_path = personas_path or default_personas_path(task_type, os.path.join(base, "src", "personas"))
    rules_path = os.path.join(base, "src", "config", "aggregation-rules.yaml")
    budget_path = os.path.join(base, "src", "config", "budget.yaml")
    template_path = os.path.join(base, "src", "templates", "cross-exam-prompt.md")

    rules = load_aggregation_rules(rules_path)
    with open(budget_path, "r", encoding="utf-8") as f:
        import yaml

        budget_config = yaml.safe_load(f)

    # ---- 阶段一：人格评审只跑一次，作为所有条件的共同基线 ----
    # 走 run_panel 而不是自己拼人格执行循环：证据预检、并发、三层校验、降级标记
    # 都在它里面。这里复制一份等于让消融实验测的是另一条不受测试覆盖的代码路径，
    # 测出来的东西也就不代表线上行为。
    # enable_cross_exam=False 是新增的显式开关，和 mode="quick" 的区别在于
    # **它不动人数**——mode 会按 REVIEW_MODE_CONFIG 截到 3 人，那会引入混淆变量。
    baseline_run = runner_cli.run_panel(
        task_type=task_type,
        artifact_bundle=artifact_bundle,
        personas_path=personas_path,
        selected_personas=selected_personas,
        api_key=effective_key,
        enable_cross_exam=False,
    )

    persona_outputs = baseline_run.get("persona_outputs") or []
    panel = baseline_run.get("panel_personas") or []
    if not persona_outputs:
        raise RuntimeError("人格评审没有产出任何有效输出，无法进行交叉质询消融")

    if progress:
        progress("panel", ",".join(p.get("id", "?") for p in panel))

    artifact_summary = artifact_bundle.get("title", "")
    persona_pack = runner_cli.load_persona_pack_meta(personas_path)
    sim = get_issue_similarity()

    # 争议点也只提取一次：它由 persona_outputs 决定，与反驳档位无关。
    # 每个条件各提一次会因语义去重的非确定性引入噪声。
    controversy_points = runner_cli.filter_genuine_controversies(
        extract_controversy_points(persona_outputs)
    )

    # ---- 阶段二：从共同基线分叉出各反驳条件 ----
    reports = {}
    raw = {}
    for condition in conditions:
        usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
        cross_exam_data = None

        if condition != BASELINE_CONDITION and controversy_points:
            cross_exam_data = runner_cli.run_cross_exam_stage(
                persona_outputs=persona_outputs,
                controversy_points=controversy_points,
                personas=panel,
                template_path=template_path,
                rules=rules,
                budget_config=budget_config,
                usage=usage,
                mode=CONDITION_TO_REVIEW_MODE[condition],
                api_key=effective_key,
            )

        reports[condition] = aggregate_report(
            persona_outputs,
            task_type,
            artifact_summary,
            rules,
            cross_exam_data,
            similarity=sim,
            panel_personas=panel,
            persona_pack=persona_pack,
        )
        raw[condition] = (cross_exam_data, usage)
        if progress:
            progress(condition, (cross_exam_data or {}).get("mode", MODE_DERIVED))

    # ---- 阶段三：全部相对基线做差 ----
    baseline_report = reports[BASELINE_CONDITION]
    summary = {}
    for condition in conditions:
        cross_exam_data, usage = raw[condition]
        summary[condition] = summarize_condition(
            baseline_report, reports[condition], cross_exam_data, usage, sim
        )

    return {
        "experiment": "cross_exam_ablation",
        "task_type": task_type,
        "panel": [p["id"] for p in panel],
        "persona_output_count": len(persona_outputs),
        "controversy_points_found": len(controversy_points),
        "similarity_method": sim.method,
        "baseline": BASELINE_CONDITION,
        "conditions": summary,
        "verdict": build_verdict(summary),
        "design_note": (
            "人格评审只跑一次并在三个条件间共用，因此交叉质询是唯一变量。"
            "不要改用 run_panel(mode=...) 复现：那条路径会按档位截断人数"
            "（REVIEW_MODE_CONFIG.max_personas = 3/6/8），人数与反驳混淆。"
        ),
    }
