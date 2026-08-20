# -*- coding: utf-8 -*-
"""两层评审第一层（全包初筛）的单元测试。

门禁是**确定性排序**——选谁进深评必须可复现、逐人可解释,这是它和
"再调一次模型来选人"的本质区别。所以这里逐条钉住排序规则。
"""

import pytest

from runner.triage import (
    TRIAGE_MATERIAL_CHARS,
    build_triage_prompt,
    parse_triage_output,
    rank_for_advance,
    run_triage,
    simulated_triage,
)


def _r(pid, stance, severity):
    return {"persona_id": pid, "persona_name": pid, "stance": stance,
            "severity": severity, "top_concern": "x"}


class TestGate:
    def test_severity_orders_advancement(self):
        results = [
            _r("p-low", "看好", "low"),
            _r("p-crit", "看好", "critical"),
            _r("p-med", "看好", "medium"),
        ]
        advanced, not_advanced = rank_for_advance(results, max_advance=2)
        assert [a["persona_id"] for a in advanced] == ["p-crit", "p-med"]
        assert advanced[0]["advanced_reason"] == "severity_critical"
        assert [n["persona_id"] for n in not_advanced] == ["p-low"]
        assert not_advanced[0]["not_advanced_reason"] == "below_cutoff"

    def test_minority_stance_beats_same_severity_majority(self):
        """同严重度下,少数派立场先晋级——分歧是对质机制的燃料,
        全员同调的面板不值得付深评的钱。"""
        results = [
            _r("p-a", "看好", "medium"),
            _r("p-b", "看好", "medium"),
            _r("p-c", "不看好", "medium"),
        ]
        advanced, _ = rank_for_advance(results, max_advance=1)
        assert advanced[0]["persona_id"] == "p-c"
        assert advanced[0]["advanced_reason"] == "minority_stance"

    def test_dissenter_guarantee_takes_a_seat(self):
        """异见者保底:哪怕初筛喊的是最低严重度,也占一个名额——
        与 panel_selector.PACK_DISSENTERS 同一条纪律。"""
        results = [
            _r("p-1", "看好", "critical"),
            _r("p-2", "看好", "high"),
            _r("p-diss", "看好", "low"),
        ]
        advanced, _ = rank_for_advance(results, max_advance=2, dissenter_id="p-diss")
        ids = [a["persona_id"] for a in advanced]
        assert "p-diss" in ids
        diss = next(a for a in advanced if a["persona_id"] == "p-diss")
        assert diss["advanced_reason"] == "dissenter_guarantee"
        # 保底占掉一个名额后,剩下的按严重度补
        assert ids == ["p-diss", "p-1"]

    def test_deterministic_tiebreak_by_persona_id(self):
        """同分必须按 persona_id 字典序——选人不可以有随机性,
        同样的初筛结果必须选出同样的深评面板。"""
        results = [_r("p-b", "看好", "high"), _r("p-a", "看好", "high")]
        a1, _ = rank_for_advance(results, max_advance=1)
        a2, _ = rank_for_advance(list(reversed(results)), max_advance=1)
        assert a1[0]["persona_id"] == a2[0]["persona_id"] == "p-a"

    def test_everyone_advances_when_slots_exceed_pool(self):
        results = [_r("p-1", "看好", "low"), _r("p-2", "观望", "low")]
        advanced, not_advanced = rank_for_advance(results, max_advance=5)
        assert len(advanced) == 2 and not_advanced == []

    def test_empty_input(self):
        assert rank_for_advance([], max_advance=3) == ([], [])


class TestPrompt:
    def _bundle(self, text):
        return {"materials": [{"type": "text", "text": text}]}

    def test_truncation_is_reported_not_silent(self):
        long = "字" * (TRIAGE_MATERIAL_CHARS + 500)
        prompt, truncated = build_triage_prompt({"id": "p", "name": "P"}, "concept_review", self._bundle(long))
        assert truncated is True
        assert "初筛截断到此" in prompt

    def test_short_materials_not_truncated(self):
        prompt, truncated = build_triage_prompt({"id": "p", "name": "P"}, "concept_review", self._bundle("短材料"))
        assert truncated is False
        assert "短材料" in prompt

    def test_context_materials_excluded(self):
        """项目历史等背景材料不进初筛——初筛判断的是本次材料本身。"""
        bundle = {"materials": [
            {"type": "text", "text": "本次正文"},
            {"type": "项目历史", "text": "历史判断内容", "is_context": True},
        ]}
        prompt, _ = build_triage_prompt({"id": "p", "name": "P"}, "concept_review", bundle)
        assert "本次正文" in prompt
        assert "历史判断内容" not in prompt


class TestParse:
    def test_valid_json(self):
        raw = '好的。{"stance": "观望", "severity": "high", "top_concern": "定价不透明"}'
        out = parse_triage_output(raw, {"id": "p1", "name": "N"})
        assert out == {
            "persona_id": "p1", "persona_name": "N", "stance": "观望",
            "severity": "high", "top_concern": "定价不透明",
        }

    def test_unknown_severity_falls_to_medium(self):
        raw = '{"stance": "看好", "severity": "urgent", "top_concern": "x"}'
        assert parse_triage_output(raw, {"id": "p"})["severity"] == "medium"

    def test_garbage_returns_none_not_fabrication(self):
        """解析失败返回 None——失败的初筛不编造立场。"""
        assert parse_triage_output("模型跑偏了没给 JSON", {"id": "p"}) is None
        assert parse_triage_output('{"severity": "high"}', {"id": "p"}) is None  # 缺 stance


class TestRunTriage:
    def test_simulation_mode_produces_divergent_stances(self):
        personas = [{"id": f"p{i}", "name": f"P{i}"} for i in range(6)]
        out = run_triage(personas, "concept_review", {"materials": []}, call_llm=None)
        assert len(out["results"]) == 6
        stances = {r["stance"] for r in out["results"]}
        assert len(stances) >= 2, "模拟初筛必须制造分歧,否则门禁逻辑测不到"

    def test_single_failure_does_not_kill_the_layer(self):
        personas = [{"id": "ok", "name": "OK"}, {"id": "boom", "name": "BOOM"}]

        def call(prompt):
            if "BOOM" in prompt:
                raise RuntimeError("网络抖了")
            return '{"stance": "看好", "severity": "low", "top_concern": "x"}', 10, 5

        out = run_triage(personas, "concept_review",
                         {"materials": [{"type": "text", "text": "m"}]}, call_llm=call)
        assert len(out["results"]) == 1
        assert out["failures"][0]["persona_id"] == "boom"
        assert out["input_tokens"] == 10 and out["output_tokens"] == 5
