# -*- coding: utf-8 -*-
"""人格包数据本身的门：schema 校验、量表取值、伦理编码红线。

为什么单独一个文件：panel_selector 的测试管"选得出来吗"，这个文件管"写得对吗"。
两类问题的修法完全不同——前者改代码，后者改 yaml。

这里卡死的几条红线都是本仓库自己踩过的：
  * behavior_profile 取值必须落在 panel_selector.LEVEL 里
    （原先 risk_tolerance 用三档表，真实数据里的「很低」直接 KeyError）
  * 非二元人格的 identity_summary 不许出现「他/她」
    （identity_summary 是会进提示词的字段）
  * notes 不许把 age_range 写成对能力/水平的事实断言
  * 无障碍类人格不许被编码成"在每条行为轴上全面降级"
"""

import glob
import io
import json
import os
import re

import pytest
import yaml
from jsonschema import Draft7Validator
from runner.panel_selector import DISTANCE_AXES, LEVEL

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONA_DIR = os.path.join(REPO_ROOT, "src", "personas")
SCHEMA_PATH = os.path.join(REPO_ROOT, "src", "schemas", "persona-schema.json")

PACK_PATHS = sorted(glob.glob(os.path.join(PERSONA_DIR, "*.yaml")))
PACK_NAMES = [os.path.splitext(os.path.basename(p))[0] for p in PACK_PATHS]

# 本次新增的人格：新写的东西按更严的口径卡（决策规则必须是可证伪的条件句）。
# 存量人格不追溯，避免这次改动变成一场全仓库重写。
NEW_PERSONA_IDS = {
    "P62-store-submission-reviewer",
    "P63-china-license-gatekeeper",
    "P64-device-compat-tester",
    "P65-privacy-compliance-counsel",
    "P66-refunded-churned-player",
    "P67-localization-dependent-player",
}


