"""面板选择：按 (task_type, 人格包) 组合挑人，保证面板里有唱反调的人。

为什么要按"组合"而不是只按 task_type：
预设表原先只按裸号（P01/P06/P14）匹配，而那张表是围绕 game-core 写的。
换成任何别的人格包时，裸号一个都对不上 —— 实测 accessibility / mobile-f2p /
vr-immersive / educational-serious 四个包在**全部 14 种 task_type 下都选出 0 个人**，
到了 cli.run_panel 就是 AllPersonasFailedError（"帮我看看我这手游的付费设计"
这种最自然的请求直接崩）。66 个人格里有 33 个永远不会被自动选中。

现在的三层解析（越靠前越优先）：
    1. preset["by_pack"][pack]  —— 手写的 (task_type, pack) 专用面板
    2. preset["default_personas"] —— 全局默认（历史行为，game-core 口径）
    3. task_affinity 排序兜底   —— 从当前包里按该任务的亲和度取人
第 3 层不是"凑数"：每个人格的 task_affinity 都是逐条标过的，按它排序得到的
面板本身就是合理面板。by_pack 只用来写"亲和度表达不了的策展意图"
（比如 localization_review 必须有懂本地化的人），**不需要穷举所有组合**。

返回值里 selection_method 如实标明这一轮用的是哪一层，不含糊。
"""

import yaml
from typing import Dict, List, Optional

# 11 条行为轴共用一张有序量表。
#
# 原先每条轴各用一张表（LEVEL_3/LEVEL_4/LEVEL_5），而 risk_tolerance /
# platform_loyalty 用的是只有 {低,中,高} 的 LEVEL_3 —— 可 16 个人格的 20 个取值
# 是「很高」或「很低」（P36/P38/P39/P41 的 risk_tolerance: 很低、P27/P31/P34 的
# agency_preference: 很高……），于是 compute_behavioral_distance 一碰真实 yaml 就
# KeyError。唯一一个用来量化"多视角不是假的"的护栏，接上就会崩。
# 统一成五档量表后，各轴刻度一致、距离可跨轴相加，且不存在查不到的取值。
LEVEL = {"很低": 1, "低": 2, "中": 3, "高": 4, "很高": 5}

DISTANCE_AXES = [
    "patience",
    "genre_literacy",
    "novelty_seeking",
    "risk_tolerance",
    "social_influence",
    "completion_drive",
    "price_sensitivity",
    "emotional_engagement",
    "agency_preference",
    "tolerance_for_ambiguity",
    "platform_loyalty",
]

# 保留这个名字：外部若按轴查量表仍可用，只是现在每轴指向同一张五档表。
AXIS_MAP = {axis: LEVEL for axis in DISTANCE_AXES}

MAX_AXIS_SPAN = max(LEVEL.values()) - min(LEVEL.values())

# game-core 的唱反调裸号。src/runner/cli.py 的 truncate_panel 导入这个常量来
# 保证按档位截断时不把唯一的负面视角切掉，故**不能**往里塞别的包的裸号：
# P01 在 game-core 是"核心独立探索者"、在 indie-creative 是"独立鉴赏家"，
# 裸号在跨包时会撞车，加进来等于让 cli 把 game-core 的 P01 误判成唱反调的。
# 别的包靠 PACK_DISSENTERS + 把唱反调的人排到面板最前面来保证（见 select_panel）。
DISSENTER_PREFIXES = ("P15", "P16")

