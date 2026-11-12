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
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from runner.task_types import default_pack_for_task_type  # noqa: E402

REPORTS = os.path.join(ROOT, "examples", "reports")
SLUGS = sorted(
    d for d in os.listdir(REPORTS) if os.path.isfile(os.path.join(REPORTS, d, "meta.json"))
) if os.path.isdir(REPORTS) else []
META_KEYS = {
    "input_file", "task_type", "persona_pack", "depth", "model_id", "date",
    "cost_usd", "tokens_in", "tokens_out", "app_commit", "retries",
    "cross_exam_run", "dedup_method", "disputes",
    # 证据 schema 版本、生成时的核对规则、以及离线复核出来的落地数
    "evidence_schema", "grounding_rule", "grounding",
}
# 一份样例要么是一次跑完的（记 run_id），要么是"人格评审一次 + 交叉质询续跑一次"
# （runner.cli.run_panel_from_outputs，记 persona_outputs_from）。出处必须写清是哪一种。
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
    for name in ("report.html", "report.json", "report.md", "meta.json", "persona_outputs.json"):
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

    # meta 里的数字必须和报告本身对得上，不能是手填的
    cross = report.get("cross_examination") or {}
    assert meta["disputes"] == len(cross.get("disputes") or [])
    assert meta["dedup_method"] == (report.get("dedup") or {}).get("method")
    if "persona_outputs_from" in meta:
        assert meta["cost_usd"] == pytest.approx(
            meta["persona_outputs_from"]["cost_usd"] + meta["cross_exam_run"]["cost_usd"], abs=1e-4
        )
        assert meta["cross_exam_run"]["method"] == "runner.cli.run_panel_from_outputs"
    else:
        assert meta.get("run_id"), "单次运行的样例必须记 run_id"
        assert 0 < meta["cross_exam_run"]["cost_usd"] < meta["cost_usd"]
    assert meta["persona_pack"] == default_pack_for_task_type(meta["task_type"]), (
        "样例用的人格包必须是该任务类型登记的默认包（用错包的运行放 docs/evaluation/runs/）"
    )
    with open(os.path.join(ROOT, "src", "personas", f"{meta['persona_pack']}.yaml"), encoding="utf-8") as f:
        pack_ids = {p["id"] for p in yaml.safe_load(f)["personas"]}
    with open(os.path.join(folder, "persona_outputs.json"), encoding="utf-8") as f:
        persona_file = json.load(f)
    ran = {o["persona_id"] for o in persona_file["validated"]} | {x["persona_id"] for x in persona_file["failed"]}
    assert ran and ran <= pack_ids, ran - pack_ids
    with open(os.path.join(folder, "persona_outputs.json"), encoding="utf-8") as f:
        persona_file = json.load(f)
    assert persona_file["validated"], "续跑的输入必须随仓库提交，才能复现"
    assert all("persona_id" in o for o in persona_file["validated"])
    assert all(set(f) <= {"persona_id", "failure_reason"} for f in persona_file["failed"]), (
        "没通过校验的人格只记 id 和结论，不提交原文"
    )


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


def test_sample_grounding_numbers_match_the_offline_recheck():
    """meta.json 里的落地数（README 表格引用的就是它）必须是脚本算出来的，不是手填的。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import revalidate_samples

    result = revalidate_samples.current_samples()
    assert set(result) == set(SLUGS)
    for slug, r in result.items():
        with open(os.path.join(REPORTS, slug, "meta.json"), encoding="utf-8") as f:
            note = json.load(f)["grounding"]
        with open(os.path.join(REPORTS, slug, "report.json"), encoding="utf-8") as f:
            report = json.load(f)
        for key in ("personas_passed", "personas_attempted", "direct_entries", "inferred_entries",
                    "gap_entries", "direct_entries_with_quote", "direct_entries_grounded"):
            assert note[key] == r[key], (slug, key)
        assert note["personas_passed"] == report["degradation"]["succeeded_count"]
        assert note["personas_attempted"] == report["degradation"]["attempted_count"]
        # 发布的样例：每条 direct 证据都带 quote，且 quote 过得了当前规则
        assert r["direct_entries"] == r["direct_entries_with_quote"] == r["direct_entries_grounded"] > 0


def test_archived_pre_quote_samples_keep_their_recorded_recheck():
    """2026-11-04 的旧样例已移到 docs/evaluation/runs/ 当证据；它们 meta 里那段
    "旧规则下生成、覆盖率规则下复核"的数字仍须和脚本一致。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import revalidate_samples

    archived = os.path.join(ROOT, revalidate_samples.ARCHIVED_DIR)
    result = revalidate_samples.revalidate()
    assert set(result) == set(SLUGS)
    for slug, r in result.items():
        with open(os.path.join(archived, slug, "meta.json"), encoding="utf-8") as f:
            note = json.load(f)["grounding_revalidation"]
        assert note["rule_at_generation"] == "any-fragment"
        assert note["personas_passing_rule_at_generation"] == r["pass_before"] == r["personas_in_report"]
        assert note["personas_passing_coverage_rule"] == r["pass_after"]
        assert note["direct_entries"] == r["direct_entries"]
        assert note["direct_entries_grounded_rule_at_generation"] == r["grounded_before"]
        assert note["direct_entries_grounded_coverage_rule"] == r["grounded_after"]


def _outside_style(html: str) -> str:
    assert html.count("<style>") == 1 and html.count("</style>") == 1
    a = html.index("<style>")
    b = html.index("</style>") + len("</style>")
    return html[:a] + html[b:]


@pytest.mark.parametrize("slug", SLUGS)
def test_only_the_stylesheet_of_report_html_was_replaced(slug):
    """样例的 report.html 在生成之后只换过 <style> 块（模板的 CSS 花括号不配平，修了之后把
    修好的样式表换进去）。<style> 之外的一切必须和引擎生成的那份逐字节相同——
    meta.json 记着生成件 <style> 之外部分的哈希，这里重算比对。模型输出没有被动过。"""
    import hashlib

    folder = os.path.join(REPORTS, slug)
    with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
        note = json.load(f)["stylesheet_updated"]
    with open(os.path.join(folder, "report.html"), "rb") as f:
        raw = f.read()
    html = raw.decode("utf-8")
    assert hashlib.sha256(_outside_style(html).encode("utf-8")).hexdigest() == note["outside_style_sha256"]
    # 整份文件确实和生成件不同（换过样式表），而且换进去的样式表花括号是配平的
    assert hashlib.sha256(raw).hexdigest() != note["generated_html_sha256"]
    css = html[html.index("<style>"):html.index("</style>")]
    assert css.count("{") == css.count("}")
    assert note["template_fix_commit"] and note["reason"]
    # 前端那份拷贝必须是同一个文件
    with open(os.path.join(ROOT, "web", "frontend", "public", "sample-reports", slug, "report.html"), "rb") as f:
        assert f.read() == raw
