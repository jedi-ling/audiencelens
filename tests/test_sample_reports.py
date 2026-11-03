"""examples/reports/ 下的样例报告，以及 /samples 页用的静态副本。

样例是真实引擎运行的原始产物（不手工修改），这里守的是三件事：
  · 文件齐全、meta.json 字段齐全（模型、成本、token、提交号都要能追溯）；
  · 没有夹带 API key、本机路径或邮箱；
  · web/frontend/public/sample-reports/ 的副本与源头一致（scripts/sync_sample_reports.py）。
"""

import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "examples", "reports")
SLUGS = sorted(
    d for d in os.listdir(REPORTS) if os.path.isfile(os.path.join(REPORTS, d, "meta.json"))
) if os.path.isdir(REPORTS) else []
META_KEYS = {
    "input_file", "task_type", "persona_pack", "depth", "model_id", "date",
    "cost_usd", "tokens_in", "tokens_out", "app_commit", "retries",
}
FORBIDDEN = [
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),
    re.compile(r"/home/[a-z]"),
    re.compile(r"[A-Za-z]:\\\\?Users\\\\?"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.(?:com|cn|net|org|io|top)\b"),
]


def test_there_are_sample_reports():
    assert len(SLUGS) >= 3, SLUGS


@pytest.mark.parametrize("slug", SLUGS)
def test_sample_is_complete(slug):
    folder = os.path.join(REPORTS, slug)
    for name in ("report.html", "report.json", "report.md", "meta.json"):
        assert os.path.getsize(os.path.join(folder, name)) > 0, name
    with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    assert META_KEYS <= set(meta), META_KEYS - set(meta)
    assert os.path.isfile(os.path.join(ROOT, meta["input_file"])), "输入材料必须在仓库里，能复现"
    with open(os.path.join(folder, "report.json"), encoding="utf-8") as f:
        report = json.load(f)
    assert (report.get("meta") or {}).get("is_synthetic") is True
    assert report["meta"]["task_type"] == meta["task_type"]
    with open(os.path.join(folder, "report.html"), encoding="utf-8") as f:
        assert f.read().rstrip().endswith("</html>"), "HTML 报告被截断了"


@pytest.mark.parametrize("slug", SLUGS)
def test_sample_has_no_secrets_paths_or_emails(slug):
    folder = os.path.join(REPORTS, slug)
    for name in os.listdir(folder):
        with open(os.path.join(folder, name), encoding="utf-8") as f:
            text = f.read()
        for pattern in FORBIDDEN:
            assert not pattern.search(text), f"{slug}/{name} 命中 {pattern.pattern}"


def test_frontend_copies_are_in_sync():
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "sync_sample_reports.py"), "--check"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_evaluation_runs_are_not_listed_as_samples():
    """docs/evaluation/runs/ 是评估证据（含修复前的失败运行），不能出现在 /samples。"""
    with open(os.path.join(ROOT, "web", "frontend", "public", "sample-reports", "index.json"), encoding="utf-8") as f:
        listed = {item["slug"] for item in json.load(f)}
    assert listed == set(SLUGS)
    assert not any("before-fix" in s for s in listed)
