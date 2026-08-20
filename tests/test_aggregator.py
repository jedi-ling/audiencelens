import os
import pytest
from datetime import datetime

from runner.aggregator import (
    load_aggregation_rules,
    compute_consensus,
    compute_disagreements,
    compute_priority_fixes,
    aggregate_report,
    render_markdown_report,
)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RULES_PATH = os.path.join(PROJECT_ROOT, "src", "config", "aggregation-rules.yaml")
SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "schemas", "report-schema.json")
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.md")


def _pyproject_version():
    """从 pyproject.toml 的 [project] 段读真实包版本。

    测试自己重新解析一遍而不是调 aggregator.resolve_build_version()：
    后者正是被测对象，用它当期望值等于"自己证明自己"，把硬编码改回去也不会红。
    """
    import re
    path = os.path.join(PROJECT_ROOT, "pyproject.toml")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    section = text.split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r"""^\s*version\s*=\s*["']([^"']+)["']""", section, re.M)
    return match.group(1)




def _make_persona(
    persona_id="p1",
    persona_name="Tester",
    primary_stance="positive",
    confidence=0.8,
    evidence_sufficiency=0.7,
    key_issues=None,
    evidence=None,
    missing_information=None,
    must_comment_on_check=None,
    continue_triggers=None,
    quit_triggers=None,
    voice_sample="Looks good to me.",
):
    return {
        "persona_id": persona_id,
        "persona_name": persona_name,
        "persona_version": "0.1.0",
        "task_type": "demo_first_play",
        "primary_stance": primary_stance,
        "confidence": confidence,
        "evidence_sufficiency": evidence_sufficiency,
        "evidence": evidence if evidence is not None else [
            {"content": "UI is clear", "inference_level": "direct"},
        ],
        "scores": {
            "base": {"clarity": 4, "trust": 3},
            "task_specific": {"fun": 4},
        },
        "key_issues": key_issues if key_issues is not None else [],
        "continue_triggers": continue_triggers if continue_triggers is not None else ["good gameplay"],
        "quit_triggers": quit_triggers if quit_triggers is not None else ["bugs"],
        "first_scan_observations": ["looks nice"],
        "must_comment_on_check": must_comment_on_check if must_comment_on_check is not None else {"gameplay": True, "visuals": True},
        "missing_information": missing_information if missing_information is not None else [],
        "voice_sample": voice_sample,
        "meta": {"caveats": ["synthetic"], "is_synthetic": True},
    }


class TestLoadAggregationRules:
    def test_loads_yaml_successfully(self):
        rules = load_aggregation_rules(RULES_PATH)
        assert "severity_boost" in rules
        assert "consensus_threshold" in rules

    def test_severity_boost_values(self):
        rules = load_aggregation_rules(RULES_PATH)
        assert rules["severity_boost"]["critical"] == 2.0
        assert rules["severity_boost"]["high"] == 1.5
        assert rules["severity_boost"]["medium"] == 1.0
        assert rules["severity_boost"]["low"] == 0.5

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_aggregation_rules("/nonexistent/path.yaml")


def _issue(title, severity="medium"):
    return {
        "severity": severity,
        "title": title,
        "why_it_matters": "matters",
        "suggested_fix": "fix",
    }


