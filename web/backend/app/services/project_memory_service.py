"""项目记忆层 —— 把同一个项目的历史判断带进下一次评审。

在此之前，每一次评审都是彻底独立的一次性事件：报告落库、展示、结束。
`Review.project_key` 只是前端用来把历史评审聚成一条时间线的**显示**标签，
没有任何代码把它读回提示词。于是同一个产品连评三版，第三版的人格既不知道
第一版被提过什么，也不知道哪条意见后来被真人测试推翻了——每次都从零开始。

这一层补的就是这个缺口：发起评审时，把同 project_key 下**尚未被证伪**的
历史判断拼成一条材料塞进 bundle，人格因此能看到"上一版这个位置被提过，
当前材料仍未处理"。

三条设计红线：

1. **被回填为 miss 的判断不再带入。** 这是整条闭环真正的收口——回填不再
   只是给校准曲线喂数据，它直接决定下一次评审看不看得到这条判断。没有这一
   条，验证按钮就永远只是个"记个分"的可选动作，没人有理由去点。

2. **匿名身份一律不带记忆。** 关掉认证时所有访客共用同一个 "anonymous"
   user_id，project_key 又是自由文本——两个互不相识的访客只要起了同名项目，
   就会读到对方的评审结论。历史侧边栏本来就有这个问题（只泄漏标题），但
   把正文注入进别人的提示词是**另一个量级**的事故，所以这里直接不做。

3. **注入的内容必须可见。** 隐式注入的上下文会让用户看着报告里冒出来的
   结论不知道从哪来的。所以：材料本身进 `Review.artifact_bundle`（本来就
   落库，天然可审计），另外在 bundle 上留一份 `project_memory` 元数据，
   前端/报告可以如实展示"本次带入了 N 条历史判断"。

一个已知的取舍：这条材料会进 `artifact_texts`，也就是说人格把历史结论当作
`direct` 证据引用时，不会被 validator 的幻觉检测拦下。没有按"证据洗白"处理，
是因为反过来（排除出 artifact_texts）会让**如实引用历史**的人格被判成幻觉，
那个误伤更糟。改用提示词正文明写"这是背景，不是本次材料的直接证据"来约束。
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session, contains_eager

from app.config import settings
from app.models import Judgment, Outcome, Review

# 一次最多带入多少条历史判断。
#
# 这个数字是成本闸不是审美选择：材料会进**每一个**人格的提示词，8 条 × 8 个
# 人格 = 同一段文字被付费 8 次。再往上加，历史的权重也会开始盖过本次材料本身
# ——人格会变成在复述上一版的结论，而不是评审这一版。
MAX_CARRIED_JUDGMENTS = 8

# 单条判断正文的截断长度。claim 落库时上限是 2000 字符，整条塞进来会把提示词
# 撑爆（8 条就是 16k 字符）。
MAX_CLAIM_CHARS = 180

# 带入的严重度优先级。没有 severity 的排最后。
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# 被回填成这个结论的判断不再带入下一次评审——真人测试已经证明它没发生。
VERDICT_EXCLUDED_FROM_MEMORY = "miss"

# 材料的 type。刻意不用 "text"：evidence_precheck.FREEFORM_EVIDENCE_TYPES 把
# "text" 当成万能证据，一旦出现就让**全部**人格跳过证据预检。历史记忆不是
# 关于本次材料的证据，不该有这个副作用。配合 is_context 标记，引擎的
# load_evidence_types 会整条跳过它。
MEMORY_MATERIAL_TYPE = "项目历史"


def _ts(row: Judgment) -> float:
    """predicted_at 的可比较形式。

    统一转成 float 而不是直接拿 datetime 排序：SQLite 取回来的是 **naive**
    datetime（列上没有 timezone=True），而代码里造的默认值带 tzinfo——两者
    直接比大小会 `TypeError: can't compare offset-naive and offset-aware`。
    转 timestamp 之后只是数字比数字，naive 的按本地时区解释，排序结果仍然正确。
    """
    ts = row.predicted_at
    if ts is None:
        return float("-inf")
    try:
        return ts.timestamp()
    except (OverflowError, OSError, ValueError):
        # Windows 上 1970 之前的 naive datetime 会抛 OSError
        return float("-inf")


def _severity_key(row: Judgment):
    rank = _SEVERITY_RANK.get((row.severity or "").lower(), 99)
    # 次序：严重度 → 时间倒序（新的在前）
    return (rank, -_ts(row))


def collect_open_judgments(
    db: Session,
    user_id: str,
    project_key: str,
    exclude_review_id: Optional[str] = None,
    limit: int = MAX_CARRIED_JUDGMENTS,
) -> List[Judgment]:
    """取同项目下仍然"悬着"的历史判断。

    悬着 = 还没回填，或回填结论不是 miss。partial / hit / unknown 都继续带入：
    hit 说明问题真实存在（是否已修复是另一回事，材料里会体现），partial 和
    unknown 都还没有定论。只有 miss 是明确的"这事没发生"，才剔除。
    """
    q = (
        db.query(Judgment)
        .join(Review, Judgment.review_id == Review.id)
        .outerjoin(Outcome, Outcome.judgment_id == Judgment.id)
        # contains_eager 而不是裸 outerjoin：Judgment.outcome 是默认 lazy="select"
        # 的关系，join 本身**不会**填充它，下面每访问一次 r.outcome 就是一条额外
        # SELECT。实测 800 条判断 = 1602 条 SQL / 约 1 秒，而这段跑在 create_review
        # 的同步请求路径上（还是 async def，会阻塞整个事件循环）。加上这一行之后
        # 是 1 条 SQL。
        .options(contains_eager(Judgment.outcome))
        .filter(
            Judgment.user_id == user_id,
            Review.user_id == user_id,  # 双向确认归属，不靠单边字段
            Review.project_key == project_key,
        )
    )
    if exclude_review_id:
        q = q.filter(Judgment.review_id != exclude_review_id)

    rows = q.all()

    # ——— 顺序至关重要：先去重，再过滤 miss ———
    #
    # 同一条问题在多次评审里会被反复提出（这正是"还没修"的信号）。按正文去重，
    # 保留最新的那条，否则 8 条名额会被同一个问题的历次副本占满。
    #
    # 反过来做（先过滤 miss 再去重）会**静默绕过本模块的第 1 条设计红线**：
    # 用户在最新那条上回填了 miss，它先被剔除，同一句 claim 的更旧未验证副本
    # 就顶上来成为去重赢家——被证伪的判断照样进了每个人格的提示词，而且还
    # 顶着"尚未验证"的标签（那条旧行确实没有 Outcome）。多代理审计实测复现过。
    # 所以判定一句 claim 带不带，只看它**最新那条**的回填结论。
    latest = {}
    for r in sorted(rows, key=_ts):
        latest[(r.claim or "").strip()] = r

    kept = [
        r
        for r in latest.values()
        if r.outcome is None or r.outcome.verdict != VERDICT_EXCLUDED_FROM_MEMORY
    ]

    return sorted(kept, key=_severity_key)[:limit]


def _format_line(row: Judgment) -> str:
    claim = (row.claim or "").strip()
    if len(claim) > MAX_CLAIM_CHARS:
        claim = claim[: MAX_CLAIM_CHARS - 1] + "…"

    bits = []
    if row.severity:
        bits.append(f"severity {row.severity}")
    if row.predicted_at:
        bits.append(row.predicted_at.strftime("%Y-%m-%d"))
    if row.outcome is not None:
        # 回填过的要标出来：hit 是"真人测试确认发生了"，权重明显不同于未验证。
        verdict_label = {
            "hit": "真人测试已确认发生",
            "partial": "真人测试确认部分成立",
            "unknown": "已回填但无法判定",
        }.get(row.outcome.verdict, row.outcome.verdict)
        bits.append(verdict_label)
    else:
        bits.append("尚未验证")

    meta = " · ".join(bits)
    return f"- [{meta}] {claim}"


def _skip_reason(
    user_id: Optional[str], project_key: Optional[str]
) -> Optional[str]:
    """三道前置门。返回 None 表示可以继续查库。

    顺序即优先级：ledger 关掉是部署选择，最应该先说；其次才是数据状态。
    """
    if not settings.ledger_enabled:
        return "ledger_disabled"
    if not project_key or not str(project_key).strip():
        return "no_project_key"
    # 匿名不带记忆：见模块头注释第 2 条。
    if not user_id or user_id == "anonymous":
        return "anonymous_identity"
    return None


def _render_material(project_key: str, rows: List[Judgment]) -> dict:
    """把已经取好的判断行拼成一条材料。**不查库**——查询由调用方做一次。"""
    lines = [_format_line(r) for r in rows]
    review_ids = {r.review_id for r in rows}

    body = (
        f"以下是本项目「{project_key}」此前评审留下的、"
        f"尚未被真人测试推翻的判断（共 {len(rows)} 条，来自 {len(review_ids)} 次历史评审）：\n"
        + "\n".join(lines)
        + "\n\n"
        "使用方式（重要）：\n"
        "- 这是**背景信息**，不是本次材料的内容。不要把它当作 direct 证据引用，"
        "本次结论的 direct 证据只能来自本次材料。\n"
        "- 请重点判断：这些老问题在**当前这一版材料**里是否已经被解决。已解决的"
        "明确说已解决；仍然存在的，按本次材料重新给出证据和严重度。\n"
        "- 不要因为某条历史判断存在就默认它仍然成立——它当时的依据可能已经不适用。"
    )

    return {
        "type": MEMORY_MATERIAL_TYPE,
        "text": body,
        "description": body,
        # 引擎的 load_evidence_types 认这个标记：这条材料是上下文，不是关于
        # 本次待评审对象的证据，不参与证据类型覆盖率的计算。
        "is_context": True,
        # 前端认这个标记：这条不是用户提交的材料，回显"你说了什么"时要跳过。
        # 与 is_context 是两件事，故意分开：is_context 管**引擎**怎么算证据，
        # is_injected 管**界面**怎么归属。技能提示只需要后者（见 apply_skill_hint）。
        "is_injected": True,
    }


def build_project_memory(
    db: Session,
    user_id: Optional[str],
    project_key: Optional[str],
    exclude_review_id: Optional[str] = None,
) -> tuple:
    """返回 (material_or_None, metadata_dict)。

    metadata 会挂到 bundle["project_memory"]，用途是让"这次评审带了哪些历史"
    在报告和前端里**可见**——隐式注入的上下文不可见就等于不可审计。

    **全程只查一次库。** 早先的写法是 build_memory_material 查一次拼材料、
    这里再查一次只为数 carried——在评审创建的同步路径上把开销和往返直接翻倍，
    而且两次查询之间理论上可以不一致（并发回填），carried 会和材料里的条数对不上。
    """
    reason = _skip_reason(user_id, project_key)
    if reason:
        return None, {"carried": 0, "reason": reason}

    key = str(project_key).strip()
    rows = collect_open_judgments(
        db, user_id, key, exclude_review_id=exclude_review_id
    )
    if not rows:
        return None, {"carried": 0, "reason": "no_open_judgments"}

    return _render_material(key, rows), {
        "carried": len(rows),
        "from_reviews": len({r.review_id for r in rows}),
        "project_key": key,
        "excluded_verdict": VERDICT_EXCLUDED_FROM_MEMORY,
        "cap": MAX_CARRIED_JUDGMENTS,
    }


def build_memory_material(
    db: Session,
    user_id: Optional[str],
    project_key: Optional[str],
    exclude_review_id: Optional[str] = None,
) -> Optional[dict]:
    """只要材料、不要元数据时的薄封装。查询次数与 build_project_memory 相同（1 次）。"""
    material, _ = build_project_memory(
        db, user_id, project_key, exclude_review_id=exclude_review_id
    )
    return material


def attach_to_bundle(
    db: Session,
    bundle: Optional[dict],
    user_id: Optional[str],
    project_key: Optional[str],
    exclude_review_id: Optional[str] = None,
) -> dict:
    """把项目记忆挂进 artifact_bundle，返回新的 bundle（不就地改入参）。

    **两条评审链路（v1 的 ReviewService.create_review 与 v2 的 create_review_v2）
    必须都调这一个函数。** 这不是洁癖：tests/test_v1_v2_convergence.py 会断言两个
    端点交给 run_panel 的参数逐字段相同，只在一边加功能会直接让它红——而那条
    测试存在的原因，正是这两条链路历史上已经悄悄漂移过一次。

    没有 project_key 时**连元数据都不挂**。理由有两条：
      · 用户没开项目，"为什么没有记忆"不是个问题，挂一段 reason 只是噪音，
        而且它会被写进每一条 Review.artifact_bundle 永久留着；
      · 挂了就会让上面那条收敛测试在最常见的无项目请求上失败。
    用户**给了** project_key 却没拿到记忆时，reason 才有信息量，那时才挂。
    """
    bundle = dict(bundle or {})
    if not project_key or not str(project_key).strip():
        return bundle

    material, meta = build_project_memory(
        db, user_id, project_key, exclude_review_id=exclude_review_id
    )
    if material is not None:
        # 插在末尾而不是开头：本次待评审的材料必须是人格最先读到的东西，
        # 历史是补充。skill hint 抢占 0 号位是因为它是**指令**，性质不同。
        bundle["materials"] = list(bundle.get("materials") or []) + [material]
    bundle["project_memory"] = meta
    return bundle
