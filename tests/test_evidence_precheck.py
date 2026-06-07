import pytest
from runner.evidence_precheck import (
    load_evidence_types,
    check_evidence_coverage,
    precheck_panel,
)

SAMPLE_PERSONAS = [
    {
        "id": "P01-test-one",
        "name": "测试一",
        "evidence_types_needed": ["核心循环说明", "实机视频", "竞品对比"],
    },
    {
        "id": "P06-test-six",
        "name": "测试六",
        "evidence_types_needed": ["胶囊图", "截图", "预告片"],
    },
    {
        "id": "P15-test-fifteen",
        "name": "测试十五",
        "evidence_types_needed": ["实机视频", "评论区样本", "EA说明"],
    },
]

SAMPLE_BUNDLE = {
    "materials": [
        {"type": "实机视频", "description": "游戏实机演示"},
        {"type": "截图", "description": "游戏截图"},
        {"type": "胶囊图", "description": "Steam胶囊图"},
        {"type": "核心循环说明", "description": "核心玩法说明"},
    ]
}


class TestLoadEvidenceTypes:
    def test_load_evidence_types_normal(self):
        result = load_evidence_types(SAMPLE_BUNDLE)
        assert isinstance(result, list)
        assert "实机视频" in result
        assert "截图" in result
        assert "胶囊图" in result
        assert "核心循环说明" in result

    def test_load_evidence_types_dedup(self):
        bundle = {
            "materials": [
                {"type": "截图", "description": "截图1"},
                {"type": "截图", "description": "截图2"},
                {"type": "视频", "description": "视频1"},
            ]
        }
        result = load_evidence_types(bundle)
        assert result.count("截图") == 1
        assert len(result) == 2

    def test_load_evidence_types_empty_materials(self):
        bundle = {"materials": []}
        result = load_evidence_types(bundle)
        assert result == []

    def test_load_evidence_types_empty_bundle(self):
        bundle = {}
        result = load_evidence_types(bundle)
        assert result == []


class TestCheckEvidenceCoverage:
    def test_full_coverage(self):
        persona = {
            "id": "P01",
            "evidence_types_needed": ["实机视频", "核心循环说明"],
        }
        available = ["实机视频", "核心循环说明", "截图"]
        result = check_evidence_coverage(persona, available)
        assert result["persona_id"] == "P01"
        assert result["coverage_ratio"] == 1.0
        assert result["sufficient"] is True
        assert result["missing"] == []

    def test_partial_coverage(self):
        persona = {
            "id": "P01",
            "evidence_types_needed": ["实机视频", "核心循环说明", "竞品对比", "UI截图"],
        }
        available = ["截图"]
        result = check_evidence_coverage(persona, available)
        assert result["coverage_ratio"] < 0.3
        assert result["sufficient"] is False

    def test_no_coverage(self):
        persona = {
            "id": "P06",
            "evidence_types_needed": ["胶囊图", "截图", "预告片"],
        }
        available = ["实机视频", "核心循环说明"]
        result = check_evidence_coverage(persona, available)
        assert result["coverage_ratio"] == 0.0
        assert result["sufficient"] is False
        assert len(result["missing"]) == 3

    def test_exact_half_coverage(self):
        persona = {
            "id": "P01",
            "evidence_types_needed": ["A", "B"],
        }
        available = ["A"]
        result = check_evidence_coverage(persona, available)
        assert result["coverage_ratio"] == 0.5
        assert result["sufficient"] is True

    def test_sufficient_threshold(self):
        persona = {
            "id": "P01",
            "evidence_types_needed": ["A", "B", "C"],
        }
        available = ["A", "B"]
        result = check_evidence_coverage(persona, available)
        assert result["coverage_ratio"] == pytest.approx(2.0 / 3.0)
        assert result["sufficient"] is True

    def test_no_evidence_types_needed(self):
        persona = {"id": "P99", "evidence_types_needed": []}
        available = ["实机视频"]
        result = check_evidence_coverage(persona, available)
        assert result["coverage_ratio"] == 1.0
        assert result["sufficient"] is True

    def test_return_fields(self):
        persona = {
            "id": "P01",
            "evidence_types_needed": ["A", "B"],
        }
        available = ["A"]
        result = check_evidence_coverage(persona, available)
        assert "persona_id" in result
        assert "needed" in result
        assert "available" in result
        assert "missing" in result
        assert "coverage_ratio" in result
        assert "sufficient" in result


class TestPrecheckPanel:
    def test_precheck_panel_normal(self):
        result = precheck_panel(SAMPLE_PERSONAS, SAMPLE_BUNDLE)
        assert "valid_personas" in result
        assert "skipped_personas" in result
        assert "evidence_summary" in result
        assert len(result["valid_personas"]) > 0

    def test_precheck_panel_skips_low_coverage(self):
        result = precheck_panel(SAMPLE_PERSONAS, SAMPLE_BUNDLE)
        for p in result["valid_personas"]:
            available = load_evidence_types(SAMPLE_BUNDLE)
            coverage = check_evidence_coverage(p, available)
            assert coverage["sufficient"] is True

    def test_precheck_panel_all_skipped(self):
        sparse_bundle = {
            "materials": [
                {"type": "不相关的类型", "description": "无用的材料"},
            ]
        }
        result = precheck_panel(SAMPLE_PERSONAS, sparse_bundle)
        assert len(result["valid_personas"]) == 0
        assert len(result["skipped_personas"]) == len(SAMPLE_PERSONAS)

    def test_precheck_panel_evidence_summary(self):
        result = precheck_panel(SAMPLE_PERSONAS, SAMPLE_BUNDLE)
        summary = result["evidence_summary"]
        assert "available_types" in summary
        assert "total_needed" in summary
        assert "total_covered" in summary
        assert isinstance(summary["total_needed"], int)
        assert isinstance(summary["total_covered"], int)

    def test_precheck_panel_skipped_format(self):
        sparse_bundle = {
            "materials": [
                {"type": "不相关", "description": "无用"},
            ]
        }
        result = precheck_panel(SAMPLE_PERSONAS, sparse_bundle)
        for skipped in result["skipped_personas"]:
            assert "persona_id" in skipped
            assert "reason" in skipped
            assert "missing" in skipped

    def test_precheck_panel_empty_bundle(self):
        result = precheck_panel(SAMPLE_PERSONAS, {})
        assert len(result["valid_personas"]) == 0
        assert result["evidence_summary"]["available_types"] == []

    def test_precheck_panel_total_needed(self):
        result = precheck_panel(SAMPLE_PERSONAS, SAMPLE_BUNDLE)
        total = sum(len(p.get("evidence_types_needed", [])) for p in SAMPLE_PERSONAS)
        assert result["evidence_summary"]["total_needed"] == total
