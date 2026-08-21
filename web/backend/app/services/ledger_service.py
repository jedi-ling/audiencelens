"""判断复利闭环（Judgment Ledger）——产品的护城河层。

一次性评审工具的问题：跑完出报告，关系就断了，经验不沉淀。
这一层把每次评审的**可证伪预测**落库并盖时间戳；日后真人测试/上线数据
回来，回填 Outcome 打分。于是系统能回答：

    "P14 价格敏感型历史上说中过多少次？"
    "'新手引导太长' 这类判断，我们的命中率是多少？"

与投资类产品不同的是：我们的验证来源是**真实用户测试**，
是干净的 ground truth，不像股价那样掺杂运气噪音——这是我们更强的地方。

诚实原则：命中率基于样本量，样本不足时必须如实标注 low_confidence，
绝不用 3 个样本吹"准确率 100%"。
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BadRequest, NotFound
from app.models import Judgment, Outcome, Review

VALID_VERDICTS = ("hit", "miss", "partial", "unknown")

# 判断的来源。panel = 引擎产出的可证伪预测；user = 用户自己下的判断。
# 两者共用同一套 Outcome 回填与校准算法，所以回填一次能同时回答
# "评审团准不准"和"你自己准不准"。
VALID_SOURCES = ("panel", "user")

# 用户判断相对评审团的立场。
VALID_STANCES = ("agree", "disagree", "partial")

# 样本量低于此值时，命中率不具统计意义，必须标注
MIN_SAMPLES_FOR_CONFIDENCE = 10


def _calibration_metrics(rows) -> dict:
    """Compute reliability metrics from (confidence, verdict) observations."""
    observations = []
    verdict_value = {"hit": 1.0, "partial": 0.5, "miss": 0.0}
    for confidence, verdict in rows:
        if confidence is None or verdict not in verdict_value:
            continue
        try:
            predicted = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            continue
        observations.append((predicted, verdict_value[verdict]))

    bins = []
    calibration_error = 0.0
    for index in range(5):
        lower = index / 5
        upper = (index + 1) / 5
        members = [
            (predicted, observed)
            for predicted, observed in observations
            if (
                (lower <= predicted <= upper)
                if index == 4
                else (lower <= predicted < upper)
            )
        ]
        if not members:
            bins.append({
                "lower": lower, "upper": upper, "sample_size": 0,
                "mean_confidence": None, "observed_hit_score": None, "gap": None,
            })
            continue
        mean_confidence = sum(item[0] for item in members) / len(members)
        observed_score = sum(item[1] for item in members) / len(members)
        gap = abs(mean_confidence - observed_score)
        calibration_error += gap * len(members)
        bins.append({
            "lower": lower,
            "upper": upper,
            "sample_size": len(members),
            "mean_confidence": round(mean_confidence, 3),
            "observed_hit_score": round(observed_score, 3),
            "gap": round(gap, 3),
        })

    sample_size = len(observations)
    mean_confidence = (
        sum(item[0] for item in observations) / sample_size if sample_size else None
    )
    observed_score = (
        sum(item[1] for item in observations) / sample_size if sample_size else None
    )
    brier_score = (
        sum((predicted - observed) ** 2 for predicted, observed in observations) / sample_size
        if sample_size else None
    )
    low_confidence = sample_size < MIN_SAMPLES_FOR_CONFIDENCE
    return {
        "sample_size": sample_size,
        "mean_predicted_confidence": round(mean_confidence, 3) if mean_confidence is not None else None,
        "observed_hit_score": round(observed_score, 3) if observed_score is not None else None,
        "brier_score": round(brier_score, 4) if brier_score is not None else None,
        "expected_calibration_error": (
            round(calibration_error / sample_size, 4) if sample_size else None
        ),
        "bins": bins,
        "low_confidence": low_confidence,
        "note": (
            f"样本量 {sample_size} < {MIN_SAMPLES_FOR_CONFIDENCE}，校准指标仅供参考，不具统计意义"
            if low_confidence else None
        ),
    }


def confidence_calibration(
    db: Session, user_id: Optional[str], persona_id: str = None
) -> dict:
    """Compare predicted confidence with verified outcomes.

    ``partial`` maps to 0.5, ``hit`` to 1, and ``miss`` to 0. Unknown outcomes
    and judgments without confidence are excluded and counted explicitly.
    """
    q = db.query(Judgment.confidence, Outcome.verdict).join(
        Outcome, Outcome.judgment_id == Judgment.id
    )
    if user_id is not None:
        q = q.filter(Judgment.user_id == user_id)
    if persona_id:
        q = q.filter(Judgment.persona_id == persona_id)
    all_rows = q.all()
    metrics = _calibration_metrics(all_rows)
    metrics.update({
        "persona_id": persona_id,
        "verified_rows": len(all_rows),
        "excluded_rows": len(all_rows) - metrics["sample_size"],
        "outcome_mapping": {"hit": 1.0, "partial": 0.5, "miss": 0.0},
        "confidence_source": (
            "synthetic_panel_heuristic_pending_empirical_recalibration"
        ),
    })
    return metrics


def extract_judgments_from_report(report: dict) -> List[dict]:
    """从评审报告里抽出可证伪的预测。

    来源优先级：priority_fixes（已经是"该修什么"的断言）> 各人格 key_issues。
    只抽有明确断言的，不抽"感觉还行"这种无法证伪的话。
    """
    out = []
    seen = set()

    # 新报告优先使用显式可证伪预测。旧报告没有 predictions 时继续走下方兼容路径。
    for prediction in report.get("predictions", []) or []:
        claim = (prediction.get("claim") or "").strip()
        if not claim or claim in seen:
            continue
        seen.add(claim)
        out.append(
            {
                "persona_id": None,
                "claim": claim,
                "severity": prediction.get("severity"),
                "confidence": prediction.get("confidence"),
                "evidence": {
                    key: prediction.get(key)
                    for key in (
                        "prediction_id", "type", "issue", "intervention", "target_metric",
                        "direction", "comparison", "success_criterion", "verification_window",
                        "verification_method", "confidence_basis", "affected_personas",
                        "evidence", "is_synthetic",
                    )
                    if prediction.get(key) is not None
                },
            }
        )

    if out:
        return out

    for fix in report.get("priority_fixes", []) or []:
        claim = (fix.get("title") or fix.get("issue") or "").strip()
        if not claim or claim in seen:
            continue
        seen.add(claim)
        out.append(
            {
                "persona_id": None,  # 合议结论
                "claim": claim,
                "severity": fix.get("severity"),
                "confidence": fix.get("confidence"),
                "evidence": fix.get("evidence") or fix.get("why_it_matters"),
            }
        )

    for note in report.get("persona_notes", []) or []:
        pid = note.get("persona_id")
        for issue in note.get("key_issues", []) or []:
            claim = (issue.get("title") or "").strip()
            key = f"{pid}::{claim}"
            if not claim or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "persona_id": pid,
                    "claim": claim,
                    "severity": issue.get("severity"),
                    "confidence": note.get("confidence"),
                    "evidence": issue.get("why_it_matters"),
                }
            )
    return out


def record_judgments(db: Session, review: Review, report: dict) -> int:
    """评审完成时调用：把预测落库并盖时间戳。返回记录条数。"""
    if not settings.ledger_enabled or not report:
        return 0

    rows = extract_judgments_from_report(report)
    now = datetime.now(timezone.utc)
    for r in rows:
        db.add(
            Judgment(
                review_id=review.id,
                user_id=review.user_id or "anonymous",
                persona_id=r["persona_id"],
                claim=r["claim"][:2000],
                severity=r.get("severity"),
                confidence=r.get("confidence"),
                evidence=(
                    r.get("evidence")
                    if isinstance(r.get("evidence"), dict)
                    else ({"note": r.get("evidence")} if r.get("evidence") else None)
                ),
                predicted_at=now,
            )
        )
    db.commit()
    return len(rows)


def list_judgments(
    db: Session, user_id: str, review_id: str = None, only_unverified: bool = False, limit: int = 200
) -> List[dict]:
    # eager 装载 outcome 与所属评审：下面每行都要读 j.outcome（序列化）和
    # j.review 的标题/项目名（追踪卡按项目分组用），不 eager 的话是每行两条
    # 额外 SELECT——这个接口是"待回填"工作台每次打开都调的。
    from sqlalchemy.orm import contains_eager, joinedload

    q = (
        db.query(Judgment)
        .outerjoin(Outcome, Outcome.judgment_id == Judgment.id)
        .options(contains_eager(Judgment.outcome), joinedload(Judgment.review))
        .filter(Judgment.user_id == user_id)
    )
    if review_id:
        q = q.filter(Judgment.review_id == review_id)
    if only_unverified:
        # **必须在 SQL 层过滤，不能取回来再在 Python 里跳过。**
        # 下面的 .limit() 是在数据库里生效的：先截断再过滤，等于"最新的 200 条
        # 里没有未回填的"就返回空——而"新的都回填了、旧的还欠着"是最正常不过的
        # 状态。首页的待验证追踪卡直接显示这个数，用户会看到「0 条待验证」
        # 然后以为自己已经回填完了。
        # 回归测试：test_platform_links.py::test_only_unverified_filters_before_the_limit
        q = q.filter(Outcome.id.is_(None))
    # 多取一条探测截断：正好取满 limit 时无法区分"就这么多"和"还有更多"，
    # 而追踪卡直接把这个数展示给用户——显示"恰好 200 条"而实际更多，
    # 数字就失真了（本仓库对数字的底线）。探测行只用于判定，不进结果。
    rows = q.order_by(Judgment.predicted_at.desc()).limit(limit + 1).all()
    truncated = len(rows) > limit
    rows = rows[:limit]

    out = []
    for j in rows:
        oc = j.outcome
        out.append(
            {
                "id": j.id,
                "review_id": j.review_id,
                "persona_id": j.persona_id,
                "claim": j.claim,
                "severity": j.severity,
                "confidence": j.confidence,
                "predicted_at": j.predicted_at.isoformat() if j.predicted_at else None,
                # 评审上下文：追踪卡要显示"哪个项目/哪次评审留下的"。
                # j.review 理论上恒存在（review_id 是 NOT NULL 外键），但被
                # 直接 SQL 动过的库什么都可能发生，缺了就发 None 而不是炸接口。
                "review_title": j.review.target_title if j.review else None,
                "project_key": j.review.project_key if j.review else None,
                "outcome": (
                    {
                        "verdict": oc.verdict,
                        "source": oc.source,
                        "note": oc.note,
                        "verified_at": oc.verified_at.isoformat() if oc.verified_at else None,
                    }
                    if oc
                    else None
                ),
            }
        )
    # 端点把 truncated 一并透出（响应形状 {"judgments": [...], "truncated": bool}）。
    # 挂在函数属性上会引入隐藏状态；改返回值又会破坏 admin 等既有调用方——
    # 用最直白的方式：返回 dict 的调用方自己解包。
    return {"judgments": out, "truncated": truncated}


def create_user_judgment(
    db: Session,
    review_id: str,
    user_id: str,
    claim: str,
    stance: str,
    confidence: Optional[float] = None,
    rationale: Optional[List[str]] = None,
    based_on_judgment_id: Optional[str] = None,
) -> dict:
    """记录**用户自己的**判断。

    为什么这件事重要：留档层此前只记评审团的预测，回填之后也只能回答
    "评审团准不准"。而用户真正关心的是自己的判断在变准——一个只给工具打分
    的系统，用户没有理由长期用它。ARTi 的「创建我的判断」抓的就是这一点。

    我们比按股价验证的产品更有底气：ground truth 是真人测试结果，
    不掺"赶上普涨"那种运气噪音。所以"你 vs 评审团"这个对比在我们这里是可信的。

    实现上刻意**复用 Judgment 表**而不是另起一张：用户判断和评审团预测要用
    同一套 Outcome 回填、同一套 Brier/ECE 算法才可比。两张表 = 两套算法 = 不可比，
    也就是本仓库反复清理的"同一件事两套实现"。
    """
    if stance not in VALID_STANCES:
        raise BadRequest(f"stance 必须是 {', '.join(VALID_STANCES)} 之一")
    claim = (claim or "").strip()
    if not claim:
        raise BadRequest("claim 不能为空——没有内容的判断无法被证伪，也就无法回填")

    review = db.get(Review, review_id)
    if not review or (review.user_id or "anonymous") != user_id:
        raise NotFound("评审不存在")  # 不泄露他人数据的存在性

    if confidence is not None:
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            raise BadRequest("confidence 必须是 0-1 之间的数字")

    j = Judgment(
        review_id=review_id,
        user_id=user_id,
        persona_id=None,
        source="user",
        stance=stance,
        claim=claim[:2000],
        confidence=confidence,
        # 理由与"针对评审团哪条判断"都存进 evidence：它是 JSON 列，
        # 不为此再加两列——这两个字段只有用户判断才有，加列会让 panel 行
        # 永远是 NULL。
        evidence={
            "rationale": rationale or [],
            "based_on_judgment_id": based_on_judgment_id,
        },
        predicted_at=datetime.now(timezone.utc),
    )
    db.add(j)
    db.commit()
    return {
        "id": j.id,
        "review_id": review_id,
        "source": "user",
        "stance": stance,
        "claim": j.claim,
        "confidence": j.confidence,
    }


def scoreboard(db: Session, user_id: str) -> dict:
    """你 vs 评审团 —— 同一批回填结果下两个来源各自的命中率。

    只有**双方都有已验证样本**时这个对比才有意义；任一方为空时如实说明，
    不拿 0/0 拼一个"你 100% 领先"出来。
    """
    panel = hit_rate(db, user_id, source="panel")
    user = hit_rate(db, user_id, source="user")
    # sample_size = 已定论条数（hit+partial+miss，unknown 不计入分母），
    # 与 hit_rate 里算 hit_rate 用的是同一个分母——两边口径必须一致。
    comparable = panel["sample_size"] > 0 and user["sample_size"] > 0
    return {
        "panel": panel,
        "user": user,
        "comparable": comparable,
        "note": (
            None
            if comparable
            else "双方都要有已回填的判断才能比较——回填得越多，这个对比越可信。"
        ),
    }


def verify_judgment(
    db: Session,
    judgment_id: str,
    verdict: str,
    user_id: str,
    source: str = "playtest",
    note: Optional[str] = None,
) -> dict:
    """回填验证结果——闭环的另一半。"""
    if verdict not in VALID_VERDICTS:
        raise BadRequest(f"verdict 必须是 {', '.join(VALID_VERDICTS)} 之一")

    j = db.get(Judgment, judgment_id)
    if not j:
        raise NotFound("判断不存在")
    if (j.user_id or "anonymous") != user_id:
        raise NotFound("判断不存在")  # 不泄露他人数据的存在性

    existing = db.query(Outcome).filter(Outcome.judgment_id == judgment_id).first()
    if existing:
        existing.verdict = verdict
        existing.source = source
        existing.note = note
        existing.verified_at = datetime.now(timezone.utc)
    else:
        db.add(
            Outcome(
                judgment_id=judgment_id, verdict=verdict, source=source, note=note
            )
        )
    db.commit()
    return {"judgment_id": judgment_id, "verdict": verdict, "source": source}


def hit_rate(
    db: Session,
    user_id: Optional[str],
    persona_id: str = None,
    source: Optional[str] = None,
) -> dict:
    """命中率统计。样本不足时如实标注，不吹牛。

    user_id=None 时不按用户过滤——用于后台管理面板的跨用户聚合视图；
    产品侧调用永远传具体 user_id，行为不变。

    source=None 时统计全部（保持既有调用方行为不变）；传 'panel' / 'user'
    可分别得到"评审团准不准"与"你自己准不准"——这两个数放在一起才是用户
    真正关心的东西，而我们的 ground truth 是真人测试，不掺股价那种运气噪音。
    """
    q = db.query(Outcome.verdict, func.count(Outcome.id)).join(
        Judgment, Outcome.judgment_id == Judgment.id
    )
    if user_id is not None:
        q = q.filter(Judgment.user_id == user_id)
    if persona_id:
        q = q.filter(Judgment.persona_id == persona_id)
    if source:
        q = q.filter(Judgment.source == source)
    counts = dict(q.group_by(Outcome.verdict).all())

    hit = int(counts.get("hit", 0))
    partial = int(counts.get("partial", 0))
    miss = int(counts.get("miss", 0))
    unknown = int(counts.get("unknown", 0))
    decided = hit + partial + miss  # unknown 不计入分母

    total_q = db.query(func.count(Judgment.id))
    if user_id is not None:
        total_q = total_q.filter(Judgment.user_id == user_id)
    if source:
        total_q = total_q.filter(Judgment.source == source)
    total_judgments = total_q.scalar() or 0

    rate = None
    if decided > 0:
        # partial 记半分
        rate = round((hit + 0.5 * partial) / decided, 3)

    return {
        "persona_id": persona_id,
        "total_judgments": int(total_judgments),
        "verified": decided + unknown,
        "pending_verification": int(total_judgments) - (decided + unknown),
        "hit": hit,
        "partial": partial,
        "miss": miss,
        "unknown": unknown,
        "hit_rate": rate,
        "sample_size": decided,
        # 诚实标注：样本太少时命中率不具统计意义
        "low_confidence": decided < MIN_SAMPLES_FOR_CONFIDENCE,
        "note": (
            f"样本量 {decided} < {MIN_SAMPLES_FOR_CONFIDENCE}，命中率仅供参考，不具统计意义"
            if decided < MIN_SAMPLES_FOR_CONFIDENCE
            else None
        ),
    }


def persona_leaderboard(db: Session, user_id: Optional[str], limit: int = 20) -> List[dict]:
    """各人格的历史命中率排行——"哪个人格的判断最值得听"。

    user_id=None 时跨全体用户聚合——用于后台管理面板的全局人格排行。
    """
    filters = [Judgment.persona_id.isnot(None), Outcome.verdict != "unknown"]
    if user_id is not None:
        filters.append(Judgment.user_id == user_id)
    rows = (
        db.query(
            Judgment.persona_id,
            func.count(Outcome.id).label("decided"),
            func.sum(case((Outcome.verdict == "hit", 1), else_=0)).label("hits"),
            func.sum(case((Outcome.verdict == "partial", 1), else_=0)).label("partials"),
        )
        .join(Outcome, Outcome.judgment_id == Judgment.id)
        .filter(*filters)
        .group_by(Judgment.persona_id)
        .order_by(func.count(Outcome.id).desc())
        .limit(limit)
        .all()
    )

    out = []
    for persona_id, decided, hits, partials in rows:
        decided = int(decided or 0)
        hits = int(hits or 0)
        partials = int(partials or 0)
        out.append(
            {
                "persona_id": persona_id,
                "sample_size": decided,
                "hit_rate": round((hits + 0.5 * partials) / decided, 3) if decided else None,
                "low_confidence": decided < MIN_SAMPLES_FOR_CONFIDENCE,
            }
        )
    return out
