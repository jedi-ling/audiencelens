# -*- coding: utf-8 -*-
"""GET /api/skills/{skill_type} 必须把服务层算出来的能力清单真的发出去。

背景：PersonaService.get_skill_detail 按技能类型认认真真组装了
available_packs / task_types / parameters，
而端点的 response_model=SkillTypeResponse 只声明了 skill_type/name/description，
其余字段被 FastAPI 静默裁掉。前端因此永远拿不到"这个技能支持哪些任务类型"的
真实答案，只好在 mock-data.ts 里自己写死一份——那份数字追溯不到任何事实源。

这条测试的形式很关键：断言"响应里的 task_types 与 TASK_TYPES 注册表一致"，
而不是断言"有 task_types 字段"。后者在有人把它改回硬编码常量时依然是绿的。
"""


def test_skill_detail_task_types_come_from_the_registry(client):
    from app.services import PersonaService

    r = client.get("/api/skills/synthetic_playtest")
    assert r.status_code == 200, r.text
    body = r.json()

    expected = [tt["task_type"] for tt in PersonaService.get_task_types()]
    assert body["task_types"] == expected, (
        "task_types 与任务类型注册表对不上——要么被 schema 裁了，要么被写死了"
    )
    assert len(expected) > 3, "注册表本身就该有多个任务类型，否则这条断言没有约束力"

    expected_packs = [p["panel_id"] for p in PersonaService.list_packs()]
    assert body["available_packs"] == expected_packs


def test_each_skill_detail_field_survives_the_response_model(client):
    """逐个技能核对：服务层给了什么，端点就必须发出什么，一个字段都不许被裁。"""
    from app.services import PersonaService

    for skill_type in (
        "synthetic_playtest",
        "audience_panel",
        "red_team_audience",
        "persona_generate",
    ):
        detail = PersonaService.get_skill_detail(skill_type)
        body = client.get(f"/api/skills/{skill_type}").json()
        for key, value in detail.items():
            assert body.get(key) == value, f"{skill_type}.{key} 被响应模型裁掉或改写了"


def test_every_review_skill_answers_task_types_from_the_registry(client):
    """三个评审类技能的 task_types 必须都等于注册表全量——创建评审入口
    只校验 task_type，与 skill_type 正交，所以"某技能只支持某几种任务类型"
    是不存在的限制；persona_generate 不是评审，明确回答空列表而不是 null。"""
    from app.services import PersonaService

    expected = [tt["task_type"] for tt in PersonaService.get_task_types()]
    for skill_type in ("synthetic_playtest", "audience_panel", "red_team_audience"):
        body = client.get(f"/api/skills/{skill_type}").json()
        assert body["task_types"] == expected, f"{skill_type} 的 task_types 不等于注册表全量"

    body = client.get("/api/skills/persona_generate").json()
    assert body["task_types"] == [], "persona_generate 不吃 task_type，应明确回答空列表"


def test_fabricated_capability_fields_are_gone(client):
    """supported_domains / attack_surfaces 是曾经手写的假能力承诺
    （全仓无任何代码按它分支），删掉后不许再以任何形式回到响应里。"""
    for skill_type in ("audience_panel", "red_team_audience"):
        body = client.get(f"/api/skills/{skill_type}").json()
        assert "supported_domains" not in body
        assert "attack_surfaces" not in body


def test_list_endpoint_stays_lean(client):
    """列表端点不该顺手把详情字段也带上——那些字段是按技能分支算的，
    列表里给一半空一半只会让调用方以为"这个技能没有攻击面"。"""
    r = client.get("/api/skills")
    assert r.status_code == 200
    for item in r.json():
        assert item["task_types"] is None
        assert item["parameters"] is None
