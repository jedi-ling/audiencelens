from harness.ablation import (
    build_condition_prompt,
    compute_condition_metrics,
    issue_divergence,
    severity_js,
    stance_entropy,
    strip_behavior_fields,
)
from runner.similarity import get_issue_similarity


def _output(pid, stance, issues):
    return {
        "persona_id": pid,
        "primary_stance": stance,
        "key_issues": [
            {"title": t, "severity": s} for t, s in issues
        ],
    }


IDENTICAL_OUTPUTS = [
    _output("P01", "观望", [("新手引导太长", "high"), ("定价偏高", "medium")]),
    _output("P02", "观望", [("新手引导太长", "high"), ("定价偏高", "medium")]),
    _output("P03", "观望", [("新手引导太长", "high"), ("定价偏高", "medium")]),
]

DIVERSE_OUTPUTS = [
    _output("P01", "愿意购买", [("美术风格出色", "low")]),
    _output("P02", "观望", [("付费墙太早", "critical")]),
    _output("P03", "不会购买", [("缺少手柄支持", "high")]),
]


class TestMetrics:
    def setup_method(self):
        self.sim = get_issue_similarity(force_lexical=True)

    def test_identical_outputs_low_divergence(self):
        assert issue_divergence(IDENTICAL_OUTPUTS, self.sim) < 0.05

    def test_diverse_outputs_high_divergence(self):
        assert issue_divergence(DIVERSE_OUTPUTS, self.sim) > 0.5

    def test_identical_severity_zero_js(self):
        assert severity_js(IDENTICAL_OUTPUTS) == 0.0

    def test_diverse_severity_positive_js(self):
        assert severity_js(DIVERSE_OUTPUTS) > 0.3

    def test_identical_stance_zero_entropy(self):
        assert stance_entropy(IDENTICAL_OUTPUTS) == 0.0

    def test_all_distinct_stances_max_entropy(self):
        assert stance_entropy(DIVERSE_OUTPUTS) == 1.0

    def test_empty_outputs(self):
        assert issue_divergence([], self.sim) == 0.0
        assert severity_js([]) == 0.0
        assert stance_entropy([]) == 0.0

    def test_compute_condition_metrics_keys(self):
        m = compute_condition_metrics(DIVERSE_OUTPUTS, self.sim)
        assert set(m) == {
            "persona_count",
            "issue_divergence",
            "severity_js",
            "stance_entropy",
        }
        assert m["persona_count"] == 3


class TestConditions:
    def test_strip_behavior_fields(self):
        persona = {
            "id": "P01",
            "identity_summary": "独立游戏老玩家",
            "behavior_profile": {"patience": "低"},
            "decision_rules": ["看评测再买"],
            "quit_triggers": ["强制教程"],
            "continue_triggers": ["新机制"],
        }
        stripped = strip_behavior_fields(persona)
        assert "behavior_profile" not in stripped
        assert "decision_rules" not in stripped
        assert "quit_triggers" not in stripped
        assert "continue_triggers" not in stripped
        assert stripped["identity_summary"] == "独立游戏老玩家"

    def test_bare_prompt_has_no_persona(self):
        prompt = build_condition_prompt(
            "bare",
            {"id": "P01", "name": "某人格"},
            "concept_review",
            "某游戏概念文档",
            persona_prompt_path="",
        )
        assert "某人格" not in prompt
        assert "concept_review" in prompt
        assert "某游戏概念文档" in prompt
