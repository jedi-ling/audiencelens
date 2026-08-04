# -*- coding: utf-8 -*-
"""对外材料里的数字必须等于仓库里数出来的数字。

为什么要有这个文件：这次的 bug 就是这么来的——往 `src/personas/` 加了一个包（launch-compliance）
和一个人格（P67），落地页、BP、中英文论文、视频物料里的「66 个人格 / 10 个 Pack」集体过期，
而**没有任何东西会提醒**。只把文字改成 72/11 治不了本：下次再加人格还会原样错一遍。

所以这里把口径反过来：真实数字从 `src/personas/` 与 `src/runner/task_types.py` 现算，
对外材料里的数字用正则捞出来逐个比对，对不上就红。落地页正文写着
「每一项都能在开源仓库里核对」——那这条核对就该是自动的。

五类检查，缺一不可：
  1. test_public_materials_counts_match_repo —— 材料里的数字 == 仓库现算出来的数字
  2. test_key_materials_still_state_the_counts —— 防"正则一条都没匹配上却全绿"（改写措辞就静默失效）
  3. test_landing_avatar_overflow_matches_persona_count —— 落地页头像行的「+N」这种**隐式**人格计数
  4. test_test_counts_are_stated_once_and_dated —— 测试数不许写死、不许同页两个值打架
  5. test_maintenance_env_table_is_complete —— MAINTENANCE.md 自称「全表」就得是全表

新增一份对外材料时不需要改这个文件：GLOB 会自动扫到。
新增一种数字写法（比如"共 72 名评审员"）时，需要往下面的 PATTERNS 里补一条正则——
补不补得上，看 2 类检查会不会因为该文件一条都没匹配到而失败。

为什么第 3 条要单独写一个测试：落地页头像行写的是 `+63`，意思是"另外还有 63 个人格"，
真实声称值是 3（画出来的头像）+ 63 = 66。它长得根本不像一个总数，任何"捞数字"的正则
都捞不到它，所以 72 人格上线后它一直错着没人发现。对付隐式计数只能是"按它的构成算回去"。
"""

import glob
import os
import re

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONA_DIR = os.path.join(REPO_ROOT, "src", "personas")
BACKEND_API_DIR = os.path.join(REPO_ROOT, "web", "backend", "app", "api")
BACKEND_SERVICES_DIR = os.path.join(REPO_ROOT, "web", "backend", "app", "services")
BACKEND_WS_INIT = os.path.join(REPO_ROOT, "web", "backend", "app", "websocket", "__init__.py")
FRONTEND_PAGES_DIR = os.path.join(REPO_ROOT, "web", "frontend", "src", "pages")
STEREOTYPE_CASES = os.path.join(REPO_ROOT, "tools", "stereotype_eval_cases.yaml")


# --------------------------------------------------------------------------
# 真实数字：现算，不写死
# --------------------------------------------------------------------------


def _load_packs():
    paths = sorted(glob.glob(os.path.join(PERSONA_DIR, "*.yaml")))
    assert paths, f"{PERSONA_DIR} 下一个人格包都没有，先确认路径对不对"
    packs = {}
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        pack_id = data.get("panel_id") or os.path.splitext(os.path.basename(path))[0]
        packs[pack_id] = [p["id"] for p in data["personas"]]
    return packs


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _count_route_handlers():
    """README 写的核对命令就是 `grep -c '^@router\\.' app/api/*.py`，这里用同一口径。"""
    if not os.path.isdir(BACKEND_API_DIR):
        return None
    total = 0
    for path in sorted(glob.glob(os.path.join(BACKEND_API_DIR, "*.py"))):
        total += len(re.findall(r"^@router\.", _read(path), re.M))
    return total


