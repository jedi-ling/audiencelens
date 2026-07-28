"""报告出来后的真对话——追问结论，或直接找某个虚拟人格聊。

此前"多轮对话"名不副实：AskPage 的多轮只是把用户历史发言拼接后重新过一遍
无状态的 intent_service（决定任务类型/技能），报告生成后就是终点——不能追问，
更不能跟某个具体人格（比如 P15 毒舌差评者）对话。这里补的是报告产出*之后*
的第二段对话，有独立的持久化上下文（ReviewChatMessage），每次追问都真的把
之前聊过的内容带给模型，而不是每次都从零开始。

两种 thread（用 persona_id 是否为空区分，同一 review 下互不干扰）：
    综合评审团：追问报告结论本身（"为什么定价页评分低"），语气是评审团口吻
    单个人格：跟该人格的 identity_summary/behavior_profile/communication_style
              保持人设一致地聊（不是通用助手腔）
"""

import logging
import os
import sys
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest, QuotaExceeded
from app.models import Review, ReviewChatMessage

logger = logging.getLogger("audiencelens")

_SRC = os.path.join(settings.repo_root, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

MAX_HISTORY_TURNS = 12  # 单条 thread 最多带这么多轮历史进 prompt，避免越聊越贵


def _find_persona(review: Review, persona_id: str) -> Optional[dict]:
    if not review.persona_pack:
        return None
    from runner.panel_selector import load_personas

    path = os.path.join(settings.repo_root, "src", "personas", f"{review.persona_pack}.yaml")
    if not os.path.isfile(path):
        return None
    for p in load_personas(path):
        if p["id"] == persona_id:
            return p
    return None


def _find_persona_note(review: Review, persona_id: str) -> Optional[dict]:
    for note in (review.report_json or {}).get("persona_notes", []) or []:
        if note.get("persona_id") == persona_id:
            return note
    return None


def _report_summary_text(review: Review) -> str:
    report = review.report_json or {}
    summary = report.get("executive_summary") or {}
    fixes = report.get("priority_fixes") or []
    notes = report.get("persona_notes") or []
    lines = [
        f"标题：{review.target_title or '(未命名)'}",
        f"整体建议：{summary.get('primary_recommendation', '(无)')}",
        f"发布风险：{summary.get('release_risk', '(无)')}",
        f"证据质量：{summary.get('evidence_quality', '(无)')}",
        "优先修复项：",
    ]
    for f in fixes[:8]:
        lines.append(f"  - [{f.get('severity', '?')}] {f.get('title', '')}：{f.get('why_it_matters', '')}")
    lines.append("各人格立场：")
    for n in notes:
        lines.append(f"  - {n.get('persona_name', n.get('persona_id', ''))}：{n.get('primary_stance', '')}")
    return "\n".join(lines)


def _build_prompt(
    review: Review, history: List[ReviewChatMessage], user_message: str, persona: Optional[dict], persona_note: Optional[dict]
) -> str:
    if persona is not None:
        from runner.persona_agent import _minify_persona

        persona_yaml = _minify_persona(persona)
        system = (
            f"你正在扮演一个虚拟评审人格，完全代入这个人设跟用户对话，不要跳出角色说"
            f"「作为AI」之类的话。你已经评审过用户的产品/项目，以下是你的人设与你当时的"
            f"评审意见：\n\n人设：\n{persona_yaml}\n\n你当时的评审意见：\n"
            f"{persona_note or '（未找到你当时的具体意见，凭人设自然回应）'}\n\n"
            f"回答要符合你的 communication_style，简体中文，不要写成正式报告腔。"
        )
    else:
        system = (
            "你是这次多人格评审的召集人，代表评审团整体回答用户对报告的追问。"
            "以下是完整报告摘要：\n\n" + _report_summary_text(review) + "\n\n"
            "如实基于报告内容回答，报告里没有的信息就说没有，不要编造。简体中文作答。"
        )

    turns = []
    for m in history[-MAX_HISTORY_TURNS:]:
        speaker = "用户" if m.role == "user" else "你"
        turns.append(f"{speaker}：{m.content}")
    turns.append(f"用户：{user_message}")
    turns.append("你：")
    return system + "\n\n对话记录：\n" + "\n".join(turns)


MAX_CHAT_IMAGES = 4  # 追问单条消息最多带几张图（data URI 全量进 prompt，防打爆）

# 追问的计量口径：kind="chat"，**不算一次"评审次数"**。
#
# 为什么不按次数扣：一次完整评审是 N 个人格各跑一轮 + 交叉质询 + 聚合，一次追问
# 只是单次 1200-token 上限的对话补全，成本差一到两个数量级。按次数扣会出现
# "问两句就把当天的评审额度问没了"，而这恰恰是报告产出后最该发生的行为
# （追问是留存点，不是要压制的行为）。
#
# 但成本必须记：quota_service 里那道按 24h 累计 server-key 成本触发的硬闸是保护
# 运营者钱包的，它按 cost_usd 求和、不区分 kind——所以追问的 cost 一进 UsageRecord
# 就自然被那道闸门覆盖。于是口径是：**只计成本、不计次数**——狂刷追问依然会把
# 成本闸门顶满从而被拦下，正常追问则不挤占评审次数。
CHAT_USAGE_KIND = "chat"


def _check_chat_quota(db: Session, user_id: str, key_source: str, plan: str) -> None:
    """追问前的配额校验。与建评审同源（都读 quota_service 的口径），但有两点不同：

    1. 不消耗次数：credits 模式下 quota_service.check_quota 会原子扣 1 次余额，
       对一次追问收一次完整评审的价钱不合理，这里只校验"有没有余额"不扣减。
    2. 判定数据全部取自 quota_service.usage_summary，不在这里复写限额来源，
       否则后台面板改 quota_free_* 时追问链路会静默失效。

    BYOK 用户花自己的钱，与 check_quota 一致地豁免（key_source != "server" 直接放行）。
    """
    if key_source != "server":
        return

    from app.services import quota_service

    summary = quota_service.usage_summary(db, user_id, plan)
    if not summary["quota_enabled"]:
        return

    if summary["quota_mode"] == "credits":
        # 纯次数制下额度就是 CDK 余额本身。余额 0 的用户不能靠追问白嫖平台 key；
        # 有余额则放行且**不扣**（追问不消耗次数）。
        if (summary["bonus_credits"] or 0) <= 0:
            raise QuotaExceeded(
                "评审次数已用完，追问也需要有余额。请兑换 CDK，"
                "或填写自己的 API Key（BYOK）以不受限制使用。"
            )
        # 但"不扣次数"在这条链路上不能等于"不设上限"：credits 模式的
        # usage_summary 里 cost_usd_limit 恒为 None（该模式没有每日成本闸，
        # 总成本靠发码量控制），而追问既不扣次数、又没有成本闸，就意味着
        # 只要余额 ≥1 就能对平台 key 无限追问——发一张码等于送一条不封顶的
        # 补全通道。这里把套餐的日成本上限当作兜底闸补上：它同样由后台
        # quota_free_cost_usd_per_day / plan_override 驱动，不是新造的旋钮，
        # 且只约束追问，评审在 credits 模式下的行为完全不变。
        from app.services import plan_service

        credits_cost_limit = plan_service.get_plan(plan, db)["cost_usd_per_day"]
        if summary["cost_usd_on_server_key"] >= credits_cost_limit:
            raise QuotaExceeded(
                f"24 小时内成本额度已用完（限 ${credits_cost_limit}/天）。"
                "请稍后再试，或填写自己的 API Key（BYOK）以不受限制使用。"
            )
        return

    cost_limit = summary["cost_usd_limit"]
    if cost_limit is not None and summary["cost_usd_on_server_key"] >= cost_limit:
        raise QuotaExceeded(
            f"24 小时内成本额度已用完（{summary['plan_name']} 套餐限 ${cost_limit}/天）。"
            "可升级套餐，或填写自己的 API Key（BYOK）以不受限制使用。"
        )


def _record_chat_usage(
    db: Session,
    review: Review,
    *,
    model: str,
    key_source: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """把这次追问的 token/cost 写进 UsageRecord。

    成本估算复用 runner.persona_agent.estimate_cost（引擎侧同一套定价表），
    不另写算法，否则计费报表会出现两种口径。

    记账失败不能让追问失败——用户已经拿到回复了，回滚它才是更糟的体验；
    但也绝不静默：按仓库既有做法（review_service 记 usage 失败的分支）打 warning 日志。
    """
    try:
        import yaml

        from app.services import BUDGET_PATH, quota_service
        from runner.persona_agent import estimate_cost

        with open(BUDGET_PATH, "r", encoding="utf-8") as f:
            budget_config = yaml.safe_load(f)
        cost = estimate_cost(input_tokens, output_tokens, model, budget_config)

        quota_service.record_usage(
            db,
            review.user_id or "anonymous",
            review_id=review.id,
            kind=CHAT_USAGE_KIND,
            persona_count=0,  # 追问不涉及人格并发，恒为 0
            cost_usd=cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            key_source=key_source,
        )
    except Exception:
        logger.warning(
            "追问 review %s 记 usage 失败（回复已返回给用户，但这次的 token/cost 没进账）",
            review.id,
            exc_info=True,
        )


def send_message(
    db: Session,
    review: Review,
    message: str,
    persona_id: Optional[str] = None,
    images: Optional[List[str]] = None,
    plan: str = "free",
) -> ReviewChatMessage:
    """images：data URI 列表（data:image/png;base64,...）。此前追问链路只收文字，
    前端附件栏里的截图被静默丢弃——用户以为"随消息发出去了"其实根本没有。
    现在拼成多模态内容块交给 chat_completion（llm_client 会按 provider 转换格式；
    模型不支持视觉时静默降级为纯文字，不报错阻断追问）。"""
    if review.status != "completed":
        raise BadRequest("评审尚未完成，还不能追问")
    if not message or not message.strip():
        raise BadRequest("消息不能为空")

    from app.services import key_service
    from runner.llm_client import chat_completion

    images = [u for u in (images or []) if u and u.startswith("data:image/")][:MAX_CHAT_IMAGES]

    # key 与配额都要在写库/调模型**之前**定：配额耗尽的用户此前能对任意一条已完成
    # 评审狂发追问，平台 key 一直在烧钱而 UsageRecord 一行都没有。
    resolved = key_service.resolve_key(db, review.user_id or "anonymous")
    _check_chat_quota(db, review.user_id or "anonymous", resolved.source, plan)

    persona = _find_persona(review, persona_id) if persona_id else None
    if persona_id and persona is None:
        raise BadRequest(f"未找到人格 {persona_id}")
    persona_note = _find_persona_note(review, persona_id) if persona_id else None

    history = (
        db.query(ReviewChatMessage)
        .filter(ReviewChatMessage.review_id == review.id, ReviewChatMessage.persona_id == persona_id)
        .order_by(ReviewChatMessage.created_at)
        .all()
    )

    # 历史记录里图片不存原图（data URI 动辄几 MB），只留标记——模型第一轮
    # 已经"看过"并把理解写进回复，后续轮次靠文字上下文接得上。
    stored_content = (f"[附图×{len(images)}] " if images else "") + message
    user_msg = ReviewChatMessage(
        review_id=review.id, persona_id=persona_id, role="user", content=stored_content
    )
    db.add(user_msg)
    db.commit()

    prompt = _build_prompt(review, history, message, persona, persona_note)
    if images:
        # OpenAI Vision 内容块格式——runner.llm_client.chat_completion 原生支持，
        # 并对不支持视觉的模型自动降级为纯文字（丢图不丢消息）
        prompt = [{"type": "text", "text": prompt}] + [
            {"type": "image_url", "image_url": {"url": u}} for u in images
        ]
    model = resolved.model or settings.intent_model
    reply_text, in_tok, out_tok = chat_completion(
        model=model,
        prompt=prompt,
        api_key=resolved.key,
        provider=resolved.provider,
        api_base=resolved.api_base,
        max_tokens=1200,
    )

    assistant_msg = ReviewChatMessage(
        review_id=review.id, persona_id=persona_id, role="assistant", content=reply_text.strip()
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    _record_chat_usage(
        db,
        review,
        model=model,
        key_source=resolved.source,
        input_tokens=in_tok or 0,
        output_tokens=out_tok or 0,
    )
    return assistant_msg


def list_messages(db: Session, review_id: str, persona_id: Optional[str] = None) -> List[ReviewChatMessage]:
    return (
        db.query(ReviewChatMessage)
        .filter(ReviewChatMessage.review_id == review_id, ReviewChatMessage.persona_id == persona_id)
        .order_by(ReviewChatMessage.created_at)
        .all()
    )
