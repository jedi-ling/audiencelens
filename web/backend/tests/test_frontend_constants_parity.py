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
