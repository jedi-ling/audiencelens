"""用户数据自主权：导出我的全部数据 / 彻底删除我的账号。

这是"凭什么相信你不拿我的东西"这个问题唯一能被用户亲手验证的答案——
政策写得再好也只是承诺，能一键导出、能一键删干净才是可检验的事实。

关于删除的边界（诚实划线，隐私政策里必须同样口径写清楚）：
    立即物理删除：评审内容、材料原文、报告、追问记录、人格输出、
                  判断留档、反馈、伦理报告（含内容摘录）、BYOK 密钥、
                  认证令牌（邮箱验证/密码重置）、账号本身
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
    AuthToken,
    CdkCode,
    CdkRedemption,
    Conversation,
    CreditLedger,
    Project,
    EthicsReport,
    EvaluationResult,
    EvaluationScorecard,
    FeedbackAdoption,
    Job,
    Judgment,
    Outcome,
    Review,
    ReviewChatMessage,
    ReviewFeedback,
    UploadedFile,
    User,
    UserApiKey,
    UsageRecord,
)


# 「导出覆盖了哪些表」的唯一声明处，由 tests/test_user_data_rights.py 钉住：
# 新加一张表而不在这两个集合之一里登记，测试立刻变红。
#
# 为什么要这么钉：导出功能天然会随时间腐化——加表的人只关心新功能，
# 不会想起"删号前先导出留个备份"这句承诺。而腐化的表现是静默的：
# 导出照样成功，只是少了几类内容，用户照做之后删号，那些内容永久消失
# 且从未出现在备份里。没有护栏就没有任何人会发现。
EXPORTED_TABLES = frozenset({
    "users",
    "user_api_keys",
    "reviews",
    "persona_outputs",
    "review_chat_messages",
    "conversations",
    "conversation_messages",
    "projects",
    "uploaded_files",
    "evaluation_results",
    "evaluation_scorecards",
    "ethics_reports",
    "judgments",
    "outcomes",
    "review_feedback",
    "feedback_adoptions",
    "usage_records",
    "jobs",
    "cdk_redemptions",
    "credit_ledger",
})

# 明确不导出，每条都要有理由——"忘了"和"故意不给"必须能被区分开。
EXPORT_EXEMPT_TABLES = {
    # 邮箱验证/密码重置令牌的哈希。对用户零信息价值，写进一个会被随手
    # 放进下载目录的文件里只是凭空多一个凭据泄露面。
    "auth_tokens": "认证令牌哈希，对用户无信息价值且属于凭据",
    # 平台侧库存/配置/审计，不是任何一个用户的内容。
    "platform_settings": "平台运行时配置，非用户内容",
    "cdk_codes": "平台兑换码库存；用户自己的兑换记录见 cdk_redemptions",
    "admin_audit_log": "管理员操作审计流水，非用户内容",
}


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

    # 评审的六类附属数据按 review_ids 一次性批量取回、内存里按 review_id 分组。
    # 以前是每条评审 5~6 次独立查询：200 条评审 = 1000+ 次往返，而这个导出端点
    # 是同步的——用户点一下"导出"，请求就挂在那里等一千次查询跑完。
    # 排序沿用原来的口径（chat 按 created_at、judgment 按 predicted_at），
    # 由 SQL 全局排序 + 稳定分组保证每组内部顺序不变，导出内容逐字节等价。
    review_ids = [r.id for r in reviews]

    chats_by_review: Dict[str, list] = {}
    judgments_by_review: Dict[str, list] = {}
    feedback_by_review: Dict[str, Any] = {}
    evaluations_by_review: Dict[str, list] = {}
    scorecard_by_review: Dict[str, Any] = {}
    ethics_by_review: Dict[str, list] = {}
    if review_ids:
        for m in (
            db.query(ReviewChatMessage)
            .filter(ReviewChatMessage.review_id.in_(review_ids))
            .order_by(ReviewChatMessage.created_at)
        ):
            chats_by_review.setdefault(m.review_id, []).append(m)
        for j in (
            db.query(Judgment)
            .filter(Judgment.review_id.in_(review_ids))
            .order_by(Judgment.predicted_at)
        ):
            judgments_by_review.setdefault(j.review_id, []).append(j)
        # 语义与原来的 .first() 一致：一条评审至多取一份反馈，
        # setdefault 保证有多行时只保留先出现的那行
        for fb in db.query(ReviewFeedback).filter(ReviewFeedback.review_id.in_(review_ids)):
            feedback_by_review.setdefault(fb.review_id, fb)
        for e in db.query(EvaluationResult).filter(EvaluationResult.review_id.in_(review_ids)):
            evaluations_by_review.setdefault(e.review_id, []).append(e)
        # EvaluationScorecard 的主键就是 review_id（原来是 db.get(…, r.id)）
        for sc in db.query(EvaluationScorecard).filter(EvaluationScorecard.review_id.in_(review_ids)):
            scorecard_by_review[sc.review_id] = sc
        for er in db.query(EthicsReport).filter(EthicsReport.review_id.in_(review_ids)):
            ethics_by_review.setdefault(er.review_id, []).append(er)

    review_payload = []
    for r in reviews:
        chats = chats_by_review.get(r.id, [])
        judgments = judgments_by_review.get(r.id, [])
        feedback = feedback_by_review.get(r.id)
        evaluations = evaluations_by_review.get(r.id, [])
        scorecard = scorecard_by_review.get(r.id)
        ethics = ethics_by_review.get(r.id, [])

        review_payload.append(
            {
                "id": r.id,
                "task_type": r.task_type,
                "target_title": r.target_title,
                "project_key": r.project_key,
                "mode": r.mode,
                "status": r.status,
                # 失败原因也要给。导出件里一条 status=failed 却不说为什么，
                # 用户只会当成"我的评审不见了"。
                "error_message": r.error_message,
                "created_at": _iso(r.created_at),
                "completed_at": _iso(r.completed_at),
                "total_cost_usd": r.total_cost_usd,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                # 这四项是用户自己选的评审参数。不带走的话，导出件只是一堆
                # 结果文本，没法回答"这次是用哪个人格包、哪些人格、什么技能跑的"，
                # 也就无法据此重建一次评审。
                "persona_pack": r.persona_pack,
                "selected_personas": r.selected_personas,
                "skill_type": r.skill_type,
                "enable_red_team": r.enable_red_team,
                # 用户自己上传的原始材料——这是"我的东西"的核心，必须给全
                "artifact_bundle": r.artifact_bundle,
                "report_json": r.report_json,
                "report_markdown": r.report_markdown,
                # 置信度校准是报告页真的会显示给用户的一块内容，
                # 缺了它导出件和用户在页面上看到的报告就不是同一份东西。
                "calibration": r.calibration,
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
                # 以下四块在 delete_user_data 的 docstring 里被明确列为
                # "立即物理删除的用户内容"，删除侧逐项删、导出侧此前一条都没给。
                # 用户被建议"删号前先导出留个备份"，照做之后这些内容永久消失
                # 且从未出现在备份里——那是这个功能能犯的最严重的错。
                "judgments": [
                    {
                        "id": j.id,
                        "persona_id": j.persona_id,
                        "claim": j.claim,
                        "severity": j.severity,
                        "confidence": j.confidence,
                        "evidence": j.evidence,
                        "predicted_at": _iso(j.predicted_at),
                        # 事后验证结果与判断是一体的，分开导出等于把
                        # "当时预测了什么"和"后来是否说中"割裂开，两边都失去意义
                        "outcome": (
                            {
                                "verdict": j.outcome.verdict,
                                "source": j.outcome.source,
                                "note": j.outcome.note,
                                "verified_at": _iso(j.outcome.verified_at),
                            }
                            if j.outcome
                            else None
                        ),
                    }
                    for j in judgments
                ],
                "feedback": (
                    {
                        "useful": feedback.useful,
                        "decision_changed": feedback.decision_changed,
                        "fixes_suggested": feedback.fixes_suggested,
                        "fixes_adopted": feedback.fixes_adopted,
                        "hours_saved": feedback.hours_saved,
                        "willingness_to_pay_usd": feedback.willingness_to_pay_usd,
                        "note": feedback.note,
                        "created_at": _iso(feedback.created_at),
                        "adoptions": [
                            {"fix_title": a.fix_title, "created_at": _iso(a.created_at)}
                            for a in feedback.adoptions
                        ],
                    }
                    if feedback
                    else None
                ),
                "evaluation": (
                    {
                        "overall_score": scorecard.overall_score,
                        "passed": scorecard.passed,
                        "critical_failures": scorecard.critical_failures_json or [],
                        "created_at": _iso(scorecard.created_at),
                    }
                    if scorecard
                    else None
                ),
                "evaluation_results": [
                    {
                        "dimension": e.dimension,
                        "score": e.score,
                        "passed": e.passed,
                        "details": e.details,
                        "evaluated_at": _iso(e.evaluated_at),
                    }
                    for e in evaluations
                ],
                "ethics_reports": [
                    {
                        "persona_id": er.persona_id,
                        "passed": er.passed,
                        "score": er.score,
                        # violations_json 里含用户材料的摘录——正因为它是用户内容，
                        # 删除侧才要物理删，导出侧也就必须给
                        "violations": er.violations_json or [],
                        "stereotype_risk": er.stereotype_risk,
                        "created_at": _iso(er.created_at),
                    }
                    for er in ethics
                ],
            }
        )

    keys = db.query(UserApiKey).filter(UserApiKey.user_id == user_id).all()
    usage = db.query(UsageRecord).filter(UsageRecord.user_id == user_id).all()
    jobs = db.query(Job).filter(Job.user_id == user_id).order_by(Job.created_at).all()

    # 上传的图片：只导元信息，不把字节 base64 进 JSON。
    # 一张 1MB 截图 base64 之后是 1.37MB 文本，几十张就能让导出件大到打不开，
    # 而用户真正想确认的是"我传过哪些图、还在不在"。
    # 附带说明下载地址，让这份清单是可兑现的而不是一串没法用的 id。
    uploads = (
        db.query(UploadedFile)
        .filter(UploadedFile.user_id == user_id)
        .order_by(UploadedFile.created_at)
        .all()
    )

    # 兑换与额度流水：删号时它们不被物理删除（财务事实源），只改写成墓碑 id。
    # 正因为删号之后用户再也查不到自己兑换过什么，导出侧更必须给全。
    redemptions = (
        db.query(CdkRedemption, CdkCode.code)
        .outerjoin(CdkCode, CdkCode.id == CdkRedemption.code_id)
        .filter(CdkRedemption.user_id == user_id)
        .order_by(CdkRedemption.created_at)
        .all()
    )
    ledger = (
        db.query(CreditLedger)
        .filter(CreditLedger.user_id == user_id)
        .order_by(CreditLedger.created_at)
        .all()
    )

    # 对话必须进导出：它不挂在 Review 上（一段对话可能没产出评审），
    # 上面按 Review 组装的 review_payload 一条都覆盖不到。少了它，
    # "导出我的全部数据"就是一句不实描述——而用户自己打的字正是他最在意的部分。
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    conversation_payload = [
        {
            "id": c.id,
            "title": c.title,
            "review_id": c.review_id,
            "project_id": c.project_id,
            "created_at": _iso(c.created_at),
            "updated_at": _iso(c.updated_at),
            "messages": [
                {
                    "seq": m.seq,
                    "role": m.role,
                    "content": m.content,  # 导出给本人，不做匿名裁剪
                    "meta": m.meta_json,
                    "created_at": _iso(m.created_at),
                }
                for m in c.messages
            ],
        }
        for c in conversations
    ]

    projects = (
        db.query(Project).filter(Project.user_id == user_id).order_by(Project.created_at).all()
    )
    project_payload = [
        {
            "id": p.id,
            "name": p.name,
            "created_at": _iso(p.created_at),
            "updated_at": _iso(p.updated_at),
        }
        for p in projects
    ]

    return {
        # 3：补上了 Project（对话分组）。
        # 版本号往上走而不是原地改，是为了让拿着老导出件的人能知道自己那份缺哪些块。
        "export_version": 3,
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
        "conversations": conversation_payload,
        "projects": project_payload,
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
        "uploaded_files": [
            {
                "id": f.id,
                "filename": f.filename,
                "media_type": f.media_type,
                "byte_size": f.byte_size,
                "sha256": f.sha256,
                "created_at": _iso(f.created_at),
                "download_path": f"/api/uploads/{f.id}",
            }
            for f in uploads
        ],
        "jobs": [
            {
                "id": j.id,
                "kind": j.kind,
                "ref_id": j.ref_id,
                "status": j.status,
                "progress": j.progress,
                "error_message": j.error_message,
                "created_at": _iso(j.created_at),
                "started_at": _iso(j.started_at),
                "finished_at": _iso(j.finished_at),
            }
            for j in jobs
        ],
        "cdk_redemptions": [
            {
                "code": code,
                "credits": red.credits,
                "created_at": _iso(red.created_at),
            }
            for red, code in redemptions
        ],
        "credit_ledger": [
            {
                "delta": e.delta,
                "reason": e.reason,
                "ref_id": e.ref_id,
                "created_at": _iso(e.created_at),
            }
            for e in ledger
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

    # 删评审之前，先把用量流水指向这些评审的外键置空。
    # 用量流水是财务事实源，不能跟着评审删（见上面的边界说明），但它的
    # review_id 是真外键：评审没了还指着，PostgreSQL 会直接拒绝这次删除，
    # 于是每个注册用户的删号请求 100% 报 500。以前这条路径在 SQLite 上
    # 一直"正常"，只是因为 SQLite 默认根本不校验外键。
    # 模型上已经改成 ondelete=SET NULL，但老库建表时没有那个子句，
    # 所以这里显式再置空一次——升级上来的实例同样不能炸。
    review_ids = [r.id for r in reviews]
    stats["usage_records_detached"] = (
        db.query(UsageRecord)
        .filter(UsageRecord.review_id.in_(review_ids))
        .update({"review_id": None}, synchronize_session=False)
        if review_ids
        else 0
    )

    for r in reviews:
        db.delete(r)

    # 对话：与评审是两套独立归属（一段对话可能一条评审都没产出），
    # 所以不会被上面的 Review 级联带走，必须单独删。逐条 db.delete 而不是
    # 批量 delete()：批量删绕过 ORM 级联，conversation_messages 会成为
    # 指向已删对话的孤儿行——用户资料删了，他打的字还留在库里。
    conversations = db.query(Conversation).filter(Conversation.user_id == user_id).all()
    stats["conversations_deleted"] = len(conversations)
    stats["conversation_messages_deleted"] = sum(len(c.messages) for c in conversations)
    for c in conversations:
        db.delete(c)

    # 项目：对话已经删完了（不管是不是先删的项目，ON DELETE SET NULL
    # 在 SQLite 下也不会自动生效），这里直接删项目记录本身即可，
    # 不需要再显式解绑什么。
    stats["projects_deleted"] = (
        db.query(Project).filter(Project.user_id == user_id).delete(synchronize_session=False)
    )

    # 上传的图片：磁盘上的字节也要删。只删库会留下永远没人认领的文件——
    # 已经没有任何记录指向它们，连"这是谁的"都查不出来。
    from app.services import file_store

    files_deleted, bytes_freed = file_store.delete_for_user(db, user_id)
    stats["uploaded_files_deleted"] = files_deleted
    stats["uploaded_bytes_freed"] = bytes_freed

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

    # 认证令牌（邮箱验证 / 密码重置）：必须随账号物理删除。
    # 两个理由，任何一个单独都足够：
    #   1. 它对 users.id 是真外键。留下孤儿行后，下面那句删 users 在
    #      PostgreSQL 上必然违反外键约束——即"删号对每个注册用户 100% 报 500"。
    #      SQLite 默认关闭外键校验，所以本机怎么删都看着成功。
    #   2. 未过期的 reset_password 令牌是能改密码的凭据，账号都删了还留着它，
    #      与隐私页写的"账号本身立即物理删除"直接矛盾。
    stats["auth_tokens_deleted"] = (
        db.query(AuthToken)
        .filter(AuthToken.user_id == user_id)
        .delete(synchronize_session=False)
    )

    user = db.get(User, user_id)
    if user:
        db.delete(user)
        stats["account_deleted"] = 1
    else:
        stats["account_deleted"] = 0

    db.commit()
    return stats
