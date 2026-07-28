"""用户数据自主权：导出我的全部数据 / 彻底删除我的账号。

这是"凭什么相信你不拿我的东西"这个问题唯一能被用户亲手验证的答案——
政策写得再好也只是承诺，能一键导出、能一键删干净才是可检验的事实。

关于删除的边界（诚实划线，隐私政策里必须同样口径写清楚）：
    立即物理删除：评审内容、材料原文、报告、追问记录、人格输出、
                  判断留档、反馈、伦理报告（含内容摘录）、BYOK 密钥、账号本身
    保留但切断关联：用量/计费流水、CDK 兑换与次数账
        —— 这些是财务事实源，法律与对账要求下不能说删就删；
           但会把 user_id 改写成不可回指的墓碑 id，从此无法关联到具体人，
           留下的只剩"某次消耗了多少 token / 多少钱"这种无主统计。
把这条边界写明白，比假称"全部彻底删除"要可信得多——后者一查就穿帮。
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models import (
    CdkRedemption,
    CreditLedger,
    Job,
    Review,
    ReviewChatMessage,
    User,
    UserApiKey,
    UsageRecord,
)


def _iso(dt) -> str:
    return dt.isoformat() if dt else None


def export_user_data(db: Session, user_id: str) -> Dict[str, Any]:
    """导出该用户的全部可读数据。

    BYOK 密钥只导出掩码后的元信息（provider/model/掩码串），绝不导出明文——
    导出文件很可能被随手放进下载目录/发邮件，不该成为密钥泄露的新渠道。
    """
    user = db.get(User, user_id)

    reviews = (
        db.query(Review)
        .filter(Review.user_id == user_id)
        .order_by(Review.created_at.desc())
        .all()
    )

    review_payload = []
    for r in reviews:
        chats = (
            db.query(ReviewChatMessage)
            .filter(ReviewChatMessage.review_id == r.id)
            .order_by(ReviewChatMessage.created_at)
            .all()
        )
        review_payload.append(
            {
                "id": r.id,
                "task_type": r.task_type,
                "target_title": r.target_title,
                "project_key": r.project_key,
                "mode": r.mode,
                "status": r.status,
                "created_at": _iso(r.created_at),
                "completed_at": _iso(r.completed_at),
                "total_cost_usd": r.total_cost_usd,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                # 用户自己上传的原始材料——这是"我的东西"的核心，必须给全
                "artifact_bundle": r.artifact_bundle,
                "report_json": r.report_json,
                "report_markdown": r.report_markdown,
                "persona_outputs": [
                    {
                        "persona_id": po.persona_id,
                        "persona_name": po.persona_name,
                        "status": po.status,
                        "output_json": po.output_json,
                        "cost_usd": po.cost_usd,
                        "input_tokens": po.input_tokens,
                        "output_tokens": po.output_tokens,
                    }
                    for po in r.persona_outputs
                ],
                "follow_up_chat": [
                    {
                        "persona_id": m.persona_id,
                        "role": m.role,
                        "content": m.content,  # 导出给本人，不做匿名裁剪
                        "created_at": _iso(m.created_at),
                    }
                    for m in chats
                ],
            }
        )

    keys = db.query(UserApiKey).filter(UserApiKey.user_id == user_id).all()
    usage = db.query(UsageRecord).filter(UsageRecord.user_id == user_id).all()

    return {
        "export_version": 1,
        "exported_at": _iso(datetime.now(timezone.utc)),
        "account": (
            {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "plan": user.plan,
                "is_active": user.is_active,
                "created_at": _iso(user.created_at),
            }
            if user
            else {"id": user_id, "note": "匿名身份，无注册账号"}
        ),
        "api_keys": [
            {
                "provider": k.provider,
                "model": k.model,
                "api_base": k.api_base,
                "masked": k.key_masked,
                "created_at": _iso(k.created_at),
                "last_used_at": _iso(k.last_used_at),
                "note": "出于安全，导出不含密钥明文",
            }
            for k in keys
        ],
        "reviews": review_payload,
        "usage_records": [
            {
                "kind": u.kind,
                "review_id": u.review_id,
                "persona_count": u.persona_count,
                "cost_usd": u.cost_usd,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "key_source": u.key_source,
                "created_at": _iso(u.created_at),
            }
            for u in usage
        ],
    }


def delete_user_data(db: Session, user_id: str) -> Dict[str, int]:
    """彻底删除该用户的内容与账号；财务流水改为切断关联的墓碑 id。

    返回各类删除/匿名化的条数，供接口回给用户看——让"删干净了"这件事
    有可核对的数字，而不是一句轻飘飘的"已删除"。
    """
    tombstone = f"deleted-{uuid.uuid4().hex[:16]}"
    stats: Dict[str, int] = {}

    # 评审——级联带走 persona_outputs / chat_messages / evaluation_results /
    # judgments(+outcomes) / feedback(+adoptions) / ethics_reports，
    # 见 models 里的 cascade 声明。伦理报告走 cascade 而不是单独 delete()：
    # 它的归属完全由 Review 决定（表里不冗余 user_id），挂在同一条删除路径上
    # 才不会出现"加了新入口忘了同步删"的漂移。
    reviews = db.query(Review).filter(Review.user_id == user_id).all()
    stats["reviews_deleted"] = len(reviews)
    # 单独报一个数字，让"含内容摘录的伦理报告也删了"这件事对用户可核对
    stats["ethics_reports_deleted"] = sum(len(r.ethics_reports) for r in reviews)
    for r in reviews:
        db.delete(r)

    stats["api_keys_deleted"] = (
        db.query(UserApiKey).filter(UserApiKey.user_id == user_id).delete(synchronize_session=False)
    )
    stats["jobs_deleted"] = (
        db.query(Job).filter(Job.user_id == user_id).delete(synchronize_session=False)
    )

    # 财务事实源：不物理删除，但改写成墓碑 id——从此无法回指到任何人
    stats["usage_records_anonymized"] = (
        db.query(UsageRecord)
        .filter(UsageRecord.user_id == user_id)
        .update({"user_id": tombstone}, synchronize_session=False)
    )
    stats["cdk_redemptions_anonymized"] = (
        db.query(CdkRedemption)
        .filter(CdkRedemption.user_id == user_id)
        .update({"user_id": tombstone}, synchronize_session=False)
    )
    stats["credit_ledger_anonymized"] = (
        db.query(CreditLedger)
        .filter(CreditLedger.user_id == user_id)
        .update({"user_id": tombstone}, synchronize_session=False)
    )

    user = db.get(User, user_id)
    if user:
        db.delete(user)
        stats["account_deleted"] = 1
    else:
        stats["account_deleted"] = 0

    db.commit()
    return stats
