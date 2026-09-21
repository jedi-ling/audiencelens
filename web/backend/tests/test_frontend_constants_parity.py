# -*- coding: utf-8 -*-
"""前端 mock-data.ts 里几份「看起来像事实源」的常量的一致性卡口。

和 test_task_type_parity.py 同一个思路：这些漂移**不会报错**，接口照 200、页面照渲染，
坏的只是用户看到的东西是假的。所以这里不测功能，只测「前端说的和后端说的是不是同一件事」。

放在后端 pytest 而不是前端：web/frontend 目前没有测试运行器（package.json 里只有
dev/build/typecheck/lint），为一个常量卡口引入 vitest 不值当；而这几条断言本质上是
「前端文件 vs 后端 Python 常量」的比对，跑在这边反而拿得到后端那一侧的真值。

覆盖三条曾经真实发生过的漂移：
  1. EVALUATION_DIMENSIONS 的 id 与 evaluation_service.RUBRIC_DIMENSIONS 完全不同名，
     导致 find(d => d.id === r.dimension) 永远 undefined，中文界面里直出
     persona_differentiation，维度说明整行空白。
  2. TASK_MATERIALS 漏了 4 个任务类型，第 2 步「上传材料」是空页却能放行，
     用户只填一个标题就能发起评审。
  3. SKILLS[].task_types 是手写枚举，凭空造出一条后端并不存在的「技能只支持某几种
     任务类型」约束，把用户要选的类型从界面上藏掉。
"""

import os
import re

import pytest

from app.services.evaluation_service import RUBRIC_DIMENSIONS

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MOCK_DATA = os.path.join(REPO_ROOT, "web", "frontend", "src", "lib", "mock-data.ts")


@pytest.fixture(scope="module")
def source() -> str:
    with open(MOCK_DATA, "r", encoding="utf-8") as f:
        return f.read()


def _block(source: str, header: str) -> str:
    """截取 `export const X ... = [` 到行首 `]` 之间的正文。
    找不到就直接失败：常量被改名/删除时，这个卡口必须红，而不是解析出空串然后全绿。"""
    start = source.index(header)
    end = source.index("\n]", start)
    return source[start:end]


def test_evaluation_dimensions_ids_match_backend_rubric(source: str) -> None:
    block = _block(source, "export const EVALUATION_DIMENSIONS")
    ids = re.findall(r"\{ id: '([a-z_]+)'", block)
    assert ids, "没解析出任何维度，说明这份常量的写法变了，卡口先失效了"
    # 用列表比而不是集合：前端按数组顺序渲染雷达图的轴，顺序也是展示的一部分
    assert ids == list(RUBRIC_DIMENSIONS), (
        f"前端评估维度 id 与后端 RUBRIC_DIMENSIONS 不一致：前端 {ids}，后端 {list(RUBRIC_DIMENSIONS)}"
    )


def test_every_task_type_has_material_fields(source: str) -> None:
    task_ids = re.findall(
        r"\{ id: '([a-z_]+)',", _block(source, "export const TASK_TYPES")
    )
    assert len(task_ids) >= 14, f"任务类型只解析出 {len(task_ids)} 条，解析规则已失效"

    materials_block = _block(source, "export const TASK_MATERIALS")
    # 只认「行首两个空格 + key:」这种顶层键，避免把字段对象里的 key 也算进来
    material_keys = re.findall(r"^  ([a-z_]+): \[", materials_block, re.M)
    missing = [t for t in task_ids if t not in material_keys]
    assert not missing, (
        f"这些任务类型没有材料字段定义，创建流程第 2 步会是空页却能放行：{missing}"
    )


