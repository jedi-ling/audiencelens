import argparse
import concurrent.futures
import copy
import json
import logging
import os
import random
import re
import threading
import time
from typing import Callable, List, Optional

import yaml

try:
    from .adaptive_panel import recommend_next_persona
    from .predictions import build_falsifiable_predictions
    from .aggregator import aggregate_report, load_aggregation_rules, render_markdown_report, render_html_report
    from .calibration import run_calibration_check
    from .cross_exam import (
        MODE_DERIVED,
        MODE_MODERATED,
        MODE_MULTI_AGENT,
        extract_controversy_points,
        run_cross_exam_protocol,
    )
    from .evidence_precheck import precheck_panel
    from .triage import run_triage, rank_for_advance
    from .llm_client import chat_completion
    from .panel_selector import (
        DISSENTER_PREFIXES,
        load_persona_pack_meta,
        load_personas,
        load_presets,
        select_panel,
    )
    # _minify_persona 是人格身份卡的唯一裁剪口径（人格评审那一轮就是用它渲染
    # persona-prompt.md 的 [PERSONA CARD]）。full 档重新调用人格做反驳时必须复用它，
    # 否则就是在代码里另开一套人格提示词，两边迟早不一致。
    from .persona_agent import (
        _minify_persona,
        estimate_cost,
        normalize_persona_output,
        parse_persona_output,
        render_prompt,
        render_prompt_split,
        select_model,
    )
    from .llm_client import LLMCallError, is_retryable_error
    from .validator import load_schema, validate_output
except ImportError:
    from runner.adaptive_panel import recommend_next_persona
    from runner.predictions import build_falsifiable_predictions
    from runner.aggregator import aggregate_report, load_aggregation_rules, render_markdown_report, render_html_report
    from runner.calibration import run_calibration_check
    from runner.cross_exam import (
        MODE_DERIVED,
        MODE_MODERATED,
        MODE_MULTI_AGENT,
        extract_controversy_points,
        run_cross_exam_protocol,
    )
    from runner.evidence_precheck import precheck_panel
    from runner.triage import run_triage, rank_for_advance
    from runner.llm_client import chat_completion
    from runner.panel_selector import (
        DISSENTER_PREFIXES,
        load_persona_pack_meta,
        load_personas,
        load_presets,
        select_panel,
    )
    from runner.persona_agent import (
        _minify_persona,
        estimate_cost,
        normalize_persona_output,
        parse_persona_output,
        render_prompt,
        render_prompt_split,
        select_model,
    )
    from runner.llm_client import LLMCallError, is_retryable_error
    from runner.validator import load_schema, validate_output

SIMULATION_WARNING = (
    "⚠️ 模拟模式（未检测到 ANTHROPIC_API_KEY）：所有人格输出均为预制占位数据，"
    "不包含任何真实评审意见，仅用于验证流水线是否可运行。"
    "请勿将本次结果用于任何决策。设置 ANTHROPIC_API_KEY 后重新运行以获得真实评审。"
)

# 评审深度档位对引擎的三个实际效果：人数上限、是否交叉质证、是否校准检查。
# 与 web/backend/app/services/__init__.py 的 REVIEW_MODES 保持一致（那边多了给
# 前端展示用的 persona_count_range 下限和 description，这里只留引擎用得到的）。
REVIEW_MODE_CONFIG = {
    "quick": {"max_personas": 3, "cross_examination": False, "calibration": False},
    "standard": {"max_personas": 6, "cross_examination": True, "calibration": False},
    "full": {"max_personas": 8, "cross_examination": True, "calibration": True},
}

# 档位 → 交叉质询模式。quick 档根本不会走到这张表（REVIEW_MODE_CONFIG 里
# cross_examination=False，一次反驳调用都不发）。
#   standard —— 一次仲裁式反驳：+1 次调用，主持人视角代双方各写一轮反驳。
#   full     —— 真多智能体反驳：每位涉事人格带着匿名的对手论据被重新调用一次，
#               成本随涉事人格数上升，所以只在 full 档开。
CROSS_EXAM_MODE_BY_REVIEW_MODE = {
    "standard": MODE_MODERATED,
    "full": MODE_MULTI_AGENT,
}

# 不传档位（CLI / MCP 等调用方）时用哪一档反驳。
#
# 这里曾经是 MODE_MULTI_AGENT，也就是"不说话就按最贵的算"：涉事人格各被重新调用
# 一次，成本随人数线性上升，而 CLI/MCP 用户根本没做过这个选择。v1 后端
# （web/backend/app/services/__init__.py 的同名表）默认是 MODE_MODERATED，
# 两条链路默认行为不一致本身也是本仓库反复清理的那类问题。
# 现在统一到较省的仲裁式一档：想要多智能体反驳必须显式 mode="full"。
DEFAULT_CROSS_EXAM_MODE = MODE_MODERATED

# full 档给每位涉事人格重新发起反驳调用时，用这段把"你是谁"重新交代一遍。
# 身份卡本体复用 persona_agent._minify_persona（与人格评审那一轮同一份卡、同一套裁剪），
# 反驳的任务说明 / 输出格式 / 匿名化口径全在 src/templates/cross-exam-prompt.md 的
# rebutter 段里——这里只补身份，不在代码里另写一套人格提示词。
REBUTTAL_PERSONA_HEADER = (
    "你是 AudienceLens 多人格评审系统中的一个固定玩家评审代理。\n"
    "你必须严格按照下方 persona 卡发言，不得切换到「通用产品经理」或「AI 助手」口吻。\n\n"
    "[PERSONA CARD]\n{persona_card}\n"
)

# 反驳轮身份卡里要摘掉的字段。**只在反驳轮摘**：人格评审那一轮（render_prompt →
# persona-prompt.md 的 [PERSONA CARD]）必须带完整身份卡，那里不受影响。
#
# 为什么反驳轮要摘：cross-exam-prompt.md 开头写着"两段都不得出现人格名字"，
# 渲染层也确实把人格名从论据正文里洗掉了——但 cli.py 又在提示词最前面接了一张
# 带 id/name 的卡，"提示词里不含人格名"这条可测的不变量当场就破了。
# 自己的名字露出来虽谈不上"按身份结盟"，却给模型留了自称身份、顺势把对手也
# 往身份上带的口子。v1 后端（_persona_identity_preamble）摘的就是这两个字段，
# 这里保持同一口径。
REBUTTAL_PERSONA_HIDDEN_FIELDS = ("id", "name")



