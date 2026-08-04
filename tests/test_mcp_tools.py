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
        """包数量对着 src/personas/ 现算，不写死。

        这条断言原本是 `== 10`，而目录里那时已经有 11 个包（launch-compliance 是
        后加的，没人回来改 MCP 的手写清单）。于是这个测试不但没抓住"MCP 选不到
        新包"这个缺陷，反而把它锁成了"正确行为"——写死的数字会把测试从
        看门人变成共犯。改成现算之后，加包不用改测试，漏包会立刻红。
        """
        import glob
        import os

        result = mcp_tools.list_persona_packs()
        packs = result["persona_packs"]
        on_disk = sorted(
            os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(mcp_tools._SRC_DIR, "personas", "*.yaml"))
        )
        assert sorted(packs) == on_disk, (
            f"MCP 暴露的人格包与 src/personas/ 对不上：清单 {sorted(packs)} / 目录 {on_disk}"
        )
        # 几个有代表性的包单独点名，措辞改了也能一眼看出少了谁
        for expected in ("game-core", "general-consumer", "startup-panel", "launch-compliance"):
            assert expected in packs, f"人格包 {expected} 没出现在 MCP 清单里"

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
