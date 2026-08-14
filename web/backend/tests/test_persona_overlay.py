# -*- coding: utf-8 -*-
"""人格表述层 overlay（I18N_CONTRACT 10.3 / 10.3.1）的机械卡口。

10.3 是终局结论不是本期取舍：**人格身份不本地化**，张伟在英文界面下仍叫张伟。
理由里有一条是硬的——`behavior_profile` 的值是 `panel_selector.LEVEL` 的键
（很低/低/中/高/很高），翻了直接 KeyError 硬崩；另一条是软的但更贵：
`region` / `age_range` 会被拼进报告的 `recruit_types`，用户照着去招真人受访者，
改名等于向英文用户断言一个从未建模过的受众。

所以这份文件里最重要的一条是 `TestForbiddenKeys`：把禁翻键钉死。
它必须能真的红——`test_the_forbidden_key_scan_is_not_a_no_op` 往一份真 overlay 的
副本里塞一个 `name`，扫描器抓不到就说明这条卡口是空转的。

其余三组分别管：
  · 覆盖率（每个包的 overlay 人数与源逐一对应；少一个 = 那个人在英文界面上是中文）
  · 防抄串（panel_id 与源逐字相等——overlay 全是英文散文，人眼看不出抄错了包）
  · 端点（英文真的发出去了，而不是被 response_model 裁掉）
"""

import copy
import os

import pytest
import yaml

from app.i18n import persona_overlay
from app.i18n.catalog_en import contains_cjk
from app.i18n.persona_overlay import (
    FORBIDDEN_KEYS,
    TRANSLATABLE_KEYS,
    PersonaOverlayError,
    load_overlay,
    merge_persona_overlay,
    overlay_path,
)
from app.services import PERSONAS_DIR, PersonaService

LOCALE = "en-US"


def _source_packs():
    """磁盘上的人格包：{pack_id: 源 yaml 文档}。"""
    packs = {}
    for fname in sorted(os.listdir(PERSONAS_DIR)):
        if fname.endswith((".yaml", ".yml")):
            pack_id = os.path.splitext(fname)[0]
            with open(os.path.join(PERSONAS_DIR, fname), "r", encoding="utf-8") as f:
                packs[pack_id] = yaml.safe_load(f)
    return packs


@pytest.fixture(scope="module")
def sources():
    packs = _source_packs()
    assert len(packs) >= 5, f"只找到 {len(packs)} 个人格包，这份测试的解析规则多半失效了"
    return packs


@pytest.fixture(autouse=True)
def _clean_overlay_cache():
    """每条用例前后都清 overlay 缓存：下面有几条会把 PERSONAS_DIR 指到临时目录，
    缓存留着会让后一条用例读到前一条造的假包。"""
    persona_overlay.invalidate_cache()
    yield
    persona_overlay.invalidate_cache()
    PersonaService.invalidate_cache()


def _forbidden_keys_in(node, path=""):
    """递归找禁翻键。递归而不是只看第一层：`review_output` 底下塞一个 `name`
    同样是把身份写进了 overlay，只看第一层的扫描器会漏掉它。"""
    hits = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = "{}.{}".format(path, key) if path else str(key)
            if key in FORBIDDEN_KEYS:
                hits.append(here)
            hits.extend(_forbidden_keys_in(value, here))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            hits.extend(_forbidden_keys_in(item, "{}[{}]".format(path, i)))
    return hits


def _write_pack(tmp_path, pack_id, doc):
    """在临时目录里造一份 overlay，并把加载器指过去。返回文件路径。"""
    en_dir = tmp_path / LOCALE
    en_dir.mkdir(exist_ok=True)
    target = en_dir / "{}.yaml".format(pack_id)
    target.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return target