def test_skill_task_types_are_not_a_handwritten_whitelist(source: str) -> None:
    """后端对「技能 × 任务类型」没有任何约束（apply_skill_hint 只插提示语，创建接口不校验），
    所以前端这份映射一旦写成手写枚举，就是一条编出来的约束在裁用户的选项。"""
    block = _block(source, "export const SKILLS")
    values = re.findall(r"^    task_types: (.+),$", block, re.M)
    assert values, "没解析出 task_types，SKILLS 的写法变了"
    hardcoded = [v for v in values if v != "ALL_TASK_TYPE_IDS"]
    assert not hardcoded, (
        f"SKILLS[].task_types 又被写成了手写枚举：{hardcoded}。"
        "真值应来自 GET /api/skills/{skill_type}；离线兜底只能是全量任务类型。"
    )


def test_no_hardcoded_persona_counts(source: str) -> None:
    """PERSONA_PACKS 的 persona_count 曾是一组和 src/personas/*.yaml 对不上的写死数字。
    删掉之后，防的是下一个人把它加回来当「N 个角色」展示。"""
    # 只禁字面量赋值。`persona_count: number` 是接口类型声明，描述的是后端真会返回这个
    # 字段，必须留着；被禁的是 `persona_count: 19` 这种前端自己填的数。
    assert not re.search(r"persona_count:\s*\d", source), (
        "mock-data.ts 里又出现了写死的 persona_count；角色数只能来自 /api/personas/packs"
    )


def test_review_mode_boundaries_match_engine_config(source: str) -> None:
    """报告页的档位边界声明从 REVIEW_MODE_BOUNDARIES 取数字（人数上限、含不含
    质询/校准）。事实源是引擎 src/runner/cli.py 的 REVIEW_MODE_CONFIG——
    引擎调档位（比如 full 从 8 人调到 10 人）而前端常量没跟上时，边界声明
    就会对用户说谎，而页面照常渲染不报任何错。"""
    block = _block(source, "export const REVIEW_MODE_BOUNDARIES")
    fe = {
        m.group(1): {
            "max_personas": int(m.group(2)),
            "cross_examination": m.group(3) == "true",
            "calibration": m.group(4) == "true",
        }
        for m in re.finditer(
            r"\{ id: '(\w+)', max_personas: (\d+), cross_examination: (true|false), calibration: (true|false) \}",
            block,
        )
    }
    assert fe, "没解析出任何档位，说明这份常量的写法变了，卡口先失效了"

    cli_path = os.path.join(REPO_ROOT, "src", "runner", "cli.py")
    with open(cli_path, "r", encoding="utf-8") as f:
        cli_src = f.read()
    cfg_start = cli_src.index("REVIEW_MODE_CONFIG = {")
    cfg_block = cli_src[cfg_start : cli_src.index(chr(10) + "}", cfg_start) + 2]
    be = {
        m.group(1): {
            "max_personas": int(m.group(2)),
            "cross_examination": m.group(3) == "True",
            "calibration": m.group(4) == "True",
        }
        for m in re.finditer(
            r'"(\w+)": \{"max_personas": (\d+), "cross_examination": (True|False), "calibration": (True|False)\}',
            cfg_block,
        )
    }
    assert be, "没从 cli.py 解析出 REVIEW_MODE_CONFIG，引擎侧写法变了，卡口先失效了"
    assert fe == be, f"前端档位边界与引擎配置不一致：前端 {fe}，引擎 {be}"