def _count_ws_events():
    """只认 `WS_EVENTS` 这张常量表——它同时是运行期真正发出的事件名白名单。"""
    if not os.path.isfile(BACKEND_WS_INIT):
        return None
    m = re.search(r"^WS_EVENTS\s*=\s*\((.*?)\)", _read(BACKEND_WS_INIT), re.S | re.M)
    assert m, "web/backend/app/websocket/__init__.py 里找不到 WS_EVENTS 元组，先确认它没被改名"
    return len(re.findall(r"[\"']([\w.]+)[\"']", m.group(1)))


def _count_page_components():
    """页面组件 = pages/ 下（含子目录）所有 .tsx。落地页 LandingPage.tsx 也算一个页面，
    所以对外只写"N 个页面组件（含落地页）"这一种口径——以前写"18 个页面 + 落地页"，
    到底算不算落地页永远说不清，两个数就永远对不上。"""
    if not os.path.isdir(FRONTEND_PAGES_DIR):
        return None
    return len(glob.glob(os.path.join(FRONTEND_PAGES_DIR, "**", "*.tsx"), recursive=True))


def _count_service_modules():
    """services/ 下除 __init__.py 外的所有 .py。

    注意口径：json_safe.py 是序列化工具而不是"业务服务"，但它确实是 services/ 下的一个模块。
    以前文档按"业务服务"数写 18、目录里实有 19，差的就是它——与其留一条"哪些不算"的
    人肉规则（下次加工具文件又会漂），不如把口径统一成"目录里的模块数"，现算即可。
    """
    if not os.path.isdir(BACKEND_SERVICES_DIR):
        return None
    return len([
        p for p in glob.glob(os.path.join(BACKEND_SERVICES_DIR, "*.py"))
        if os.path.basename(p) != "__init__.py"
    ])


def _count_stereotype_cases():
    if not os.path.isfile(STEREOTYPE_CASES):
        return None
    return len(yaml.safe_load(_read(STEREOTYPE_CASES))["cases"])


def repo_truth():
    """每个 metric 的真实值，全部现算。值为 None = 这份检出里没有对应源码，跳过该 metric。"""
    from runner.task_types import VALID_TASK_TYPES

    packs = _load_packs()
    persona_ids = [pid for ids in packs.values() for pid in ids]
    # 同一个 id 出现在两个包里 = 总数会被重复计，先卡死这条
    assert len(persona_ids) == len(set(persona_ids)), "人格 id 跨包重复，总数不可信"
    return {
        "persona": len(persona_ids),
        "pack": len(packs),
        "task_type": len(VALID_TASK_TYPES),
        "route": _count_route_handlers(),
        "ws_event": _count_ws_events(),
        "page": _count_page_components(),
        "service": _count_service_modules(),
        "stereotype_case": _count_stereotype_cases(),
    }


# --------------------------------------------------------------------------
# 待检材料 + 数字写法
# --------------------------------------------------------------------------

# archive/ 是已归档的历史 PDF 源，按发布当时的口径留档，不跟着现状走
EXCLUDED_DIR_PARTS = (os.sep + "archive" + os.sep,)

# 自带这句话的文档是"停在某个版本、明确标注请勿引用"的存档件，正文按当时口径保留。
# 它们顶部的勘误清单仍然会被扫到（见 _scannable_part 对"实际为"的处理），
# 所以"作废件的勘误也得写对"这条依然有保障。
DEPRECATED_MARKER = "本文件已作废"

MATERIAL_GLOBS = (
    "docs/**/*.md",
    "docs/**/*.html",
    "web/frontend/src/pages/landing/landing-body.html",
)

# 整份不参与现状核对的文件，每个都要写清为什么。
EXEMPT_FILES = {
    # 路线图按版本记「那一版当时交付了什么」，v0.1 那节的 50 人格 / 8 包是历史事实，
    # 改成今天的 72/11 反而是把历史记错。
    "docs/project/roadmap.md",
    # PDF 审计报告的**全部内容就是引用 PDF 里写错的数字**（"4 份 PDF 全部写
    # '66 个人格 / 10 个 YAML Pack'"）。引用错误值是它的职责所在，跟着仓库改
    # 反而会把这份证据毁掉——它就不再能证明 PDF 错在哪了。
    # 注意这跟 FROZEN_BODY_FILES 不是一回事：那些是"已发出的稿子正文冻结"，
    # 这份是"内容本身即错误值的引用"。
    "REMOVED/business-plan/pdf-audit-report.md",
}