def _json_safe(value):
    """把不能进 JSON 的字典键（主要是元组）递归拍平成字符串。

    修在这里而不是 calibration.py：元组键对 calibration 的 Python 消费方是合理的，
    真正的约束来自"report 必须可 JSON 序列化"这一条引擎自己的契约。谁把值放进
    report，谁负责满足这个契约。

    web/backend/app/services/json_safe.py 有一份同语义的实现，服务于 JSON 列。
    这里不复用它：src/runner/ 是可独立运行的引擎，反向依赖 web/backend 会让
    CLI 在没有后端的环境里直接 import 失败。
    """
    if isinstance(value, dict):
        return {
            ("|".join(str(k) for k in key) if isinstance(key, tuple) else key): _json_safe(v)
            for key, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value

def _rebuttal_persona_card(persona: dict) -> str:
    """反驳轮用的匿名身份卡：同一套 _minify_persona 裁剪，只是先摘掉 id/name。"""
    anonymous = {
        k: v for k, v in (persona or {}).items()
        if k not in REBUTTAL_PERSONA_HIDDEN_FIELDS
    }
    return _minify_persona(anonymous)

# 单一注册表：见 runner/task_types.py（这里 re-export 保持既有导入路径不破）
try:
    from .task_types import VALID_TASK_TYPES
except ImportError:
    from runner.task_types import VALID_TASK_TYPES


class AllPersonasFailedError(RuntimeError):
    """一个人格都没跑成时抛出——绝不允许拿空报告冒充"没发现问题"。

    为什么必须抛异常而不是返回报告：aggregate_report([]) 会产出
    primary_recommendation=""、release_risk="low"、0 条修复项的"干净"报告，
    用户读到的是"8 个人格都评了，没发现问题"，实际是 8 个全挂了。
    这种伪装成正常结果的失败比直接崩溃危险得多，所以必须让调用方无法忽略。

    异常也是两个调用方都已经能自然处理的形态：src/cli.py 的 run 命令外层
    catch Exception → 打印错误并 exit 1；web 后端 run_review_task 外层
    catch Exception → 把 Review 标成 failed 并广播 review.failed。

    failures：[{"persona_id": ..., "error": ...}]，各人格的真实报错原因。
    attempted / skipped_count：分别是实际发起的人格数、被证据预检等跳过的人格数。
    """

    def __init__(self, failures: List[dict], attempted: int, skipped_count: int = 0, message: str = None):
        self.failures = list(failures or [])
        self.attempted = attempted
        self.failed_count = len(self.failures)
        self.skipped_count = skipped_count
        super().__init__(message or self._build_message())

    def _build_message(self) -> str:
        if self.attempted == 0:
            return (
                "本次没有任何人格进入评审（预设面板为空，或全部被证据预检跳过），"
                f"跳过 {self.skipped_count} 位。没有任何人格输出，因此不产出报告。"
            )
        details = "; ".join(
            f"{f.get('persona_id', '?')}: {str(f.get('error', ''))[:200]}"
            for f in self.failures
        )
        return (
            f"全部 {self.attempted} 位人格评审失败，未产出任何有效输出，因此不产出报告。"
            f"各人格错误：{details}"
        )


# ---- 重试口径（budget.yaml 的 retry 段，见那里的注释）----
#
# 这四个值就是 retry_on 认的全部取值。配置里写别的会被忽略——但不是静默忽略：
# _retry_settings 会把无法识别的值原样带进返回值的 unknown 字段，run_panel 把它
# 记进 report["validation"]["retry"]，让"配了个拼错的旋钮"看得见。
RETRY_TRANSPORT = "transport_error"
RETRY_SCHEMA = "schema_failure"
RETRY_ROLE_DRIFT = "role_drift"
RETRY_HALLUCINATION = "hallucination"
KNOWN_RETRY_REASONS = (RETRY_TRANSPORT, RETRY_SCHEMA, RETRY_ROLE_DRIFT, RETRY_HALLUCINATION)

# 单个人格调用的输出上限。chat_completion 的默认 4096 对 Claude 够用，但
# MiniMax-M3 这类中文长文模型的人格 schema 输出会超过 4096 而被截断——
# 截断在 llm_client 里按不可重试的硬失败处理，等于这位人格白花钱。
# max_tokens 是上限不是目标：简洁的模型不会因此多输出。
PERSONA_MAX_TOKENS = 8192

# schema 校验里哪些字段不合格算"这位人格根本没交出可用意见"（硬失败、计入
# failed_personas / degradation），哪些只是元数据瑕疵（标注即可）。
#
# 判断依据：报告是从哪些字段拼出来的。evidence / key_issues / scores /
# primary_stance / persona_id 缺失或形状不对，聚合器就只能拿到空东西——那位人格
# 出现在"N 位角色完成评审"里但一句话没贡献，正是本仓库反复清理的那种谎话。
# 反过来，persona_version 没填、meta 里多个字段这类问题不影响任何结论，
# 把它们也判成失败会让第三方 BYOK 模型（几乎没人严格守 additionalProperties:false）
# 大面积"评审失败"，那是另一种形式的不诚实。
BLOCKING_SCHEMA_FIELDS = frozenset({
    "persona_id",
    "primary_stance",
    "evidence",
    "key_issues",
    "scores",
})

_REQUIRED_PROP_RE = re.compile(r"'([^']+)' is a required property")


def _schema_error_field(message: str) -> str:
    """从 validate_schema 拼出来的错误字符串里取出"这条错误说的是哪个顶层字段"。

    validate_schema 返回的是 f"{'.'.join(path)}: {message}"，两种形态：
      · "evidence.0.inference_level: 'x' is not one of [...]" → 顶层字段 evidence
      · ": 'evidence' is a required property"（路径为空，缺顶层必填字段）→ evidence
    """
    path, _, detail = message.partition(": ")
    if path:
        return path.split(".")[0]
    m = _REQUIRED_PROP_RE.search(detail)
    return m.group(1) if m else ""


def blocking_schema_errors(schema_errors: List[str]) -> List[str]:
    """挑出"足以让这位人格作废"的 schema 错误，见 BLOCKING_SCHEMA_FIELDS 的说明。"""
    return [e for e in schema_errors if _schema_error_field(e) in BLOCKING_SCHEMA_FIELDS]


def _retry_settings(budget_config: dict) -> dict:
    """把 budget.yaml 的 retry 段读成引擎真正用得上的形状。

    配置缺失时退回"不重试"——不是退回某个隐含默认值。默认值藏在代码里、
    配置文件里看不见，本身就是下一个"配置和行为对不上"的种子。
    """
    raw = (budget_config or {}).get("retry") or {}
    try:
        max_retries = int(raw.get("max_retries_per_persona") or 0)
    except (TypeError, ValueError):
        max_retries = 0
    try:
        backoff = float(raw.get("backoff_base_seconds") or 1.0)
    except (TypeError, ValueError):
        backoff = 1.0

    configured = raw.get("retry_on") or []
    if isinstance(configured, str):
        configured = [configured]
    reasons = [r for r in configured if r in KNOWN_RETRY_REASONS]
    unknown = [r for r in configured if r not in KNOWN_RETRY_REASONS]

    return {
        "max_retries": max(0, max_retries),
        "retry_on": reasons,
        "unknown_retry_on": unknown,
        "backoff_base_seconds": max(0.0, backoff),
    }


def _backoff_sleep(attempt: int, backoff_base_seconds: float) -> None:
    """指数退避 + 抖动，与 llm_client.chat_completion 同一口径。

    重试预算在 run_single_persona 一层统一管理（见 2.3 的实现说明），
    所以传输层调用 chat_completion 时不再叠它的 max_retries——退避在这里做，
    才能让"总共最多重试 N 次"真的只有一套计数。
    """
    delay = backoff_base_seconds * (2 ** attempt)
    time.sleep(delay + random.uniform(0, backoff_base_seconds))


# 争议点去重没有语义模型时，报告里必须如实写出来：词面相似度合并不了换个说法的
# 同一问题，交叉质询往往一个争议点都凑不出来——报告却只会显示"本次无显著分歧"。
# 实测见 docs/evaluation/dedup-fallback-finding.md（三份中文样例 0/61 条被合并）。
DEDUP_LEXICAL_NOTICE = (
    "语义去重未安装（Semantic dedup not installed — cross-examination may not trigger）："
    "换个说法的同一问题不会被合并成争议点，交叉质询可能无法触发。"
)


def _issue_dedup_method() -> str:
    """当前进程里争议点去重实际用的是哪一档：'semantic' 或 'lexical'。"""
    try:
        from .similarity import get_issue_similarity
    except ImportError:
        from runner.similarity import get_issue_similarity
    return get_issue_similarity().method


# ---- 诊断落盘（默认关闭）----
# AUDIENCELENS_DEBUG_RUNS=1 时，每位人格每一次尝试的**原始响应**（有没有调用
# 工具、工具输入、文本块、stop_reason）和校验结论写进仓库根的 .debug/runs/
# （已 .gitignore）。用来回答"为什么这位人格没过校验"——默认关闭，因为原始
# 响应里有完整评审内容。绝不写请求头、API key 或 prompt。
DEBUG_RUNS_ENV = "AUDIENCELENS_DEBUG_RUNS"


def _debug_runs_enabled() -> bool:
    return os.environ.get(DEBUG_RUNS_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def _write_debug_attempt(run_dir: Optional[str], persona_id: str, attempt: int, record: dict) -> None:
    if not run_dir:
        return
    try:
        os.makedirs(run_dir, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", persona_id)
        with open(os.path.join(run_dir, f"{safe}-attempt{attempt}.json"), "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, default=str)
    except OSError:
        pass  # 诊断落盘失败不得影响评审本身


def _validation_failure_reason(validation: dict) -> Optional[str]:
    """把 validate_output 的布尔结论翻译成 retry_on / 门控认的失败类型。

    优先顺序：schema_failure → role_drift → hallucination，只返回第一个命中的——
    门控和重试都只需要"这一条为什么失败"，细节留给 error 消息。
    schema 只认 BLOCKING_SCHEMA_FIELDS（persona_id/primary_stance/evidence/
    key_issues/scores）上的错误：meta 里多个字段这类不伤结论的瑕疵，重试一百次
    也一样，不该烧钱也不该拦人（见 BLOCKING_SCHEMA_FIELDS 的说明）。
    """
    if not validation.get("schema_valid"):
        schema = (validation.get("details") or {}).get("schema") or {}
        if blocking_schema_errors(schema.get("errors") or []):
            return RETRY_SCHEMA
    if not validation.get("role_consistent"):
        return RETRY_ROLE_DRIFT
    if not validation.get("evidence_grounded"):
        return RETRY_HALLUCINATION
    return None


REPAIR_FEEDBACK_MAX_ITEMS = 8
REPAIR_FEEDBACK_MAX_UNCOVERED = 3


def _repair_feedback(reason: str, validation: Optional[dict]) -> str:
    """重试时回喂给模型的那段话：校验器说了什么，就原样告诉它，并说清楚怎么改。

    不说"请再试一次"这种空话——同一份提示词原样重发，模型大概率交回同样的东西
    （诊断实测：同一位人格连续 4 次交回同一种残缺的工具输入）。
    """
    details = (validation or {}).get("details") or {}
    if reason == RETRY_HALLUCINATION:
        evidence = details.get("evidence") or {}
        # 逐条点名：是哪一条 evidence、quote 是缺了还是对不上、对不上的是哪一段。
        # 只甩回一句"没通过"，模型不知道该补 quote、改 quote，还是改标 inferred。
        entries = [d for d in (evidence.get("ungrounded_details") or []) if isinstance(d, dict)]
        if not entries:  # 兼容只带 ungrounded_evidence 的旧结构
            entries = [{"content": q} for q in (evidence.get("ungrounded_evidence") or [])]
        lines = []
        for d in entries[:REPAIR_FEEDBACK_MAX_ITEMS]:
            where = f"evidence 第 {d['index'] + 1} 条" if isinstance(d.get("index"), int) else "evidence"
            lines.append(f"- {where}（content：{str(d.get('content') or '')[:120]}）")
            if d.get("reason") == "quote_missing":
                lines.append("  缺少 quote：direct 条目必须在 quote 里放一段从材料逐字复制的原文")
                continue
            if d.get("quote"):
                lines.append(f"  quote：「{str(d['quote'])[:160]}」")
            parts = [str(u)[:60] for u in (d.get("uncovered") or []) if str(u).strip()]
            if parts:
                shown = "、".join(f"「{u}」" for u in parts[:REPAIR_FEEDBACK_MAX_UNCOVERED])
                more = "等" if len(parts) > REPAIR_FEEDBACK_MAX_UNCOVERED else ""
                lines.append(f"  原文里找不到的部分：{shown}{more}")
            else:
                lines.append("  quote 里的数字或文字与原文对不上")
        listed = "\n".join(lines)
        return (
            "你上一次提交的评审没有通过证据校验：下面这些标为 direct 的证据，quote 不是材料原文的"
            "逐字引用：\n" + listed + "\n\n"
            "规则只有一条：能把材料原文一字不差地复制进 quote，才是 direct（你的观察和评论写在 "
            "content 里，不要写进 quote）；复制不出来的概括、改写或判断请改标 inferred 并去掉 "
            "quote；材料里没有提到的请标为 gap。"
        )
    if reason == RETRY_SCHEMA:
        errors = blocking_schema_errors(((details.get("schema") or {}).get("errors")) or [])
        listed = "\n".join(f"- {e}" for e in errors[:REPAIR_FEEDBACK_MAX_ITEMS])
        return (
            "你上一次的提交没有通过 JSON Schema 校验：\n" + listed + "\n\n"
            "请按提示词里的输出骨架提交**完整**结果：所有必填字段都要有；evidence 和 "
            "key_issues 必须是对象数组，不是字符串；不要在字段值里写 <parameter> 之类的标签。"
        )
    return (
        "你上一次的回复里没有可以解析的评审结果。请通过调用提交工具交出完整的评审结果，"
        "不要用普通文本作答。"
    )


def _validation_error_message(validation: dict, reason: str) -> str:
    """把一条校验失败翻译成能直接进 failed_personas[].error 的人话。"""
    details = validation.get("details") or {}
    if reason == RETRY_SCHEMA:
        schema = details.get("schema") or {}
        top = blocking_schema_errors(schema.get("errors") or [])[:2]
        return "校验未通过（schema_failure）" + (f"：{'; '.join(top)}" if top else "")
    if reason == RETRY_ROLE_DRIFT:
        role = details.get("role") or {}
        issues = role.get("issues") or ["角色一致性不达标"]
        return "校验未通过（role_drift）：" + "; ".join(issues)
    if reason == RETRY_HALLUCINATION:
        evidence = details.get("evidence") or {}
        # hallucination_risk 是兼容键名，含义是"direct 证据中未落地条目的占比"，不是幻觉概率。
        risk = float(evidence.get("hallucination_risk", 0.0) or 0.0)
        return (
            f"校验未通过（hallucination）：direct 证据中 {risk:.0%} 的条目 quote 缺失或不是材料原文的逐字引用"
            "（阈值 30%）"
        )
    return f"校验未通过：{reason}"


def _is_dissenter(persona: dict) -> bool:
    """唱反调人格（P15 毒舌怀疑者 / P16 竞品老兵），口径复用 panel_selector 的前缀表。"""
    return any(str(persona.get("id", "")).startswith(prefix) for prefix in DISSENTER_PREFIXES)


def truncate_panel(panel_selected: List[dict], max_personas: int) -> List[dict]:
    """按档位截断面板，但必须保住"唱反调"名额。

    为什么不能直接 panel_selected[:max_personas]：select_panel 为保证面板里有异议者，
    是把 P15 **append 到列表末尾**的，从头切等于系统性地把唯一的负面视角切掉——
    quick 档（3 人）遇到预设 5 人时 P15 永远被丢弃，共识度和 release_risk 因此
    结构性偏乐观（"大家都挺看好"其实是因为唱反调的那个人没被叫来）。
    """
    if max_personas < 1 or len(panel_selected) <= max_personas:
        return panel_selected

    kept = panel_selected[:max_personas]
    if any(_is_dissenter(p) for p in kept):
        return kept

    dissenter = next((p for p in panel_selected[max_personas:] if _is_dissenter(p)), None)
    if dissenter is None:
        return kept
    # 用异议者替换掉名单里最后一位，人数上限不变（档位的省钱承诺不打折）
    return kept[:-1] + [dissenter]


def filter_genuine_controversies(controversy_points: List[dict]) -> List[dict]:
    """只保留真有分歧的议题：severity 方差 > 0 且至少 2 个不同人格参与。

    extract_controversy_points 只按方差倒序取 top3、不过滤方差为 0 的议题，于是
    只要有任何人格提了任何 issue，争议列表就恒非空 —— 单人格议题进了交叉质证后
    pro/con 是同一个 persona_id，论点还是"未从原始 persona 输出中提取到…"这类占位
    文案，用户读到的是被制造出来的对立。宁可显示"本次无显著分歧"，也不要假造争议。
    """
    genuine = []
    for cp in controversy_points:
        views = cp.get("persona_views", []) or []
        participants = {v.get("persona_id", "") for v in views}
        if len(participants) < 2:
            continue
        if (cp.get("severity_variance") or 0) <= 0:
            continue
        genuine.append(cp)
    return genuine


def run_cross_exam_stage(
    persona_outputs: List[dict],
    controversy_points: List[dict],
    personas: List[dict],
    template_path: str,
    rules: dict,
    budget_config: dict,
    usage: dict,
    mode: Optional[str] = None,
    api_key: Optional[str] = None,
    provider: str = "anthropic",
    model_override: Optional[str] = None,
    api_base: Optional[str] = None,
    max_concurrency: Optional[int] = None,
) -> dict:
    """把交叉质询真的接到 LLM 上——以前这里只把提示词渲染出来，然后原地丢掉。

    分档见 CROSS_EXAM_MODE_BY_REVIEW_MODE；mode 为空时走 DEFAULT_CROSS_EXAM_MODE
    （仲裁式一次调用，与 v1 后端同一默认）。没有 api_key（模拟模式）时**一次调用都不发**，
    直接如实走派生摘要：先发一轮注定失败的调用再回落只会白记一条 failure，
    并且会让报告里出现"交叉质询失败"这种误导性说明（真实情况是根本没有 key）。

    usage 由调用方传进来、在这里累加（calls / input_tokens / output_tokens / cost），
    调用方必须把它并进 cost_summary —— 这是新增的付费调用，不计就是计费漏洞。
    反驳失败不在这里吞：异常照原样抛给协议核心，由它记进 failures[] 并回落 mode。
    """
    if not api_key:
        return run_cross_exam_protocol(
            persona_outputs,
            controversy_points,
            mode=MODE_DERIVED,
            template_path=template_path,
            rules=rules,
        )

    requested_mode = CROSS_EXAM_MODE_BY_REVIEW_MODE.get(mode or "", DEFAULT_CROSS_EXAM_MODE)
    personas_by_id = {p.get("id", ""): p for p in personas or []}
    # 仲裁视角不属于任何人格，没有 model_hint 可依据：用预算配置的默认模型
    # （select_model 对空人格就是返回 default_model，不另写一套选型规则）。
    moderator_model = model_override or select_model({}, budget_config)
    cross_exam_max_tokens = int(budget_config.get("cross_exam_max_tokens") or PERSONA_MAX_TOKENS)

    # usage 的累加必须加锁：multi_agent 反驳档会把下面这个闭包丢进 ThreadPoolExecutor
    # 并发调用（见 cross_exam.run_cross_exam_protocol），而 `usage["calls"] += 1`
    # 这种读-改-写在多线程下不是原子操作——两个线程同时读到 3、各自写回 4，
    # 就丢了一次调用和它对应的成本（正是本文件反复强调的那种"账上看不到的钱"）。
    # 锁只圈住累加这几行，**绝不覆盖网络调用本身**，否则并发就退化成串行。
    usage_lock = threading.Lock()

    def llm_call(prompt, persona_id: str = ""):
        """交叉质询的模型出口，走仓库统一的 llm_client.chat_completion。

        persona_id 非空（full 档）时重新注入该人格的身份卡，并沿用它在人格评审
        那一轮用的模型；为空（standard 档的仲裁视角）时用默认模型。
        """
        # 先记一次尝试：失败的调用也要在账面上看得见"发过、没成"，否则计费和重试
        # 都成了黑箱。协议核心的 usage.calls 同样按尝试计，两边口径保持一致。
        with usage_lock:
            usage["calls"] += 1
        model = moderator_model
        if persona_id:
            persona = personas_by_id.get(persona_id)
            if persona is None:
                # 拿不到身份卡就不能自称"多智能体反驳"——那只是一次没有人格的通用调用。
                # 抛出去由协议核心记成该论据的失败（报告里会显示 partial/failed），
                # 而不是悄悄降级成无人格反驳还照旧宣称每个人格都重新发言过。
                raise ValueError(
                    f"人格 {persona_id} 不在本次面板里，无法注入身份卡，跳过它的反驳调用"
                )
            prompt = (
                REBUTTAL_PERSONA_HEADER.format(persona_card=_rebuttal_persona_card(persona))
                + "\n"
                + prompt
            )
            model = model_override or select_model(persona, budget_config)

        cache_usage: dict = {}
        response_info: dict = {}
        text, input_tokens, output_tokens = chat_completion(
            model=model,
            prompt=prompt,
            api_key=api_key,
            provider=provider,
            api_base=api_base,
            usage_details=cache_usage,
            # 以前这里不传，走 chat_completion 的默认 4096：带自适应思考的模型
            # （Sonnet 5.5 等）思考 token 也算在 max_tokens 里，反驳正文会被截断。
            max_tokens=cross_exam_max_tokens,
            debug_details=response_info,
        )
        # 成本在锁外先算好（纯 CPU、不碰 usage），锁内只做累加，临界区尽量短
        call_cost = estimate_cost(
            input_tokens, output_tokens, model, budget_config, cache_breakdown=cache_usage
        )
        with usage_lock:
            usage["input_tokens"] += input_tokens
            usage["output_tokens"] += output_tokens
            usage["cost"] += call_cost
        if response_info.get("stop_reason") == "max_tokens":
            # 文本档没有 schema 兜底：被截断的反驳照样"返回成功"，下游再解析失败。
            # 在这里如实标成失败（钱已经记上了），由协议核心写进 failures[] 并回落。
            raise LLMCallError(
                f"交叉质询的反驳被 max_tokens（上限 {cross_exam_max_tokens}）截断，"
                "按失败处理（可调大 budget.yaml 的 cross_exam_max_tokens）",
                retryable=False,
            )
        return text, input_tokens, output_tokens

    return run_cross_exam_protocol(
        persona_outputs,
        controversy_points,
        llm_call=llm_call,
        mode=requested_mode,
        template_path=template_path,
        rules=rules,
        max_concurrency=max_concurrency,
    )


def _insert_body_banner(html: str, banner_html: str) -> str:
    """把横幅插到 <body> 开标签之后。没有 <body>（模板被换成片段）时原样返回，
    不让"加个提示"这种事把整份报告搞崩。"""
    if "<body" not in html:
        return html
    idx = html.index(">", html.index("<body")) + 1
    return html[:idx] + banner_html + html[idx:]


def load_artifact_bundle(path: str) -> dict:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Artifact bundle not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8") as f:
        if ext == ".json":
            return json.load(f)
        elif ext in (".yaml", ".yml"):
            return yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported artifact format: {ext}")


def _build_simulated_output(persona: dict, task_type: str) -> dict:
    must_comment_on = persona.get("review_output", {}).get("must_comment_on", [])
    must_comment_on_check = {item: True for item in must_comment_on}
    return {
        "persona_id": persona["id"],
        "persona_name": persona.get("name", persona["id"]),
        "persona_version": "0.1.0",
        "task_type": task_type,
        "primary_stance": "观望",
        "confidence": 0.7,
        "evidence_sufficiency": 0.8,
        "evidence": [
            {
                "content": "模拟证据内容",
                "inference_level": "direct",
                "quote": "模拟证据内容",
            }
        ],
        "scores": {
            "base": {"clarity": 3, "trust": 3},
            "task_specific": {"overall": 3},
        },
        "key_issues": [
            {
                "severity": "medium",
                "title": "模拟问题",
                "why_it_matters": "模拟原因",
                "suggested_fix": "模拟建议",
            }
        ],
        "continue_triggers": persona.get("continue_triggers", []),
        "quit_triggers": persona.get("quit_triggers", []),
        "first_scan_observations": ["模拟观察"],
        "must_comment_on_check": must_comment_on_check,
        "missing_information": [],
        "voice_sample": "（模拟占位数据，非真实评审意见）",
        "meta": {
            "caveats": ["此为模拟占位输出，不包含任何真实评审意见，请勿用于决策"],
            "is_synthetic": True,
            "is_simulated": True,
        },
    }


def run_single_persona(
    persona: dict,
    task_type: str,
    artifact_summary: str,
    artifact_texts: List[str],
    config: dict,
    artifact_bundle: dict = None,
    api_key: str = None,
    provider: str = "anthropic",
    model_override: Optional[str] = None,
    api_base: Optional[str] = None,
    retry_settings: dict = None,
    output_schema: dict = None,
) -> dict:
    """api_key 显式传入优先于环境变量——多用户服务端并发跑评审时，
    绝不能靠进程全局的 os.environ 注入 key（会在用户间串 key）。

    provider/api_base：BYOK 支持任意 OpenAI 兼容服务商（DeepSeek/Kimi/通义千问/智谱GLM/
    Ollama…），不再只认 Anthropic，见 src/runner/llm_client.py。
    model_override：非 Anthropic 服务商没有"haiku/sonnet/opus"分级概念，必须传一个具体
    模型名；显式传了就优先于人格的 model_hint 分级（用户在 BYOK 里选了具体模型即是本意）。

    retry_settings：budget.yaml 的 retry 段读取结果（_retry_settings）。None = 不重试，
    与旧行为完全一致（所有既有调用方不受影响）；给出时在**这一层**统一执行最多
    max_retries 次重试，重试预算只有这一套，覆盖四类失败：
      transport_error —— chat_completion 抛出的可重试异常（限流/超时/5xx）
      schema_failure  —— 模型返回无法解析，或输出缺 BLOCKING_SCHEMA_FIELDS 关键字段
      role_drift      —— validate_output 的角色一致性不过（must_comment_on 覆盖过低等）
      hallucination   —— validate_output 的证据依据不过（direct 证据在材料里找不到出处）
    哪几类真的重试由 retry_on 决定。校验结果随返回 dict 带出（validation 键），
    run_panel 直接复用，不重复校验。
    output_schema：非 None 时在返回前做三层校验（配合 retry 判定 role_drift /
    hallucination / schema_failure）；不传则保持"run_panel 统一校验"的旧路径。
    """
    budget_config = config.get("budget", {})
    persona_prompt_path = config.get("persona_prompt_path", "")

    model = model_override or select_model(persona, budget_config)

    # 拆成 (shared, user) 两段而不是拼成一份 prompt：shared 对本次评审的每一位
    # 人格逐字相同，作为 system 传给 chat_completion 后能被服务商缓存/折扣——
    # 见 persona_agent.py::render_prompt_split 头部注释，那是本次改动的核心。
    # prompt/system 两个变量名对齐 chat_completion 的形参名，别改混。
    template_dir = os.path.dirname(persona_prompt_path)
    system, prompt = render_prompt_split(persona, task_type, artifact_summary, template_dir, artifact_bundle)
    # 仅用于返回值里的 "prompt" 调试字段（日志/测试断言用），从不发给模型：
    # 真正发给模型的是 system + prompt 两个独立字段，拼接只是为了这里的可读性。
    prompt_for_log = system + "\n\n" + (
        prompt if isinstance(prompt, str) else "\n".join(b.get("text", "") for b in prompt if b.get("type") == "text")
    )

    if api_key is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        output = _build_simulated_output(persona, task_type)
        return {
            "persona_id": persona["id"],
            "output": output,
            "prompt": prompt_for_log,
            "model": model,
            "cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": None,
            "retries": 0,
            "retry_reasons": [],
        }

    retry = retry_settings or {
        "max_retries": 0,
        "retry_on": [],
        "backoff_base_seconds": 1.0,
        "unknown_retry_on": [],
    }
    max_attempts = int(retry.get("max_retries", 0)) + 1
    retry_on = set(retry.get("retry_on") or [])
    backoff = float(retry.get("backoff_base_seconds") or 1.0)
    retry_reasons = []

    # 重试过的人格的账要照实记：每次失败重试都真花了钱，最终返回值里的
    # cost/tokens 是**所有尝试的累计**，不能只记最后一次（那是计费漏洞）。
    total_cost = 0.0
    total_input_tokens = 0
    total_output_tokens = 0

    # 上一次交卷没过校验时的修复信息（上一次的原始响应块 + 校验错误），交给下一次
    # 调用接成一轮修复对话；传输层错误的重试仍是原样重发（repair 为 None）。
    repair: Optional[dict] = None

    for attempt in range(max_attempts):
        try:
            # 缓存明细走出参：返回的 input_tokens 是真实 token 数（落库/配额用），
            # 缓存折扣只在 estimate_cost 那一步生效，见 persona_agent 的不变式注释。
            cache_usage: dict = {}
            debug_dir = config.get("debug_run_dir")
            debug_details: Optional[dict] = {} if debug_dir else None
            response_blocks: list = []
            raw_output, input_tokens, output_tokens = chat_completion(
                model=model,
                prompt=prompt,
                api_key=api_key,
                provider=provider,
                api_base=api_base,
                usage_details=cache_usage,
                system=system,
                max_tokens=PERSONA_MAX_TOKENS,
                # 有 schema 就要求模型结构化交卷（Anthropic 强制工具调用 / OpenAI
                # 兼容开 json_object），schema_failure 这类"整次重发"的重试从源头消掉。
                # 没传 schema（run_panel 的旧统一校验路径）就保持老行为。
                json_schema=output_schema,
                debug_details=debug_details,
                repair=repair,
                response_blocks=response_blocks,
            )
            cost = estimate_cost(
                input_tokens, output_tokens, model, budget_config, cache_breakdown=cache_usage
            )
            total_cost += cost
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            output = normalize_persona_output(parse_persona_output(raw_output))

            # 解析失败 = 这位人格**没有**交出可用意见，必须当失败处理。
            #
            # parse_persona_output 三条解析路径全挂时返回 {"parse_error": True, "raw_output": ...}，
            # normalize_persona_output 原样透传。以前这里不检查它，下面几行 setdefault
            # 反而给它补上 persona_id / persona_name / primary_stance="观望"，
            # 于是 run_panel 的 `if r["output"] is not None` 判定它成功 —— 后果是一串谎：
            #   · degradation 里 failed_count=0，用户读到「8 位角色全部完成评审」；
            #   · 它的 key_issues 是空的，release_risk 被结构性拉低（聚合器只数真实 issue）；
            #   · "观望" 计进立场分布，污染共识与最终建议；
            #   · cost_summary.persona_count 把它算成成功人格，照常计费。
            # 触发面并不小：max_tokens 截断就足以让花括号不配对，人格 schema 又很大；
            # 第三方 BYOK 模型不守 JSON 格式更是常态。
            if isinstance(output, dict) and output.get("parse_error"):
                _write_debug_attempt(debug_dir, persona["id"], attempt, {
                    "persona_id": persona["id"], "attempt": attempt, "model": model,
                    "response": debug_details, "raw_output": raw_output, "parse_error": True,
                })
                if RETRY_SCHEMA in retry_on and attempt < max_attempts - 1:
                    retry_reasons.append(RETRY_SCHEMA)
                    repair = {"assistant_content": response_blocks, "feedback": _repair_feedback("parse_error", None)}
                    _backoff_sleep(attempt, backoff)
                    continue
                snippet = str(output.get("raw_output") or "")[:200]
                return {
                    "persona_id": persona["id"],
                    "output": None,
                    "prompt": prompt_for_log,
                    "model": model,
                    # 成本照记：这次调用的钱是真花掉了，失败不等于免费
                    "cost": total_cost,
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "error": f"模型返回无法解析为评审结果（可能被截断或不是 JSON）：{snippet}",
                    "retries": attempt,
                    "retry_reasons": retry_reasons,
                }

            # 身份不靠模型回填：聚合器要 output 里带 persona_id/persona_name，但不同模型
            # 未必按 schema 原样吐回来（MiniMax 就把身份塞进了 persona:{name,archetype}，
            # 顶层没有 persona_id，聚合时 KeyError 整份报告作废）。用我们已知的 persona
            # 强制注入，engine 从此不依赖模型是否老实 echo 身份字段。
            if isinstance(output, dict):
                output.setdefault("persona_id", persona["id"])
                output.setdefault("persona_name", persona.get("name", persona["id"]))
                # 聚合器对 primary_stance 是硬取值——模型偶尔漏这个字段就会让整份
                # 报告 KeyError 作废。缺了就按"观望"兜底（各任务 stance_enum 的通用中立项）。
                output.setdefault("primary_stance", "观望")

            validation = None
            if output_schema is not None:
                validation = validate_output(output, persona, output_schema, artifact_texts)
                reason = _validation_failure_reason(validation)
                _write_debug_attempt(debug_dir, persona["id"], attempt, {
                    "persona_id": persona["id"], "attempt": attempt, "model": model,
                    "response": debug_details, "raw_output": raw_output,
                    "validation": validation, "failure_reason": reason,
                })
                if reason is not None and reason in retry_on and attempt < max_attempts - 1:
                    retry_reasons.append(reason)
                    if reason in (RETRY_SCHEMA, RETRY_HALLUCINATION):
                        repair = {
                            "assistant_content": response_blocks,
                            "feedback": _repair_feedback(reason, validation),
                        }
                    else:
                        repair = None
                    _backoff_sleep(attempt, backoff)
                    continue

            return {
                "persona_id": persona["id"],
                "output": output,
                "prompt": prompt_for_log,
                "model": model,
                "cost": total_cost,
                # 真实 token 计数（来自各 provider 的 usage 字段），供上层汇总/落库
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "error": None,
                "validation": validation,
                "retries": attempt,
                "retry_reasons": retry_reasons,
            }
        except Exception as e:
            # 传输层错误按"是否可重试"分类（限流/超时/5xx vs 401/余额不足这类死错），
            # retry_on 里开了 transport_error 且次数没用完才重试；死错一次就返回，
            # 不把"key 配错了"这种该立刻报的错误拖成 N 次重试后才报。
            retryable = is_retryable_error(e)
            _write_debug_attempt(config.get("debug_run_dir"), persona["id"], attempt, {
                "persona_id": persona["id"], "attempt": attempt, "model": model,
                "exception": f"{type(e).__name__}: {e}"[:2000], "retryable": retryable,
            })
            if retryable and RETRY_TRANSPORT in retry_on and attempt < max_attempts - 1:
                retry_reasons.append(RETRY_TRANSPORT)
                repair = None
                _backoff_sleep(attempt, backoff)
                continue
            return {
                "persona_id": persona["id"],
                "output": None,
                "prompt": prompt_for_log,
                "model": model,
                "cost": total_cost,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "error": str(e),
                "error_retryable": retryable,
                "retries": attempt,
                "retry_reasons": retry_reasons,
            }


def run_panel_from_outputs(
    task_type: str,
    artifact_bundle: dict,
    persona_outputs: List[dict],
    retries_by_persona: Optional[dict] = None,
    **kwargs,
) -> dict:
    """用已有的人格输出续跑评审：只做争议提取 → 交叉质询 → 聚合 → 渲染 → 降级说明。

    persona_outputs 是**每位人格最后一次尝试**的原始输出（通过和没通过校验的都要给，
    否则降级说明会漏掉失败的人格）。这里不信任任何旧的校验结论：清掉后由 run_panel
    用当前的校验器重新校验、重新门控。复用的人格输出不再计费（cost / token 记 0），
    返回值 cost_summary 里只有这次新发生的调用（交叉质询）。

    其余参数原样交给 run_panel（personas_path / mode / model_override / api_key …）。
    """
    results = []
    for out in persona_outputs:
        pid = out.get("persona_id")
        if not pid:
            raise ValueError("续跑用的人格输出缺 persona_id")
        results.append({
            "persona_id": pid,
            "output": out,
            "model": kwargs.get("model_override") or "",
            "cost": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": None,
            "retries": int((retries_by_persona or {}).get(pid, 0)),
            "retry_reasons": [],
        })
    return run_panel(
        task_type=task_type,
        artifact_bundle=artifact_bundle,
        selected_personas=[r["persona_id"] for r in results],
        precomputed_persona_results=results,
        **kwargs,
    )


def run_panel(
    task_type: str,
    artifact_bundle: dict,
    personas_path: str = None,
    presets_path: str = None,
    rules_path: str = None,
    budget_path: str = None,
    output_schema_path: str = None,
    report_schema_path: str = None,
    persona_prompt_path: str = None,
    cross_exam_prompt_path: str = None,
    report_template_path: str = None,
    html_template_path: str = None,
    max_concurrency: int = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    api_key: str = None,
    provider: str = "anthropic",
    model_override: Optional[str] = None,
    api_base: Optional[str] = None,
    selected_personas: Optional[List[str]] = None,
    mode: Optional[str] = None,
    enable_cross_exam: Optional[bool] = None,
    adaptive_panel: bool = False,
    adaptive_initial_size: int = 3,
    adaptive_min_score: float = 0.35,
    wide_screen: bool = False,
    precomputed_persona_results: Optional[List[dict]] = None,
) -> dict:
    """progress_callback(done_count, total, persona_id)：每个人格评审完成后
    在 worker 线程内回调一次（线程安全计数）。回调抛异常不影响评审流程。
    默认 None 时行为与旧版完全一致。

    api_key：显式传入优先于环境变量。服务端多用户并发时必须显式传，
    避免通过进程全局 os.environ 注入导致用户间串 key（安全+计费问题）。

    provider/model_override/api_base：BYOK 选了非 Anthropic 服务商时透传下去，
    见 run_single_persona 的同名参数说明。

    selected_personas：显式指定要哪几个具体角色（id 列表），跳过 select_panel
    按 task_type 预设自动选人的逻辑——对话里"呼叫角色"用这个。id 一个都不在
    personas_path 对应人格包里时（拼错/串包），静默回落到自动选人，不让评审
    因为一次无效的显式指定就直接跑空面板。

    mode：评审深度档位（quick/standard/full，见 REVIEW_MODE_CONFIG）——控制人数
    上限、是否交叉质证、是否校准检查。None（CLI/旧调用方）保持历史行为：不截人数、
    交叉质证和校准都跑；但交叉质询用的是较省的默认档位，见下方说明。此前 Web v2 链路的 mode 只落库不进引擎，
    "快速扫一眼"实际跑的是全量流程，人数和钱都没省——这个参数就是补那条断链的。

    交叉质询按档位分流（见 CROSS_EXAM_MODE_BY_REVIEW_MODE）：quick 不跑、
    standard 一次仲裁式反驳（+1 次调用）、full 走多智能体反驳（每位涉事人格各一次
    调用）。**mode=None 在这一项上不等价于 full**：它走 DEFAULT_CROSS_EXAM_MODE，
    即较省的仲裁式一档，与 v1 后端默认一致——不能让没做选择的 CLI/MCP 用户默认
    掉进最贵的路径。想要多智能体反驳必须显式传 mode="full"。
    没有 api_key 的模拟模式下一次反驳调用都不发，如实标成派生摘要。

    enable_cross_exam：显式覆盖"跑不跑交叉质询"，优先级高于 mode。None（默认）
    完全保持既有行为——由 mode 决定，不传 mode 就跑。传 False 时无论哪一档都不发
    反驳调用，且**不影响人数**：mode 的 max_personas 截断与这一项无关。
    加它是因为这两件事在 REVIEW_MODE_CONFIG 里被绑成了一档（quick 同时意味着
    3 人 + 不反驳），想单独关掉反驳而保持人数不变，此前没有任何入口。
    交叉质询消融实验（src/harness/cross_exam_ablation.py）依赖这一点取得基线：
    人数一起变的话，三档之间的差异里人数和反驳无法分离。"""
    if task_type not in VALID_TASK_TYPES:
        raise ValueError(f"Unknown task type: {task_type}")

    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if personas_path is None:
        personas_path = os.path.join(base, "src", "personas", "game-core.yaml")
    if presets_path is None:
        presets_path = os.path.join(base, "src", "presets", "panel-presets.yaml")
    if budget_path is None:
        budget_path = os.path.join(base, "src", "config", "budget.yaml")
    if rules_path is None:
        rules_path = os.path.join(base, "src", "config", "aggregation-rules.yaml")
    if output_schema_path is None:
        output_schema_path = os.path.join(base, "src", "schemas", "output-schema.json")
    if report_schema_path is None:
        report_schema_path = os.path.join(base, "src", "schemas", "report-schema.json")
    if persona_prompt_path is None:
        persona_prompt_path = os.path.join(base, "src", "templates", "persona-prompt.md")
    if cross_exam_prompt_path is None:
        cross_exam_prompt_path = os.path.join(base, "src", "templates", "cross-exam-prompt.md")
    if report_template_path is None:
        report_template_path = os.path.join(base, "src", "templates", "report-template.md")
    if html_template_path is None:
        html_template_path = os.path.join(base, "src", "templates", "report-template.html")

    effective_api_key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY")
    simulated = not effective_api_key
    if simulated:
        print(f"\n{SIMULATION_WARNING}\n", flush=True)

    personas = load_personas(personas_path)
    presets = load_presets(presets_path)

    with open(budget_path, "r", encoding="utf-8") as f:
        budget_config = yaml.safe_load(f)

    rules = load_aggregation_rules(rules_path)
    output_schema = load_schema(output_schema_path)

    # budget.yaml 的 retry 段在这里读一次，随人格调用传下去（2.3）：
    # 配置缺失时 _retry_settings 退回"不重试"，不会改变任何既有调用方的行为。
    retry_settings = _retry_settings(budget_config)

    # 材料形态统一：对话链路（/ask）发的是 {type:'text', text:内容}，Wizard 发的是
    # {type:字段名, description:内容}。引擎的模板/证据抽取全按 description 读——不统一
    # 的话对话评审的正文（在 text 键里）根本到不了人格手上，人格拿到空材料。
    # 这里把 text 补进 description（已有 description 的 Wizard 材料原样不动），
    # 图片材料（image_data）不碰，交给 render_prompt 走多模态。
    # 动手前先深拷贝：往下会改写 material dict（补 description），就地改调用方
    # 传进来的 bundle 会污染它的对象——调用方可能还要拿原 bundle 干别的事。
    artifact_bundle = copy.deepcopy(artifact_bundle)
    _materials = artifact_bundle.get("materials", []) or []
    for _m in _materials:
        if _m.get("type") != "image" and not _m.get("description") and _m.get("text"):
            _m["description"] = _m["text"]

    artifact_texts = [
        (m.get("description") or m.get("text") or "")
        for m in _materials
        if m.get("type") != "image"
    ]
    artifact_summary = artifact_bundle.get("title", "")

    panel_selected = None
    panel_skipped = []
    # 面板是怎么选出来的：preset（任务类型预设名单）/ pack_preset（该人格包的
    # 专属名单）/ affinity_fallback（预设名单在这个包里一个都没命中，按任务亲和度
    # 现凑）。显式点名人格时保持 None——那种情况面板是用户自己定的，没有"选法"。
    panel_selection_method = None
    # 显式点名的人格里哪些没匹配上，必须留痕。以前是纯静默回落：对话里"呼叫某某角色"
    # 时 id 拼错或串了人格包，引擎不报错、直接换成 task_type 预设面板跑完，报告里
    # 一个字都不提——用户会以为自己点的角色发过言了。部分匹配更隐蔽（指定 3 个命中
    # 1 个，另外 2 个被悄悄丢弃）。degradation / budget / cross_exam 都做了留痕，
    # 唯独这条没有，这里补上，口径与 report["degradation"] 一致。
    requested_personas = list(selected_personas or [])
    matched_persona_ids = []
    fell_back_to_auto = False
    if selected_personas:
        panel_selected = [p for p in personas if p["id"] in selected_personas]
        matched_persona_ids = [p["id"] for p in panel_selected]
        if not panel_selected:
            panel_selected = None  # 一个都没匹配上——回落自动选人，别跑空面板

    # mode_config 必须在选人**之前**取到：档位的 max_personas 既是截断上限，
    # 也是自动选人的凑人目标（select_panel 的 target_size）。以前它在选人之后
    # 才算，于是选人阶段完全不知道这次要几个人，只能凑到预设的 min_panel_size
    # 就收手——档位承诺的 6/8 人对绝大多数人格包从来没有兑现过。
    mode_config = REVIEW_MODE_CONFIG.get(mode) if mode else None

    if panel_selected is None:
        fell_back_to_auto = bool(requested_personas)
        matched_persona_ids = []
        panel = select_panel(
            task_type,
            personas,
            presets,
            # mode 为 None 是 CLI/MCP 等旧调用方，历史行为是"不截人数"——
            # 那就按预设自己的上限凑满，不再受 min_panel_size 压着。
            target_size=mode_config["max_personas"] if mode_config else None,
        )
        panel_selected = panel["selected"]
        panel_skipped = panel["skipped"]
        panel_selection_method = panel["selection_method"]

    # 点名的 id 在人格包里根本不存在的那部分，单独记下来：它和"存在但被截断/预检
    # 跳过"是两种不同的缺席原因，notice 里要分开说。
    unknown_persona_ids = [pid for pid in requested_personas if pid not in matched_persona_ids]

    # ——— 两层评审：全包初筛（L1）→ 门禁 → 深评（L2） ———
    #
    # 默认关（wide_screen=False）走老路：先按档位截断再预检——包里其余人格的
    # 视角被直接扔掉。开启后改成：预检全包 → 每人一次廉价短调用（立场+严重度+
    # 一句话关切）→ 确定性门禁按分歧信号选出深评面板。同样的档位人数上限，
    # 但"选谁"从"预设顺序的前 N 个"变成"全包过目后分歧最大的 N 个"。
    #
    # 显式点名人格时不做初筛：用户指定的角色一个都不能被门禁筛掉，
    # 这与 adaptive_panel 对点名的让位是同一条纪律。
    triage_block = None
    # 并发上限在这里就定下来（以前在人格评审那一段才解析）：L1 初筛同样要用它，
    # 而初筛发生在更早。全引擎共用这一个旋钮——后台面板改的运行时并发值就是
    # 通过 run_panel(max_concurrency=...) 传进来的这个参数。
    if max_concurrency is None:
        max_concurrency = int(os.environ.get("AUDIENCELENS_MAX_CONCURRENCY", "6"))
    wide_screen_active = bool(wide_screen) and not requested_personas and mode_config is not None
    if wide_screen_active:
        # 初筛的对象是**整个人格包**（personas），不是预设面板子集——
        # 这正是两层评审存在的意义：包里每个人格都过目一遍材料，
        # 而不是预设名单外的人格连被考虑的机会都没有。
        precheck = precheck_panel(personas, artifact_bundle)
        valid_personas = precheck["valid_personas"]
        max_advance = mode_config["max_personas"]
        if len(valid_personas) > max_advance:
            triage_model = None
            if simulated:
                triage_call = None
            else:
                # 初筛用便宜档模型：这一层要的是"大概什么状况"的判断力，
                # 不是深评质量。BYOK 指定了具体模型时尊重用户选择（非 Anthropic
                # 服务商没有档位概念，fallback_model 对它们不是合法模型名）。
                triage_model = model_override or budget_config.get(
                    "fallback_model", budget_config.get("default_model")
                )

                def triage_call(prompt, _m=triage_model):
                    # 不传 temperature：初筛可能跑在 model_override 指定的任意模型上，
                    # 而 Sonnet 5 / Opus 5 这代移除了采样参数，传非默认值直接 400
                    # （见 llm_client.chat_completion 的形参注释）。
                    return chat_completion(
                        model=_m, prompt=prompt, api_key=effective_api_key,
                        provider=provider, api_base=api_base,
                        max_tokens=300,
                    )
            triage_out = run_triage(
                valid_personas, task_type, artifact_bundle,
                call_llm=triage_call, max_concurrency=max_concurrency,
            )
            # 初筛是**真实付费调用**：token 记了、钱不记，就是本文件
            # run_cross_exam_stage 注释里说的那种计费漏洞——开了 wide_screen
            # 等于白送一整轮调用。模拟模式（triage_call 为 None）一分钱没花，记 0。
            triage_cost = 0.0
            if triage_call is not None:
                triage_cost = estimate_cost(
                    triage_out["input_tokens"], triage_out["output_tokens"],
                    triage_model, budget_config,
                )
            pack_name = valid_personas[0].get("_pack") if valid_personas else None
            dissenter_id = None
            for _p in valid_personas:
                from runner.panel_selector import _is_dissenter
                if _is_dissenter(_p, pack_name):
                    dissenter_id = _p["id"]
                    break
            advanced, not_advanced = rank_for_advance(
                triage_out["results"], max_advance, dissenter_id=dissenter_id
            )
            advanced_ids = {a["persona_id"] for a in advanced}
            valid_personas = [p for p in valid_personas if p["id"] in advanced_ids]
            triage_block = {
                "enabled": True,
                "screened_count": len(triage_out["results"]) + len(triage_out["failures"]),
                "advanced": advanced,
                "not_advanced": not_advanced,
                "failures": triage_out["failures"],
                "materials_truncated": triage_out["materials_truncated"],
                "material_char_limit": triage_out["material_char_limit"],
                "input_tokens": triage_out["input_tokens"],
                "output_tokens": triage_out["output_tokens"],
                "cost": triage_cost,
                "simulated": simulated,
            }
        else:
            # 包本来就不比档位上限大——没有什么可筛的，如实记原因而不是硬跑一层
            triage_block = {
                "enabled": False,
                "reason": "pack_not_larger_than_panel",
                "screened_count": 0,
            }
    else:
        if mode_config:
            panel_selected = truncate_panel(panel_selected, mode_config["max_personas"])
        precheck = precheck_panel(panel_selected, artifact_bundle)
        valid_personas = precheck["valid_personas"]
        if wide_screen and requested_personas:
            triage_block = {"enabled": False, "reason": "explicit_persona_selection", "screened_count": 0}

    # 自适应面板只对自动选人启用。用户显式点名角色时，少跑其中任何一个都违背
    # 用户意图；这种情况下保留 fixed 执行，并在报告里说明为什么没有自适应缩面。
    adaptive_requested = bool(adaptive_panel)
    adaptive_disabled_reason = ""
    if adaptive_requested and requested_personas:
        adaptive_disabled_reason = "explicit_persona_selection"
    adaptive_enabled = adaptive_requested and not requested_personas and bool(valid_personas)
    try:
        adaptive_initial_size = max(1, int(adaptive_initial_size))
    except (TypeError, ValueError):
        raise ValueError("adaptive_initial_size must be a positive integer")
    try:
        adaptive_min_score = float(adaptive_min_score)
    except (TypeError, ValueError):
        raise ValueError("adaptive_min_score must be a number between 0 and 1")
    if not 0 <= adaptive_min_score <= 1:
        raise ValueError("adaptive_min_score must be a number between 0 and 1")

    # matched 必须在截断与预检**之后**才能定稿：以前它在 truncate_panel 之前算好
    # 就不再动了，点名 5 人但 mode 限 3 人时，报告会说 5 个全参与、missing 为空——
    # 用户以为自己点的角色都发过言。这里按真正进入评审的名单收敛一遍，
    # 被 mode 上限截掉的单独记 truncated_by_mode，在 notice 里如实说明。
    truncated_by_mode_ids = []
    if matched_persona_ids:
        participating_ids = {p["id"] for p in valid_personas}
        panel_ids_after_truncate = {p["id"] for p in panel_selected}
        truncated_by_mode_ids = [
            pid for pid in matched_persona_ids if pid not in panel_ids_after_truncate
        ]
        matched_persona_ids = [
            pid for pid in matched_persona_ids if pid in participating_ids
        ]
    missing_persona_ids = [pid for pid in requested_personas if pid not in matched_persona_ids]
    skipped_count = len(panel_skipped) + len(precheck["skipped_personas"])

    config = {
        "budget": budget_config,
        "persona_prompt_path": persona_prompt_path,
        "debug_run_dir": (
            os.path.join(base, ".debug", "runs", time.strftime("%Y%m%d-%H%M%S") + f"-{task_type}")
            if _debug_runs_enabled() else None
        ),
    }

    # 人格评审彼此独立，是 I/O 密集（等 LLM 返回）任务，用线程池并发。
    # run_single_persona 内部已兜住异常并返回 error 字段，故 future 不会抛。
    # max_concurrency 已在 L1 初筛之前解析好（初筛也要用同一个旋钮）。
    workers = max(1, min(max_concurrency, len(valid_personas))) if valid_personas else 1

    # 实时进度：线程安全计数器，每个人格完成后在 worker 线程内回调
    total_personas = len(valid_personas)
    progress_lock = threading.Lock()
    done_counter = [0]

    def _run(persona):
        result = run_single_persona(
            persona, task_type, artifact_summary, artifact_texts, config, artifact_bundle,
            api_key=effective_api_key,
            provider=provider,
            model_override=model_override,
            api_base=api_base,
            retry_settings=retry_settings,
            output_schema=output_schema,
        )
        if progress_callback is not None:
            with progress_lock:
                done_counter[0] += 1
                done = done_counter[0]
            try:
                progress_callback(done, total_personas, persona["id"])
            except Exception:
                # 进度回调故障不得影响评审本身
                pass
        return result

    def _run_batch(batch):
        if workers <= 1 or len(batch) <= 1:
            return [_run(p) for p in batch]
        # 已知局限：这里是真并发（不是"提交后一个个等"），N 个人格几乎同时把
        # 请求发出去。Anthropic 的 Prompt Caching 要求缓存先被写入才能被读到，
        # 真同时到达的请求有可能全部撞上"缓存还没写完"，全部 miss 一次——
        # 不算错，只是那一轮吃不到折扣。刻意不为了"保证吃满缓存"改成先发一个
        # 探路再并发剩下的：那样多绕一轮网络往返换来的延迟，比偶尔一轮 miss
        # 贵得多，尤其是本来就没几个人格的 quick/standard 档。
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(workers, len(batch))) as ex:
            # 按提交顺序收集 future 结果，保证与输入人格顺序一致（确定性）
            futures = [ex.submit(_run, p) for p in batch]
            return [f.result() for f in futures]

    adaptive_decisions = []
    if precomputed_persona_results is not None:
        # 断点续跑（run_panel_from_outputs）：人格评审已经跑过，这里只接上结果，
        # 之后的校验门控 / 交叉质询 / 聚合 / 渲染 / 降级说明全部走下面同一条路径。
        by_id = {r["persona_id"]: r for r in precomputed_persona_results}
        valid_ids = {p["id"] for p in valid_personas}
        missing = sorted(pid for pid in by_id if pid not in valid_ids)
        if missing:
            raise ValueError(
                "这些人格不在本次面板里（或被证据预检跳过），不能用来续跑：" + ", ".join(missing)
            )
        executed_personas = [p for p in valid_personas if p["id"] in by_id]
        persona_results = [dict(by_id[p["id"]]) for p in executed_personas]
    elif adaptive_enabled:
        initial_count = min(adaptive_initial_size, len(valid_personas))
        executed_personas = list(valid_personas[:initial_count])
        persona_results = _run_batch(executed_personas)

        while len(executed_personas) < len(valid_personas):
            unresolved_evidence = sorted({
                str(gap).strip()
                for result in persona_results
                if result.get("output")
                for gap in (result["output"].get("missing_information") or [])
                if str(gap).strip()
            })
            recommendation = recommend_next_persona(
                candidates=valid_personas,
                selected=executed_personas,
                task_type=task_type,
                unresolved_evidence=unresolved_evidence,
                min_score=adaptive_min_score,
            )
            recommendation["panel_size_before"] = len(executed_personas)
            recommendation["unresolved_evidence"] = unresolved_evidence

            # 人格调用已经逐步发生，可以在扩面前执行真实成本刹车；固定并发路径只能
            # 在全员跑完后阻止交叉质询，自适应路径则可以少发后续人格调用。
            running_cost = sum(float(item.get("cost") or 0.0) for item in persona_results)
            max_run_cost = float(budget_config.get("max_cost_per_run_usd") or 0.0)
            if max_run_cost > 0 and running_cost >= max_run_cost:
                recommendation["should_continue"] = False
                recommendation["recommended_persona_id"] = None
                recommendation["stop_reason"] = "cost_budget_reached"
            elif not recommendation["should_continue"]:
                recommendation["stop_reason"] = "marginal_value_below_threshold"
            else:
                recommendation["stop_reason"] = None
            adaptive_decisions.append(recommendation)

            if not recommendation["should_continue"]:
                break
            next_id = recommendation["recommended_persona_id"]
            next_persona = next(p for p in valid_personas if p.get("id") == next_id)
            executed_personas.append(next_persona)
            persona_results.extend(_run_batch([next_persona]))
    else:
        executed_personas = list(valid_personas)
        persona_results = _run_batch(valid_personas)

    persona_outputs = []
    failed_personas = []
    for r in persona_results:
        if r["output"] is not None:
            # run_single_persona 传入 output_schema 时已做过校验（含重试判定），
            # 结果随返回 dict 带出，这里直接复用；旧调用方没传 schema 时照旧补校验。
            validation = r.get("validation")
            if validation is None:
                validation = validate_output(
                    r["output"],
                    next((p for p in valid_personas if p["id"] == r["persona_id"]), {}),
                    output_schema,
                    artifact_texts,
                )
                r["validation"] = validation

            # 模拟占位输出（meta.is_simulated）不参与门控：它们存在的唯一意义是让
            # 没有 LLM 的环境里流水线还能跑通——把它们拦在门外，模拟模式就永远报
            # "全员失败"，既测不了流水线，也违背 AGENTS.md 对模拟模式的定位。
            # 真实模式（有 key）下模型吐的正常输出不带这个标记，门控照常生效。
            if simulated or (r["output"].get("meta") or {}).get("is_simulated"):
                persona_outputs.append(r["output"])
                continue

            # 三层校验结果真正参与门控（2.2）：schema 关键字段不合格 / 角色漂移 /
            # 幻觉率超标的输出**不计入**聚合报告，计入 failed_personas 与 degradation。
            # 以前 validate_output 的结果只写进 r["validation"] 就原地归档，输出照样
            # 进聚合——"校验"是一道谁都能绕过去的假门。
            failure_reason = _validation_failure_reason(validation)
            if failure_reason is None:
                persona_outputs.append(r["output"])
            else:
                failed_personas.append({
                    "persona_id": r["persona_id"],
                    "error": _validation_error_message(validation, failure_reason),
                    "model": r.get("model", ""),
                    "failure_reason": failure_reason,
                    "retries": r.get("retries", 0),
                })
        else:
            # 失败的人格必须被记下来并透出去：以前这里直接 continue，
            # 每个人格的 error 从头到尾没有一条带出 run_panel。
            failed_personas.append({
                "persona_id": r["persona_id"],
                "error": r.get("error") or "未知错误",
                "model": r.get("model", ""),
            })

    # 全盘失败（含"一个人格都没进来"）绝不产出报告——见 AllPersonasFailedError 的说明
    if not persona_outputs:
        raise AllPersonasFailedError(
            failures=failed_personas,
            attempted=len(persona_results),
            skipped_count=skipped_count,
        )

    attempted_count = len(persona_results)
    succeeded_count = len(persona_outputs)
    failed_count = len(failed_personas)
    degraded = failed_count > 0

    # ---- 单次评审成本上限（budget.yaml 的 max_cost_per_run_usd）----
    #
    # 这个配置项存在很久，但**从来没有任何代码读过它**——而 quota_service 的注释
    # 和 docs/MAINTENANCE.md 都把它当作 credits 模式下的成本护栏在写。也就是说
    # 「单次评审有封顶」一直是句空话，运营照着文档配置会以为自己有保护。
    #
    # 人格是并发跑的，跑到一半没法刹车（钱已经花了）。但交叉质询是人格评审**之后**
    # 才发起的额外付费调用——预算已经超了就该停在这里，而不是继续加钱。
    # 停了必须说出来：静默少跑一个环节，等于又造一份"看起来完整"的报告。
    max_cost_per_run = float(budget_config.get("max_cost_per_run_usd") or 0.0)
    persona_cost_so_far = sum(float(r.get("cost") or 0.0) for r in persona_results)
    budget_exceeded = max_cost_per_run > 0 and persona_cost_so_far >= max_cost_per_run
    budget_notice = ""
    if budget_exceeded:
        budget_notice = (
            f"本次评审在人格环节已花费约 ${persona_cost_so_far:.2f}，达到单次上限 "
            f"${max_cost_per_run:.2f}（budget.yaml 的 max_cost_per_run_usd），"
            "交叉质询已跳过以免继续增加成本。"
        )
        logging.getLogger("audiencelens").warning(budget_notice)

    # 显式开关优先于档位：enable_cross_exam=None 时才回退到 mode 的决定（既有行为）
    if enable_cross_exam is not None:
        cross_exam_enabled = bool(enable_cross_exam)
    else:
        cross_exam_enabled = mode_config["cross_examination"] if mode_config else True
    cross_exam_data = None
    # 交叉质询的用量单独记一份：它是人格评审之外新增的付费调用，必须并进 cost_summary
    cross_exam_usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
    cross_exam_notice = ""
    if cross_exam_enabled and not budget_exceeded and persona_outputs and cross_exam_prompt_path:
        # filter_genuine_controversies 仍然守在最前面：没有真分歧时连争议点都不产出，
        # 更不会为了"看起来跑过辩论"而发一轮凭空造对立的反驳调用。
        controversy_points = filter_genuine_controversies(
            extract_controversy_points(persona_outputs)
        )
        if controversy_points:
            cross_exam_data = run_cross_exam_stage(
                persona_outputs=persona_outputs,
                controversy_points=controversy_points,
                personas=executed_personas,
                template_path=cross_exam_prompt_path,
                rules=rules,
                budget_config=budget_config,
                usage=cross_exam_usage,
                mode=mode,
                api_key=effective_api_key,
                provider=provider,
                model_override=model_override,
                api_base=api_base,
                # 反驳阶段与人格评审共用同一个并发上限：后台面板改的运行时值
                # 必须真的管到这一段，而不是只管得到人格评审那一段。
                max_concurrency=max_concurrency,
            )
            # 反驳失败/只完成一半不会让整场评审失败，但必须在渲染产物里留痕——
            # 只躺在 JSON 的 limitation 里，读报告的人不会发现这场"辩论"其实没跑成。
            if cross_exam_data.get("failures"):
                cross_exam_notice = cross_exam_data.get("limitation", "")

    dedup_method = _issue_dedup_method() if cross_exam_enabled else None
    dedup_notice = DEDUP_LEXICAL_NOTICE if dedup_method == "lexical" else ""

    report = aggregate_report(
        persona_outputs,
        task_type,
        artifact_summary,
        rules,
        cross_exam_data,
        # 受众画像只有人格 YAML 里有（persona_outputs 是 LLM 的输出，没有这些字段），
        # 不传的话 next_human_test.recruit_types 会如实留空
        panel_personas=executed_personas,
        persona_pack=load_persona_pack_meta(personas_path),
    )

    # 把“建议”提升成可验证假设：每条都有目标指标、对照方式、方向、验证窗口，
    # 但绝不凭空编效果量。confidence 明示为合成面板启发式，等待 Ledger 真实结果校准。
    report["predictions"] = build_falsifiable_predictions(
        report, task_type, panel_size=len(persona_outputs)
    )

    report["adaptive_panel"] = {
        "requested": adaptive_requested,
        "enabled": adaptive_enabled,
        "disabled_reason": adaptive_disabled_reason or None,
        "method": "marginal_value_proxy_v1" if adaptive_enabled else "fixed_panel",
        "initial_size": min(adaptive_initial_size, len(valid_personas)) if adaptive_enabled else None,
        "eligible_personas": len(valid_personas),
        "executed_personas": len(executed_personas),
        "saved_persona_calls": len(valid_personas) - len(executed_personas),
        "min_score": adaptive_min_score if adaptive_enabled else None,
        "decisions": adaptive_decisions,
        "limitation": (
            "The expansion score is an explainable heuristic, not measured information gain; "
            "its weights require calibration against verified outcomes."
            if adaptive_enabled else None
        ),
    }

    if simulated:
        report["simulation_notice"] = SIMULATION_WARNING

    # 降级标记进 report 本体：web 后端把 report 整份落库（report_json），
    # 前端读的也是它——只放在返回值顶层的话，重新打开历史报告就看不到"本次有人
    # 没跑成"了，那份报告又会被当成完整结论。
    report["degradation"] = {
        "degraded": degraded,
        "attempted_count": attempted_count,
        "succeeded_count": succeeded_count,
        "failed_count": failed_count,
        "failed_personas": failed_personas,
        "notice": (
            f"本次有 {failed_count} 位人格未能完成评审，以下结论仅基于 {succeeded_count} 位人格的输出。"
            if degraded
            else ""
        ),
    }

    # 项目记忆进 report 本体：它本身挂在 artifact_bundle 上（是**入参**不是产出），
    # 但导出件（md / html）只拿得到 report——不搬过来，发给同事的报告里就看不到
    # "本次带了几条历史判断"，而报告里那些"当前材料里没有的问题"正来源于它。
    # 只搬元数据不搬材料正文：正文已经在 bundle 里可审计，重复一份只会撑大报告。
    _pm = (artifact_bundle or {}).get("project_memory")
    if isinstance(_pm, dict) and _pm.get("carried"):
        report["project_memory"] = _pm

    # 初筛（两层评审 L1）进 report 本体：全包谁被筛过、谁晋级、为什么，
    # 都要在重新打开历史报告时看得到。triage_block 为 None = 本次没请求 wide_screen。
    if triage_block is not None:
        report["triage"] = triage_block

    # 弃权进 report 本体：证据预检跳过的人格此前只有一个**个数**进 cost_summary，
    # persona_id / 原因 / 缺哪些证据全部丢弃——报告里"我选了 8 个人怎么只有 5 个
    # 发言"没有任何交代。弃权和失败是两回事：失败是跑了没跑成（degradation），
    # 弃权是"这次材料里没有我需要的证据类型，按规矩不硬评"——它是面板诚实性的
    # 正面证据，应该作为一种立场展示出来，而不是藏在计数里。
    report["abstentions"] = [
        {
            "persona_id": sk.get("persona_id"),
            "reason": sk.get("reason"),
            "missing_evidence": sk.get("missing") or [],
        }
        for sk in precheck["skipped_personas"]
    ]

    # 校验/重试口径进 report 本体：只放在返回值顶层的话，重新打开历史报告就看不到
    # "这次配了哪些重试、有人因为校验没过被拦下来"了（与 degradation 同一个理由）。
    # gated_out 与 degradation.failed_personas 里的 failure_reason 一一对应，这里
    # 单独列一份便于按原因统计。
    report["validation"] = {
        "retry": retry_settings,
        "gated_out": [
            {"persona_id": f["persona_id"], "failure_reason": f["failure_reason"]}
            for f in failed_personas if f.get("failure_reason")
        ],
    }

    # 预算刹车同样要进 report 本体：只放返回值顶层的话，重新打开历史报告就看不见
    # "这次少跑了交叉质询"，那份报告又会被当成完整结论（和 degradation 同一个理由）。
    report["budget"] = {
        "max_cost_per_run_usd": max_cost_per_run,
        "persona_cost_usd": round(persona_cost_so_far, 6),
        "exceeded": budget_exceeded,
        "skipped_stages": ["cross_examination"] if budget_exceeded else [],
        "notice": budget_notice,
    }

    # 显式点名人格的匹配结果进 report 本体（与 degradation / budget 同一个理由：
    # 只放返回值顶层的话，重新打开历史报告就看不见"你点的角色其实没参与"）。
    # 没有显式点名时整键不写，免得给报告塞一堆恒为空的字段。
    # notice 按缺席原因分开说：id 不存在（unknown）和被评审模式人数上限截掉
    # （truncated_by_mode）是两回事，混在一句"不存在"里会让用户去查一个
    # 明明存在的 id。missing 仍是"点名了但没参与"的总集，供程序方消费。
    notice_parts = []
    if unknown_persona_ids:
        notice_parts.append(
            "你指定的人格 " + "、".join(unknown_persona_ids) + " 在本次人格包中不存在，"
            + ("已改用任务类型的预设面板。" if fell_back_to_auto else "未参与本次评审。")
        )
    if truncated_by_mode_ids:
        notice_parts.append(
            "你指定的人格 " + "、".join(truncated_by_mode_ids)
            + " 因评审模式的人数上限被截断，未参与本次评审。"
        )
    # 兜底选人必须说出来。14 个任务类型预设里，default_personas 写的都是
    # game-core 的人格 id，只有 11 组 (任务类型 × 人格包) 配了专属 by_pack 名单；
    # 其余组合——包括 general-consumer / startup-panel / mobile-f2p 等 6 个包的
    # **全部**任务类型——预设名单一个都命中不了，面板实际是按任务亲和度现凑的。
    # 这跟"策展过的面板"是两种可信度，用户有权知道自己拿到的是哪一种。
    if panel_selection_method == "affinity_fallback":
        notice_parts.append(
            "本次人格包没有为该任务类型配置专属面板名单，参与评审的人格是按任务亲和度"
            "从包内自动挑选的（不是策展过的面板）。"
        )
    if requested_personas or notice_parts:
        report["panel_selection"] = {
            "requested": requested_personas,
            "matched": matched_persona_ids,
            "missing": missing_persona_ids,
            "truncated_by_mode": truncated_by_mode_ids,
            "fell_back_to_auto": fell_back_to_auto,
            # preset / pack_preset / affinity_fallback；显式点名时为 None
            "selection_method": panel_selection_method,
            "notice": "".join(notice_parts),
        }

    calibration_enabled = mode_config["calibration"] if mode_config else True
    calibration = run_calibration_check(persona_outputs, artifact_texts) if calibration_enabled else None

    # 校准结果也挂进 report["validation"]：它是引擎真算出来的三个指标
    # （角色一致性 / 视角覆盖度 / 无幻觉率），以前只从 run_panel 顶层返回，
    # 导出的 HTML/Markdown 里一个数都没有，而 HTML 模板里那块指标卡等的是
    # harness_score / grounding_rate / divergence_score——引擎从不产出这三个字段，
    # 于是整块永远不渲染。现在让模板读真实存在的 calibration，那三个假字段已删。
    if calibration:
        # 必须先把元组键拍平再塞进 report。calibration.coverage.pairwise_distances
        # 用 (id1, id2) 元组做键——对 CLI 这种 Python 消费方完全合理，但 report
        # **由引擎自己承诺可 JSON 序列化**（本文件下方 json.dump(result["report"])，
        # 以及 web 侧 review.report_json 是 JSON 列）。不拍平的话：
        #   · CLI：跑完整场评审，最后一步写文件 TypeError，报告全丢
        #   · web：SQLAlchemy flush 时崩，整条 UPDATE 失败，评审 100% 标 failed，
        #          而且报错是一句与评审内容毫无关系的 "keys must be str"
        # 只要成功人格 ≥2 就必现（<2 时 compute_coverage_score 返回带
        # not_applicable 标记的 dict，pairwise_distances 为空，元组键根本不生成，
        # 这正是单人格的模拟模式测不出它的原因）。
        report["validation"]["calibration"] = _json_safe(calibration)

    # markdown / html 两处横幅都要用，所以在两个分支之外算一次
    panel_notice = (report.get("panel_selection") or {}).get("notice")
    if dedup_method:
        report["dedup"] = {"method": dedup_method, "notice": dedup_notice}

    markdown = ""
    if report_template_path:
        markdown = render_markdown_report(report, report_template_path)
        if simulated:
            markdown = f"> **{SIMULATION_WARNING}**\n\n{markdown}"
        if cross_exam_notice:
            markdown = f"> **⚠️ 交叉质询未完整完成：{cross_exam_notice}**\n\n{markdown}"
        if dedup_notice:
            markdown = f"> **⚠️ {dedup_notice}**\n\n{markdown}"
        if budget_notice:
            markdown = f"> **⚠️ {budget_notice}**\n\n{markdown}"
        if panel_notice:
            markdown = f"> **⚠️ {panel_notice}**\n\n{markdown}"
        # 报告模板不认识 degradation 字段（模板不在本次改动范围），横幅在这里补上，
        # 保证降级信息在渲染产物里也看得见，而不是只躺在 JSON 里
        if degraded:
            markdown = f"> **⚠️ {report['degradation']['notice']}**\n\n{markdown}"

    report["_persona_outputs"] = persona_outputs
    html = ""
    if html_template_path:
        html = render_html_report(report, html_template_path)
        if simulated:
            html = _insert_body_banner(
                html,
                '<div style="background:#fef3c7;border:2px solid #d97706;color:#92400e;'
                'padding:12px 16px;margin:8px;border-radius:8px;font-weight:bold;">'
                f"{SIMULATION_WARNING}</div>",
            )
        if cross_exam_notice:
            html = _insert_body_banner(
                html,
                '<div style="background:#fef3c7;border:2px solid #d97706;color:#92400e;'
                'padding:12px 16px;margin:8px;border-radius:8px;font-weight:bold;">'
                f"⚠️ 交叉质询未完整完成：{cross_exam_notice}</div>",
            )
        if dedup_notice:
            html = _insert_body_banner(
                html,
                '<div style="background:#fef3c7;border:2px solid #d97706;color:#92400e;'
                'padding:12px 16px;margin:8px;border-radius:8px;font-weight:bold;">'
                f"⚠️ {dedup_notice}</div>",
            )
        if panel_notice:
            html = _insert_body_banner(
                html,
                '<div style="background:#fef3c7;border:2px solid #d97706;color:#92400e;'
                'padding:12px 16px;margin:8px;border-radius:8px;font-weight:bold;">'
                f"⚠️ {panel_notice}</div>",
            )
        if degraded:
            failed_list = "、".join(f["persona_id"] for f in failed_personas)
            html = _insert_body_banner(
                html,
                '<div style="background:#fee2e2;border:2px solid #dc2626;color:#991b1b;'
                'padding:12px 16px;margin:8px;border-radius:8px;font-weight:bold;">'
                f"⚠️ {report['degradation']['notice']}未完成的人格：{failed_list}"
                "</div>",
            )
    del report["_persona_outputs"]

    # 交叉质询与 L1 初筛的用量必须一起计进总账：它们都是人格评审之外真实发生的
    # 付费调用，漏掉就是"花了钱但账上看不到"——本仓库刚修过一批这类问题。
    # （初筛的钱以前完全没进 total_cost，开着 wide_screen 就等于白送一整轮调用；
    #   web 后端只按 total_cost 计费。）
    triage_cost_total = float((triage_block or {}).get("cost") or 0.0)
    total_cost = (
        sum(r["cost"] for r in persona_results)
        + cross_exam_usage["cost"]
        + triage_cost_total
    )
    total_input_tokens = (
        sum(r.get("input_tokens", 0) for r in persona_results) + cross_exam_usage["input_tokens"]
    )
    total_output_tokens = (
        sum(r.get("output_tokens", 0) for r in persona_results) + cross_exam_usage["output_tokens"]
    )

    return {
        "report": report,
        "markdown": markdown,
        "html": html,
        "calibration": calibration,
        "simulated": simulated,
        # 通过校验的人格原始输出。report.persona_notes 是渲染用的子集，字段不全，
        # 拿它做二次分析会少掉 key_issues 的 severity 等字段。
        # 交叉质询消融要在同一批人格输出上分叉出多种反驳条件（人格评审只跑一次），
        # 需要的就是这份原件。
        "persona_outputs": persona_outputs,
        # 同一批输出对应的人格 YAML 定义，反驳轮渲染身份卡要用
        "panel_personas": executed_personas,
        # 降级标记也放顶层：调用方在落库前就能判断要不要提示用户 / 要不要按满额计费
        "degraded": degraded,
        "failed_personas": failed_personas,
        # 交叉质询没跑成时的说明（已写进 markdown/html 横幅，顶层再给一份供 API 直接透出）
        "cross_exam_notice": cross_exam_notice,
        "cost_summary": {
            "total_cost": total_cost,
            # persona_count 必须是真实成功数：以前算的是 len(persona_results)（把失败的
            # 也算进去），于是"8 个人格"的说法和计费都建立在没跑成的人格上。
            "persona_count": succeeded_count,
            # 每位人格的重试（修复轮 / 传输层重发）次数之和；钱已经算进 total_cost 了
            "persona_retries": sum(int(r.get("retries") or 0) for r in persona_results),
            "attempted_count": attempted_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            # 初筛（L1）的 token 单列：它用的是便宜档模型，混进人格深评的
            # 用量会让单价估算失真
            "triage_input_tokens": (triage_block or {}).get("input_tokens", 0),
            "triage_output_tokens": (triage_block or {}).get("output_tokens", 0),
            # 初筛的钱**已经算进上面的 total_cost 了**，这里单列只为对账，别再加一遍
            # （与 cross_exam.cost 同一口径）。模拟模式恒为 0.0。
            "triage_cost": triage_cost_total,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            # 交叉质询单列一份便于对账（已包含在上面的 total_* 里，不要再加一遍）
            "cross_exam": {
                "calls": cross_exam_usage["calls"],
                "input_tokens": cross_exam_usage["input_tokens"],
                "output_tokens": cross_exam_usage["output_tokens"],
                "cost": cross_exam_usage["cost"],
                "mode": (cross_exam_data or {}).get("mode"),
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description="AudienceLens 多人评审系统 CLI")
    parser.add_argument("task_type", choices=VALID_TASK_TYPES, help="评审任务类型")
    parser.add_argument("artifact_path", help="评审材料包路径")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    parser.add_argument("--personas", default=None, help="Persona YAML 路径")
    parser.add_argument("--presets", default=None, help="Preset YAML 路径")

    args = parser.parse_args()

    artifact_bundle = load_artifact_bundle(args.artifact_path)

    src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    personas_path = args.personas or os.path.join(src_root, "personas", "game-core.yaml")
    presets_path = args.presets or os.path.join(src_root, "presets", "panel-presets.yaml")
    rules_path = os.path.join(src_root, "config", "aggregation-rules.yaml")
    budget_path = os.path.join(src_root, "config", "budget.yaml")
    output_schema_path = os.path.join(src_root, "schemas", "output-schema.json")
    report_schema_path = os.path.join(src_root, "schemas", "report-schema.json")
    persona_prompt_path = os.path.join(src_root, "templates", "persona-prompt.md")
    cross_exam_prompt_path = os.path.join(src_root, "templates", "cross-exam-prompt.md")
    report_template_path = os.path.join(src_root, "templates", "report-template.md")

    try:
        result = run_panel(
            task_type=args.task_type,
            artifact_bundle=artifact_bundle,
            personas_path=personas_path,
            presets_path=presets_path,
            rules_path=rules_path,
            budget_path=budget_path,
            output_schema_path=output_schema_path,
            report_schema_path=report_schema_path,
            persona_prompt_path=persona_prompt_path,
            cross_exam_prompt_path=cross_exam_prompt_path,
            report_template_path=report_template_path,
        )
    except AllPersonasFailedError as e:
        # 一份文件都不写：宁可什么都没有，也不要在磁盘上留一份"无风险"的假报告
        print("=" * 60)
        print(f"评审失败：{e}")
        print("=" * 60)
        raise SystemExit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    json_path = os.path.join(
        args.output_dir, f"{args.task_type}_report.json"
    )
    with open(json_path, "w", encoding="utf-8") as f:
        # allow_nan=False：报告里出现 NaN/Infinity 会写出非法 JSON，任何下游
        # （web 后端、harness-evaluate、用户的 JSON 解析器）都会炸或读不到。
        # 报告是纯聚合产物（比率都有除零保护），出现 NaN 说明上游算错了，
        # 当场抛出来比落一份坏文件强。
        json.dump(result["report"], f, ensure_ascii=False, indent=2, allow_nan=False)

    md_path = os.path.join(
        args.output_dir, f"{args.task_type}_report.md"
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result["markdown"])

    html_path = os.path.join(
        args.output_dir, f"{args.task_type}_report.html"
    )
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(result["html"])

    if result.get("simulated"):
        print("=" * 60)
        print(SIMULATION_WARNING)
        print("=" * 60)