class TestComputeConsensus:
    """共识必须是议题级的。

    这组测试钉的是"agreed_points 里装的是被多数人格各自提到的**议题**，
    不是立场标签"：谁把它改回按 primary_stance 频次统计，下面这些断言就红。
    """

    def test_agreed_points_are_issues_not_stance_labels(self):
        personas = [
            _make_persona("p1", primary_stance="positive", key_issues=[_issue("新手引导讲不清")]),
            _make_persona("p2", primary_stance="positive", key_issues=[_issue("新手引导讲不清")]),
            _make_persona("p3", primary_stance="positive", key_issues=[_issue("新手引导讲不清")]),
        ]
        result = compute_consensus(personas, threshold=0.7)
        assert result["agreed_points"] == ["新手引导讲不清"]
        # 立场标签绝不能出现在共识点里
        assert "positive" not in result["agreed_points"]
        assert "positive" not in result["questioned_points"]
        assert result["stance_distribution"]["positive"] == 3

    def test_agreed_points_can_exceed_one(self):
        """旧实现受 threshold>0.5 所限，agreed_points 长度恒 ≤1。"""
        personas = [
            _make_persona("p1", key_issues=[_issue("新手引导讲不清楚"), _issue("价格明显高于同类竞品")]),
            _make_persona("p2", key_issues=[_issue("新手引导讲不清楚"), _issue("价格明显高于同类竞品")]),
            _make_persona("p3", key_issues=[_issue("新手引导讲不清楚"), _issue("价格明显高于同类竞品")]),
        ]
        result = compute_consensus(personas, threshold=0.7)
        assert sorted(result["agreed_points"]) == ["价格明显高于同类竞品", "新手引导讲不清楚"]

    def test_minority_issue_goes_to_questioned(self):
        personas = [
            _make_persona("p1", key_issues=[_issue("新手引导讲不清楚"), _issue("音乐循环太短容易腻")]),
            _make_persona("p2", key_issues=[_issue("新手引导讲不清楚")]),
            _make_persona("p3", key_issues=[_issue("新手引导讲不清楚")]),
        ]
        result = compute_consensus(personas, threshold=0.7)
        assert "新手引导讲不清楚" in result["agreed_points"]
        assert "音乐循环太短容易腻" in result["questioned_points"]

    def test_single_persona_is_never_consensus(self):
        """一个人的独角戏不构成共识，哪怕它占了 100%。"""
        personas = [_make_persona("p1", key_issues=[_issue("我一个人提到的问题")])]
        result = compute_consensus(personas, threshold=0.7)
        assert result["agreed_points"] == []
        assert result["min_personas_for_agreement"] >= 2

    def test_no_issues_means_empty_consensus(self):
        """没有议题就诚实地返回空，不许拿立场词凑数。"""
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
            _make_persona("p3", primary_stance="positive"),
        ]
        result = compute_consensus(personas, threshold=0.7)
        assert result["agreed_points"] == []
        assert result["questioned_points"] == []

    def test_shared_concerns_expose_who_raised_it(self):
        personas = [
            _make_persona("p1", key_issues=[_issue("同一件事")]),
            _make_persona("p2", key_issues=[_issue("同一件事")]),
        ]
        result = compute_consensus(personas, threshold=0.7)
        concern = result["shared_concerns"][0]
        assert concern["persona_count"] == 2
        assert set(concern["personas"]) == {"p1", "p2"}

    def test_empty_input(self):
        result = compute_consensus([], threshold=0.7)
        assert result["agreed_points"] == []
        assert result["questioned_points"] == []
        assert result["stance_distribution"] == {}


class TestComputeDisagreements:
    def test_no_disagreements(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
        ]
        result = compute_disagreements(personas)
        assert len(result) == 0

    def test_basic_disagreement(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        result = compute_disagreements(personas)
        assert len(result) >= 1
        assert result[0]["topic"] != ""
        assert len(result[0]["persona_stances"]) >= 2
        # resolution_suggestion 已删除：以前填的是把标题回填进英文套话，
        # 前端却以"建议："的口吻展示。没有调解逻辑就不许有这个字段。
        assert "resolution_suggestion" not in result[0]

    def test_disagreement_with_common_issues(self):
        personas = [
            _make_persona(
                "p1",
                primary_stance="positive",
                key_issues=[
                    {"severity": "low", "title": "UI lag", "why_it_matters": "annoying", "suggested_fix": "optimize"},
                ],
            ),
            _make_persona(
                "p2",
                primary_stance="negative",
                key_issues=[
                    {"severity": "critical", "title": "UI lag", "why_it_matters": "game-breaking", "suggested_fix": "rewrite"},
                ],
            ),
        ]
        result = compute_disagreements(personas)
        assert len(result) >= 1
        topic_found = any("UI lag" in d["topic"] for d in result)
        assert topic_found
        # resolution_suggestion 的删除必须两个分支都钉住：test_basic_disagreement
        # 只覆盖立场两两配对分支，这里补上 controversial_issues 主分支——
        # 变异实测过：把 f"Further investigation needed on {title}" 加回主分支，
        # 没有这条断言时整个测试文件仍然全绿。
        for d in result:
            assert "resolution_suggestion" not in d

    def test_disagreement_persona_stances_structure(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        result = compute_disagreements(personas)
        for d in result:
            for ps in d["persona_stances"]:
                assert "persona_id" in ps
                assert "stance" in ps
                assert "evidence" in ps

    def test_disagreement_dedup_method_recorded(self):
        """P1-2: disagreements 应记录 dedup_method"""
        from runner.similarity import get_issue_similarity
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="negative"),
        ]
        result = compute_disagreements(personas)
        for d in result:
            assert "dedup_method" in d
            assert d["dedup_method"] in ("semantic", "lexical")

    def test_disagreement_similarity_merges_paraphrased_titles(self):
        """P1-2: 相似度合并应将换措辞的同一议题归为一组"""
        personas = [
            _make_persona(
                "p1",
                primary_stance="positive",
                key_issues=[
                    {"severity": "low", "title": "UI lag", "why_it_matters": "annoying", "suggested_fix": "optimize"},
                ],
            ),
            _make_persona(
                "p2",
                primary_stance="negative",
                key_issues=[
                    {"severity": "critical", "title": "UI lag", "why_it_matters": "game-breaking", "suggested_fix": "rewrite"},
                ],
            ),
        ]
        from runner.similarity import get_issue_similarity
        sim = get_issue_similarity(force_lexical=True)
        result = compute_disagreements(personas, similarity=sim)
        # 两个 persona 对同一议题有不同立场，应产生争议
        assert len(result) >= 1
        for d in result:
            assert d["dedup_method"] == "lexical"