class TestForbiddenKeys:
    """10.3 点名要求的那条机械卡口。"""

    def test_no_overlay_file_contains_an_identity_key(self, sources):
        offenders = {}
        for pack_id in sources:
            path = overlay_path(pack_id, LOCALE)
            with open(path, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f)
            hits = _forbidden_keys_in(doc.get("persona_overlays", {}))
            if hits:
                offenders[pack_id] = hits
        assert not offenders, (
            f"overlay 里出现了禁翻键（10.3）：{offenders}。"
            "身份字段会被拼进报告的 recruit_types，用户照着去招真人受访者；"
            "behavior_profile 的值是 panel_selector.LEVEL 的键，翻了直接 KeyError 硬崩"
        )

    def test_the_forbidden_key_scan_is_not_a_no_op(self, sources, tmp_path, monkeypatch):
        """往真 overlay 的副本里塞一个 `name`，扫描器必须抓到。

        缺了这条，上面那条断言在扫描规则写错时会永远绿——而永远绿的卡口
        比没有卡口更危险，它会让人以为查过了。
        """
        pack_id = "game-core"
        with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        victim = sorted(doc["persona_overlays"])[0]
        doc["persona_overlays"][victim]["name"] = "Zhang Wei"

        assert _forbidden_keys_in(doc["persona_overlays"]) == ["{}.name".format(victim)]

        # 加载器也必须拒收，而不是只有扫描脚本知道
        _write_pack(tmp_path, pack_id, doc)
        monkeypatch.setattr(persona_overlay, "PERSONAS_DIR", str(tmp_path))
        persona_overlay.invalidate_cache()
        with pytest.raises(PersonaOverlayError) as exc:
            load_overlay(pack_id, doc["panel_id"], LOCALE)
        assert "name" in str(exc.value)

    def test_a_behavior_profile_override_is_rejected(self, sources, tmp_path, monkeypatch):
        """单独钉 behavior_profile：它是唯一一个翻了会**硬崩**的键，
        崩的地方在 panel_selector.LEVEL[...]，报错完全指不到 overlay 上。"""
        pack_id = "game-core"
        with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        victim = sorted(doc["persona_overlays"])[0]
        doc["persona_overlays"][victim]["behavior_profile"] = {"patience": "high"}
        _write_pack(tmp_path, pack_id, doc)
        monkeypatch.setattr(persona_overlay, "PERSONAS_DIR", str(tmp_path))
        persona_overlay.invalidate_cache()
        with pytest.raises(PersonaOverlayError) as exc:
            load_overlay(pack_id, doc["panel_id"], LOCALE)
        assert "behavior_profile" in str(exc.value)

    def test_only_the_frozen_closed_set_may_appear(self, sources):
        """闭集之外的键一律不许进：加一个可翻字段必须是显式决定，不是顺手多写一行。"""
        for pack_id in sources:
            with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f)
            for persona_id, entry in doc["persona_overlays"].items():
                outside = sorted(set(entry) - TRANSLATABLE_KEYS)
                assert not outside, f"{pack_id}/{persona_id} 有闭集之外的键 {outside}"


class TestCoverage:
    def test_every_source_pack_has_an_overlay_file(self, sources):
        missing = [p for p in sources if not os.path.isfile(overlay_path(p, LOCALE))]
        assert not missing, (
            f"这些人格包没有 {LOCALE} overlay：{missing}。"
            "缺 overlay 的表现是英文界面上整包人设是中文，且没有任何报错"
        )

    def test_overlay_headcount_matches_each_pack(self, sources):
        """每个包的 overlay 人数与源逐一对应。少一个就是漏译，而漏译在界面上
        只表现为「这一条是中文」，不会有任何报错。"""
        bad = {}
        for pack_id, doc in sources.items():
            src_ids = [p["id"] for p in doc.get("personas", [])]
            with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
                overlays = yaml.safe_load(f)["persona_overlays"]
            missing = [i for i in src_ids if i not in overlays]
            extra = [i for i in overlays if i not in src_ids]
            if missing or extra:
                bad[pack_id] = {"缺英文": missing, "源里没有": extra}
        assert not bad, f"overlay 覆盖率对不上：{bad}"

    def test_a_dropped_persona_turns_this_red(self, sources, tmp_path, monkeypatch):
        """从 overlay 里删掉一个人，合并必须抛——这是「漏译一个人」的唯一症状来源，
        界面上它只表现为那一条是中文。"""
        pack_id = "game-core"
        doc = sources[pack_id]
        with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
            overlay_doc = yaml.safe_load(f)
        dropped = sorted(overlay_doc["persona_overlays"])[0]
        del overlay_doc["persona_overlays"][dropped]
        _write_pack(tmp_path, pack_id, overlay_doc)
        monkeypatch.setattr(persona_overlay, "PERSONAS_DIR", str(tmp_path))
        persona_overlay.invalidate_cache()
        with pytest.raises(PersonaOverlayError) as exc:
            merge_persona_overlay(pack_id, doc["personas"], doc["panel_id"], LOCALE)
        assert dropped in str(exc.value)

    def test_english_text_is_not_copied_chinese(self, sources):
        """英文栏里出现中文 = 照抄源占位。它长得和「翻好了」一模一样。"""
        for pack_id in sources:
            with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
                overlays = yaml.safe_load(f)["persona_overlays"]

            def _walk(node, where):
                if isinstance(node, str):
                    assert not contains_cjk(node), f"{pack_id}/{where} 里有中文：{node!r}"
                elif isinstance(node, list):
                    for i, item in enumerate(node):
                        _walk(item, "{}[{}]".format(where, i))
                elif isinstance(node, dict):
                    for k, v in node.items():
                        _walk(v, "{}.{}".format(where, k))

            _walk(overlays, pack_id)