def material_files():
    files = set()
    for pattern in MATERIAL_GLOBS:
        for path in glob.glob(os.path.join(REPO_ROOT, pattern), recursive=True):
            if any(part in path for part in EXCLUDED_DIR_PARTS):
                continue
            rel = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
            if rel in EXEMPT_FILES:
                continue
            files.add(path)
    return sorted(files)


def _scannable_part(line):
    """勘误行只看"实际为"后面那半句。

    这类行长这样：`**75 个人格 / 8 个 Pack** —— 实际为 **72 个人格 / 11 个 Pack**`。
    前半句是引用历史错误声称，本来就该保持原样；后半句才是现状，必须跟着仓库走。
    """
    idx = line.rfind("实际为")
    return line[idx:] if idx >= 0 else line


def rel_path(path):
    return os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")


# 正文冻结的文件：**已经发布出去的东西的稿子**。
#
# 为什么不按「有没有作废横幅」一刀切：带横幅的文件其实有两类，两类的正确做法相反。
#   · 视频脚本 —— 视频已经录完发出去了，片子里说的就是"75 个人格"。
#     正文必须冻结，改了反而和视频对不上；顶部勘误负责说明现状。
#   · BP / 说明类文档 —— 它们还会被人打开当作产品说明来读，
#     里面的数字错着就是在误导，正文该跟着仓库走。
# 以前一刀切豁免了全部带横幅的文件，结果 REMOVED-bp.html 的正文被改成
# 72 却不受检查，同一个文件里 171/287 行改对、222 行漏改，谁都不会发现。
# 所以改成显式白名单：加进来必须写清"这份东西已经以什么形式发出去了"。
FROZEN_BODY_FILES = frozenset(
    {
        "docs/video-promotion-campaign.md",  # 已录制视频的分镜脚本
        "docs/video-publishing-kit.md",  # 同上，发布物料脚本
    }
)


# 这些行里的数字不是"我们现在有多少"，扫进来只会逼着把正则放松到什么都拦不住。
# 每条都写清为什么豁免；加新条目前先想想能不能改措辞让它不再像总数声明。
EXEMPT_LINE_SUBSTRINGS = (
    # 讲的是历史缺陷（当时只注册了 6 个任务类型），不是现在的数量
    "`VALID_TASK_TYPES` 不一致",
    # 说的是 .claude/agents/ 下的 Markdown 镜像文件数，且原句明确写着
    # "只镜像了游戏池"——那是 72 个里的游戏向子集，与总数是两个口径。
    "只镜像了游戏池",
)


