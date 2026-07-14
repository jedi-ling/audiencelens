"""评审执行：把 runner 引擎接进 Web 全链路。

链路全貌（每一环都已通电）：
    POST /api/reviews
      → 限流 → 身份 → key 解析(BYOK/server) → 配额检查
      → 落库 Review(pending) + 入队 Job
      → 202 返回 review_id
    后台 worker
      → 执行 runner.run_panel（人格并发，见 src/runner/cli.py）
      → WS 广播 progress/persona/completed 事件
      → 落库 report + persona_outputs
      → 写 Judgment（判断复利闭环）
      → 写 UsageRecord（计费事实源）

绝不返回模拟数据：无 key 时在入口就 428 拒绝（LLMKeyMissing），
不让用户拿到没有评审价值的占位内容。
"""

import os
import sys
from datetime import datetime, timezone

from app.config import settings
from app.core.logging import logger
from app.db import session_scope
from app.models import PersonaOutput, Review
from app.services import job_service, ledger_service, quota_service

# 把仓库的 src/ 挂到 path，复用 CLI 那套已经过 232 项测试的引擎
_SRC = os.path.join(settings.repo_root, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def _broadcast(review_id: str, event: str, data: dict) -> None:
    """WS 广播；后台线程里调用，故用 manager 的线程安全入口。"""
    try:
        from app.websocket import manager

        manager.publish_threadsafe(review_id, {"event": event, "data": data})
    except Exception as exc:  # WS 挂了不能拖垮评审
        logger.warning("ws broadcast failed (%s): %s", event, exc)


def enqueue_review(
    review_id: str,
    *,
    api_key: str,
    key_source: str,
    user_id: str = "anonymous",
) -> str:
    """入队一次评审，返回 job_id。"""
    job_id = job_service.create_job(
        kind="review", ref_id=review_id, user_id=user_id, payload={"key_source": key_source}
    )
    job_service.get_backend().submit(
        job_id,
        _execute_review,
        review_id,
        api_key,
        key_source,
        user_id,
        job_id,
    )
    return job_id


def _execute_review(
    review_id: str, api_key: str, key_source: str, user_id: str, job_id: str
) -> None:
    """后台执行。异常向上抛给 job_service 记录为 failed。"""
    from runner.cli import run_panel  # 延迟导入：避免启动时就拉起重依赖

    db = session_scope()
    try:
        review = db.get(Review, review_id)
        if not review:
            raise RuntimeError(f"review {review_id} 不存在")

        review.status = "running"
        db.commit()
        _broadcast(review_id, "review.started", {"review_id": review_id})
        job_service.update_progress(job_id, 5)

        # runner 通过环境变量读 key；这里在本线程内注入，用完即撤
        prev_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = api_key
        try:
            personas_path = None
            if review.persona_pack:
                personas_path = os.path.join(
                    settings.repo_root, "src", "personas", f"{review.persona_pack}.yaml"
                )
                if not os.path.isfile(personas_path):
                    personas_path = None

            result = run_panel(
                task_type=review.task_type,
                artifact_bundle=review.artifact_bundle,
                personas_path=personas_path,
                max_concurrency=settings.review_concurrency,
            )
        finally:
            if prev_key is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = prev_key

        job_service.update_progress(job_id, 80)

        # 安全网：绝不把模拟数据当成真实评审入库
        if result.get("simulated"):
            raise RuntimeError(
                "评审在模拟模式下运行（未检测到有效 API Key），结果无评审价值，已丢弃。"
            )

        report = result.get("report") or {}
        review.report_json = report
        review.report_markdown = result.get("markdown") or ""
        review.calibration = result.get("calibration")
        cost = float((result.get("cost_summary") or {}).get("total_cost", 0.0))
        persona_count = int((result.get("cost_summary") or {}).get("persona_count", 0))
        review.total_cost_usd = cost
        review.status = "completed"
        review.completed_at = datetime.now(timezone.utc)

        for note in report.get("persona_notes", []) or []:
            db.add(
                PersonaOutput(
                    review_id=review.id,
                    persona_id=note.get("persona_id", ""),
                    persona_name=note.get("persona_name"),
                    status="completed",
                    output_json=note,
                    completed_at=datetime.now(timezone.utc),
                )
            )
        db.commit()

        # 判断复利闭环：把预测盖时间戳落库
        n_judgments = ledger_service.record_judgments(db, review, report)

        # 计费事实源：无论配额是否开启都记
        quota_service.record_usage(
            db,
            user_id,
            review_id=review.id,
            persona_count=persona_count,
            cost_usd=cost,
            key_source=key_source,
        )

        job_service.update_progress(job_id, 100)
        _broadcast(
            review_id,
            "review.completed",
            {
                "review_id": review_id,
                "persona_count": persona_count,
                "cost_usd": cost,
                "judgments_recorded": n_judgments,
            },
        )
        logger.info(
            "review %s completed: %d personas, $%.4f, %d judgments",
            review_id,
            persona_count,
            cost,
            n_judgments,
        )
    except Exception as exc:
        logger.exception("review %s failed", review_id)
        try:
            review = db.get(Review, review_id)
            if review:
                review.status = "failed"
                review.error_message = str(exc)[:2000]
                review.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            _broadcast(review_id, "review.failed", {"review_id": review_id, "error": str(exc)})
        raise
    finally:
        db.close()