class TestAntiCrossContamination:
    def test_panel_id_matches_the_source_verbatim(self, sources):
        for pack_id, doc in sources.items():
            with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
                overlay_doc = yaml.safe_load(f)
            assert overlay_doc["panel_id"] == doc["panel_id"], (
                f"{pack_id} 的 overlay panel_id 是 {overlay_doc['panel_id']!r}，"
                f"源是 {doc['panel_id']!r}"
            )

    def test_a_wrong_panel_id_turns_this_red(self, sources, tmp_path, monkeypatch):
        pack_id = "game-core"
        with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
            overlay_doc = yaml.safe_load(f)
        overlay_doc["panel_id"] = "mobile-f2p"
        _write_pack(tmp_path, pack_id, overlay_doc)
        monkeypatch.setattr(persona_overlay, "PERSONAS_DIR", str(tmp_path))
        persona_overlay.invalidate_cache()
        with pytest.raises(PersonaOverlayError) as exc:
            load_overlay(pack_id, sources[pack_id]["panel_id"], LOCALE)
        assert "panel_id" in str(exc.value)

    def test_the_source_must_declare_a_panel_id(self, sources):
        """源包没写 panel_id 时不许拿 pack_id 兜底——兜底会让防抄串校验变成必然通过。"""
        doc = sources["game-core"]
        with pytest.raises(PersonaOverlayError) as exc:
            merge_persona_overlay("game-core", doc["personas"], None, LOCALE)
        assert "panel_id" in str(exc.value)

    def test_an_overlay_field_absent_from_the_source_turns_this_red(self, sources, tmp_path, monkeypatch):
        """overlay 给了源里没有的字段 = 多半抄了别的人格。"""
        pack_id = "game-core"
        doc = sources[pack_id]
        with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
            overlay_doc = yaml.safe_load(f)
        # 只从**源**里拿掉一个字段（人还在，所以覆盖率那条不会先红），
        # overlay 却还给着它——这正是「抄了别的人格」的形态。
        personas = copy.deepcopy(doc["personas"])
        victim = personas[0]["id"]
        personas[0].pop("likes", None)
        _write_pack(tmp_path, pack_id, overlay_doc)
        monkeypatch.setattr(persona_overlay, "PERSONAS_DIR", str(tmp_path))
        persona_overlay.invalidate_cache()
        with pytest.raises(PersonaOverlayError) as exc:
            merge_persona_overlay(pack_id, personas, doc["panel_id"], LOCALE)
        assert "likes" in str(exc.value) and victim in str(exc.value)


