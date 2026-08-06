# -*- coding: utf-8 -*-
"""高级技能的免费体验次数。

产品口径：高级技能（默认只有红队）每个账号免费用 N 次；用完**不挡人**，
静默降级成普通评审——报告照出，只是少了那一层，并如实告诉用户降级了。

为什么是降级而不是 402：新用户往往还没建立价值感就撞墙，转化反而更差。
"你已经见过好东西、现在它没了"比"此路不通"更能推动兑换。
但降级必须**说出来**——不吭声地少给一层能力，是这个仓库反复要根除的
"静默降级"，用户会以为产品本来就这样。

三条豁免，与本项目其它额度机制保持同一口径：
  · BYOK —— 花的是用户自己的钱，没有任何理由限制；
  · 共享匿名桶 —— 所有未登录访客共用一个 user_id，按它计次等于
    "全站一共只能用 N 次"，是全局故障不是限流；
  · 配置为负数 —— 显式关闭本机制。
"""

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Review


def is_premium(skill_type: Optional[str]) -> bool:
    return bool(skill_type) and skill_type in settings.premium_skills


def _exempt(user_id: str, key_source: str) -> bool:
    if key_source != "server":
        return True  # BYOK 不受限
    if user_id == settings.anonymous_user_id:
        return True  # 共享匿名桶：按它计次 = 全站共用 N 次
    return settings.skill_free_uses < 0


def used_count(db: Session, user_id: str, skill: str) -> int:
    """该用户用平台 key 用过几次这个高级技能。

    只统计 key_source == 'server' 的历史。老数据这一列是 NULL（当时确实不知道
    花的是谁的钱），NULL 不等于 'server'，自然不计入——宁可少算，
    也不能凭空扣掉老用户的免费次数。

    红队有两条独立的入口：skill_type='red_team_audience'，以及与技能选择
    正交的 enable_red_team 开关（选了受众面板也能再叠红队）。两条都要算，
    只算一条的话用户换个开关就能无限用。
    """
    q = db.query(Review).filter(
        Review.user_id == user_id,
        Review.key_source == "server",
    )
    if skill == "red_team_audience":
        from sqlalchemy import or_

        q = q.filter(
            or_(Review.skill_type == skill, Review.enable_red_team.is_(True))
        )
    else:
        q = q.filter(Review.skill_type == skill)
    return q.count()


def uses_left(db: Session, user_id: str, skill: str, key_source: str = "server") -> Optional[int]:
    """还剩几次；None = 不受限（豁免或本机制关闭）。"""
    if not is_premium(skill) or _exempt(user_id, key_source):
        return None
    return max(0, settings.skill_free_uses - used_count(db, user_id, skill))


def apply(
    db: Session,
    user_id: str,
    key_source: str,
    skill_type: Optional[str],
    enable_red_team: bool,
) -> Tuple[Optional[str], bool, Optional[str]]:
    """按剩余次数决定这次评审实际用什么技能。

    返回 (生效的 skill_type, 生效的 enable_red_team, 降级说明或 None)。

    调用方**必须用返回值覆盖入参**再去落库和拼 prompt——只把说明拿去展示、
    仍按原参数跑，就成了"提示说降级了、实际没降"，比不做更糟。
    """
    notes = []

    if is_premium(skill_type):
        left = uses_left(db, user_id, skill_type, key_source)
        if left is not None and left <= 0:
            notes.append(f"「{skill_type}」的免费体验次数已用完，本次按普通评审运行")
            skill_type = None

    # 红队开关单独判一次：它与 skill_type 正交，上面那段管不到它。
    # 漏掉这里的话，用户把技能选成受众面板、再打开红队开关，就绕过了整个限制。
    if enable_red_team and is_premium("red_team_audience"):
        left = uses_left(db, user_id, "red_team_audience", key_source)
        if left is not None and left <= 0:
            if not notes:
                notes.append("红队对抗视角的免费体验次数已用完，本次不叠加红队")
            enable_red_team = False

    return skill_type, enable_red_team, ("；".join(notes) if notes else None)
