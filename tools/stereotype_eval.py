"""刻板印象检测评测：在标注集上评估正则层和 LLM 层的准确率。

用法：
    python tools/stereotype_eval.py            # 仅正则层（离线）
    python tools/stereotype_eval.py --llm      # 正则 + LLM 层（需 ANTHROPIC_API_KEY）
"""

import argparse
import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from harness.stereotype_judge import detect_stereotypes  # noqa: E402

CASES_PATH = os.path.join(os.path.dirname(__file__), "stereotype_eval_cases.yaml")


def evaluate(use_llm: bool) -> dict:
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = yaml.safe_load(f)["cases"]

    tp = fp = tn = fn = 0
    errors = []
    for case in cases:
        result = detect_stereotypes([case["text"]], use_llm=use_llm)
        predicted_violation = len(result["violations"]) > 0
        actual_violation = case["label"] == "violation"
        if predicted_violation and actual_violation:
            tp += 1
        elif predicted_violation and not actual_violation:
            fp += 1
            errors.append(("误报", case["text"]))
        elif not predicted_violation and not actual_violation:
            tn += 1
        else:
            fn += 1
            errors.append(("漏报", case["text"]))

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {
        "total": total,
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="刻板印象检测评测")
    parser.add_argument("--llm", action="store_true", help="启用 LLM 复审层")
    args = parser.parse_args()

    if args.llm and not os.environ.get("ANTHROPIC_API_KEY"):
        print("错误：--llm 需要设置 ANTHROPIC_API_KEY")
        sys.exit(1)

    method = "regex+llm" if args.llm else "regex"
    print(f"评测方法: {method}")
    r = evaluate(use_llm=args.llm)
    print(f"用例数: {r['total']}")
    print(f"准确率: {r['accuracy']:.1%}  精确率: {r['precision']:.1%}  召回率: {r['recall']:.1%}")
    print(f"TP={r['tp']} FP={r['fp']} TN={r['tn']} FN={r['fn']}")
    if r["errors"]:
        print("\n错误样本:")
        for kind, text in r["errors"]:
            print(f"  [{kind}] {text[:60]}")


if __name__ == "__main__":
    main()
