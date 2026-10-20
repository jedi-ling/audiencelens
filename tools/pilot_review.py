#!/usr/bin/env python3
"""试点交付用评审驱动器：跑 AudienceLens 面板 + 可选 single-prompt 盲比基线。

为什么不是直接用 audiencelens CLI：CLI 的 run 命令目前不透传 provider/api_base/
model_override（BYOK 是 Web 端能力），试点期用 MiniMax 端点只能走 run_panel 的
Python 参数面。若试点成立，再把这些开关提进 CLI，别现在动发布面。

key 来源（不落盘、不进环境变量历史）：
  1. 默认读本机 cc-switch 数据库里的 MiniMax(claude) 配置；
  2. 环境变量 PILOT_LLM_KEY / PILOT_LLM_BASE / PILOT_LLM_MODEL 可覆盖。

用法（仓库根目录，用 web/backend 的 venv）：
  ./web/backend/.venv/Scripts/python.exe tools/pilot_review.py \
      --artifact pilot-data/<case>/artifact.json \
      --output-dir pilot-data/<case>/output \
      [--mode standard] [--baseline]
"""

import argparse
import json
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

CC_SWITCH_DB = os.path.expanduser(r"~\.cc-switch\cc-switch.db")
CC_SWITCH_PROVIDER_ID = "02069a2d-b726-4808-9b7c-132fde3def06"  # MiniMax (claude app)

# 试点手册的 single-prompt 公平基线（docs/pilot-playbook.md 原文，逐字不可改——
# 改了盲比就失去对照意义）。同模型、同材料、相近输出上限，调用一次不追问。
SINGLE_PROMPT_BASELINE = (
    "你是一名资深独立游戏发行与商店页评审专家。请只依据提供的材料，评估该 Steam 商店页的"
    "愿望单吸引力、卖点清晰度、信任信号和价格价值感。输出主要立场、置信度、关键问题、"
    "证据和按优先级排列的修改建议。缺失信息必须标记为缺口，不得编造。"
)


def load_llm_config() -> dict:
    key = os.environ.get("PILOT_LLM_KEY")
    base = os.environ.get("PILOT_LLM_BASE")
    model = os.environ.get("PILOT_LLM_MODEL")
    if key and base:
        return {"key": key, "base": base, "model": model or "MiniMax-M3"}
    cfg = json.loads(
        sqlite3.connect(CC_SWITCH_DB)
        .execute(
            "SELECT settings_config FROM providers WHERE id=? AND app_type='claude'",
            (CC_SWITCH_PROVIDER_ID,),
        )
        .fetchone()[0]
    )["env"]
    return {
        "key": key or cfg["ANTHROPIC_AUTH_TOKEN"],
        "base": base or cfg["ANTHROPIC_BASE_URL"],
        "model": model or cfg.get("ANTHROPIC_MODEL", "MiniMax-M3"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="试点评审驱动器（面板 + 可选基线）")
    ap.add_argument("--artifact", required=True, help="材料包 JSON（{materials:[...]}）")
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--task-type", default="steam_page_review")
    ap.add_argument("--mode", default="standard", choices=["quick", "standard", "full"])
    ap.add_argument("--baseline", action="store_true", help="同材料跑 single-prompt 公平基线")
    ap.add_argument("--budget", default=os.path.join("src", "config", "budget-pilot.yaml"),
                    help="预算配置（默认试点版：四类重试全开；Web/CLI 默认 budget.yaml 不受影响）")
    args = ap.parse_args()

    llm = load_llm_config()
    with open(args.artifact, encoding="utf-8") as f:
        bundle = json.load(f)

    from src.runner import cli as runner_cli

    t0 = time.time()
    result = runner_cli.run_panel(
        task_type=args.task_type,
        artifact_bundle=bundle,
        api_key=llm["key"],
        provider="anthropic",
        api_base=llm["base"],
        model_override=llm["model"],
        mode=args.mode,
        budget_path=args.budget,
        progress_callback=lambda d, t, pid: print(f"  [{d}/{t}] {pid}", flush=True),
    )

    os.makedirs(args.output_dir, exist_ok=True)
    # 完整信封（含 cost_summary / persona_outputs）一起存：试点手册要求成本与判据留档，
    # 只存 report 子树会把成本账丢掉。
    envelope = {k: v for k, v in result.items()}
    with open(os.path.join(args.output_dir, "panel_result_envelope.json"), "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2, default=str)
    with open(os.path.join(args.output_dir, f"{args.task_type}_report.md"), "w", encoding="utf-8") as f:
        f.write(result.get("markdown", ""))
    with open(os.path.join(args.output_dir, f"{args.task_type}_report.html"), "w", encoding="utf-8") as f:
        f.write(result.get("html", ""))

    cs = result.get("cost_summary") or {}
    deg = result.get("report", {}).get("degradation", {})
    print(
        f"\n面板完成 {time.time()-t0:.0f}s | 人格 {cs.get('persona_count')}/{cs.get('attempted_count')} 成功"
        f" | 成本 ${cs.get('total_cost', 0):.4f}"
        f"（输入 {cs.get('total_input_tokens', 0)} tok / 输出 {cs.get('total_output_tokens', 0)} tok）"
        f" | 降级: {deg.get('degraded')}"
    )

    if args.baseline:
        from src.runner.llm_client import chat_completion

        material_text = "\n\n".join(
            m.get("description") or m.get("text", "")
            for m in bundle.get("materials", [])
            if m.get("type") != "image"
        )
        b0 = time.time()
        text, it, ot = chat_completion(
            model=llm["model"],
            prompt=SINGLE_PROMPT_BASELINE + "\n\n【商店页材料】\n" + material_text,
            api_key=llm["key"],
            provider="anthropic",
            api_base=llm["base"],
            max_tokens=8192,
        )
        from src.runner.persona_agent import estimate_cost

        baseline_cost = estimate_cost(it, ot, llm["model"])
        with open(os.path.join(args.output_dir, "baseline_single_prompt.md"), "w", encoding="utf-8") as f:
            f.write(f"<!-- single-prompt 公平基线 | 模型 {llm['model']} | "
                    f"输入 {it} tok / 输出 {ot} tok | 成本 ${baseline_cost:.4f} -->\n\n")
            f.write(text)
        print(f"基线完成 {time.time()-b0:.0f}s | 成本 ${baseline_cost:.4f}（单次调用，不追问）")

    return 0


if __name__ == "__main__":
    sys.exit(main())
