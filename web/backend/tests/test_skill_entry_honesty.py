# -*- coding: utf-8 -*-
"""创建评审入口（SkillSelectPage / CreateReviewPage）的诚实性卡口。

和 test_frontend_constants_parity.py 同一个思路：这里的漂移都**不会报错**——
接口照 200、页面照渲染、构建照过，坏的只是用户看到的东西是假的，或者点了不起作用。
所以这些断言全部写成「即使有人改回硬编码/改回假入口也会红」的形式。

跑在后端 pytest 而不是前端：web/frontend 没有测试运行器（package.json 只有
dev/build/typecheck/lint），而这几条里最关键的一条（哪个技能真的会改变评审行为）
的真值就在后端 Python 常量里，跑在这边才拿得到。
"""

import os
import re

import pytest

from app.services import PersonaService
from app.models import SkillType

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PAGES = os.path.join(REPO_ROOT, "web", "frontend", "src", "pages")
SKILL_SELECT = os.path.join(PAGES, "SkillSelectPage.tsx")
CREATE_REVIEW = os.path.join(PAGES, "CreateReviewPage.tsx")
# 两页共用的技能加载逻辑（以 /api/skills 为事实源）住在这里
SKILLS_LIB = os.path.join(REPO_ROOT, "web", "frontend", "src", "lib", "skills.ts")


def _strip_comments(source: str) -> str:
    """去掉 /* */ 与 // 注释。断言「页面上不该再出现某个东西」时必须先去注释，
    否则解释「这里为什么删掉它」的注释本身会让断言红——那会逼着后来的人把
    解释删掉才能过测试，正好和留注释的初衷相反。"""
    without_block = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", without_block, flags=re.M)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def skill_select() -> str:
    return _read(SKILL_SELECT)


@pytest.fixture(scope="module")
def create_review() -> str:
    return _read(CREATE_REVIEW)


@pytest.fixture(scope="module")
def skills_lib() -> str:
    return _read(SKILLS_LIB)


def _non_review_skills_from_backend() -> set:
    """后端口径的「点了不改变评审行为」的技能。

    判据是 PersonaService.get_skill_prompt_hint 给不给提示语：给了，创建评审时
    prompt 真的会变；不给，skill_type 就只是被落库当标签。synthetic_playtest 例外——
    它是默认流程，本来就不需要额外提示语，跑出来的正是它承诺的东西。
    """
    return {
        st.value
        for st in SkillType
        if st.value != SkillType.SYNTHETIC_PLAYTEST.value
        and not PersonaService.get_skill_prompt_hint(st.value)
    }


def _frontend_non_review_skills(source: str) -> set:
    m = re.search(r"export const NON_REVIEW_SKILL_TYPES = \[(.*?)\]", source, re.S)
    assert m, "lib/skills.ts 里找不到 NON_REVIEW_SKILL_TYPES——常量被删或改名时这条必须红"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def test_non_review_skills_match_backend_behaviour(skills_lib):
    """前端「不能用来创建评审」的名单必须等于后端「不改变评审行为」的名单。

    两个方向都要卡住：
      · 后端给 persona_generate 补上提示语（它开始真的起作用了），前端却还禁着 → 红，
        提醒把入口放开；
      · 有人把 persona_generate 从名单里删掉、入口放回去，而后端依旧什么都不做 → 红。
    """
    assert _frontend_non_review_skills(skills_lib) == _non_review_skills_from_backend()


def test_persona_generate_is_actually_inert_today():
    """给上面那条断言一个反空转的锚：今天 persona_generate 确实没有任何提示语。
    如果哪天它有了，这条会红，那时应当同时放开前端入口。"""
    assert PersonaService.get_skill_prompt_hint("persona_generate") == ""
    assert PersonaService.get_skill_prompt_hint("red_team_audience") != ""


def test_skill_select_does_not_offer_review_entry_for_inert_skills(skill_select):
    """「使用此技能创建评审」这个 CTA 必须被 startsReview 守着，
    而不是无条件渲染给每一张卡。"""
    assert "startsReview" in skill_select
    assert "disabled={!startsReview}" in skill_select
    idx = skill_select.index("使用此技能创建评审")
    assert "startsReview ? (" in skill_select[max(0, idx - 400) : idx]


