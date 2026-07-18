import os

import mcp_tools


class TestDiscoveryTools:
    def test_list_task_types(self):
        result = mcp_tools.list_task_types()
        ids = [t["id"] for t in result["task_types"]]
        assert "steam_page_review" in ids
        assert "product_feedback_review" in ids  # 通用产品向任务类型（不限游戏）
        assert "pitch_review" in ids  # 创业项目评审
        assert len(ids) == 14
        assert all(t["description"] for t in result["task_types"])

    def test_list_persona_packs(self):
        result = mcp_tools.list_persona_packs()
        assert "game-core" in result["persona_packs"]
        assert "general-consumer" in result["persona_packs"]  # 通用产品向人格包（不限游戏）
        assert "startup-panel" in result["persona_packs"]  # 创业评审团
        assert len(result["persona_packs"]) == 10

    def test_list_personas_default_pack(self):
        result = mcp_tools.list_personas()
        assert result["pack"] == "game-core"
        assert result["count"] > 0
        assert all("id" in p for p in result["personas"])

    def test_list_personas_unknown_pack(self):
        result = mcp_tools.list_personas("nonexistent")
        assert "error" in result


class TestArtifactResolution:
    def test_inline_text(self):
        bundle = mcp_tools._resolve_artifact_bundle("这是一段评审材料")
        assert bundle["materials"][0]["description"] == "这是一段评审材料"

    def test_inline_json(self):
        bundle = mcp_tools._resolve_artifact_bundle(
            '{"title": "某游戏", "materials": [{"type": "text", "description": "核心循环"}]}'
        )
        assert bundle["title"] == "某游戏"

    def test_empty_raises(self):
        import pytest

        with pytest.raises(ValueError):
            mcp_tools._resolve_artifact_bundle("")


class TestRunReviewGuards:
    def test_unknown_task_type(self):
        result = mcp_tools.run_synthetic_review("bad_type", "材料")
        assert "error" in result
        assert "未知任务类型" in result["error"]

    def test_unknown_mode(self):
        result = mcp_tools.run_synthetic_review("concept_review", "材料", mode="ultra")
        assert "error" in result

    def test_unknown_pack(self):
        result = mcp_tools.run_synthetic_review(
            "concept_review", "材料", personas_pack="bad_pack"
        )
        assert "error" in result

    def test_no_api_key_refuses_by_default(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = mcp_tools.run_synthetic_review("concept_review", "某游戏核心循环材料")
        assert result.get("needs_api_key") is True
        assert "ANTHROPIC_API_KEY" in result["error"]

    def test_allow_simulation_runs_pipeline(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        bundle = '{"title": "某独立游戏", "materials": [{"type": "text", "description": "探索-战斗-成长的核心循环"}]}'
        result = mcp_tools.run_synthetic_review(
            "concept_review", bundle, allow_simulation=True
        )
        assert "report" in result
        assert result["simulated"] is True