def test_review_switches_reach_the_backend_from_the_ui() -> None:
    """UI 上的评审开关必须一路传到后端 schema —— 断在中间是**静默**的。

    这个仓库真实踩过两次：enable_evaluation 与 enable_red_team 都曾经从 UI
    传出去、被后端 schema 静默丢弃，用户以为开了实际没开，且没有任何回执。
    wide_screen（两层评审）是第三个走同一条链路的开关，加它时链路有四段：

        CreateReviewPage 的 state → review-store 的 payload 透传
        → 后端 CreateReviewRequest schema → Review 模型列

    任何一段漏掉，功能都"看起来接上了"但不生效。只声明类型而不写透传是最
    容易漏的一段（类型对了、tsc 绿了、值没传）。
    """
    import os

    switches = ("enable_evaluation", "enable_red_team", "wide_screen", "adaptive_panel")

    store = os.path.join(REPO_ROOT, "web", "frontend", "src", "store", "review-store.ts")
    with open(store, "r", encoding="utf-8") as f:
        store_src = f.read()

    from app.api.platform import CreateReviewRequest
    from app.models import Review

    backend_fields = set(CreateReviewRequest.model_fields)
    review_columns = {c.name for c in Review.__table__.columns}

    for sw in switches:
        # 透传：payload 里必须真的有 `sw: ...` 这一行，不能只在类型声明里出现
        assert f"{sw}: data.{sw}" in store_src, (
            f"review-store 只声明了 {sw} 的类型却没往 payload 里写——"
            "这正是「传了但被丢弃」的形状，tsc 不会报错"
        )
        assert sw in backend_fields, f"后端 CreateReviewRequest 缺 {sw}，请求体会被静默丢弃"
        assert sw in review_columns, f"Review 模型缺 {sw} 列，开关不会落库，事后查不到这次开没开"


def test_mode_cost_cross_exam_calls_match_engine():
    """ModeCostCompare 里的 CROSS_EXAM_CALLS 硬编码了"各档交叉质询发几次调用"，
    事实源是引擎两处：
      · src/runner/cli.py 的 CROSS_EXAM_MODE_BY_REVIEW_MODE（哪档走哪种质询）
      · src/runner/cross_exam.py 的分支（moderated=1 次；multi_agent=每争议点每方各 1 次）

    这个数字直接画进了用户选档位时看的开销对比图。引擎把 standard 从仲裁式
    改成多智能体（或反过来）而前端没跟上时，那张图就会对用户少报/多报开销，
    而页面照常渲染、不报任何错——与 REVIEW_MODE_BOUNDARIES 是同一类失效。
    """
    comp = os.path.join(REPO_ROOT, "web", "frontend", "src", "components", "ModeCostCompare.tsx")
    with open(comp, "r", encoding="utf-8") as f:
        fe_src = f.read()
    # _block 是为数组（以行首 ] 收尾）写的，这两个常量都是对象，就地取块
    def _obj_block(src: str, header: str) -> str:
        start = src.index(header)
        return src[start:src.index(chr(10) + "}", start)]

    block = _obj_block(fe_src, "const CROSS_EXAM_CALLS")
    fe = {}
    for m in re.finditer(r"(\w+):\s*(\d+|null)", block):
        fe[m.group(1)] = None if m.group(2) == "null" else int(m.group(2))
    assert fe, "没解析出 CROSS_EXAM_CALLS，前端写法变了，卡口先失效了"

    cli_path = os.path.join(REPO_ROOT, "src", "runner", "cli.py")
    with open(cli_path, "r", encoding="utf-8") as f:
        cli_src = f.read()
    ce_block = _obj_block(cli_src, "CROSS_EXAM_MODE_BY_REVIEW_MODE")
    engine_modes = {
        m.group(1): m.group(2)
        for m in re.finditer(r'"(\w+)":\s*(MODE_\w+)', ce_block)
    }
    assert engine_modes, "没从 cli.py 解析出 CROSS_EXAM_MODE_BY_REVIEW_MODE"

    # quick 不在那张表里 = 该档不跑质询，前端必须记 0
    assert fe.get("quick") == 0, "quick 档不跑交叉质询，前端却记了非 0 次调用"

    for mode, engine_mode in engine_modes.items():
        if engine_mode == "MODE_MODERATED":
            assert fe.get(mode) == 1, (
                f"引擎 {mode} 档走仲裁式质询（总共 1 次调用），前端记的是 {fe.get(mode)}"
            )
        elif engine_mode == "MODE_MULTI_AGENT":
            assert fe.get(mode) is None, (
                f"引擎 {mode} 档走多智能体反驳（次数随分歧数变化，事前不可确定），"
                f"前端不该记成固定的 {fe.get(mode)} 次——那是给用户一个假的确定数字"
            )