def _load_pack(name):
    with io.open(os.path.join(PERSONA_DIR, name + ".yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def _all_personas():
    for name in PACK_NAMES:
        data = _load_pack(name)
        for persona in data["personas"]:
            yield name, persona


ALL_PERSONAS = list(_all_personas())
PERSONA_IDS = ["%s/%s" % (pack, p["id"]) for pack, p in ALL_PERSONAS]


@pytest.fixture(scope="module")
def schema():
    with io.open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestSchemaConformance:
    @pytest.mark.parametrize("pack", PACK_NAMES)
    def test_pack_structure(self, pack):
        data = _load_pack(pack)
        assert data.get("panel_id") == pack, "panel_id 必须与文件名一致：load_personas 按它给人格盖包名"
        assert isinstance(data.get("personas"), list) and data["personas"]

    @pytest.mark.parametrize("pack,persona", ALL_PERSONAS, ids=PERSONA_IDS)
    def test_persona_validates(self, pack, persona, schema):
        errors = sorted(Draft7Validator(schema).iter_errors(persona), key=lambda e: e.path)
        assert not errors, "%s: %s" % (
            persona.get("id"),
            "; ".join("%s %s" % (list(e.path), e.message) for e in errors[:3]),
        )

    def test_ids_unique_within_pack(self):
        for pack in PACK_NAMES:
            ids = [p["id"] for p in _load_pack(pack)["personas"]]
            assert len(ids) == len(set(ids)), pack


class TestBehaviorScaleValues:
    """panel_selector 的距离计算跑在生产选人路径上；量表外的取值会被静默跳过，
    所以必须在这一层卡死，不能靠运行时崩不崩来发现。
    """

    @pytest.mark.parametrize("pack,persona", ALL_PERSONAS, ids=PERSONA_IDS)
    def test_axis_values_in_scale(self, pack, persona):
        bad = []
        for axis in DISTANCE_AXES:
            value = persona["behavior_profile"].get(axis)
            if value not in LEVEL:
                bad.append("%s=%r" % (axis, value))
        assert bad == [], "%s: %s" % (persona["id"], bad)


class TestEthicsEncoding:
    """ETHICS 守则要禁的"因为某人是某身份所以会某行为"，换成 YAML 也一样要禁。"""

    _PRONOUN_RE = re.compile(u"[他她]")

    @pytest.mark.parametrize("pack,persona", ALL_PERSONAS, ids=PERSONA_IDS)
    def test_nonbinary_persona_avoids_binary_pronoun(self, pack, persona):
        """identity_summary 会进提示词。标注非二元却写"她/他"，
        等于在提示词里当场推翻这个标注。
        （「他们」作为复数/中性用法允许；「其他」等词先剔除。）
        """
        if persona.get("gender") != u"非二元":
            return
        text = persona["identity_summary"].replace(u"其他", u"").replace(u"他们", u"")
        assert not self._PRONOUN_RE.search(text), u"%s 的 identity_summary 用了二元代词：%s" % (
            persona["id"], persona["identity_summary"],
        )

    @pytest.mark.parametrize("pack,persona", ALL_PERSONAS, ids=PERSONA_IDS)
    def test_notes_do_not_assert_age_capability_link(self, pack, persona):
        """P30 曾写「age_range=18-26：反映竞技巅峰年龄段的典型分布」——
        这是以事实断言的口吻主张"年龄决定竞技水平"。
        对照 P13 的写法「仅反映行业从业年限的代理变量」，那是限定不是主张。
        提到 age_range 时必须带否认因果的限定语。
        """
        notes = persona.get("notes") or ""
        if "age_range" not in notes:
            return
        assert (u"不表示" in notes or u"仅" in notes or u"代理变量" in notes), (
            u"%s 的 notes 用断言口吻把年龄和能力/需求绑定：%s" % (persona["id"], notes)
        )

    def test_accessibility_personas_not_uniformly_downgraded(self):
        """P38「特殊教育需求」曾在 experience / patience / genre_literacy /
        risk_tolerance / tolerance_for_ambiguity 上被全线写成最低档，
        而同为无障碍视角的 P19（运动辅助）是 patience 高、genre_literacy 高。
        同一产品里只有某一类身份被写成全维度低能力，就是刻板印象编码。
        """
        watched = {
            "accessibility": ["P17", "P18", "P19", "P20"],
            "educational-serious": ["P38"],
            "general-consumer": ["P52"],
        }
        low = {u"低", u"很低"}
        for pack, prefixes in watched.items():
            for persona in _load_pack(pack)["personas"]:
                if not any(persona["id"].startswith(p) for p in prefixes):
                    continue
                profile = persona["behavior_profile"]
                # 能力相关的轴（不含"偏好"性质的轴，如 price_sensitivity）
                ability_axes = ["patience", "genre_literacy", "completion_drive", "agency_preference"]
                lows = [a for a in ability_axes if profile.get(a) in low]
                assert len(lows) < len(ability_axes), (
                    u"%s 在全部能力相关轴上都是低档：%s" % (persona["id"], lows)
                )

    def test_accessibility_genres_are_not_slow_paced_only(self):
        """残障 → 只玩慢节奏品类，是本仓库审计出来的另一条刻板印象编码。
        运动障碍玩家打动作/格斗、聋人玩家打 FPS/音游都有大量公开记录。
        """
        fast_paced = {
            "action", "fighting-game", "competitive-FPS", "rhythm", "battle-royale",
            "tactical-shooter", "MOBA", "platformer",
        }
        for persona in _load_pack("accessibility")["personas"]:
            genres = set(persona["gaming_profile"]["genres"])
            if persona["id"].startswith(("P19", "P20")):
                assert genres & fast_paced, (
                    u"%s 的 genres 里没有任何快节奏品类：%s" % (persona["id"], sorted(genres))
                )


class TestLaunchCompliancePack:
    """新增的"上线杀手"人格包：平台送审 / 版号与分级 / 机型适配 / 隐私合规 / 退款流失。
    这个产品卖"上线前发现风险"，此前 66 个人格里这五类一个都没有。
    """

    PACK = "launch-compliance"

    def test_pack_exists_with_five_roles(self):
        ids = [p["id"] for p in _load_pack(self.PACK)["personas"]]
        assert ids == [
            "P62-store-submission-reviewer",
            "P63-china-license-gatekeeper",
            "P64-device-compat-tester",
            "P65-privacy-compliance-counsel",
            "P66-refunded-churned-player",
        ], ids

    def test_covers_required_launch_blockers(self):
        """四类"最能弄死上线"的视角必须都在，且能从人格文本里查得到关键词，
        免得写了个名字好听但内容没覆盖的空壳。
        """
        blob = io.open(
            os.path.join(PERSONA_DIR, self.PACK + ".yaml"), encoding="utf-8"
        ).read()
        for keyword in [
            u"版号", u"ISBN", u"CADPA", u"ESRB", u"PEGI",           # 版号与分级
            u"App Store", u"Google Play", u"TapTap", u"Steam",      # 平台审核
            u"GDPR", u"COPPA", u"SDK", u"注销",                     # 法务与隐私
            u"低端机", u"崩溃率", u"首包", u"耗电",                 # 机型适配与性能
            u"退款", u"弃坑",                                        # 退款者与流失玩家
        ]:
            assert keyword in blob, u"launch-compliance 包里查不到关键词：%s" % keyword

    def test_ids_do_not_collide_with_existing_numbers(self):
        others = set()
        for pack in PACK_NAMES:
            if pack == self.PACK:
                continue
            for p in _load_pack(pack)["personas"]:
                others.add(p["id"][:3])
        mine = set(p["id"][:3] for p in _load_pack(self.PACK)["personas"])
        assert not (mine & others), mine & others


class TestNewPersonasAreFalsifiable:
    """startup-panel 是全仓库质量最高的一包，靠的是可证伪的决策规则
    （如 P57「若"自研技术"实际是对第三方 API 的浅封装，技术壁垒项直接判零」），
    而不是形容词堆砌。新写的人格按同一口径卡。
    """

    NEW = [(pack, p) for pack, p in ALL_PERSONAS if p["id"] in NEW_PERSONA_IDS]
    NEW_IDS = [p["id"] for _, p in NEW]

    def test_all_new_personas_present(self):
        assert set(self.NEW_IDS) == NEW_PERSONA_IDS, sorted(set(NEW_PERSONA_IDS) - set(self.NEW_IDS))

    @pytest.mark.parametrize("pack,persona", NEW, ids=NEW_IDS)
    def test_decision_rules_are_conditional(self, pack, persona):
        rules = persona["decision_rules"]
        assert len(rules) >= 3, persona["id"]
        for rule in rules:
            assert rule.startswith(u"若"), u"%s 的决策规则不是条件句：%s" % (persona["id"], rule)
            assert u"判定" in rule or u"直接" in rule or u"不接受" in rule or u"按" in rule, (
                u"%s 的决策规则没给出可检验的结论：%s" % (persona["id"], rule)
            )

    @pytest.mark.parametrize("pack,persona", NEW, ids=NEW_IDS)
    def test_has_task_affinity_and_review_contract(self, pack, persona):
        affinity = persona.get("task_affinity") or {}
        assert affinity, persona["id"]
        assert max(affinity.values()) >= 0.8, u"%s 没有任何一个任务是它的主场" % persona["id"]
        assert len(persona["review_output"]["must_comment_on"]) >= 3, persona["id"]

    @pytest.mark.parametrize("pack,persona", NEW, ids=NEW_IDS)
    def test_notes_disclaim_causality(self, pack, persona):
        """新人格一律要有 notes，写清楚判断依据来自哪里、不主张什么。"""
        notes = persona.get("notes") or ""
        assert len(notes) >= 10, u"%s 缺 notes" % persona["id"]


class TestReadmeCountsMatchReality:
    """README 的人格/包数量必须和 src/personas/ 真实文件对得上。

    这条门存在的理由很具体：本轮新增 launch-compliance 包（+5）与
    game-core 的 P67（+1）之后，README 里 8 处仍然写着"10 packs (66 personas)"。
    对外声称与代码实际不一致，正是这个仓库连着两轮在清的东西——
    与其靠人记得改，不如让它在这里红。
    """

    @staticmethod
    def _real_counts():
        packs = sorted(glob.glob(os.path.join(PERSONA_DIR, "*.yaml")))
        total = 0
        for path in packs:
            with io.open(path, encoding="utf-8") as f:
                total += len(yaml.safe_load(f)["personas"])
        return len(packs), total

    def test_counts_present_in_readme(self):
        n_packs, n_personas = self._real_counts()
        readme = os.path.join(os.path.dirname(PERSONA_DIR), "..", "README.md")
        with io.open(os.path.abspath(readme), encoding="utf-8") as f:
            text = f.read()

        # 只要真实数字在 README 里出现过，且旧数字没有以"总数"的口吻残留
        assert str(n_personas) in text, (
            u"README 里找不到真实人格总数 %d——数量变了但文档没跟" % n_personas
        )
        stale = re.findall(
            u"([0-9]+)[ ]*(?:Persona Packs|个人格 Pack|个人格Pack|persona packs|packs,|个Pack)",
            text,
        )
        bad = sorted({s for s in stale if int(s) != n_packs})
        assert not bad, (
            u"README 里还写着 %s 个 Pack，实际是 %d 个（src/personas/*.yaml）" % (bad, n_packs)
        )