class TestComputePriorityFixes:
    def test_basic_priority(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "critical", "title": "Crash on start", "why_it_matters": "can't play", "suggested_fix": "fix init"},
                ],
            ),
            _make_persona(
                "p2",
                key_issues=[
                    {"severity": "medium", "title": "Slow menu", "why_it_matters": "annoying", "suggested_fix": "optimize"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        assert len(result) >= 2
        assert result[0]["severity"] == "critical"
        assert result[0]["priority"] == 1

    def test_deduplication_by_title(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "high", "title": "UI lag", "why_it_matters": "bad UX", "suggested_fix": "optimize"},
                ],
            ),
            _make_persona(
                "p2",
                key_issues=[
                    {"severity": "high", "title": "UI lag", "why_it_matters": "slow", "suggested_fix": "cache"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        ui_lag_items = [r for r in result if r["issue"] == "UI lag"]
        assert len(ui_lag_items) == 1
        assert len(ui_lag_items[0]["affected_personas"]) == 2

    def test_severity_score_calculation(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "critical", "title": "Crash", "why_it_matters": "broken", "suggested_fix": "fix"},
                ],
            ),
            _make_persona(
                "p2",
                key_issues=[
                    {"severity": "low", "title": "Typo", "why_it_matters": "minor", "suggested_fix": "edit"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        crash_item = next(r for r in result if r["issue"] == "Crash")
        typo_item = next(r for r in result if r["issue"] == "Typo")
        assert crash_item["score"] > typo_item["score"]

    def test_affected_count_increases_score(self):
        # 两个"不同议题"的标题必须真的不像：去重改成相似度聚类后，
        # 原来用的 "Bug A"/"Bug B" 字面相似度 0.8 会被正确地判为同一个议题。
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "high", "title": "Crash on launch", "why_it_matters": "bad", "suggested_fix": "fix"},
                ],
            ),
            _make_persona(
                "p2",
                key_issues=[
                    {"severity": "high", "title": "Crash on launch", "why_it_matters": "bad", "suggested_fix": "fix"},
                ],
            ),
            _make_persona(
                "p3",
                key_issues=[
                    {"severity": "high", "title": "Typo in tooltip", "why_it_matters": "bad", "suggested_fix": "fix"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        crash = next(r for r in result if r["issue"] == "Crash on launch")
        typo = next(r for r in result if r["issue"] == "Typo in tooltip")
        assert crash["score"] > typo["score"]

    def test_empty_issues(self):
        personas = [_make_persona("p1", key_issues=[])]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        assert result == []

    def test_result_structure(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "high", "title": "Bug", "why_it_matters": "bad", "suggested_fix": "fix it"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        result = compute_priority_fixes(personas, rules)
        item = result[0]
        assert "priority" in item
        assert "issue" in item
        assert "severity" in item
        assert "why_it_matters" in item
        assert "affected_personas" in item
        assert "suggested_fix" in item
        assert "score" in item


class _StubSimilarity:
    """确定性相似度：groups 里映射到同一 key 的标题视为同一议题。

    真机上的相似度档位取决于有没有装 sentence-transformers（semantic/lexical
    两套阈值），聚类语义的断言必须和它解耦，否则测试会随环境飘。
    """

    method = "stub"

    def __init__(self, groups):
        self.groups = groups

    def is_same_issue(self, a: str, b: str) -> bool:
        return self.groups.get(a, a) == self.groups.get(b, b)


class TestPriorityFixesDedupMatchesClustering:
    """priority_fixes 以前用 title 精确相等去重，而 disagreements/controversy 用相似度
    聚类——同一个问题换个措辞就裂成 N 条、每条 affected_count=1，排序退化成只看
    severity。这组测试锁住"同口径去重 + severity 取最高"。"""

    @staticmethod
    def _rules():
        return load_aggregation_rules(RULES_PATH)

    def test_reworded_titles_merge_into_one_fix(self):
        sim = _StubSimilarity({
            "新手引导讲不清": "onboarding",
            "教程没说明白核心循环": "onboarding",
            "前 10 分钟不知道要干什么": "onboarding",
        })
        personas = [
            _make_persona("p1", key_issues=[{"severity": "medium", "title": "新手引导讲不清", "why_it_matters": "a", "suggested_fix": "x"}]),
            _make_persona("p2", key_issues=[{"severity": "medium", "title": "教程没说明白核心循环", "why_it_matters": "b", "suggested_fix": "y"}]),
            _make_persona("p3", key_issues=[{"severity": "medium", "title": "前 10 分钟不知道要干什么", "why_it_matters": "c", "suggested_fix": "z"}]),
        ]
        result = compute_priority_fixes(personas, self._rules(), similarity=sim)
        assert len(result) == 1
        assert sorted(result[0]["affected_personas"]) == ["p1", "p2", "p3"]
        assert len(result[0]["title_variants"]) == 3
        assert result[0]["dedup_method"] == "stub"

    def test_severity_takes_max_not_first_reporter(self):
        """A 说 low、B/C 说 critical 时，合并后必须是 critical——
        旧实现取第一个报出者的值，等于把最严重的判断永久吞掉。"""
        sim = _StubSimilarity({"存档偶尔丢": "save", "存档丢失导致进度归零": "save"})
        personas = [
            _make_persona("p1", key_issues=[{"severity": "low", "title": "存档偶尔丢", "why_it_matters": "小概率", "suggested_fix": "看看"}]),
            _make_persona("p2", key_issues=[{"severity": "critical", "title": "存档丢失导致进度归零", "why_it_matters": "直接退款", "suggested_fix": "加校验"}]),
        ]
        result = compute_priority_fixes(personas, self._rules(), similarity=sim)
        assert len(result) == 1
        assert result[0]["severity"] == "critical"
        # 描述跟着最严重的那份走，避免 critical 配一句无关痛痒的理由
        assert result[0]["why_it_matters"] == "直接退款"
        assert result[0]["suggested_fix"] == "加校验"

    def test_widely_reported_issue_outranks_isolated_critical(self):
        """排序不再退化成只看 severity：3 人都提的 medium（1.0×3）
        必须排在 1 人提的 critical（2.0×1）前面。"""
        sim = _StubSimilarity({
            "手感偏钝": "feel",
            "打击感不足": "feel",
            "反馈太轻": "feel",
        })
        personas = [
            _make_persona("p1", key_issues=[{"severity": "medium", "title": "手感偏钝", "why_it_matters": "a", "suggested_fix": "x"}]),
            _make_persona("p2", key_issues=[{"severity": "medium", "title": "打击感不足", "why_it_matters": "b", "suggested_fix": "y"}]),
            _make_persona(
                "p3",
                key_issues=[
                    {"severity": "medium", "title": "反馈太轻", "why_it_matters": "c", "suggested_fix": "z"},
                    {"severity": "critical", "title": "某个孤立的崩溃", "why_it_matters": "d", "suggested_fix": "w"},
                ],
            ),
        ]
        result = compute_priority_fixes(personas, self._rules(), similarity=sim)
        assert result[0]["issue"] in ("手感偏钝",)
        assert result[0]["priority"] == 1
        assert len(result[0]["affected_personas"]) == 3
        assert result[1]["severity"] == "critical"

    def test_uses_real_similarity_not_exact_equality_by_default(self):
        """不注入 similarity 时也必须走相似度：措辞差一个字不该裂成两条。"""
        from runner.similarity import get_issue_similarity

        sim = get_issue_similarity(force_lexical=True)
        personas = [
            _make_persona("p1", key_issues=[{"severity": "high", "title": "UI lag on menus", "why_it_matters": "a", "suggested_fix": "x"}]),
            _make_persona("p2", key_issues=[{"severity": "high", "title": "UI lag on menu", "why_it_matters": "b", "suggested_fix": "y"}]),
        ]
        result = compute_priority_fixes(personas, self._rules(), similarity=sim)
        assert len(result) == 1
        assert len(result[0]["affected_personas"]) == 2
        assert result[0]["dedup_method"] == "lexical"

    def test_report_shares_one_dedup_method_across_sections(self):
        """同一份报告里 disagreements 和 priority_fixes 必须同口径。"""
        personas = [
            _make_persona("p1", primary_stance="positive", key_issues=[{"severity": "high", "title": "UI lag", "why_it_matters": "a", "suggested_fix": "x"}]),
            _make_persona("p2", primary_stance="negative", key_issues=[{"severity": "low", "title": "UI lag", "why_it_matters": "b", "suggested_fix": "y"}]),
        ]
        report = aggregate_report(personas, "demo_first_play", "GameX", self._rules())
        methods = {f["dedup_method"] for f in report["priority_fixes"]}
        methods |= {d["dedup_method"] for d in report["major_disagreements"]}
        assert len(methods) == 1


class TestAggregateReport:
    def test_basic_report_structure(self):
        personas = [
            _make_persona("p1", primary_stance="positive", missing_information=["price"]),
            _make_persona("p2", primary_stance="positive", missing_information=["release date"]),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert "meta" in report
        assert "executive_summary" in report
        assert "consensus" in report
        assert "major_disagreements" in report
        assert "priority_fixes" in report
        assert "persona_notes" in report
        assert "information_gaps" in report
        assert "next_human_test" in report

    def test_meta_fields(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        meta = report["meta"]
        assert meta["task_type"] == "demo_first_play"
        assert meta["target"] == "GameX"
        # 版本号必须来自真实事实源。这条断言故意跟 pyproject.toml 对齐：
        # 谁把 build_version 改回硬编码字面量，它就红。
        assert meta["build_version"] == _pyproject_version()
        # 没有事实源的字段不许存在（提示词模板从来没有版本机制）
        assert "prompt_version" not in meta
        # 没传 persona_pack 时不许凭空编一个包版本
        assert "persona_pack_version" not in meta
        assert meta["is_synthetic"] is True
        datetime.fromisoformat(meta["generated_at"])

    def test_executive_summary_primary_recommendation(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
            _make_persona("p3", primary_stance="negative"),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["primary_recommendation"] == "positive"

    def test_executive_summary_release_risk(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "critical", "title": "Crash", "why_it_matters": "broken", "suggested_fix": "fix"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["release_risk"] in ["low", "medium", "high", "critical"]

    def test_executive_summary_release_risk_critical(self):
        personas = [
            _make_persona(
                "p1",
                key_issues=[
                    {"severity": "critical", "title": "Crash", "why_it_matters": "broken", "suggested_fix": "fix"},
                    {"severity": "high", "title": "Bug", "why_it_matters": "bad", "suggested_fix": "fix"},
                ],
            ),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["release_risk"] == "critical"

    def test_executive_summary_evidence_quality(self):
        personas = [
            _make_persona("p1", evidence_sufficiency=0.9),
            _make_persona("p2", evidence_sufficiency=0.8),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["evidence_quality"] in ["strong", "medium", "weak", "insufficient"]

    def test_information_gaps_dedup(self):
        personas = [
            _make_persona("p1", missing_information=["price", "release date"]),
            _make_persona("p2", missing_information=["price", "system requirements"]),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        gaps = report["information_gaps"]
        assert "price" in gaps
        assert gaps.count("price") == 1

    def test_next_human_test_structure(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        nht = report["next_human_test"]
        assert "suggested_tasks" in nht
        assert "recruit_types" in nht
        assert "next_materials" in nht

    def test_persona_notes_structure(self):
        personas = [_make_persona("p1", persona_name="Alice")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        notes = report["persona_notes"]
        assert len(notes) == 1
        assert notes[0]["persona_id"] == "p1"
        assert notes[0]["persona_name"] == "Alice"

    def test_with_cross_exam_data(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        cross_exam = {"rounds": [{"round_num": 1, "is_current": True}], "disputes": [], "vote_changes": [], "confidence_changes": []}
        report = aggregate_report(personas, "demo_first_play", "GameX", rules, cross_exam_data=cross_exam)
        assert "meta" in report
        assert "cross_examination" in report
        assert report["cross_examination"] is not None


class TestRenderMarkdownReport:
    def test_renders_basic_report(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        md = render_markdown_report(report, TEMPLATE_PATH)
        assert "GameX" in md
        assert "demo_first_play" in md
        assert "positive" in md

    def test_template_file_not_found(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        with pytest.raises(FileNotFoundError):
            render_markdown_report(report, "/nonexistent/template.md")

    def test_markdown_contains_sections(self):
        personas = [
            _make_persona("p1", primary_stance="positive"),
            _make_persona("p2", primary_stance="positive"),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        md = render_markdown_report(report, TEMPLATE_PATH)
        assert "Consensus" in md
        assert "Priority Fixes" in md


class TestAggregatorToleratesOffSchemaOutput:
    """第三方模型（MiniMax 等）产出的 persona 输出未必严格贴合 output-schema：
    可能缺 persona_id / key_issues，或 evidence 项少 content 字段。聚合器过去
    对这些字段是硬取值，一份不合规输出就 KeyError 让整份报告作废、报告空壳。
    加固后应降级容忍：缺字段用默认值，绝不崩，仍产出可用报告。"""

    def test_missing_persona_id_and_key_issues_does_not_crash(self):
        rules = load_aggregation_rules(RULES_PATH)
        off_schema = [
            {"primary_stance": "观望", "scores": {}},  # 无 persona_id / key_issues / evidence
            {"persona_id": "P02", "primary_stance": "会买",
             "evidence": [{"label": "只有label没有content"}]},  # evidence 项缺 content
        ]
        report = aggregate_report(off_schema, "concept_review", "X", rules)
        assert "executive_summary" in report
        assert len(report["persona_notes"]) == 2  # 两个都保留，没被崩掉

    def test_non_dict_issue_items_skipped(self):
        rules = load_aggregation_rules(RULES_PATH)
        weird = [
            {"persona_id": "P1", "primary_stance": "会买",
             "key_issues": ["裸字符串不是dict", {"title": "真issue", "severity": "high"}]},
        ]
        report = aggregate_report(weird, "concept_review", "X", rules)
        assert "executive_summary" in report


class TestTruthfulReportFields:
    """把"这些数字来自真实来源"钉死：改回硬编码/占位串就红。"""

    def test_caveats_come_from_persona_outputs(self):
        personas = [
            _make_persona("p1"),  # 默认 meta.caveats = ["synthetic"]
            _make_persona("p2"),
        ]
        personas[1]["meta"]["caveats"] = ["仅基于商店页文案"]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["meta"]["caveats"] == ["synthetic", "仅基于商店页文案"]

    def test_caveats_render_into_markdown(self):
        personas = [_make_persona("p1")]
        personas[0]["meta"]["caveats"] = ["只看了 30 秒预告片"]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        md = render_markdown_report(report, TEMPLATE_PATH)
        assert "Limitations & Caveats" in md
        assert "只看了 30 秒预告片" in md

    def test_persona_pack_version_comes_from_pack(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(
            personas, "demo_first_play", "GameX", rules,
            persona_pack={"pack_id": "mobile-f2p", "version": "0.1.0"},
        )
        # 必须带包名：所有人格包目前都是 0.1.0，只写版本号等于没有版本信息
        assert report["meta"]["persona_pack_version"] == "mobile-f2p@0.1.0"

    def test_recruit_types_are_never_persona_names(self):
        """招募人群绝不能是本次跑过的 AI 人格代号。"""
        personas = [_make_persona("p1", persona_name="林岚")]
        panel = [{
            "id": "p1",
            "name": "林岚",
            "age_range": "25-32",
            "region": "中国华东",
            "gaming_profile": {"experience": "核心", "platforms": ["PC", "Switch"]},
        }]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(
            personas, "demo_first_play", "GameX", rules, panel_personas=panel
        )
        recruit = report["next_human_test"]["recruit_types"]
        assert recruit == ["25-32 · 中国华东 · 核心 · PC/Switch"]
        assert "林岚" not in recruit

    def test_no_english_placeholder_when_nothing_derived(self):
        """推不出来就留空，不许回落成 General players 这类占位串。"""
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        nht = report["next_human_test"]
        assert nht["suggested_tasks"] == []
        assert nht["recruit_types"] == []
        assert nht["next_materials"] == []

    def test_release_risk_counts_deduped_issues(self):
        """两位人格用不同措辞说同一个 high 问题，不该升级成 critical。"""
        personas = [
            _make_persona("p1", key_issues=[_issue("新手引导讲不清楚", "high")]),
            _make_persona("p2", key_issues=[_issue("新手引导讲不清楚", "high")]),
        ]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert len(report["priority_fixes"]) == 1
        assert report["executive_summary"]["release_risk"] == "high"

    def test_missing_evidence_sufficiency_is_excluded_not_zero(self):
        """缺字段的人格排除出分母，不能按 0 拉低"证据充分度"。"""
        personas = [
            _make_persona("p1", evidence_sufficiency=0.9),
            _make_persona("p2", evidence_sufficiency=0.9),
        ]
        del personas[1]["evidence_sufficiency"]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        assert report["executive_summary"]["evidence_quality"] == "strong"

    def test_all_missing_evidence_sufficiency_is_unknown_not_insufficient(self):
        personas = [_make_persona("p1")]
        del personas[0]["evidence_sufficiency"]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        # None 而不是 "insufficient"：字段缺失不等于证据很差
        assert report["executive_summary"]["evidence_quality"] is None

    def test_markdown_contains_cross_exam_and_compliance(self):
        """服务端 Markdown 必须和 HTML 说同样的话。"""
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(
            personas, "demo_first_play", "GameX", rules,
            cross_exam_data={
                "mode": "derived_summary",
                "is_live_debate": False,
                "limitation": "没有发生实时反驳",
                "disputes": [],
            },
        )
        md = render_markdown_report(report, TEMPLATE_PATH)
        assert "交叉质询" in md
        assert "这不是一场辩论" in md
        assert "没有发生实时反驳" in md
        assert "合规检查" in md
        assert "身份-行为解耦检查" in md

    def test_markdown_has_no_python_list_repr(self):
        """导出件里不许出现 ['a', 'b'] 这种列表 repr。"""
        personas = [_make_persona("p1", key_issues=[_issue("引导太长")])]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        md = render_markdown_report(report, TEMPLATE_PATH)
        assert "['" not in md

    def test_markdown_omits_version_rows_without_source(self):
        personas = [_make_persona("p1")]
        rules = load_aggregation_rules(RULES_PATH)
        report = aggregate_report(personas, "demo_first_play", "GameX", rules)
        md = render_markdown_report(report, TEMPLATE_PATH)
        assert "prompt_version" not in md
        assert "persona_pack_version" not in md
        assert "0.1.0" not in md


# ---------------------------------------------------------------------------
# report 必须可 JSON 序列化 —— 这是引擎对外的硬契约
# ---------------------------------------------------------------------------


def test_report_with_calibration_is_json_serializable():
    """report 里挂了 calibration 之后仍然必须能 json.dumps。

    这条测试的存在是因为一次真实的破坏：有人把 run_calibration_check 的原始
    返回值直接塞进 report["validation"]["calibration"]，而它的
    coverage.pairwise_distances 用 (id1, id2) **元组**做键。后果是两条链路同时炸：
      · CLI：cli.py 最后一步 json.dump(result["report"]) TypeError，
        用户跑完整场评审，报告在写文件那一刻全丢
      · web：review.report_json 是 JSON 列，flush 时崩 → 整条 UPDATE 失败 →
        评审 100% 标 failed，报错还是一句与评审内容毫无关系的 "keys must be str"

    当时**三套测试全绿**都没拦住它，因为模拟模式默认只跑 1 个人格，而
    compute_coverage_score 在 len(ids) < 2 时提前返回空 dict，元组键根本不生成。
    所以这条测试必须显式构造 ≥2 个人格。
    """
    import json

    from runner.calibration import compute_coverage_score
    from runner.cli import _json_safe

    outputs = [
        {"persona_id": "P01", "key_issues": ["首屏说不清玩法", "价格偏高"]},
        {"persona_id": "P02", "key_issues": ["移动端适配差", "引导太长"]},
    ]
    coverage = compute_coverage_score(outputs)

    # 前置条件：确认这次真的生成了元组键，否则下面的断言什么都证明不了
    assert coverage.get("pairwise_distances"), "前置条件不成立：没有生成 pairwise_distances"
    assert any(
        isinstance(k, tuple) for k in coverage["pairwise_distances"]
    ), "前置条件不成立：键不是元组，这条测试失去意义"

    # 反向对照：不拍平就是会炸。这一句失败说明 calibration 的结构变了，
    # 那时应当重新确认本测试是否还有意义，而不是直接删掉它。
    with pytest.raises(TypeError):
        json.dumps({"validation": {"calibration": {"coverage": coverage}}})

    report = {"validation": {"calibration": _json_safe({"coverage": coverage})}}
    json.dumps(report)  # 不抛异常即通过


class TestEvidenceProfileAndDimensionScores:
    """报告的"可信度记账"：证据构成 + 维度均分。

    设计边界（有逻辑的参考，不是抄 ARTi）：ARTi 给股票打加权综合分，权重是拍的；
    我们**不做**任何加权综合分——evidence_profile 度量的是报告自身的证据构成
    （direct/inferred/gap 各多少条），dimension_scores 只给逐维度的简单均分加
    min/max。这两块的每个数字都能从 persona_outputs 逐条对出来。
    """

    @staticmethod
    def _rules():
        return load_aggregation_rules(RULES_PATH)

    def _personas(self):
        return [
            _make_persona(
                "p1",
                evidence=[
                    {"content": "a", "inference_level": "direct"},
                    {"content": "b", "inference_level": "direct"},
                    {"content": "c", "inference_level": "inferred"},
                    {"content": "d", "inference_level": "gap"},
                ],
            ),
            _make_persona(
                "p2",
                evidence=[
                    {"content": "e", "inference_level": "inferred"},
                    {"content": "f"},  # 未标注等级：进分母、不算 inferred（与 validator 同口径）
                ],
            ),
        ]

    def test_profile_counts_match_inputs_and_validator_basis(self):
        report = aggregate_report(self._personas(), "demo_first_play", "GameX", self._rules())
        ep = report["evidence_profile"]
        assert ep["total"] == 6
        assert ep["direct"] == 2
        assert ep["inferred"] == 2
        assert ep["gap"] == 1
        # 口径 = validator 的 inferred / 全部条数（未标注计入分母）
        assert ep["inferred_ratio"] == round(2 / 6, 3)
        # 阈值必须随报告落库，且与 validator 的常量同源——历史报告按当时规则解读
        from runner.validator import MAX_INFERRED_RATIO

        assert ep["threshold"] == MAX_INFERRED_RATIO
        p2 = next(x for x in ep["per_persona"] if x["persona_id"] == "p2")
        assert p2 == {
            "persona_id": "p2", "direct": 0, "inferred": 1, "gap": 0,
            "total": 2, "inferred_ratio": 0.5,
        }

    def test_dimension_scores_are_plain_averages_with_spread(self):
        personas = self._personas()
        personas[0]["scores"] = {"base": {"clarity": 4, "trust": 2}, "task_specific": {"pacing": 5}}
        personas[1]["scores"] = {"base": {"clarity": 2}, "task_specific": {}}
        report = aggregate_report(personas, "demo_first_play", "GameX", self._rules())
        ds = {d["dim"]: d for d in report["dimension_scores"]}
        assert ds["clarity"] == {"dim": "clarity", "avg": 3.0, "min": 2.0, "max": 4.0, "count": 2}
        assert ds["trust"]["count"] == 1
        assert ds["pacing"]["avg"] == 5.0
        # 红线：不存在任何加权综合分
        assert "overall_score" not in report
        assert all("weight" not in d for d in report["dimension_scores"])

    def test_empty_evidence_does_not_divide_by_zero(self):
        personas = [_make_persona("p1", evidence=[])]
        report = aggregate_report(personas, "demo_first_play", "GameX", self._rules())
        assert report["evidence_profile"]["total"] == 0
        assert report["evidence_profile"]["inferred_ratio"] == 0.0
        assert report["dimension_scores"] == [] or isinstance(report["dimension_scores"], list)

