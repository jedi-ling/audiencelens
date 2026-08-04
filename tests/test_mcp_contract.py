# -*- coding: utf-8 -*-
"""MCP 通道与引擎之间的契约。

这个文件存在的理由很具体：本仓库最常见的缺陷形状是「一条链路修了、另一条没修」。
下面两条都是这个形状的实例——同一件事在 CLI 上是对的，在 MCP 上是坏的，
而且坏了很久没人发现，因为没有任何测试覆盖 MCP 这条通道。

1. mode 传参：src/cli.py 修过一次「--mode 收下就丢」，当时没意识到
   src/mcp_tools.py 有一份一模一样的断链——校验完 mode 合法性就丢掉，
   run_panel 收到 None 走全量流程。用户选 quick 想省钱，实际按最贵的档花。
2. 人格包清单：PERSONA_PACKS 曾是手写的 10 项列表，而 src/personas/ 下有 11 个包，
   新增的 launch-compliance 选不到（直接被判「未知人格包」）。
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

import mcp_tools  # noqa: E402


class TestModeReachesTheEngine:
    @pytest.mark.parametrize("mode", ["quick", "standard", "full"])
    def test_mode_is_passed_to_run_panel(self, monkeypatch, tmp_path, mode):
        """核心断言：run_panel 真的收到了 mode。

        只断言"调用没报错"是不够的——旧代码也不报错，它只是安静地按全量档跑。
        """
        captured = {}

        def fake_run_panel(**kwargs):
            captured.update(kwargs)
            return {"report": {}, "calibration": None, "cost_summary": {}, "simulated": True}

        monkeypatch.setattr(mcp_tools.runner_cli, "run_panel", fake_run_panel)

        # artifact 直接传纯文本：文件路径分支只认 .json/.yaml/.yml，
        # 传 .txt 路径会被 load_artifact_bundle 拒掉（这是既有契约，不是缺陷）。
        out = mcp_tools.run_synthetic_review(
            task_type="concept_review",
            artifact="一个用于测试的产品概念说明。",
            mode=mode,
            allow_simulation=True,
        )

        assert "error" not in out, out
        assert captured.get("mode") == mode, (
            f"run_panel 没收到 mode={mode!r} —— MCP 客户端选了档位，引擎却按默认档跑。"
            f"实际收到的参数：{sorted(captured)}"
        )

    def test_invalid_mode_is_still_rejected(self):
        """补齐 mode 不能把校验一起弄丢。"""
        out = mcp_tools.run_synthetic_review(
            task_type="concept_review", artifact="一段材料", mode="turbo"
        )
        assert "error" in out and "未知模式" in out["error"]


class TestPersonaPacksAreDiscovered:
    def test_pack_list_matches_the_directory(self):
        """清单必须等于 src/personas/ 下的真实文件，不是手写常量。"""
        import glob

        on_disk = sorted(
            os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(SRC, "personas", "*.yaml"))
        )
        assert on_disk, "src/personas/ 下一个 YAML 都没有，先确认路径"
        assert list(mcp_tools.PERSONA_PACKS) == on_disk, (
            "MCP 的 PERSONA_PACKS 与 src/personas/ 目录对不上。\n"
            "如果这是因为有人又把它写成了手写列表——不要补一行了事，"
            "改回从目录现算，否则下次加包还会漏。\n"
            f"清单：{list(mcp_tools.PERSONA_PACKS)}\n目录：{on_disk}"
        )

    def test_every_listed_pack_is_actually_selectable(self, monkeypatch):
        """清单里的每个包都要真的能被选中——不能只是名字对得上。"""
        monkeypatch.setattr(
            mcp_tools.runner_cli,
            "run_panel",
            lambda **kw: {"report": {}, "calibration": None, "cost_summary": {}, "simulated": True},
        )
        for pack in mcp_tools.PERSONA_PACKS:
            out = mcp_tools.run_synthetic_review(
                task_type="concept_review",
                artifact="一段材料",
                personas_pack=pack,
                allow_simulation=True,
            )
            assert "error" not in out, f"人格包 {pack} 选不了：{out.get('error')}"
