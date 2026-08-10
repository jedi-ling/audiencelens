"""评审报告的只读分享链接。

一句话：给一份评审生成一个不可猜的 token，任何人凭 token 能只读地看这份报告，
作者随时可以撤销。

三条设计约束，改这个文件的人别破坏：

1) **公开字段是白名单，不是黑名单。**
   to_public_dict 里一条条列出要给的字段。诱惑是写成"把 Review 序列化了再
   pop 掉几个敏感列"——那样每次给 Review 加新列，都在默认公开它，只有记得
   回来补 pop 的那次才不漏。报告里是用户还没发布的产品材料、定价策略、BP，
   这种地方的默认值必须是"不给"。

2) **建链接必须要求已登录身份（require_isolated_identity）。**
   这不只是权限洁癖，是堵一个具体的漏洞：匿名用户看自己的报告是被
   report_gating 裁剪过的（登录墙），如果匿名也能建分享链接，那就是
   跑评审 → 给自己建个链接 → 打开 → 看到完整报告，登录墙当场作废。
   CDK 兑换出来的游客不受影响：他们 is_anonymous=False、本来就看完整报告，
   分享不构成绕过（见 deps.is_shared_anonymous 的说明）。

3) **只有 completed 的评审能分享。**
   分享一份 pending/failed 的评审，对方打开是个空壳或半截错误；而
   error_message 里可能带着用户材料的片段。两个理由都指向同一个结论。
"""

import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Review

# 32 字节 → base64url 后 43 个字符。够长到不可枚举，又还能手动复制粘贴。
SHARE_TOKEN_BYTES = 32


def enable_share(db: Session, review: Review) -> str:
    """给这份评审生成（或返回已有的）分享 token。

    幂等：已经分享过就原样返回旧 token，不重新生成。否则用户每点一次"分享"
    都会让上一个已经发出去的链接失效——那是"复制链接发给合伙人，隔天自己
    再点一次分享，合伙人的链接就打不开了"这种莫名其妙的失败。
    """
    if review.share_token:
        return review.share_token
    review.share_token = secrets.token_urlsafe(SHARE_TOKEN_BYTES)
    review.shared_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return review.share_token


def disable_share(db: Session, review: Review) -> None:
    """撤销分享。置回 NULL 即所有已发出的旧链接立刻失效。"""
    review.share_token = None
    review.shared_at = None
    db.commit()


def get_by_token(db: Session, token: str) -> Optional[Review]:
    """按 token 查评审。空 token 直接判否——否则 `share_token IS NULL` 的
    海量未分享评审会被一个空字符串查询命中第一条，等于全站报告任人取阅。"""
    if not token:
        return None
    return db.query(Review).filter(Review.share_token == token).first()


def to_public_dict(review: Review) -> dict:
    """公开视图。**只加你确认过可以给陌生人看的字段。**

    刻意不包含，每条都有具体理由：
      · user_id / 邮箱     —— 分享报告不等于公开作者身份
      · total_cost_usd
        input_tokens
        output_tokens      —— 作者的账单数据，跟看报告的人没关系
      · artifact_bundle    —— 用户上传的原始材料，最敏感的一坨
      · error_message      —— 可能带材料片段（且只有 completed 能分享，本就为空）
      · project_key        —— 作者给自己项目起的名字，可能暴露其他在做的东西
      · report_markdown    —— 与 report 同源的全文镜像，白给一份扩大暴露面
      · id                 —— 对外的标识就是 token，评审 id 没有必要出现
    """
    return {
        "task_type": review.task_type,
        "mode": review.mode,
        "target_title": review.target_title,
        "persona_pack": review.persona_pack,
        "selected_personas": review.selected_personas,
        "skill_type": review.skill_type,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
        "shared_at": review.shared_at.isoformat() if review.shared_at else None,
        "report": review.report_json,
        "calibration": review.calibration,
    }