# 每条正则捕获一个"总数"声明。只收总数写法，不收 "51 游戏向"、"~20 persona"（竞品）、
# "v0.1 MVP（16 人格）"（里程碑）、"3–8 个人物"（面板规模）这类——它们各有各的口径。
PATTERNS = {
    "persona": [
        r"(\d+)\s*个\*{0,2}行为驱动",
        r"(\d+)\s*行为驱动\s*persona",
        r"(\d+)\s*个\s*AI\s*评审员",
        r"(\d+)个AI评审员",
        r"(\d+)\s*个互不通气",
        r"(\d+)\s*个由\s*12\s*轴",
        r"(\d+)\s*个人格中选",
        r"(\d+)\s*persona\s*[×x]",
        r"(\d+)\s*persona\s*定义",
        r"(\d+)\s*persona[（：]",
        r"共\s*(\d+)\s*个(?:行为驱动)?人物",
        r"(\d+)\s*个人物的数量",
        r"这\s*(\d+)\s*个人物是否",
        r"(\d+)\s+behavior-driven\s+personas",
        r"(\d+)\s+personas\s+across",
        r"the\s+(\d+)\s+personas\s+produce",
        r"(\d+)-persona\s+count",
        r"实际为\s*\*\*(\d+)\*\*",
        r"实际为\s*<?b?>?\*{0,2}(\d+)\s*个人格",
        r"实际为\s*\*{0,2}(\d+)\s*个人格",
        r"\|\s*Persona 数\s*\|\s*(\d+)（",
        r'<span class="val">(\d+)\s*\(\d+\s*游戏向',
        r'data-target="(\d+)">\d+</div><div class="lbl">行为驱动人格',
        # 论文 3.1 总表第 3 列 / 人格分类表第 2 列
        r"\|\s*\*\*(?:Total|合计)\*\*\s*\|\s*\*\*\d+\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*\d+\*\*",
        r"\|\s*\*\*(?:Total|合计)\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\|",
        # 「N 个 agent」这种写法。补这条是有具体来由的：
        # REMOVED-bp.html 同一个文件里，171 和 287 行的「72 个 agent」改对了，
        # 222 行的「66 个 agent」漏改 —— 同一处声称改了一半，正是本测试要治的病。
        # 而它当时逃掉，就是因为下面这两条正则不存在。
        r"(\d+)\s*个\s*agent",
        r"跑\s*(\d+)\s*个\s*agent",
    ],
    "pack": [
        r"(\d+)\s*个\s*(?:YAML\s*)?(?:人格\s*)?Pack",
        r"(\d+)\s*个\s*(?:YAML\s*)?人格包",
        r"(\d+)\s*个\s*YAML\s*包",
        r"YAML\s*(\d+)\s*Pack",
        r"across\s+(\d+)\s+(?:YAML\s+)?(?:packs|packages)",
        r"the\s+(\d+)\s+YAML\s+packs",
        r'data-target="(\d+)">\d+</div><div class="lbl">人格 Pack',
        r"\|\s*\*\*(?:Total|合计)\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*\d+\*\*",
    ],
    "task_type": [
        r"(\d+)\s*(?:种|类|个)\s*(?:评审)?任务类型",
        r"(\d+)\s*种场景",
        r"(\d+)\s*种\s*review\s+task\s+type",
        r"(\d+)\s*个任务\s*id",
        r"(\d+)\s+task\s+types",
        r'data-target="(\d+)">\d+</div><div class="lbl">任务类型',
        r"\|\s*\*\*(?:Total|合计)\*\*\s*\|\s*\*\*\d+\*\*\s*\|\s*\*\*\d+\*\*\s*\|\s*\*\*(\d+)\*\*",
    ],
}

# 哪些材料该声明哪些数字。这里列出来的文件，如果某个 metric 一条都匹配不到，
# 就说明措辞被改写、正则失效了 —— 那属于"检查悄悄停止工作"，必须让它红。
MUST_STATE = {
    "web/frontend/src/pages/landing/landing-body.html": ("persona", "pack", "task_type"),
    "docs/business-plan.md": ("persona", "pack"),
    "docs/paper/arxiv-paper.md": ("persona", "pack", "task_type"),
    "docs/paper/arxiv-paper-zh.md": ("persona", "pack", "task_type"),
    "REMOVED/benchmark-report.md": ("persona", "pack"),
    "REMOVED/business-plan/index.html": ("persona", "pack"),
}


def _scan(path, metric):
    """返回 [(行号, 数字, 原始行)]。"""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    deprecated = DEPRECATED_MARKER in text

    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if any(s in line for s in EXEMPT_LINE_SUBSTRINGS):
            continue
        chunk = _scannable_part(line)
        # 正文冻结只按 FROZEN_BODY_FILES 白名单来，不再按「有没有作废横幅」一刀切。
        # 理由见 FROZEN_BODY_FILES 的注释：作废件里其实有两种东西，
        # 一刀切必然把其中一种做错。
        if rel_path(path) in FROZEN_BODY_FILES and chunk is line:
            continue
        _ = deprecated  # 横幅本身仍由 test_deprecated_files_declare_errata 校验
        for pattern in PATTERNS[metric]:
            for m in re.finditer(pattern, chunk):
                hits.append((lineno, int(m.group(1)), line.strip()))
    return hits


