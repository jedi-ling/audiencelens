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
      → 写 UsageRecord（计费事实源；平台垫付时是把入口占位改写成真实用量）
      → 失败时退还入口扣掉的 CDK 次数（quota_service.refund_review_credit，幂等）
        并释放入口占的日配额名额（quota_service.release_review_slot）

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
from app.services import admin_settings_service, job_service, ledger_service, quota_service
from app.services.json_safe import json_safe

# 把仓库的 src/ 挂到 path，复用 CLI 那套引擎（引擎侧 tests/ 有独立测试套件；
# 不在这里写死项数——数字会随开发漂移，写死了下一个读到的人就被骗一次）
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
    provider: str = "anthropic",
    model: str = None,
    api_base: str = None,
) -> str:
    """入队一次评审，返回 job_id。

    provider/model/api_base：BYOK 选了非 Anthropic 服务商（DeepSeek/Kimi/通义千问/
    智谱GLM/Ollama…）时透传给引擎，见 src/runner/llm_client.py。
    """
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
        provider,
        model,
        api_base,
    )
    return job_id


def _execute_review(
    review_id: str,
    api_key: str,
    key_source: str,
    user_id: str,
    job_id: str,
    provider: str = "anthropic",
    model: str = None,
    api_base: str = None,
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

        # key 显式传参，绝不写进程全局 os.environ ——
        # 多 worker 并发跑不同用户的评审时，环境变量注入会在用户间串 key（安全+计费问题）
        personas_path = None
        if review.persona_pack:
            personas_path = os.path.join(
                settings.repo_root, "src", "personas", f"{review.persona_pack}.yaml"
            )
            if not os.path.isfile(personas_path):
                personas_path = None

        def _on_persona_done(done: int, total: int, persona_id: str) -> None:
            """runner worker 线程回调：逐人格推 WS 进度 + 更新 job 进度。

            进度映射：人格阶段占 5%→80% 区间，即 5 + int(75 * done / total)。
            run_panel 已兜住回调异常，这里失败不会拖垮评审。
            """
            progress = 5 + int(75 * done / total) if total else 5
            _broadcast(
                review_id,
                "review.persona_completed",
                {
                    "review_id": review_id,
                    "persona_id": persona_id,
                    "done": done,
                    "total": total,
                },
            )
            _broadcast(
                review_id,
                "review.progress",
                {"review_id": review_id, "progress": progress},
            )
            job_service.update_progress(job_id, progress)

        result = run_panel(
            task_type=review.task_type,
            artifact_bundle=review.artifact_bundle,
            personas_path=personas_path,
            # 后台面板可实时覆盖（回落 env）——并发度直接决定单次评审的
            # 峰值成本与上游 429 风险，运营必须能在不重启的情况下调。
            max_concurrency=admin_settings_service.get(
                db, "review_concurrency", settings.review_concurrency
            ),
            progress_callback=_on_persona_done,
            api_key=api_key,
            provider=provider,
            model_override=model,
            api_base=api_base,
            selected_personas=review.selected_personas,
            mode=review.mode,
        )

        job_service.update_progress(job_id, 80)

        # 安全网：绝不把模拟数据当成真实评审入库
        if result.get("simulated"):
            raise RuntimeError(
                "评审在模拟模式下运行（未检测到有效 API Key），结果无评审价值，已丢弃。"
            )

        report = result.get("report") or {}
        review.report_json = report
        review.report_markdown = result.get("markdown") or ""
        # 必须过 json_safe：calibration.coverage.pairwise_distances 用 (id1, id2)
        # 元组做键，直接进 JSON 列会 TypeError("keys must be str ... not tuple")，
        # 整条 UPDATE 失败 → full 档评审 100% 标成 failed，且报错与评审内容毫无关系。
        # v1（services/__init__.py）早就这么做了，v2 漏了——而前端走的正是 v2。
        review.calibration = json_safe(result.get("calibration"))
        cost_summary = result.get("cost_summary") or {}
        cost = float(cost_summary.get("total_cost", 0.0))
        persona_count = int(cost_summary.get("persona_count", 0))
        input_tokens = int(cost_summary.get("total_input_tokens", 0))
        output_tokens = int(cost_summary.get("total_output_tokens", 0))
        review.total_cost_usd = cost
        review.input_tokens = input_tokens
        review.output_tokens = output_tokens
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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            key_source=key_source,
        )

        # 自动质量评估（Wizard"启用评估"开关）：失败不拖垮已完成的评审
        if review.enable_evaluation:
            try:
                from app.services.evaluation_service import EvaluationService

                EvaluationService.run_full_evaluation(db, review.id)
                _broadcast(
                    review_id,
                    "review.evaluation_completed",
                    {"review_id": review_id},
                )
            except Exception as exc:
                logger.warning("review %s 自动评估失败（评审本身不受影响）: %s", review_id, exc)

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

            # 退还入口扣掉的评审次数（credits 模式）。次数是用户花钱买的，
            # 不该被一次模型报错吞掉；以 review_id 为幂等键，同一条评审
            # 失败/重试多次也只退一次（见 cdk_service.refund_credit）。
            # 单独包一层 try 的理由：退还失败不能顶替掉原始异常——job 里
            # 必须记着"评审为什么挂"，而不是"退款时又挂了"。但它绝不静默：
            # 留 ERROR 级堆栈 + 明确说清"用户次数被吞、需人工补"，
            # 钱的事情出问题必须在日志里看得见。
            try:
                refunded = quota_service.refund_review_credit(
                    db, user_id, review_id, key_source=key_source
                )
                if refunded:
                    logger.info("review %s 失败，已退还 1 次评审次数给 %s", review_id, user_id)
                # plan 模式的日名额是在入口占位的（quota_service._reserve_review_slot）。
                # 评审没跑成，这个占位必须立刻还回去——否则用户被自己失败的评审
                # 挡在门外，最长挡满一个 TTL。与上面的次数退还是两种资源，
                # 各自独立，不能只做一半（credits 模式没有占位，这里自然是空操作）。
                if quota_service.release_review_slot(db, user_id, key_source=key_source):
                    logger.info("review %s 失败，已释放 %s 的 1 个日配额占位", review_id, user_id)
            except Exception:
                db.rollback()
                logger.exception(
                    "review %s 失败后退还评审次数/释放配额占位也失败——"
                    "用户 %s 的额度被吞了，需人工补偿",
                    review_id,
                    user_id,
                )
        finally:
            _broadcast(review_id, "review.failed", {"review_id": review_id, "error": str(exc)})
        raise
    finally:
        db.close()
