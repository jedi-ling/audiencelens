# -*- coding: utf-8 -*-
"""目录英文（I18N_CONTRACT D4）到底有没有被接上——以及缺一条时它会不会红。

这份文件测的不是「有没有 name_en 字段」，那种断言在字段被填成中文、填成 id、
甚至被 response_model 裁掉之后照样是绿的。这里测的是三件会真实发生的漂移：

  1. **英文条目与中文源的 id 集对不上。** 后果不是报错，是英文界面上那一条静默显示中文。
     所以卡口必须在 import 期，而不是在请求期补一句 `or name_zh`。
  2. **英文被 FastAPI 的 response_model 静默裁掉。** 本仓吃过一次
     （见 SkillTypeResponse 的文件头注释：服务层认真算了一遍，一个字都没到前端）。
     所以这里断言的是**端点响应体**里有英文，而不是服务层返回值里有。
  3. **`stance_enum` 被顺手翻了。** 它是聚合器做立场分桶的 dict 键，翻了不报错、
     只是把所有立场算进错误的桶。英文只允许存在于 `stance_labels_en` 这个显示层副本里。

第 2 组测试（TestTheAssertsAreNotNoOps）专门证明上面这些卡口不是空转：
把英文目录改坏一条，断言必须抛。一个永远绿的卡口比没有卡口更危险——
它会让人以为查过了。
"""

import copy
import json

import pytest

from app.i18n import catalog_en
from app.i18n.catalog_en import CatalogEnError, contains_cjk
from app.models import SkillType
from app.services import REVIEW_MODES, TASK_TYPES, PersonaService


@pytest.fixture
def broken_catalog(monkeypatch):
    """给一份可改坏的英文目录副本，改完自动还原（不碰磁盘上的 json）。"""

    def _break(mutate):
        data = copy.deepcopy(catalog_en.load_catalog_en())
        mutate(data)
        monkeypatch.setattr(catalog_en, "_cache", data)
        return data

    return _break


class TestTheEnglishIsActuallyWired:
    def test_task_types_carry_english_from_import_time(self):
        """直接读模块级常量：能读到英文就说明合并发生在 import 期。

        如果哪天有人把 merge 挪进请求处理里，这条会红——而挪进去的代价是
        「忘了合并的那个端点静默发中文」，正是 D4 要消灭的形态。
        """
        assert TASK_TYPES, "任务类型注册表是空的，下面所有断言都会在空集上通过"
        for task_type, info in TASK_TYPES.items():
            assert info.get("name_en"), f"{task_type} 没有 name_en"
            assert info.get("description_en"), f"{task_type} 没有 description_en"
            assert info.get("stance_labels_en"), f"{task_type} 没有 stance_labels_en"

    def test_review_modes_carry_english_from_import_time(self):
        for mode, config in REVIEW_MODES.items():
            assert config.get("description_en"), f"{mode} 没有 description_en"

    def test_catalog_ids_match_every_chinese_source(self):
        """五个分节的 id 集逐一对应。这是 import 期那条 assert 的同款口径，
        在这里再跑一遍是为了让失败信息落在测试报告里而不是启动日志里。"""
        catalog_en.assert_catalog_en_complete(
            task_type_ids=TASK_TYPES,
            review_mode_ids=REVIEW_MODES,
            skill_ids=[st.value for st in SkillType],
            pack_ids=[p["panel_id"] for p in PersonaService.list_packs()],
            pack_category_ids={p["category"] for p in PersonaService.list_packs()},
        )

    def test_stance_labels_en_is_positional_with_stance_enum(self):
        """两个列表按下标配对，所以必须等长、且英文侧不许有重复。

        长度不等时按下标取值会静默取到隔壁那个立场的词——界面上是一句通顺的英文，
        说的是相反的意思；英文侧重复则等于把两个立场画成同一个。
        顺序对不对机器判不了，但「等长 + 不重复 + 中文侧没被翻」这三条能挡住绝大多数改错。
        """
        for task_type, info in TASK_TYPES.items():
            zh = list(info["stance_enum"])
            en = list(info["stance_labels_en"])
            assert len(en) == len(zh), (
                f"{task_type}: stance_labels_en {len(en)} 个 / stance_enum {len(zh)} 个 {zh}"
            )
            assert len(set(en)) == len(en), f"{task_type}: 英文立场词有重复 {en}"

    def test_stance_enum_itself_is_never_translated(self):
        """`stance_enum` 是聚类键，永不翻译。

        判据用「必须仍是中文」而不是「必须等于某个常量」：后者会在有人整体换一套
        中文立场词时误红，前者只在真的被翻成英文时红——而被翻成英文正是那个
        不报错、只把所有立场算进错误桶的缺陷。
        """
        for task_type, info in TASK_TYPES.items():
            for word in info["stance_enum"]:
                assert contains_cjk(word), (
                    f"{task_type} 的 stance_enum 里出现了非中文的 {word!r}——"
                    "它是聚合器的分桶键，翻了不会报错，只会让立场统计整体算错"
                )

    def test_english_fields_contain_no_chinese(self):
        for task_type, info in TASK_TYPES.items():
            for field in ("name_en", "description_en"):
                assert not contains_cjk(info[field]), f"{task_type}.{field} 里有中文"
            for label in info["stance_labels_en"]:
                assert not contains_cjk(label), f"{task_type} 的英文立场词里有中文：{label!r}"
        for mode, config in REVIEW_MODES.items():
            assert not contains_cjk(config["description_en"]), f"{mode}.description_en 里有中文"


