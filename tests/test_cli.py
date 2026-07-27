import json
import os
import tempfile

import pytest
import yaml
from click.testing import CliRunner

from runner import cli as runner_cli
from runner.cli import (
    AllPersonasFailedError,
    filter_genuine_controversies,
    load_artifact_bundle,
    main,
    run_panel,
    run_single_persona,
    truncate_panel,
)
from src import cli as audiencelens_cli

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PERSONAS_PATH = os.path.join(PROJECT_ROOT, "src", "personas", "game-core.yaml")
PRESETS_PATH = os.path.join(PROJECT_ROOT, "src", "presets", "panel-presets.yaml")
RULES_PATH = os.path.join(PROJECT_ROOT, "src", "config", "aggregation-rules.yaml")
BUDGET_PATH = os.path.join(PROJECT_ROOT, "src", "config", "budget.yaml")
OUTPUT_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "schemas", "output-schema.json")
REPORT_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "schemas", "report-schema.json")
PERSONA_PROMPT_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "persona-prompt.md")
CROSS_EXAM_PROMPT_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "cross-exam-prompt.md")
REPORT_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.md")


@pytest.fixture
def sample_persona():
    return {
        "id": "P01-indie-core-operator",
        "name": "林岚",
        "mbti": "INTJ",
        "archetype": "核心独立探索者",
        "identity_summary": "更在意这游戏是否真的有自己的一套东西",
        "behavior_profile": {
            "patience": "高",
            "genre_literacy": "高",
            "novelty_seeking": "高",
            "risk_tolerance": "中",
            "social_influence": "低",
            "completion_drive": "中",
            "price_sensitivity": "中",
            "emotional_engagement": "中",
            "agency_preference": "高",
            "tolerance_for_ambiguity": "高",
            "platform_loyalty": "中",
        },
        "motivations": ["独特机制", "作者表达"],
        "decision_rules": [
            "若15秒内看不到核心钩子，不加愿望单",
        ],
        "quit_triggers": ["卖点说不清"],
        "continue_triggers": ["机制互锁明显"],
        "first_scan_focus": ["一句话定位"],
        "review_output": {
            "must_comment_on": ["独特性", "核心循环证据"],
        },
        "evidence_types_needed": ["核心循环说明", "实机视频"],
        "model_hint": "sonnet",
    }


