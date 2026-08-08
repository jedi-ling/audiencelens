"""钉住报告页/评估页与后端的量纲、合格线一致性。

前端没有测试运行器（web/frontend/package.json 只有 dev/build/typecheck/lint），
为几条常量卡口引入 vitest 不合算。参照 tests/test_task_type_parity.py 的先例，
这里用源码断言的方式把「前端展示的这些数来自真实事实源」钉住：任何人把量纲
或合格线改回硬编码，这几条会红。

覆盖的三类历史事故：
  1. 维度分是 0-3（evaluation_service），前端按 0-100 渲染 —— 满分被画成
     「3/100」的红色空条；
  2. 校准仪表盘的配色阈值写死 80/60/40，与「视角覆盖度合格线 0.3」完全对不上 ——
     合格值被涂成红色，同一屏页脚却写着「校准通过」；
  3. 引擎写进 report 的坏消息（budget 预算刹车、validation.gated_out 校验门控）
     前端一个字都不渲染。
"""

import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FRONTEND_SRC = os.path.join(REPO_ROOT, "web", "frontend", "src")
EVALUATION_PAGE = os.path.join(FRONTEND_SRC, "pages", "EvaluationPage.tsx")
REPORT_PAGE = os.path.join(FRONTEND_SRC, "pages", "ReportPage.tsx")
CALIBRATION_GAUGE = os.path.join(FRONTEND_SRC, "components", "CalibrationGauge.tsx")
CALIBRATION_PY = os.path.join(REPO_ROOT, "src", "runner", "calibration.py")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_dimension_max_score_matches_rubric_anchors():
    """前端的单维度满分必须等于 rubric 实际的最高档位。

    事实源是 RUBRIC_SCORES：每个维度的档位键是 "0".."3"，最大档就是满分。
    有人给 rubric 加了第 5 档而前端还写 3，这条会红。
    """
    from app.services.evaluation_service import RUBRIC_SCORES

    max_anchor = max(int(k) for anchors in RUBRIC_SCORES.values() for k in anchors)

    for path in (EVALUATION_PAGE, REPORT_PAGE):
        source = _read(path)
        match = re.search(r"const DIMENSION_MAX_SCORE = (\d+)", source)
        assert match, f"{path} 里应有 DIMENSION_MAX_SCORE 常量（维度满分必须显式写出来）"
        assert int(match.group(1)) == max_anchor, (
            f"{path} 的 DIMENSION_MAX_SCORE={match.group(1)}，"
            f"但 RUBRIC_SCORES 的最高档是 {max_anchor}"
        )


def test_dimension_charts_do_not_use_0_to_100_axis():
    """维度图的坐标轴不许再是 0-100：满分 3 在 0-100 轴上恒定贴地。"""
    for path in (EVALUATION_PAGE, REPORT_PAGE):
        source = _read(path)
        assert "domain={[0, 100]}" not in source, (
            f"{path} 仍有 0-100 的图表坐标轴；维度分是 0-3，"
            "请用 DIMENSION_MAX_SCORE"
        )
        assert "DIMENSION_MAX_SCORE]}" in source, f"{path} 的图表轴上限应取 DIMENSION_MAX_SCORE"


def test_dimension_score_is_not_rendered_out_of_100():
    """维度分不许再显示成 x/100，也不许再用 >70 / >=50 这类 0-100 的颜色阈值。"""
    for path in (EVALUATION_PAGE, REPORT_PAGE):
        source = _read(path)
        assert "result.score}/100" not in source, f"{path} 仍把维度分显示成 x/100"
        assert not re.search(r"result\.score\s*>\s*70", source), (
            f"{path} 仍按 0-100 的阈值给维度分配色（result.score > 70）"
        )
        assert not re.search(r"width: `\$\{result\.score\}%`", source), (
            f"{path} 仍把 0-3 的维度分直接当百分比画进度条"
        )


