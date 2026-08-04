# -*- coding: utf-8 -*-
"""8 维评估对齐引擎真实报告结构（spec 2.1）。

历史缺陷：harness 评估器只认 report["persona_reviews"] 和
"next_human_test_recommendations"，而引擎（run_panel / aggregate_report）产出的
顶层键是 persona_notes / next_human_test——于是 6 个维度恒定拿到空列表：
"没数据"被记成"5 分通过"，评估器对引擎自产报告永远给假阳性。

这组测试锁住三条：
  1. 引擎结构的报告（persona_reviews + persona_notes + next_human_test）8 个
     维度全部基于真实数据打分；
  2. 空输入绝不通过——没有任何维度会因"空列表"拿到通过/满分；
  3. 键名兼容：next_human_test 与 next_human_test_recommendations 都认，
     persona_notes（有损摘要）兜底时如实标记数据来源。
"""

import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SRC = os.path.join(PROJECT_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from harness.evaluator import evaluate_report  # noqa: E402


def _review(pid, name, stance, issues, evidences):
    """一份含全字段（severity/suggested_fix/inference_level）的人格逐条评审。"""
    return {
        "persona_id": pid,
        "persona_name": name,
        "primary_stance": stance,
        "evidence": [
            {"content": content, "inference_level": level}
            for content, level in evidences
        ],
        "key_issues": [
            {
                "severity": sev,
                "title": title,
                "why_it_matters": why,
                "suggested_fix": fix,
            }
            for sev, title, why, fix in issues
        ],
    }


def _engine_style_report():
    """模拟引擎聚合报告的形状：persona_reviews（全量）+ persona_notes +
    consensus / major_disagreements / priority_fixes / information_gaps /
    next_human_test / cross_examination（引擎实际键名）。"""
    personas = [
        _review(
            "P01-a",
            "人格甲",
            "值得推进",
            issues=[
                (
                    "critical",
                    "新手引导讲不清",
                    "新玩家卡在序章反复失败",
                    "添加一段分步引导并强化目标标记",
                ),
                (
                    "high",
                    "加载流程过长",
                    "每次启动等待超过三十秒",
                    "优化资源加载顺序并加入跳过动画",
                ),
            ],
            evidences=[("核心循环说明", "direct"), ("实机视频", "inferred")],
        ),
        _review(
            "P02-b",
            "人格乙",
            "观望",
            issues=[
                (
                    "high",
                    "付费点位置突兀",
                    "首充弹窗打断核心体验",
                    "把付费入口移到结算环节并弱化弹窗频率",
                )
            ],
            evidences=[("核心循环说明", "direct")],
        ),
        _review(
            "P03-c",
            "人格丙",
            "不推荐",
            issues=[
                (
                    "critical",
                    "存档机制缺失",
                    "退出后进度全部丢失",
                    "增加自动存档并提示手动保存路径",
                )
            ],
            evidences=[("竞品对比", "direct")],
        ),
    ]
    return {
        "meta": {"task_type": "concept_review", "target": "某独立游戏概念文档", "is_synthetic": True},
        "executive_summary": {"primary_recommendation": "值得推进", "release_risk": "high", "evidence_quality": "strong"},
        "consensus": {"agreed_points": ["核心循环清晰"], "questioned_points": ["新手引导"]},
        "major_disagreements": [
            {
                "topic": "付费设计",
                "severity": "high",
                "persona_stances": [
                    {"persona_id": "P01-a", "stance": "值得推进", "evidence": "付费点可接受"},
                    {"persona_id": "P03-c", "stance": "不推荐", "evidence": "付费点太突兀"},
                ],
                "resolution_suggestion": "A/B 测试",
            }
        ],
        "priority_fixes": [
            {"priority": 1, "issue": "新手引导讲不清", "severity": "critical",
             "why_it_matters": "卡关", "affected_personas": ["P01-a"], "suggested_fix": "添加引导"},
        ],
        "persona_reviews": personas,
        "persona_notes": [
            {
                "persona_id": p["persona_id"],
                "persona_name": p["persona_name"],
                "stance": p["primary_stance"],
                "evidence_top3": [e["content"] for e in p["evidence"]],
                "top_issues": [i["title"] for i in p["key_issues"]],
                "continue_triggers": [],
                "quit_triggers": [],
            }
            for p in personas
        ],
        "information_gaps": ["实机视频"],
        "next_human_test": {
            "suggested_tasks": ["验证新手引导"],
            "recruit_types": ["新玩家"],
            "next_materials": ["实机视频"],
        },
        "cross_examination": {
            "mode": "derived_summary",
            "controversy_points": [
                {"topic": "付费设计", "severity": "high"},
                {"topic": "新手引导", "severity": "critical"},
            ],
        },
    }


class TestEngineReportScoresOnRealData:
    """对引擎真实结构的报告：8 个维度必须全部基于数据打分，没有"无法评估"。"""

    def test_all_eight_dimensions_are_evaluable(self):
        result = evaluate_report(_engine_style_report())

        assert result["persona_reviews_source"] == "persona_reviews"
        assert result["persona_reviews_count"] == 3
        assert result["unevaluable_dimensions"] == [], result["unevaluable_dimensions"]

        names = {d["name"] for d in result["dimensions"]}
        assert not any("无法评估" in n for n in names), names
        assert all(d["evaluable"] for d in result["dimensions"])
        # 每一维的分数都来自真实数据，而不是"空列表 → 满分"的假阳性
        assert all(d["score"] >= 1 for d in result["dimensions"])

    def test_overall_passes_for_good_report(self):
        result = evaluate_report(_engine_style_report())
        assert result["overall_passed"] is True
        assert result["overall_score"] >= 3.0

    def test_actionability_uses_suggested_fix(self):
        result = evaluate_report(_engine_style_report())
        actionability = next(d for d in result["dimensions"] if d["key"] == "actionability")
        assert actionability["value"] >= 0.7
        assert actionability["details"]["total_issues"] == 4

    def test_risk_detection_sees_severity(self):
        result = evaluate_report(_engine_style_report())
        risk = next(d for d in result["dimensions"] if d["key"] == "risk_detection")
        assert risk["details"]["critical_count"] >= 1
        assert risk["passed"] is True

    def test_segment_conflict_sees_controversy_points(self):
        result = evaluate_report(_engine_style_report())
        conflict = next(d for d in result["dimensions"] if d["key"] == "segment_conflict")
        assert conflict["details"]["meaningful_disagreements"] >= 2
        assert conflict["passed"] is True


class TestEmptyInputNeverPasses:
    """"空输入反而通过"是这个维度历史上最严重的假阳性：报告里没有人格数据时，
    循环体一次都不执行，violation_count=0 → 满分通过。现在必须全部判失败/无法评估。"""

    def test_empty_report_no_dimension_passes(self):
        result = evaluate_report({})

        assert result["persona_reviews_source"] == "none"
        assert result["persona_reviews_count"] == 0
        assert result["overall_passed"] is False
        assert result["unevaluable_dimensions"], "空报告必须至少有一个维度标无法评估"

        for d in result["dimensions"]:
            assert d["passed"] is False, f"空输入时 {d['key']} 竟然通过了"
            assert d["score"] < 4, f"空输入时 {d['key']} 竟然拿了高分 {d['score']}"

    def test_stereotype_check_on_empty_text_is_unevaluable_not_passed(self):
        """刻板印象检查权重最高（1.5），历史上因为输入为空列表而恒定 5 分通过。"""
        result = evaluate_report({})
        stereotype = next(d for d in result["dimensions"] if d["key"] == "stereotype_check")
        assert "无法评估" in stereotype["name"]
        assert stereotype["passed"] is False
        assert stereotype["evaluable"] is False

    def test_report_without_persona_data_marks_unevaluable(self):
        """有章节但没有人格数据：可以评结构，但依赖人格数据的维度必须无法评估。"""
        report = {
            "consensus": {"agreed_points": [], "questioned_points": []},
            "major_disagreements": [],
            "priority_fixes": [],
            "information_gaps": [],
            "next_human_test": {"suggested_tasks": [], "recruit_types": [], "next_materials": []},
        }
        result = evaluate_report(report)
        assert result["overall_passed"] is False
        keys = {d["key"] for d in result["dimensions"] if not d["evaluable"]}
        assert {"actionability", "calibration_honesty"} <= keys


class TestKeyNameCompatibility:
    """评估器读的键名必须同时认引擎键与旧键，否则"各说各的键名"会重现。"""

    def test_next_human_test_is_recognized(self):
        report = _engine_style_report()
        result = evaluate_report(report)
        structural = next(d for d in result["dimensions"] if d["key"] == "structural_integrity")
        assert "next_human_test" in structural["details"]["present_sections"]
        assert structural["details"]["missing_sections"] == []

    def test_legacy_next_human_test_recommendations_is_recognized(self):
        report = _engine_style_report()
        report["next_human_test_recommendations"] = report.pop("next_human_test")
        result = evaluate_report(report)
        structural = next(d for d in result["dimensions"] if d["key"] == "structural_integrity")
        assert structural["details"]["coverage"] == 1.0
        assert structural["passed"] is True

    def test_persona_notes_fallback_is_lossy_and_visible(self):
        """持久化后的引擎报告只有 persona_notes（有损摘要）：必须能评估，但
        数据来源要如实标出来——不能假装是全量数据打的分。"""
        report = _engine_style_report()
        report.pop("persona_reviews")  # 模拟落盘后的报告：全量输出已丢弃
        result = evaluate_report(report)

        assert result["persona_reviews_source"] == "persona_notes"
        # 有损摘要没有 severity/suggested_fix/inference_level：
        # 依赖这些字段的维度必须判"无法评估"而不是拿 0% 当结论
        unevaluable = {d["key"] for d in result["dimensions"] if not d["evaluable"]}
        assert {"actionability", "input_grounding", "risk_detection"} <= unevaluable
        # 校准诚实度对"有证据条目但没 inference_level"的处理是如实低分
        # （不是假装无法评估，也不是假装满分）
        calibration = next(d for d in result["dimensions"] if d["key"] == "calibration_honesty")
        assert calibration["passed"] is False
        assert result["overall_passed"] is False
