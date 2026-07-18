import json
import os
import tempfile

import pytest
import yaml
from click.testing import CliRunner

from runner.cli import load_artifact_bundle, main, run_panel, run_single_persona
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

    def test_missing_required_args(self):
        import sys

        original_argv = sys.argv
        try:
            sys.argv = ["cli.py"]
            with pytest.raises(SystemExit):
                main()
        finally:
            sys.argv = original_argv