@pytest.fixture
def budget_config():
    with open(BUDGET_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def sample_artifact_bundle():
    return {
        "task_type": "concept_review",
        "target": "某独立游戏概念文档",
        "materials": [
            {"type": "核心循环说明", "text": "游戏核心循环是探索-战斗-成长"},
            {"type": "实机视频", "text": "3分钟实机演示视频"},
            {"type": "竞品对比", "text": "与Hades和Dead Cells对比分析"},
        ],
    }


@pytest.fixture
def artifact_json_file(sample_artifact_bundle):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(sample_artifact_bundle, f, ensure_ascii=False)
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def artifact_yaml_file(sample_artifact_bundle):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.dump(sample_artifact_bundle, f, allow_unicode=True)
        path = f.name
    yield path
    os.unlink(path)


class TestPersonaCatalogIntegrity:
    def test_mobile_extension_personas_do_not_reuse_family_prefixes(self):
        with open(os.path.join(PROJECT_ROOT, "src", "personas", "mobile-f2p.yaml"), "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        ids = {persona["id"] for persona in data.get("personas", [])}

        assert "P42-mobile-monthly-card" not in ids
        assert "P43-mobile-ad-tolerant" not in ids
        assert "P44-mobile-monthly-card" in ids
        assert "P45-mobile-ad-tolerant" in ids


class TestAudienceLensCli:
    def test_run_command_invokes_runner(self, artifact_json_file, monkeypatch, tmp_path):
        called = {}

        def fake_run_panel(**kwargs):
            called.update(kwargs)
            return {"report": {}, "markdown": "", "html": "", "calibration": {}, "cost_summary": {"total_cost": 0.0}}

        monkeypatch.setattr(audiencelens_cli.runner_cli, "run_panel", fake_run_panel)
        runner = CliRunner()
        result = runner.invoke(
            audiencelens_cli.main,
            [
                "run",
                "synthetic-playtest",
                "concept_review",
                artifact_json_file,
                "--output-dir",
                str(tmp_path),
            ],
        )

        assert result.exit_code == 0
        assert called["task_type"] == "concept_review"
        assert called["artifact_bundle"]["task_type"] == "concept_review"
        assert "runner 模块未完全配置" not in result.output


class TestLoadArtifactBundle:
    def test_load_json(self, artifact_json_file, sample_artifact_bundle):
        result = load_artifact_bundle(artifact_json_file)
        assert result["task_type"] == "concept_review"
        assert result["target"] == "某独立游戏概念文档"
        assert len(result["materials"]) == 3

    def test_load_yaml(self, artifact_yaml_file, sample_artifact_bundle):
        result = load_artifact_bundle(artifact_yaml_file)
        assert result["task_type"] == "concept_review"
        assert result["target"] == "某独立游戏概念文档"
        assert len(result["materials"]) == 3

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_artifact_bundle("/nonexistent/path/bundle.json")

    def test_unsupported_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("some text")
            path = f.name
        try:
            with pytest.raises(ValueError):
                load_artifact_bundle(path)
        finally:
            os.unlink(path)


class TestRunSinglePersona:
    def test_simulated_mode_no_api_key(self, sample_persona, budget_config):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_single_persona(
            persona=sample_persona,
            task_type="concept_review",
            artifact_summary="某独立游戏概念文档",
            artifact_texts=["游戏核心循环是探索-战斗-成长"],
            config={"budget": budget_config, "persona_prompt_path": PERSONA_PROMPT_PATH},
        )
        assert result["persona_id"] == "P01-indie-core-operator"
        assert result["prompt"] != ""
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["cost"] == 0.0
        assert result["error"] is None
        assert result["output"] is not None

    def test_prompt_rendered(self, sample_persona, budget_config):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_single_persona(
            persona=sample_persona,
            task_type="concept_review",
            artifact_summary="某独立游戏概念文档",
            artifact_texts=["游戏核心循环是探索-战斗-成长"],
            config={"budget": budget_config, "persona_prompt_path": PERSONA_PROMPT_PATH},
        )
        assert "P01-indie-core-operator" in result["prompt"]
        assert "concept_review" in result["prompt"]

    def test_model_selection(self, sample_persona, budget_config):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_single_persona(
            persona=sample_persona,
            task_type="concept_review",
            artifact_summary="某独立游戏概念文档",
            artifact_texts=["游戏核心循环是探索-战斗-成长"],
            config={"budget": budget_config, "persona_prompt_path": PERSONA_PROMPT_PATH},
        )
        assert result["model"] == "claude-sonnet-4-20250514"

    def test_model_selection_haiku(self, budget_config):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        persona = {
            "id": "P06-casual-browser",
            "name": "赵悦",
            "mbti": "ESFP",
            "archetype": "休闲浏览者",
            "identity_summary": "随便看看",
            "behavior_profile": {
                "patience": "低",
                "genre_literacy": "低",
                "novelty_seeking": "低",
                "risk_tolerance": "低",
                "social_influence": "高",
                "completion_drive": "低",
                "price_sensitivity": "高",
                "emotional_engagement": "高",
                "agency_preference": "低",
                "tolerance_for_ambiguity": "低",
                "platform_loyalty": "高",
            },
            "motivations": ["社交"],
            "decision_rules": ["朋友推荐就加"],
            "quit_triggers": ["无聊"],
            "continue_triggers": ["有趣"],
            "first_scan_focus": ["截图"],
            "review_output": {"must_comment_on": ["截图"]},
            "model_hint": "haiku",
        }
        result = run_single_persona(
            persona=persona,
            task_type="steam_page_review",
            artifact_summary="某游戏Steam页面",
            artifact_texts=["某游戏截图"],
            config={"budget": budget_config, "persona_prompt_path": PERSONA_PROMPT_PATH},
        )
        assert result["model"] == "claude-haiku-4-5-20251001"

    def test_simulated_output_has_required_fields(self, sample_persona, budget_config):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_single_persona(
            persona=sample_persona,
            task_type="concept_review",
            artifact_summary="某独立游戏概念文档",
            artifact_texts=["游戏核心循环是探索-战斗-成长"],
            config={"budget": budget_config, "persona_prompt_path": PERSONA_PROMPT_PATH},
        )
        output = result["output"]
        assert output is not None
        assert "persona_id" in output
        assert "persona_name" in output
        assert "primary_stance" in output
        assert "confidence" in output
        assert "evidence" in output
        assert "key_issues" in output
        assert "must_comment_on_check" in output
        assert "task_type" in output
        assert output["task_type"] == "concept_review"


class TestRunPanel:
    def test_full_flow_simulated(self, sample_artifact_bundle):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=sample_artifact_bundle,
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
        )
        assert "report" in result
        assert "markdown" in result
        assert "calibration" in result
        assert "cost_summary" in result
        assert "total_cost" in result["cost_summary"]
        assert "persona_count" in result["cost_summary"]
        assert "skipped_count" in result["cost_summary"]

    def test_simulated_mode_carries_warning(self, sample_artifact_bundle):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=sample_artifact_bundle,
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
        )
        assert result["simulated"] is True
        assert "simulation_notice" in result["report"]
        assert "模拟模式" in result["report"]["simulation_notice"]
        assert "模拟模式" in result["markdown"]

    def test_selected_personas_overrides_preset_selection(self, sample_artifact_bundle):
        """对话里"呼叫角色"就是靠这个参数生效——显式指定的 id 必须真的进面板，
        而不是像 v2 链路曾经那样，selected_personas 落库了但从没传给引擎。"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=sample_artifact_bundle,
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
            selected_personas=["P01-indie-core-operator"],
        )
        persona_ids = {n["persona_id"] for n in result["report"]["persona_notes"]}
        assert persona_ids == {"P01-indie-core-operator"}

    @staticmethod
    def _rich_bundle():
        """材料类型覆盖整个人格包的 evidence_types_needed 全集——
        让 precheck 一个人都不跳过，人数断言才真正测的是 mode 截断而不是证据筛选。"""
        import yaml as _yaml

        with open(PERSONAS_PATH, "r", encoding="utf-8") as f:
            pack = _yaml.safe_load(f)
        evidence_types = set()
        for p in pack["personas"]:
            evidence_types.update(p.get("evidence_types_needed", []))
        return {
            "task_type": "concept_review",
            "target": "覆盖全证据类型的测试包",
            "materials": [{"type": t, "text": f"{t} 的占位材料"} for t in sorted(evidence_types)],
        }

    def test_quick_mode_caps_personas_and_skips_cross_exam_and_calibration(self):
        """mode 曾经只落库不进引擎——"快速扫一眼"实际跑的是全量流程。
        quick 档必须：人数 ≤3、无交叉质证、无校准。"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=self._rich_bundle(),
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
            mode="quick",
        )
        assert result["cost_summary"]["persona_count"] <= 3
        assert result["calibration"] is None

    def test_no_mode_keeps_legacy_full_behavior(self):
        """CLI/旧调用方不传 mode：不截人数（concept_review 预设面板 >3 人）、
        校准照跑——保持历史行为不回归。"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=self._rich_bundle(),
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
        )
        assert result["calibration"] is not None
        assert result["cost_summary"]["persona_count"] > 3

    def test_selected_personas_with_no_match_falls_back_to_auto_select(self, sample_artifact_bundle):
        """id 全部拼错/串包时不能跑出一个空面板——静默回落到自动选人。"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=sample_artifact_bundle,
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
            selected_personas=["not-a-real-persona-id"],
        )
        assert result["cost_summary"]["persona_count"] > 0

    def test_report_has_required_sections(self, sample_artifact_bundle):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=sample_artifact_bundle,
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
        )
        report = result["report"]
        assert "meta" in report
        assert "executive_summary" in report
        assert "consensus" in report
        assert "priority_fixes" in report
        assert "persona_notes" in report

    def test_calibration_check(self, sample_artifact_bundle):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=sample_artifact_bundle,
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
        )
        calibration = result["calibration"]
        assert "role_consistency" in calibration
        assert "coverage" in calibration
        assert "overall_pass" in calibration

    def test_skipped_personas_tracked(self, sample_artifact_bundle):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=sample_artifact_bundle,
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
        )
        assert isinstance(result["cost_summary"]["skipped_count"], int)

    def test_markdown_rendered(self, sample_artifact_bundle):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = run_panel(
            task_type="concept_review",
            artifact_bundle=sample_artifact_bundle,
            personas_path=PERSONAS_PATH,
            presets_path=PRESETS_PATH,
            rules_path=RULES_PATH,
            budget_path=BUDGET_PATH,
            output_schema_path=OUTPUT_SCHEMA_PATH,
            report_schema_path=REPORT_SCHEMA_PATH,
            persona_prompt_path=PERSONA_PROMPT_PATH,
            cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
            report_template_path=REPORT_TEMPLATE_PATH,
        )
        assert isinstance(result["markdown"], str)
        assert len(result["markdown"]) > 0

    def test_invalid_task_type_raises(self, sample_artifact_bundle):
        with pytest.raises(ValueError):
            run_panel(
                task_type="invalid_type",
                artifact_bundle=sample_artifact_bundle,
                personas_path=PERSONAS_PATH,
                presets_path=PRESETS_PATH,
                rules_path=RULES_PATH,
                budget_path=BUDGET_PATH,
                output_schema_path=OUTPUT_SCHEMA_PATH,
                report_schema_path=REPORT_SCHEMA_PATH,
                persona_prompt_path=PERSONA_PROMPT_PATH,
                cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
                report_template_path=REPORT_TEMPLATE_PATH,
            )