@pytest.mark.parametrize("metric", sorted(PATTERNS))
def test_public_materials_counts_match_repo(metric):
    # repo_truth() 现在返回 {metric: 真实值} 的 dict（新增了路由/事件/页面/服务/标注集
    # 五个现算指标），不再是早先的 (personas, packs, task_types) 三元组。
    truth = repo_truth()
    expected = truth.get(metric)
    if expected is None:
        # 这份检出里没有对应源码（例如只 clone 了 docs），跳过而不是假装通过
        pytest.skip(f"仓库里没有可现算「{metric}」的源码，跳过")

    bad = []
    for path in material_files():
        rel = os.path.relpath(path, REPO_ROOT).replace(os.sep, "/")
        for lineno, value, line in _scan(path, metric):
            if value != expected:
                bad.append(f"  {rel}:{lineno} 写着 {value}，仓库真实是 {expected}\n    {line[:160]}")

    assert not bad, (
        f"对外材料里的「{metric}」数字与仓库现状不一致（真实值 {expected}）。\n"
        "这是加了人格/包/任务类型但没同步对外材料的典型症状——改材料，不要改这个断言。\n"
        + "\n".join(bad)
    )


@pytest.mark.parametrize("rel,metrics", sorted(MUST_STATE.items()))
def test_key_materials_still_state_the_counts(rel, metrics):
    """正则一条都没匹配上 = 检查已经悄悄失效，比数字写错更危险。"""
    path = os.path.join(REPO_ROOT, rel.replace("/", os.sep))
    assert os.path.isfile(path), f"{rel} 不存在；文件改名了就同步改 MUST_STATE"
    for metric in metrics:
        hits = _scan(path, metric)
        assert hits, (
            f"{rel} 里一条「{metric}」数字都没匹配到。\n"
            "要么这份材料不再声明这个数字（那就从 MUST_STATE 里去掉），"
            "要么换了种写法（那就往 PATTERNS 里补一条正则）——"
            "放着不管等于这份材料从此不再被核对。"
        )


# --------------------------------------------------------------------------
# MAINTENANCE.md 的「环境变量全表」得真的是全表
# --------------------------------------------------------------------------


def test_maintenance_env_table_is_complete():
    """漏项的代价不是"文档不全"，而是"照着全表配完，服务起不来"。

    历史上漏掉的正是 AL_ENCRYPTION_KEY 与整个邮件段——两处配不对就会被启动自检
    直接拒绝启动的开关。
    """
    config_path = os.path.join(REPO_ROOT, "web", "backend", "app", "config.py")
    doc_path = os.path.join(REPO_ROOT, "docs", "MAINTENANCE.md")
    with open(config_path, "r", encoding="utf-8") as f:
        config_src = f.read()
    with open(doc_path, "r", encoding="utf-8") as f:
        doc = f.read()

    names = sorted(set(re.findall(r"[\"']((?:AL_|ANTHROPIC_|AUDIENCELENS_)[A-Z0-9_]+)[\"']", config_src)))
    assert names, "没从 config.py 里解析出任何环境变量名，先确认正则还对得上文件"

    missing = [n for n in names if n not in doc]
    assert not missing, (
        "docs/MAINTENANCE.md §2 自称「环境变量全表」，但下列变量在 config.py 里读、文档里没有：\n"
        + "\n".join("  " + n for n in missing)
    )


# --------------------------------------------------------------------------
# CLI 的技能提示语与 Web 链路必须逐字一致
# --------------------------------------------------------------------------


