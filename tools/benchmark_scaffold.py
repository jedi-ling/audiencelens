"""为真实试点创建一致、隔离且不覆盖已有数据的基准案例目录。"""

import json
import re
from pathlib import Path


METHOD_FILES = {
    "audiencelens": "audiencelens.json",
    "single_prompt": "single-prompt.json",
    "expert_quick": "expert-quick.json",
}


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_case(root: str, case_id: str, title: str = "") -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}", case_id):
        raise ValueError("case-id 只能包含 2-64 位字母、数字、下划线和连字符")
    root_path = Path(root).resolve()
    case_dir = root_path / case_id
    if case_dir.exists():
        raise FileExistsError(f"案例目录已存在，拒绝覆盖: {case_dir}")
    root_path.mkdir(parents=True, exist_ok=True)
    case_dir.mkdir()

    reference = {
        "case_id": case_id,
        "title": title,
        "collected_after_candidates_frozen": False,
        "reviewers": [],
    }
    candidate = {
        "case_id": case_id,
        "benchmark_meta": {
            "model": "",
            "prompt_version": "",
            "cost_usd": None,
            "duration_minutes": None,
            "generated_at": None,
        },
        "reviews": [],
    }
    _write_json(case_dir / "reference.json", reference)
    for filename in METHOD_FILES.values():
        _write_json(case_dir / filename, candidate)
    (case_dir / "README.md").write_text(
        f"# {case_id}: {title or '未命名试点'}\n\n"
        "1. 冻结输入材料。\n2. 独立生成三个候选文件。\n"
        "3. 候选封存后才收集 reference.json；完成后将 collected_after_candidates_frozen 改为 true。\n"
        "4. 禁止把 reference.json 内容提供给任何候选方法。\n",
        encoding="utf-8",
    )

    manifest_path = root_path / "benchmark-suite.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "name": "steam-page-validation-v1",
            "target_method": "audiencelens",
            "baseline_method": "single_prompt",
            "cases": [],
        }
    if any(str(item.get("id")) == case_id for item in manifest.get("cases", [])):
        raise ValueError(f"manifest 已包含案例 {case_id}")
    manifest.setdefault("cases", []).append({
        "id": case_id,
        "reference": f"{case_id}/reference.json",
        "candidates": {name: f"{case_id}/{filename}" for name, filename in METHOD_FILES.items()},
    })
    _write_json(manifest_path, manifest)
    return {"case_dir": str(case_dir), "manifest": str(manifest_path), "case_id": case_id}