def _llm_json(persona_id: str, severity: str = "medium", title: str = "上手门槛偏高") -> str:
    """一份能通过 parse/normalize 的最小合法人格输出，用来伪造 LLM 返回。"""
    return json.dumps(
        {
            "persona_id": persona_id,
            "persona_name": persona_id,
            "persona_version": "0.1.0",
            "task_type": "concept_review",
            "primary_stance": "观望",
            "confidence": 0.6,
            "evidence_sufficiency": 0.7,
            "evidence": [{"content": "核心循环写得比较清楚", "inference_level": "direct"}],
            "scores": {"base": {"clarity": 3, "trust": 3}, "task_specific": {"overall": 3}},
            "key_issues": [
                {
                    "severity": severity,
                    "title": title,
                    "why_it_matters": "新玩家可能在第一关就走不下去",
                    "suggested_fix": "补一段引导",
                }
            ],
            "continue_triggers": [],
            "quit_triggers": [],
            "first_scan_observations": ["定位一句话说清了"],
            "must_comment_on_check": {},
            "missing_information": [],
            "voice_sample": "看起来还行，但门槛有点高。",
            "meta": {"caveats": [], "is_synthetic": True},
        },
        ensure_ascii=False,
    )


def _rich_bundle():
    """材料覆盖全部 evidence_types_needed，让证据预检一个人格都不跳过——
    多人格断言必须建立在"面板真的有多人"之上（默认的 sample bundle 只过得了 P01）。"""
    return TestRunPanel._rich_bundle()