def _calibration_pass_lines() -> dict:
    """从 run_calibration_check 的源码里取出两条真实合格线。

    读源码而不是调函数：这两个数字是写死在 overall_pass 判据里的字面量，
    只有盯住字面量，才能在有人改了判据却忘了改前端时报红。
    """
    source = _read(CALIBRATION_PY)
    body = source.split("def run_calibration_check", 1)[1]
    role = re.search(r'role_consistency\["average"\]\s*>=\s*([0-9.]+)', body)
    coverage = re.search(r'coverage\["average_distance"\]\s*>=\s*([0-9.]+)', body)
    assert role and coverage, "run_calibration_check 的 overall_pass 判据形状变了，请同步这个测试"
    return {"role_consistency": float(role.group(1)), "coverage": float(coverage.group(1))}


def test_calibration_gauge_thresholds_come_from_the_engine():
    """仪表盘不许自带配色阈值，合格线必须由调用方按引擎判据传入。"""
    gauge = _read(CALIBRATION_GAUGE)
    assert not re.search(r"percentage\s*>=\s*\d+", gauge), (
        "CalibrationGauge 又写死了百分比配色阈值；合格线必须来自 passLine"
    )
    assert "passLine" in gauge, "CalibrationGauge 应接收 passLine"

    expected = _calibration_pass_lines()
    report = _read(REPORT_PAGE)

    role_block = re.search(r'label="角色一致性"(.{0,200}?)/>', report, re.S)
    coverage_block = re.search(r'label="视角覆盖度"(.{0,200}?)/>', report, re.S)
    assert role_block and coverage_block, "ReportPage 的校准仪表盘调用形状变了"

    role_pass = re.search(r"passLine=\{([0-9.]+)\}", role_block.group(1))
    coverage_pass = re.search(r"passLine=\{([0-9.]+)\}", coverage_block.group(1))
    assert role_pass and coverage_pass, "两个有合格线的校准指标都必须显式传 passLine"

    assert float(role_pass.group(1)) == expected["role_consistency"]
    assert float(coverage_pass.group(1)) == expected["coverage"]


def test_hallucination_gauge_has_no_invented_pass_line():
    """无幻觉率没有参与 overall_pass，就不许给它安一条合格线。"""
    report = _read(REPORT_PAGE)
    block = re.search(r'label="无幻觉率"(.{0,300}?)/>', report, re.S)
    assert block, "ReportPage 的无幻觉率仪表盘调用形状变了"
    assert "passLine" not in block.group(1), (
        "无幻觉率的平均值不是 run_calibration_check 的判据，"
        "给它配合格线等于凭空判定一个指标合格与否"
    )


def test_report_page_renders_budget_and_validation_gate():
    """引擎写进 report 的两条坏消息必须在页面上出现（网页 + markdown 兜底导出）。"""
    report = _read(REPORT_PAGE)
    assert "report.budget" in report, "预算刹车（跳过交叉质询）仍未渲染"
    assert "report.validation" in report, "校验门控 gated_out 仍未渲染"
    # 三个失败类型枚举与 runner/cli.py 的常量一一对应
    cli = _read(os.path.join(REPO_ROOT, "src", "runner", "cli.py"))
    for const in ("RETRY_SCHEMA", "RETRY_ROLE_DRIFT", "RETRY_HALLUCINATION"):
        value = re.search(rf'{const} = "([a-z_]+)"', cli)
        assert value, f"runner/cli.py 里找不到 {const}"
        assert f"{value.group(1)}:" in report, (
            f"ReportPage 的 GATE_REASON_LABELS 缺少 {value.group(1)} 的中文说明，"
            "用户会看到一个英文枚举"
        )


def test_cross_examination_absence_is_explained():
    """交叉质询整节缺席时必须有说明，不能凭空消失。"""
    report = _read(REPORT_PAGE)
    assert "CrossExamAbsentNotice" in report, (
        "crossExam 为 null 时整节直接消失，用户会读成「这次没什么争议」"
    )
