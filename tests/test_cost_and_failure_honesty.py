"""成本口径与失败口径的诚实性。

三条缺陷有共同的形状：**它们都让系统对外报告一个比现实更好看的数字**，
而且全都不报错、不告警，纯静默。

  1. estimate_cost 对不在 budget.yaml 价目表里的模型返回 0.0
     → quota_service 的 24 小时成本硬闸 `if cost >= cost_limit` 永远不成立，
       平台垫付的钱没有上限；后台成本面板恒显示 $0。
       而后台面板本来就允许把垫付 key 配成任意 OpenAI 兼容模型。
  2. 模型吐非法 JSON 时被算成"评审成功的人格"
     → degradation 报 0 失败、用户读到"全部角色完成评审"，
       而那位角色交的是废纸；立场分布还被兜底的"观望"污染。
  3. CLI 的 --mode 收下就丢
     → 用户 --mode quick 想省钱，实际跑全量面板，钱按最贵的档花，
       终端还明明白白打着「模式: quick」。
"""

import os
import sys

import pytest
import yaml

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
SRC = os.path.join(PROJECT_ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from runner import cli as runner_cli  # noqa: E402
from runner.persona_agent import (  # noqa: E402
    estimate_cost,
    estimate_cost_detailed,
    resolve_model_pricing,
)

BUDGET_PATH = os.path.join(SRC, "config", "budget.yaml")
PERSONA_PROMPT_PATH = os.path.join(SRC, "templates", "persona-prompt.md")


@pytest.fixture
def budget_config():
    with open(BUDGET_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_persona():
    return {
        "id": "P01-test",
        "name": "测试人格",
        "archetype": "测试原型",
        "identity_summary": "用于测试的人格",
        "behavior_profile": {"patience": "中", "evidence_threshold": "中", "risk_tolerance": "中"},
        "motivations": ["动机"],
        "decision_rules": ["规则"],
    }


class TestUnknownModelIsNotFree:
    def test_registered_model_uses_its_own_price(self, budget_config):
        in_p, out_p, priced = resolve_model_pricing("claude-sonnet-4-20250514", budget_config)
        assert priced is True
        assert (in_p, out_p) == (3.0, 15.0)

    def test_unknown_model_costs_money_and_is_flagged(self, budget_config):
        """核心断言：没登记价格 ≠ 免费。"""
        cost, priced = estimate_cost_detailed(
            1_000_000, 1_000_000, "deepseek-chat-not-in-table", budget_config
        )
        assert priced is False, "必须如实告诉调用方这个价格是估的"
        assert cost > 0, (
            "不在价目表里的模型成本被算成 0 —— 成本硬闸会因此永远不触发，"
            "后台成本面板会恒显示 $0，而且完全静默"
        )

    def test_unknown_model_estimated_conservatively(self, budget_config):
        """宁可高估：高估只让闸提前触发，低估等于没有闸。"""
        unknown = estimate_cost(1_000_000, 1_000_000, "some-third-party-model", budget_config)
        cheapest = estimate_cost(1_000_000, 1_000_000, "claude-haiku-4-5-20251001", budget_config)
        assert unknown >= cheapest, "未知模型的估价不能低于表里最便宜的一档"

    def test_budget_yaml_declares_the_fallback(self, budget_config):
        """兜底价必须是配置里显式写着的，而不是散落在代码里的魔数。"""
        fb = budget_config.get("unknown_model_pricing") or {}
        assert float(fb.get("input_per_mtok", 0)) > 0
        assert float(fb.get("output_per_mtok", 0)) > 0


class TestUnparseableOutputCountsAsFailure:
    def test_non_json_reply_is_a_failure_not_a_success(
        self, monkeypatch, sample_persona, budget_config
    ):
        """模型回一段散文（或被 max_tokens 截断的半截 JSON）时，
        这位人格必须进 failed，而不是顶着空意见冒充成功。"""

        def fake_chat_completion(**kwargs):
            return ("抱歉，我无法按要求的格式回答。这里是一段普通的散文。", 1200, 800)

        monkeypatch.setattr(runner_cli, "chat_completion", fake_chat_completion)

        result = runner_cli.run_single_persona(
            persona=sample_persona,
            task_type="concept_review",
            artifact_summary="某产品概念",
            artifact_texts=["核心循环"],
            config={"budget": budget_config, "persona_prompt_path": PERSONA_PROMPT_PATH},
            api_key="test-key-not-real",
        )

        assert result["output"] is None, (
            "解析失败的人格被当成成功了 —— 它会进 persona_outputs、"
            "让 degradation 报 0 失败、并被计入 cost_summary.persona_count"
        )
        assert result["error"], "必须留下失败原因，否则用户和运维都看不出发生了什么"
        assert "解析" in result["error"] or "JSON" in result["error"]

    def test_failed_parse_still_records_the_spend(
        self, monkeypatch, sample_persona, budget_config
    ):
        """这次调用的 token 是真花掉了，失败不等于免费。"""

        def fake_chat_completion(**kwargs):
            return ("not json at all", 1_000_000, 1_000_000)

        monkeypatch.setattr(runner_cli, "chat_completion", fake_chat_completion)

        result = runner_cli.run_single_persona(
            persona=sample_persona,
            task_type="concept_review",
            artifact_summary="某产品概念",
            artifact_texts=["核心循环"],
            config={"budget": budget_config, "persona_prompt_path": PERSONA_PROMPT_PATH},
            api_key="test-key-not-real",
        )
        assert result["cost"] > 0, "失败也花了钱，账必须记上"
        assert result["input_tokens"] == 1_000_000
        assert result["output_tokens"] == 1_000_000


class TestCliModeReachesTheEngine:
    def test_mode_option_is_passed_through(self, monkeypatch, tmp_path):
        """--mode 必须真的传给引擎。以前它只在终端打印里露个脸就被丢掉：
        用户选 quick 想省钱，实际跑的是默认档。"""
        from click.testing import CliRunner

        from src import cli as top_cli

        artifact = tmp_path / "material.txt"
        artifact.write_text("一个用于测试的产品概念说明。", encoding="utf-8")

        captured = {}

        def fake_run_panel(**kwargs):
            captured.update(kwargs)
            return {"report": {}, "markdown": "", "html": ""}

        monkeypatch.setattr(top_cli.runner_cli, "run_panel", fake_run_panel)
        monkeypatch.setattr(
            top_cli.runner_cli, "load_artifact_bundle", lambda p: {"materials": []}
        )

        res = CliRunner().invoke(
            top_cli.main,
            [
                "run",
                "synthetic-playtest",
                "concept_review",
                str(artifact),
                "--mode",
                "quick",
                "--output-dir",
                str(tmp_path / "out"),
            ],
        )

        assert res.exit_code == 0, res.output
        assert captured.get("mode") == "quick", (
            "--mode 没有传到 run_panel —— 用户选了 quick，引擎却按默认档跑，"
            f"实际收到的参数：{sorted(captured)}"
        )