def _panel(**overrides):
    kwargs = dict(
        task_type="concept_review",
        personas_path=PERSONAS_PATH,
        presets_path=PRESETS_PATH,
        rules_path=RULES_PATH,
        budget_path=BUDGET_PATH,
        output_schema_path=OUTPUT_SCHEMA_PATH,
        report_schema_path=REPORT_SCHEMA_PATH,
        persona_prompt_path=PERSONA_PROMPT_PATH,
        cross_exam_prompt_path=CROSS_EXAM_PROMPT_PATH,
        report_template_path=REPORT_TEMPLATE_PATH,
    )
    kwargs.update(overrides)
    return run_panel(**kwargs)


class TestPanelFailureIsNeverSilent:
    """全员失败时曾经会返回一份 primary_recommendation=""、release_risk="low"、
    0 条修复项的"合法"报告——用户读成"都评过了，没问题"，实际一个都没跑成。
    这组测试锁住"失败必须让调用方无法忽略"。"""

    def test_all_personas_failed_raises_instead_of_returning_report(self, monkeypatch):
        def boom(**kwargs):
            raise RuntimeError("模拟 provider 429：额度用尽")

        monkeypatch.setattr(runner_cli, "chat_completion", boom)

        with pytest.raises(AllPersonasFailedError) as exc:
            _panel(artifact_bundle=_rich_bundle(), api_key="sk-test-not-real")

        err = exc.value
        assert err.attempted > 1
        assert err.failed_count == err.attempted
        # 各人格的错误必须带出来，否则用户/日志只知道"失败了"不知道为什么
        assert len(err.failures) == err.attempted
        assert all(f["persona_id"] for f in err.failures)
        assert all("429" in f["error"] for f in err.failures)
        assert "429" in str(err)

    def test_empty_panel_also_raises(self, sample_artifact_bundle, monkeypatch):
        """一个人格都没进来（面板为空 / 全被证据预检跳过）同样不许产出报告。"""
        monkeypatch.setattr(
            runner_cli,
            "precheck_panel",
            lambda panel, bundle: {
                "valid_personas": [],
                "skipped_personas": [{"persona_id": p["id"], "reason": "no evidence"} for p in panel],
            },
        )

        with pytest.raises(AllPersonasFailedError) as exc:
            _panel(artifact_bundle=sample_artifact_bundle)

        assert exc.value.attempted == 0
        assert exc.value.skipped_count > 0

    def test_partial_failure_is_degraded_and_counts_only_successes(self, monkeypatch):
        """部分失败可以出报告，但必须带降级标记，且 persona_count 是真实成功数。"""
        ok_persona = "P01-indie-core-operator"

        def flaky(**kwargs):
            if ok_persona in kwargs["prompt"]:
                return _llm_json(ok_persona), 100, 200
            raise RuntimeError("模拟 provider 超时")

        monkeypatch.setattr(runner_cli, "chat_completion", flaky)

        result = _panel(artifact_bundle=_rich_bundle(), api_key="sk-test-not-real")

        cost = result["cost_summary"]
        assert cost["persona_count"] == 1  # 真实成功数，不是发起数
        assert cost["attempted_count"] > 1
        assert cost["failed_count"] == cost["attempted_count"] - 1

        assert result["degraded"] is True
        assert len(result["failed_personas"]) == cost["failed_count"]
        assert all("超时" in f["error"] for f in result["failed_personas"])

        degradation = result["report"]["degradation"]
        assert degradation["degraded"] is True
        assert degradation["succeeded_count"] == 1
        assert degradation["failed_count"] == cost["failed_count"]
        assert ok_persona not in [f["persona_id"] for f in degradation["failed_personas"]]
        # 降级必须在渲染产物里也看得见，不能只躺在 JSON 里
        assert "未能完成" in result["markdown"]

    def test_all_success_is_not_marked_degraded(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = _panel(artifact_bundle=_rich_bundle())
        cost = result["cost_summary"]
        assert result["degraded"] is False
        assert result["failed_personas"] == []
        assert cost["persona_count"] == cost["attempted_count"] > 0
        assert cost["failed_count"] == 0
        assert result["report"]["degradation"]["degraded"] is False


class TestControversyFiltering:
    """无争议时不许凭空制造对立：variance==0 或参与人格 <2 的议题不得进争议列表。"""

    def test_zero_variance_and_single_persona_points_are_dropped(self):
        points = [
            {  # 只有一个人格提到——进了交叉质证 pro/con 会是同一个人
                "title": "单人格议题",
                "severity_variance": 0.0,
                "persona_views": [{"persona_id": "p1", "severity": "high"}],
            },
            {  # 两个人格但严重度完全一致，没有分歧可言
                "title": "一致议题",
                "severity_variance": 0.0,
                "persona_views": [
                    {"persona_id": "p1", "severity": "medium"},
                    {"persona_id": "p2", "severity": "medium"},
                ],
            },
            {  # 真分歧：一个说 low 一个说 critical
                "title": "真争议",
                "severity_variance": 2.25,
                "persona_views": [
                    {"persona_id": "p1", "severity": "low"},
                    {"persona_id": "p2", "severity": "critical"},
                ],
            },
        ]
        kept = filter_genuine_controversies(points)
        assert [p["title"] for p in kept] == ["真争议"]

    def test_no_cross_exam_when_everyone_agrees(self):
        """模拟模式下 6 位人格都报同一条 medium 议题（方差 0）——
        以前这里照样生成一份 pro/con 全是占位文案的"争议"。"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = _panel(artifact_bundle=_rich_bundle())
        assert len(result["report"]["persona_notes"]) > 1
        assert result["report"]["cross_examination"] is None

    def test_cross_exam_still_runs_on_real_disagreement(self, monkeypatch):
        """有真分歧时交叉质证必须照跑——过滤不能把正常争议一起干掉。"""
        severities = {
            "P01-indie-core-operator": "critical",
            "P02-systems-theorycrafter": "low",
        }

        def fake(**kwargs):
            prompt = kwargs["prompt"]
            for pid, severity in severities.items():
                if pid in prompt:
                    return _llm_json(pid, severity=severity, title="核心循环说不清"), 10, 20
            raise RuntimeError("本次只让两位人格成功")

        monkeypatch.setattr(runner_cli, "chat_completion", fake)
        result = _panel(artifact_bundle=_rich_bundle(), api_key="sk-test-not-real")

        cross = result["report"]["cross_examination"]
        assert cross is not None
        dispute = cross["disputes"][0]
        # pro/con 必须是两个不同人格，不能自己跟自己吵
        assert dispute["pro_args"][0]["persona_id"] != dispute["con_args"][0]["persona_id"]


class TestTruncatePanelKeepsDissenter:
    """select_panel 把唱反调人格放在列表末尾，从头切等于系统性删掉唯一负面视角。"""

    @staticmethod
    def _panel_of(*ids):
        return [{"id": i} for i in ids]

    def test_dissenter_survives_truncation(self):
        panel = self._panel_of("P01-a", "P02-b", "P04-c", "P06-d", "P15-toxic-skeptic-reviewer")
        kept = truncate_panel(panel, 3)
        assert len(kept) == 3
        assert [p["id"] for p in kept] == ["P01-a", "P02-b", "P15-toxic-skeptic-reviewer"]

    def test_no_replacement_when_dissenter_already_kept(self):
        panel = self._panel_of("P16-veteran", "P01-a", "P02-b", "P04-c")
        kept = truncate_panel(panel, 2)
        assert [p["id"] for p in kept] == ["P16-veteran", "P01-a"]

    def test_panel_without_dissenter_is_plain_head_slice(self):
        panel = self._panel_of("P01-a", "P02-b", "P04-c")
        assert [p["id"] for p in truncate_panel(panel, 2)] == ["P01-a", "P02-b"]

    def test_no_truncation_when_panel_fits(self):
        panel = self._panel_of("P01-a", "P15-x")
        assert truncate_panel(panel, 5) == panel

    def test_quick_mode_panel_keeps_dissenter(self):
        """端到端：quick 档（3 人）跑 concept_review 预设（6 人，P16 在末位）时，
        面板里必须仍有唱反调的人格，否则共识度和 release_risk 系统性偏乐观。"""
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = _panel(artifact_bundle=TestRunPanel._rich_bundle(), mode="quick")
        persona_ids = [n["persona_id"] for n in result["report"]["persona_notes"]]
        assert len(persona_ids) <= 3
        assert any(pid.startswith(("P15", "P16")) for pid in persona_ids), persona_ids


class TestMain:
    def test_argument_parsing(self, artifact_json_file):
        import sys

        original_argv = sys.argv
        try:
            sys.argv = [
                "cli.py",
                "concept_review",
                artifact_json_file,
                "--output-dir",
                tempfile.gettempdir(),
                "--personas",
                PERSONAS_PATH,
                "--presets",
                PRESETS_PATH,
            ]
            os.environ.pop("ANTHROPIC_API_KEY", None)
            main()
            output_dir = tempfile.gettempdir()
            json_files = [f for f in os.listdir(output_dir) if f.endswith(".json") and "concept_review" in f]
            md_files = [f for f in os.listdir(output_dir) if f.endswith(".md") and "concept_review" in f]
            assert len(json_files) > 0 or len(md_files) > 0
        finally:
            sys.argv = original_argv

    def test_all_failed_exits_nonzero_and_writes_no_report(self, artifact_json_file, tmp_path, monkeypatch):
        """CLI 全员失败时必须非零退出、且磁盘上不留任何"无风险"假报告。"""
        import sys

        def boom(**kwargs):
            raise RuntimeError("模拟 provider 鉴权失败")

        monkeypatch.setattr(runner_cli, "chat_completion", boom)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")

        original_argv = sys.argv
        try:
            sys.argv = [
                "cli.py",
                "concept_review",
                artifact_json_file,
                "--output-dir",
                str(tmp_path),
                "--personas",
                PERSONAS_PATH,
                "--presets",
                PRESETS_PATH,
            ]
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
            assert list(tmp_path.iterdir()) == []
        finally:
            sys.argv = original_argv

    def test_missing_required_args(self):
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["cli.py"]
            with pytest.raises(SystemExit):
                main()
        finally:
            sys.argv = original_argv