class TestEndpointsReallyEmitIt:
    """服务层算出来的英文必须真的出现在响应体里。

    本仓吃过一次「response_model 把字段静默裁掉」——服务层认真算了一遍，
    一个字都没到前端，前端只好自己写死一份假清单。所以这一组全都打真端点。
    """

    def test_task_types_endpoint(self, client):
        r = client.get("/api/task-types")
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == len(TASK_TYPES)
        for entry in body:
            assert entry["name_en"], f"{entry['task_type']} 的 name_en 被裁掉了"
            assert entry["description_en"]
            assert len(entry["stance_labels_en"]) == len(entry["stance_enum"])

    def test_review_modes_endpoint(self, client):
        r = client.get("/api/review-modes")
        assert r.status_code == 200, r.text
        for entry in r.json():
            assert entry["description_en"], f"{entry['mode']} 的 description_en 被裁掉了"

    def test_skills_endpoint(self, client):
        r = client.get("/api/skills")
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == len(list(SkillType))
        for entry in body:
            assert entry["name_en"], f"{entry['skill_type']} 的 name_en 被裁掉了"
            assert entry["description_en"]
            assert not contains_cjk(entry["name_en"] + entry["description_en"])

    def test_skill_detail_endpoint_keeps_english(self, client):
        r = client.get("/api/skills/synthetic_playtest")
        assert r.status_code == 200, r.text
        assert r.json()["name_en"]

    def test_packs_endpoint(self, client):
        r = client.get("/api/personas/packs")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body, "人格包列表是空的"
        for entry in body:
            assert entry["name_en"], f"{entry['panel_id']} 的 name_en 被裁掉了"
            assert entry["description_en"]
            assert entry["category_name_en"]
            assert not contains_cjk(entry["name_en"]), entry["name_en"]

    def test_no_missing_marker_leaks_into_any_catalog_payload(self, client):
        """D8 的全链路断言：缺译标记 ⟦missing:…⟧ 一旦出现在目录响应里就是缺译上了线。"""
        for path in ("/api/task-types", "/api/review-modes", "/api/skills", "/api/personas/packs"):
            r = client.get(path)
            assert r.status_code == 200, r.text
            assert "⟦missing:" not in r.text, f"{path} 的响应里带着缺译标记"


class TestTheAssertsAreNotNoOps:
    """把英文目录改坏，证明上面那些卡口真的会红。

    这一组不改磁盘：改的是 catalog_en 的模块级缓存副本，跑完 monkeypatch 自动还原。
    """

    def test_a_missing_task_type_fails_loudly(self, broken_catalog):
        broken_catalog(lambda d: d["task_types"].pop("concept_review"))
        with pytest.raises(CatalogEnError) as exc:
            catalog_en.merge_task_types_en(copy.deepcopy(TASK_TYPES))
        assert "concept_review" in str(exc.value)

    def test_an_extra_english_entry_fails_loudly(self, broken_catalog):
        """多出来的英文同样要红：它意味着中文源改了名而英文没跟，
        而改名那一侧的表现是「这条在英文界面上显示中文」。"""
        broken_catalog(
            lambda d: d["task_types"].update({"ghost_review": {"name": "Ghost", "description": "x", "stance_labels": []}})
        )
        with pytest.raises(CatalogEnError) as exc:
            catalog_en.merge_task_types_en(copy.deepcopy(TASK_TYPES))
        assert "ghost_review" in str(exc.value)

    def test_a_short_stance_label_list_fails_loudly(self, broken_catalog):
        broken_catalog(lambda d: d["task_types"]["monetization_review"]["stance_labels"].pop())
        with pytest.raises(CatalogEnError) as exc:
            catalog_en.merge_task_types_en(copy.deepcopy(TASK_TYPES))
        assert "stance_labels" in str(exc.value)

    def test_chinese_left_in_an_english_field_fails_loudly(self, tmp_path, monkeypatch):
        """照抄中文源占位是最难发现的一种「翻好了」：字段在、非空、id 集也齐，
        断言全绿，只有英文用户看得见那一行中文。所以它按硬失败处理。

        这条要打磁盘（扫中文发生在读文件时），所以把 CATALOG_EN_PATH 指到临时副本上，
        跑完把模块缓存恢复成真目录——不然后面的用例会拿着临时目录跑。
        """
        data = copy.deepcopy(catalog_en.load_catalog_en())
        data["skills"]["audience_panel"]["name"] = "受众面板"
        fake = tmp_path / "catalog.en-US.json"
        fake.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(catalog_en, "CATALOG_EN_PATH", str(fake))
        catalog_en._cache.clear()
        try:
            with pytest.raises(CatalogEnError) as exc:
                catalog_en.load_catalog_en()
            assert "受众面板" in str(exc.value)
        finally:
            catalog_en._cache.clear()
            monkeypatch.undo()
            catalog_en.load_catalog_en()

    def test_a_missing_skill_fails_loudly(self, broken_catalog):
        broken_catalog(lambda d: d["skills"].pop("red_team_audience"))
        with pytest.raises(CatalogEnError) as exc:
            catalog_en.assert_skills_en([st.value for st in SkillType])
        assert "red_team_audience" in str(exc.value)

    def test_a_missing_pack_fails_loudly(self, broken_catalog):
        broken_catalog(lambda d: d["persona_packs"].pop("game-core"))
        with pytest.raises(CatalogEnError) as exc:
            catalog_en.assert_persona_packs_en([p["panel_id"] for p in PersonaService.list_packs()])
        assert "game-core" in str(exc.value)