# 每个包里"以否决/挑刺为职责"的人格，按优先级排列，用**全 id** 而不是裸号。
# 没有这张表时，select_panel 只会去找 P15 —— 除 game-core 外的九个包一个都找不到，
# "保证面板里有反对者"这条承诺在这些包上是空的。
PACK_DISSENTERS: Dict[str, List[str]] = {
    "game-core": ["P15-toxic-skeptic-reviewer", "P16-competitor-loyal-veteran"],
    "general-consumer": ["P47-skeptical-reviewer-general", "P53-competitor-loyal-switcher"],
    "startup-panel": ["P61-devils-advocate", "P60-unit-economics-skeptic"],
    "mobile-f2p": ["P22-free-lunch-hunter", "P25-hypercasual-passerby"],
    "accessibility": ["P17-color-vision-aid", "P19-motor-accessibility"],
    "vr-immersive": ["P26-vr-motion-sensitive", "P27-presence-seeker"],
    "competitive-esport": ["P30-rank-climber", "P31-speedrun-challenger"],
    "educational-serious": ["P36-parent-gatekeeper", "P35-teacher-evaluator"],
    "family-casual": ["P42-nostalgia-retro", "P39-parent-child-creator"],
    "indie-creative": ["P01-indie-connoisseur", "P02-creativity-seeker"],
    "launch-compliance": ["P62-store-submission-reviewer", "P66-refunded-churned-player"],
}

# 面板兜底人数：预设没写 min_panel_size 时用它。
DEFAULT_MIN_PANEL_SIZE = 4

# 行为距离低于这个值就算"两个人在行为轴上几乎是同一个人"。
# 取值依据：全部 10 个包的同包两两距离共 245 对，中位数 0.205、最小 0.068，
# 0.10 大致落在第 10 百分位——只标出真正贴脸的那几对，不会把半个面板都判成冗余。
DEFAULT_MIN_DISTANCE = 0.10