class TestShape:
    """10.3.1 冻结的文件形状。留白的代价本仓已经吃过一次：三个并行 agent 写出三种外壳。"""

    def test_all_real_overlays_have_the_frozen_top_level(self, sources):
        for pack_id in sources:
            with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f)
            assert set(doc) == {"version", "locale", "panel_id", "persona_overlays"}, (
                f"{pack_id} 的 overlay 顶层是 {sorted(doc)}"
            )
            assert doc["locale"] == LOCALE
            assert isinstance(doc["persona_overlays"], dict)

    def test_a_personas_container_is_rejected(self, sources, tmp_path, monkeypatch):
        """源文件的 `personas:` 是完整人格记录的**列表**，overlay 是以 id 为键的 mapping。
        同名不同形状是最容易看错的组合，所以加载器直接拒收。"""
        pack_id = "game-core"
        with open(overlay_path(pack_id, LOCALE), "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        doc["personas"] = []
        _write_pack(tmp_path, pack_id, doc)
        monkeypatch.setattr(persona_overlay, "PERSONAS_DIR", str(tmp_path))
        persona_overlay.invalidate_cache()
        with pytest.raises(PersonaOverlayError) as exc:
            load_overlay(pack_id, doc["panel_id"], LOCALE)
        assert "persona_overlays" in str(exc.value)

    def test_a_missing_overlay_file_is_not_silently_skipped(self, tmp_path, monkeypatch):
        (tmp_path / LOCALE).mkdir()
        monkeypatch.setattr(persona_overlay, "PERSONAS_DIR", str(tmp_path))
        persona_overlay.invalidate_cache()
        with pytest.raises(PersonaOverlayError) as exc:
            load_overlay("game-core", "game-core", LOCALE)
        assert "game-core" in str(exc.value)

    def test_an_unsupported_locale_does_not_fall_back(self):
        """不做「最接近的语言」匹配：匹配到别的语言就是静默换语种，与缺译一样看不出来。"""
        with pytest.raises(PersonaOverlayError):
            overlay_path("game-core", "ja-JP")

    def test_overlay_root_is_the_same_personas_dir_as_services(self):
        """两处各算一遍路径。算岔了的表现是 overlay 读不到、英文人设静默缺失。"""
        assert os.path.normcase(persona_overlay.PERSONAS_DIR) == os.path.normcase(PERSONAS_DIR)


class TestMergeAndEndpoint:
    def test_merge_adds_english_siblings_and_leaves_identity_untouched(self, sources):
        pack_id = "game-core"
        doc = sources[pack_id]
        merged = merge_persona_overlay(pack_id, doc["personas"], doc["panel_id"], LOCALE)
        assert len(merged) == len(doc["personas"])
        for src, out in zip(doc["personas"], merged):
            # 身份字段逐字不动（10.3）
            for key in FORBIDDEN_KEYS:
                if key in src:
                    assert out[key] == src[key], f"{src['id']} 的 {key} 被动过了"
                assert key + "_en" not in out, f"{src['id']} 冒出了 {key}_en"
            assert out["archetype_en"] and not contains_cjk(out["archetype_en"])
            assert out["identity_summary_en"]
            assert out["archetype"] == src["archetype"], "中文表述也不该被替换，是**双发**不是替换"

    def test_persona_service_cache_carries_the_overlay(self):
        """服务层缓存里就已经带着英文——合并发生在加载时，而不是某个端点里。
        放到端点里意味着每个端点都要记得合一次，忘掉的那个会静默发中文。"""
        PersonaService.invalidate_cache()
        for pack_id, personas in PersonaService.load_all_personas().items():
            for p in personas:
                assert p.get("archetype_en"), f"{pack_id}/{p['id']} 缺 archetype_en"
                assert p.get("identity_summary_en"), f"{pack_id}/{p['id']} 缺 identity_summary_en"

    def test_personas_endpoint_emits_english(self, client):
        r = client.get("/api/personas")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body, "人格列表是空的"
        for entry in body:
            assert entry["archetype_en"], f"{entry['id']} 的 archetype_en 被裁掉了"
            assert entry["identity_summary_en"]
            # 身份不本地化：名字仍是中文源里的那个
            assert entry["name"], entry["id"]
        assert "⟦missing:" not in r.text

    def test_pack_endpoint_emits_english(self, client):
        r = client.get("/api/personas/packs/game-core")
        assert r.status_code == 200, r.text
        for entry in r.json():
            assert entry["archetype_en"], f"{entry['id']} 的 archetype_en 被裁掉了"