def test_task_type_lists_come_from_the_backend_not_local_skills(skill_select, create_review, skills_lib):
    """技能→任务类型的映射必须来自后端详情，不能再回落到本地手写的 SKILLS[].task_types。

    后端对 skill_type × task_type 的组合零校验，本地那份枚举是凭空发明的约束：
    它会把用户真正要选的任务类型从界面上藏掉，还把长度当成「N 种任务」显示出去。
    """
    for name, source in (
        ("SkillSelectPage", skill_select),
        ("CreateReviewPage", create_review),
        ("lib/skills.ts", skills_lib),
    ):
        assert "deco?.task_types" not in source, f"{name} 又用回了本地写死的 task_types"
        assert ".task_types.length" not in source, f"{name} 在用本地清单的长度报数"
    assert "skill.taskTypes" in skill_select
    assert "selectedSkill?.taskTypes" in create_review


def test_create_review_uses_backend_skill_names(create_review):
    """名称/描述以 /api/skills 为准。本地再存一份必然漂移，表现是同一个技能
    在技能中心和创建页显示两种说法。"""
    assert "loadSkillTruth" in create_review
    assert "description_zh" not in create_review, "创建页又读回了本地的技能描述"
    assert re.search(r"^import .*\bSKILLS\b.*from '@/lib/mock-data'", create_review, re.M) is None


def test_no_fabricated_cost_estimate(create_review):
    """确认页不许再出现「预估成本 $X.XX」。

    那块由本文件里一张写死的每任务类型单价表算出，真实成本由 token 数 × 模型定价
    决定（runner.persona_agent.estimate_cost 读 budget.yaml），发起前不可知，
    且后端没有任何预估端点。精确到分的假数比不给数更糟——用户会拿它做预算。
    """
    # 注释里要讲清楚这块为什么被删，讲的时候难免写出「预估成本 $0.05」这样的字样，
    # 所以断言只看去掉注释后的代码本身。
    code = _strip_comments(create_review)
    assert "baseCostMap" not in code
    assert "预估成本" not in code
    assert not re.search(r"\$\$?\{?[\d.]+\}?", code), "确认页又出现了写死的金额"


def test_materials_cannot_be_empty(create_review):
    """两道闸：任务类型没有字段定义时退到一个必填的通用正文框；
    发起前再确认材料非空。缺任何一道，用户都能只填一个标题就跑完整条流程，
    拿回一份基于一句话生成的报告而不自知。"""
    assert "GENERIC_MATERIAL_FIELD" in create_review
    assert "definedFields.length === 0 ? [GENERIC_MATERIAL_FIELD]" in create_review
    assert "if (materials.length === 0)" in create_review


def test_extracted_extra_fields_are_visible(create_review):
    """AI 提取出来但不属于当前任务类型标准字段的内容，必须在界面上露出来。
    它们本来就会被一并提交给评审引擎，看不见等于用户在不知情下交了东西。"""
    assert "extraFieldKeys" in create_review


def test_extract_failure_shows_the_real_reason(create_review):
    """提取失败要透出后端给的原因（文件过大/格式不支持/没配 key/限流…），
    不能一律替换成一句「AI 提取失败」——那会让用户以为是模型能力不行而放弃。"""
    assert "AI 提取失败：${reason}" in create_review


def test_evaluation_dimension_labels_are_not_hardcoded(create_review):
    """第 4 步「启用评估报告」列出的维度必须来自 EVALUATION_DIMENSIONS
    （其 id 逐字对齐后端 RUBRIC_DIMENSIONS），不能是另写一套词表。"""
    from app.services.evaluation_service import RUBRIC_DIMENSIONS

    assert "EVALUATION_DIMENSIONS.map" in create_review
    assert "EVALUATION_DIMENSIONS.length" in create_review
    for stale in ("'覆盖度'", "'新颖性'", "'偏见检测'"):
        assert stale not in create_review, "又写死了一套和后端对不上的维度词表"
    assert len(RUBRIC_DIMENSIONS) > 0