def load_personas(yaml_path: str) -> List[dict]:
    """读人格包，并把包名 (panel_id) 盖到每个人格上。

    盖 _pack 是为了让 select_panel 在**不改调用方签名**的前提下知道"这批人是哪个包的"
    —— cli.run_panel 只传 personas 列表进来，没有 pack 参数。
    下划线前缀是内部字段：persona_agent._minify_persona 按 CORE_FIELDS 白名单裁剪，
    因此 _pack 不会漏进提示词；persona-schema 校验读的是 yaml 原文，也不受影响。
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    personas = data["personas"]
    pack = data.get("panel_id")
    if pack:
        for p in personas:
            p["_pack"] = pack
    return personas


def load_presets(yaml_path: str) -> dict:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["presets"]


def _match_persona(ref: str, personas: List[dict]) -> Optional[dict]:
    """按全 id 精确匹配，匹配不上再退回裸号前缀（历史预设写的是 P06 这种裸号）。"""
    for p in personas:
        if p.get("id") == ref:
            return p
    for p in personas:
        if str(p.get("id", "")).startswith(ref + "-"):
            return p
    return None


def detect_pack(personas: List[dict]) -> Optional[str]:
    """从人格自带的 _pack 推断当前包名；手工拼的人格列表（测试里常见）返回 None。"""
    for p in personas:
        pack = p.get("_pack")
        if pack:
            return pack
    return None


def _is_dissenter(persona: dict, pack: Optional[str] = None) -> bool:
    pid = str(persona.get("id", ""))
    if pack and pack in PACK_DISSENTERS:
        return pid in PACK_DISSENTERS[pack]
    return any(pid.startswith(prefix) for prefix in DISSENTER_PREFIXES)


def _axis_value(persona: dict, axis: str) -> Optional[int]:
    """取不到 / 取值不在量表里时返回 None，由调用方跳过这条轴。

    为什么不直接抛：这个函数现在跑在生产选人路径上（select_panel 的多样性平局判定），
    一个人格 yaml 写错一个字就让整场评审崩掉，代价与收益完全不匹配。
    数据本身的正确性由 tests/test_personas.py 逐个包卡死（取值必须落在 LEVEL 里），
    所以写错也不会悄无声息地混过去。
    """
    raw = (persona.get("behavior_profile") or {}).get(axis)
    return LEVEL.get(raw)


def compute_behavioral_distance(p1: dict, p2: dict) -> float:
    """两个人格在行为轴上的归一化距离，0=完全一致，1=每条轴都相隔满量程。

    只按两边都能取到值的轴计算并按这些轴归一化：缺轴的人格不会因为"缺"而被
    算成差异巨大（那会让兜底选人优先挑数据残缺的人）。一条轴都对不上时返回 0.0，
    即"无从判断差异"——保守地当成可能冗余，而不是假装很多样。
    """
    total = 0
    compared = 0
    for axis in DISTANCE_AXES:
        v1 = _axis_value(p1, axis)
        v2 = _axis_value(p2, axis)
        if v1 is None or v2 is None:
            continue
        total += abs(v1 - v2)
        compared += 1
    if compared == 0:
        return 0.0
    return total / (compared * MAX_AXIS_SPAN)


def ensure_diversity(
    selected: List[dict], min_distance: float = DEFAULT_MIN_DISTANCE
) -> List[dict]:
    """列出面板里行为轴上几乎重合的人格对（距离 < min_distance）。

    它只是**检测器**，不负责踢人：行为轴只有 11 条通用维度，量不出"色觉辅助"和
    "运动辅助"这种功能上完全不同、轴上却很接近的差别——按它自动换人会把真正需要的
    视角换掉。生产路径上它有两个真实作用（见 select_panel）：
      1. 兜底选人时作平局裁决——亲和度同档的候选里，挑与已选面板行为差异最大的那个；
      2. 结果写进返回值的 diversity_warnings，面板确实贴脸时如实报出来。
    """
    redundant_pairs = []
    for i in range(len(selected)):
        for j in range(i + 1, len(selected)):
            dist = compute_behavioral_distance(selected[i], selected[j])
            if dist < min_distance:
                redundant_pairs.append({
                    "persona_1": selected[i]["id"],
                    "persona_2": selected[j]["id"],
                    "distance": dist,
                })
    return redundant_pairs


def _affinity(persona: dict, task_type: str) -> float:
    ta = persona.get("task_affinity") or {}
    try:
        return float(ta.get(task_type, 0.0))
    except (TypeError, ValueError):
        return 0.0


def _passes_evidence(persona: dict, artifact_evidence_types: Optional[List[str]]) -> bool:
    if artifact_evidence_types is None:
        return True
    needed = set(persona.get("evidence_types_needed", []) or [])
    if not needed:
        return True
    return bool(needed & set(artifact_evidence_types))


def _min_distance_to(persona: dict, panel: List[dict]) -> float:
    if not panel:
        return 1.0
    return min(compute_behavioral_distance(persona, p) for p in panel)


def _pick_by_affinity(
    candidates: List[dict], task_type: str, panel: List[dict]
) -> Optional[dict]:
    """从候选里挑一个：先看任务亲和度（按 0.1 分档，避免 0.79/0.80 这种噪声主导），
    同档再挑与现有面板行为差异最大的那个——这就是 ensure_diversity 那套距离度量
    在生产路径上真正起作用的地方。

    并列时 max() 取候选表里靠前的那个，而候选表始终按人格包 yaml 里的声明顺序，
    所以结果是确定的（同样输入永远同样面板）。
    """
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda c: (round(_affinity(c, task_type), 1), _min_distance_to(c, panel)),
    )


def select_panel(
    task_type: str,
    personas: List[dict],
    presets: dict,
    artifact_evidence_types: Optional[List[str]] = None,
    pack: Optional[str] = None,
) -> dict:
    """按 (task_type, pack) 选面板。

    pack 不传时从 personas 自带的 _pack 推断（load_personas 会盖上）；两者都没有时
    只用 presets 里的全局 default_personas，行为与旧版一致。

    返回：
        selected            最终面板（唱反调的人排在第一位，见下）
        skipped             被跳过的人及原因
        task_type / pack
        selection_method    preset / pack_preset / affinity_fallback，如实标明来源
        dissenter_id        面板里承担否决职责的人格 id（真没有时是 None）
        diversity_warnings  行为轴上几乎重合的人格对
    """
    if task_type not in presets:
        raise ValueError(f"Unknown task type: {task_type}")

    preset = presets[task_type] or {}
    pack = pack or detect_pack(personas)

    by_pack = preset.get("by_pack") or {}
    pack_list = by_pack.get(pack) if pack else None
    if pack_list:
        wanted = list(pack_list)
        method = "pack_preset"
    else:
        wanted = list(preset.get("default_personas", []) or [])
        method = "preset"
    # optional_personas 是预设里写了三年却从来没人读的字段（典型的假旋钮）。
    # 现在它有确定含义：人数不够 min_panel_size 时，优先从这里补，再轮到亲和度兜底。
    optional = list(preset.get("optional_personas", []) or [])

    min_size = int(preset.get("min_panel_size", DEFAULT_MIN_PANEL_SIZE) or DEFAULT_MIN_PANEL_SIZE)
    max_size = int(preset.get("max_panel_size", 0) or 0)

    selected: List[dict] = []
    skipped: List[dict] = []
    seen_ids = set()

    for ref in wanted:
        persona = _match_persona(ref, personas)
        if persona is None:
            # 预设点名的人不在当前包里。以前这里直接导致空面板；现在只记一笔，
            # 缺的人数由下面的兜底补齐。
            skipped.append({
                "persona_id": ref,
                "reason": f"Persona not in pack '{pack or 'unknown'}'",
            })
            continue
        if persona["id"] in seen_ids:
            continue
        if not _passes_evidence(persona, artifact_evidence_types):
            skipped.append({
                "persona_id": persona["id"],
                "reason": "No evidence type overlap",
            })
            continue
        selected.append(persona)
        seen_ids.add(persona["id"])

    matched_from_preset = len(selected)

    # 候选池：本包里还没入选、且过得了证据门槛的人
    def _pool() -> List[dict]:
        return [
            p for p in personas
            if p.get("id") not in seen_ids and _passes_evidence(p, artifact_evidence_types)
        ]

    # 补 optional 名单（预设里写了却一直没人读的那个字段，现在真的用上）
    for ref in optional:
        if len(selected) >= min_size:
            break
        persona = _match_persona(ref, personas)
        if persona is None or persona["id"] in seen_ids:
            continue
        if not _passes_evidence(persona, artifact_evidence_types):
            continue
        selected.append(persona)
        seen_ids.add(persona["id"])

    # 仍然不够就按任务亲和度从本包里补
    if len(selected) < min_size:
        while len(selected) < min_size:
            pick = _pick_by_affinity(_pool(), task_type, selected)
            if pick is None:
                break
            selected.append(pick)
            seen_ids.add(pick["id"])

    if matched_from_preset == 0:
        # 预设名单在这个包里一个都没命中——这一轮实际是亲和度兜底选出来的，
        # 不能继续标成 preset，否则调用方以为面板是策展过的。
        method = "affinity_fallback"

    # 保证有人唱反调。放到**队首**而不是队尾：cli.truncate_panel 按档位截断时是
    # 从头切的（quick 档只留 3 人），排在末尾的人会被系统性切掉——这正是它当初
    # 要打的补丁。排在队首则任何"取前 N 个"都必然留下他，且对非 game-core 的包
    # 同样有效（cli 那边的 P15/P16 前缀表覆盖不到别的包）。
    dissenter_id = None
    existing = next((p for p in selected if _is_dissenter(p, pack)), None)
    if existing is not None:
        dissenter_id = existing["id"]
        selected = [existing] + [p for p in selected if p["id"] != existing["id"]]
    else:
        for ref in PACK_DISSENTERS.get(pack or "", []) or list(DISSENTER_PREFIXES):
            persona = _match_persona(ref, personas)
            if persona is None or persona["id"] in seen_ids:
                continue
            dissenter_id = persona["id"]
            selected = [persona] + selected
            seen_ids.add(persona["id"])
            break

    if max_size and len(selected) > max_size:
        selected = selected[:max_size]

    return {
        "selected": selected,
        "skipped": skipped,
        "task_type": task_type,
        "pack": pack,
        "selection_method": method,
        "dissenter_id": dissenter_id,
        "diversity_warnings": ensure_diversity(selected),
    }
