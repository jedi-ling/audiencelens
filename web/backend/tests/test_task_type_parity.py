# -*- coding: utf-8 -*-
"""任务类型四份定义的一致性卡口。

同一份事实在这个项目里存了四处：
  1. web/backend/app/services  TASK_TYPES          —— 后端注册表（唯一准绳）
  2. src/runner/task_types.py  VALID_TASK_TYPES    —— 引擎认不认这个类型
  3. src/runner/persona_agent  TASK_STANCE_ENUM    —— 引擎注入提示词的立场词表
  4. web/frontend/src/lib/mock-data.ts TASK_TYPES  —— 界面展示的卡片

第 4 份漂过一次：4 个「通用产品」类型的立场与维度是前端自造的
（「有价值/价值有限」「会购买」「顺利上手」「值得投入」）。这类漂移**不会报错**——
前端只把 task_type 的 id 发给后端，引擎用自己那份词表，评审照跑、接口照 200。
坏的是界面在向用户承诺一套它不会兑现的东西：选「会不会买」，报告里写的是「会付费」；
报告页按维度渲染时整列对不上。

立场词尤其不能差一个字：聚合器拿它当立场聚类的 dict 键，自造说法会让
共识度/分歧点统计静默变成垃圾——数字照出，全是错的。

所以这里不测「功能能不能跑」，只测「四处说的是不是同一件事」。
"""

import os
import re

import pytest

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
MOCK_DATA = os.path.join(
    REPO_ROOT, "web", "frontend", "src", "lib", "mock-data.ts"
)

# 逐条解析前端那张表。用正则而不是上 TS 解析器：这份数据是一行一条的字面量，
# 结构稳定；真正的风险不是解析不准，而是**解析器悄悄匹配到 0 条却仍然通过**——
# 那样这个卡口会变成一个永远绿的摆设。所以下面有一条专门断言"确实解析出了东西"。
ENTRY_RE = re.compile(
    r"\{ id: '(?P<id>[a-z_]+)', name: '(?P<name>[^']+)'.*?"
    r"stance_enum: \[(?P<stance>[^\]]*)\], "
    r"score_dimensions: \[(?P<dims>[^\]]*)\]"
)


def _parse_frontend():
    out = {}
    with open(MOCK_DATA, encoding="utf-8") as f:
        for line in f:
            m = ENTRY_RE.search(line)
            if not m:
                continue
            split = lambda s: [x.strip().strip("'") for x in s.split(",") if x.strip()]
            out[m.group("id")] = {
                "name": m.group("name"),
                "stance": split(m.group("stance")),
                "dims": split(m.group("dims")),
            }
    return out


@pytest.fixture(scope="module")
def frontend():
    return _parse_frontend()


@pytest.fixture(scope="module")
def backend():
    from app.services import TASK_TYPES

    return TASK_TYPES


class TestFrontendMatchesBackend:
    def test_parser_actually_found_entries(self, frontend):
        """先证明解析器没白跑。

        缺了这条，只要 mock-data.ts 改个格式让正则匹配不上，下面所有比对都会在
        空集合上通过——一个永远绿的卡口比没有卡口更危险，它会让人以为查过了。
        """
        assert len(frontend) >= 10, f"只从 mock-data.ts 解析出 {len(frontend)} 条，正则多半失配了"

    def test_same_id_set(self, frontend, backend):
        assert set(frontend) == set(backend), (
            f"前端多出: {set(frontend) - set(backend)}；"
            f"后端多出（界面里选不到）: {set(backend) - set(frontend)}"
        )

    def test_stance_words_identical(self, frontend, backend):
        """立场词必须逐字一致，顺序也算。

        顺序也管是因为界面按顺序渲染标签，第一个通常被读成"正面选项"。
        """
        bad = {
            t: (frontend[t]["stance"], list(backend[t]["stance_enum"]))
            for t in frontend
            if frontend[t]["stance"] != list(backend[t]["stance_enum"])
        }
        assert not bad, f"立场词不一致（前端, 后端）: {bad}"

    def test_dimensions_identical(self, frontend, backend):
        bad = {
            t: (frontend[t]["dims"], list(backend[t]["score_dimensions"]))
            for t in frontend
            if frontend[t]["dims"] != list(backend[t]["score_dimensions"])
        }
        assert not bad, f"评分维度不一致（前端, 后端）: {bad}"


class TestEngineMatchesBackend:
    """引擎那两份也一起钉住——它们此前对齐过，但没有任何东西拦着它们再漂开。"""

    def test_engine_accepts_every_task_type(self, backend):
        import sys

        src = os.path.join(REPO_ROOT, "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from runner.task_types import VALID_TASK_TYPES

        missing = set(backend) - set(VALID_TASK_TYPES)
        assert not missing, f"界面能选但引擎不认（用户一点就 ValueError）: {missing}"

    def test_engine_stance_enum_identical(self, backend):
        import sys

        src = os.path.join(REPO_ROOT, "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from runner.persona_agent import TASK_STANCE_ENUM

        bad = {
            t: (list(TASK_STANCE_ENUM.get(t, [])), list(backend[t]["stance_enum"]))
            for t in backend
            if list(TASK_STANCE_ENUM.get(t, [])) != list(backend[t]["stance_enum"])
        }
        assert not bad, f"引擎立场词表与后端不一致（引擎, 后端）: {bad}"

    def test_every_task_type_has_preset(self, backend):
        """没有 preset 的类型选不出评审团。"""
        import yaml

        from app.services import PRESETS_PATH

        with open(PRESETS_PATH, encoding="utf-8") as f:
            presets = (yaml.safe_load(f) or {}).get("presets", {})
        missing = set(backend) - set(presets)
        assert not missing, f"缺 panel preset（选不出人格）: {missing}"