def test_cli_skill_hints_match_backend():
    """同一个技能名在 CLI 与 Web 上必须跑出同一种评审口径。

    src/ 不能反向依赖 web/backend（引擎要能单独发包），所以提示语在两边各存一份；
    两份漂移的后果是"同一个 --skill 在两条链路上结果不同"，而且没人看得出来。
    web/backend 不在核心引擎的依赖里，装不上时跳过——但只跳过这一条，不影响上面的检查。
    """
    from src import cli as audiencelens_cli

    backend_app = os.path.join(REPO_ROOT, "web", "backend")
    if not os.path.isdir(backend_app):
        pytest.skip("web/backend 不在这个检出里")

    import sys

    # 把 web/backend 塞进 sys.path 会引入一个顶层 `app` 包，可能盖住别的测试的导入，
    # 所以用完就撤干净——只为读一张常量表，不该改变整个会话的导入环境。
    added = backend_app not in sys.path
    if added:
        sys.path.insert(0, backend_app)
    before = set(sys.modules)
    try:
        try:
            from app.services import PersonaService
        except Exception as exc:  # 缺 fastapi/sqlalchemy 等后端依赖时
            pytest.skip(f"后端依赖不可用，跳过跨链路一致性检查：{type(exc).__name__}: {exc}")

        for cli_skill, hint in audiencelens_cli.SKILL_PROMPT_HINTS.items():
            backend_skill = cli_skill.replace("-", "_")
            assert PersonaService.get_skill_prompt_hint(backend_skill) == hint, (
                f"技能 {cli_skill} 的提示语在 CLI（src/cli.py）与 Web"
                f"（web/backend/app/services/__init__.py）两处不一致——同一个技能会跑出两种评审。"
            )
    finally:
        if added and backend_app in sys.path:
            sys.path.remove(backend_app)
        for name in set(sys.modules) - before:
            if name == "app" or name.startswith("app."):
                sys.modules.pop(name, None)


def test_cli_skill_hint_is_actually_injected():
    """--skill 不能是"收下就丢"：提示语必须真的进到人格看得见的材料里。"""
    from src import cli as audiencelens_cli

    bundle = {"title": "x", "materials": [{"type": "text", "text": "原始材料"}]}
    out = audiencelens_cli.apply_skill_hint(bundle, "red-team-audience")
    assert out["materials"][0]["text"].startswith("[评审技能：red-team-audience]")
    assert out["materials"][-1]["text"] == "原始材料"
    # 原 bundle 不被就地改写：调用方可能还要拿它做别的事
    assert len(bundle["materials"]) == 1

    # 没有提示语的技能原样返回，不能凭空插一条空材料
    assert audiencelens_cli.apply_skill_hint(bundle, "synthetic-playtest") is bundle


def test_cli_run_passes_skill_hint_down_to_run_panel(tmp_path, monkeypatch):
    """真正要守的是命令层：--skill 必须一路走到 run_panel 收到的 bundle 里。

    只测 apply_skill_hint 不够——它以前也"存在"，问题恰恰是 run() 根本没调它。
    """
    from click.testing import CliRunner

    from src import cli as audiencelens_cli

    import json as _json

    artifact = tmp_path / "artifact.json"
    artifact.write_text(
        _json.dumps({"title": "测试材料", "materials": [{"type": "text", "text": "待评审材料"}]},
                    ensure_ascii=False),
        encoding="utf-8",
    )

    captured = {}

    def fake_run_panel(**kwargs):
        captured.update(kwargs)
        return {"report": {}, "markdown": "", "html": ""}

    monkeypatch.setattr(audiencelens_cli.runner_cli, "run_panel", fake_run_panel)

    result = CliRunner().invoke(
        audiencelens_cli.main,
        ["run", "red-team-audience", "concept_review", str(artifact),
         "--output-dir", str(tmp_path / "out")],
    )
    assert result.exit_code == 0, result.output

    texts = [m.get("text", "") for m in captured["artifact_bundle"]["materials"]]
    assert any(t.startswith("[评审技能：red-team-audience]") for t in texts), (
        f"--skill 没有进到 run_panel 的材料里：{texts}"
    )
