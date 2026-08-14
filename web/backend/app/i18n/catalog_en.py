# -*- coding: utf-8 -*-
"""目录数据的英文事实源加载器（I18N_CONTRACT D4）。

做什么：把 `catalog.en-US.json` 的值在 **import 期** 合并成原 dict 的同级键
（`name_en` / `description_en` / `stance_labels_en` / `category_name_en`），
中英一起发。端点签名一个字不改：没有 `lang` 参数，没有 `Accept-Language` 分支。

为什么把断言放在 import 期而不是请求期：
「缺译」这件事的默认表现是**静默显示中文**——接口照 200、页面照渲染，只有英文用户
看见一半中文，而没有任何日志、没有任何报错。请求期补一句 `or name_zh` 就是把这个
静默固化下来。所以这里反过来：英文 JSON 的 id 集必须与中文源逐一对应，缺一个后端
**启动就失败**。上线前必然撞上，上线后不可能悄悄发生。

这里没有任何 fallback 分支。查不到就抛 `CatalogEnError`，不回落中文。

永不翻译的东西（翻了会静默算错，不是显示难看）：
  · `stance_enum` —— 聚合器拿它当立场聚类的 dict 键（见 test_task_type_parity 的文件头）。
    英文只存在于 `stance_labels_en` 这个**显示层**副本里，逐位对应，位置即契约：
    顺序错一位就等于把「会买」显示成「不买」，而且不会报错。
  · `score_dimensions` / 一切 id —— wire contract。
  · 人格身份字段 —— 见 I18N_CONTRACT 10.3，本文件根本不碰人格档案。
"""

import json
import os
import re
from typing import Any, Dict, Iterable, List, Mapping

CATALOG_EN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.en-US.json")

# `_meta` 是给维护者看的说明块，不是目录条目。只有这一个下划线开头的顶层键，
# 各分节内部**不允许**再出现下划线键——否则 id 集断言就得开始做过滤，
# 而一个会过滤的断言迟早会把真条目也过滤掉。
_META_KEY = "_meta"

_SECTIONS = ("task_types", "review_modes", "skills", "persona_packs", "pack_categories")

_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿　-〿＀-￯]")


class CatalogEnError(RuntimeError):
    """英文目录与中文源对不上。故意用会让 import 炸掉的异常，见模块头。"""


_cache: Dict[str, Any] = {}


def _fail(msg: str) -> None:
    raise CatalogEnError(f"{msg}\n（英文目录事实源：{CATALOG_EN_PATH}）")


def contains_cjk(text: str) -> bool:
    """英文栏里有没有中日韩文字。人格 overlay（`persona_overlay.py`）用的是同一份判定——
    两处各写一份正则必然漂移，而漂移的表现是「一边拦得住、一边拦不住」，
    比两边都没有更难查。"""
    return bool(_CJK_RE.search(text))


def _assert_no_cjk(section: str, entry_id: str, field: str, value: str) -> None:
    """英文栏里出现中日韩文字，几乎只有一种成因：条目是复制中文源占位的。

    不拦的话它长得和「翻好了」一模一样——字段在、非空、断言全绿，
    只有英文用户看得见那行中文。所以这条按硬失败处理。
    """
    if contains_cjk(value):
        _fail(f"{section}.{entry_id}.{field} 里有中文字符，这是没翻的占位而不是英文文案：{value!r}")


def load_catalog_en() -> Dict[str, Any]:
    """读英文目录。文件缺失/JSON 语法错/分节缺失一律抛，不返回空 dict——
    空 dict 会让下面每一条断言都在空集上通过，那是一个永远绿的卡口。"""
    if _cache:
        return _cache

    if not os.path.isfile(CATALOG_EN_PATH):
        _fail("英文目录文件不存在")

    with open(CATALOG_EN_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:  # 让报错说清楚是哪一行，别只说 500
            raise CatalogEnError(f"英文目录不是合法 JSON：{exc}\n（{CATALOG_EN_PATH}）") from exc

    if not isinstance(data, dict):
        _fail("英文目录顶层必须是对象")

    for section in _SECTIONS:
        if section not in data or not isinstance(data[section], dict):
            _fail(f"英文目录缺少分节 {section}（或它不是对象）")
        if not data[section]:
            _fail(f"英文目录的 {section} 是空的")
        for entry_id, entry in data[section].items():
            if entry_id.startswith("_"):
                _fail(
                    f"{section} 里出现了下划线键 {entry_id!r}。说明块只能写在顶层 {_META_KEY} 里——"
                    "分节里一旦有非条目键，id 集断言就得开始做过滤，而会过滤的断言迟早漏掉真条目"
                )
            if not isinstance(entry, dict):
                _fail(f"{section}.{entry_id} 必须是对象")
            for field, value in entry.items():
                if isinstance(value, str):
                    if not value.strip():
                        _fail(f"{section}.{entry_id}.{field} 是空串")
                    _assert_no_cjk(section, entry_id, field, value)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if not isinstance(item, str) or not item.strip():
                            _fail(f"{section}.{entry_id}.{field}[{i}] 不是非空字符串")
                        _assert_no_cjk(section, entry_id, f"{field}[{i}]", item)

    _cache.update(data)
    return _cache


def _require_same_ids(section: str, zh_ids: Iterable[str]) -> Dict[str, Any]:
    """英文 JSON 的 id 集必须与中文源逐一对应。缺一个就启动失败。"""
    catalog = load_catalog_en()
    en = catalog[section]
    zh = set(zh_ids)
    missing = zh - set(en)
    extra = set(en) - zh
    if missing or extra:
        _fail(
            f"{section} 的英文条目与中文源对不上："
            f"缺英文（会静默显示中文）{sorted(missing)}；"
            f"多出的英文（中文源里没有这个 id，多半是改名后没跟）{sorted(extra)}"
        )
    return en


def _require_fields(section: str, entry_id: str, entry: Mapping[str, Any], fields: Iterable[str]) -> None:
    for field in fields:
        if field not in entry:
            _fail(f"{section}.{entry_id} 缺字段 {field}")


def merge_task_types_en(task_types: Dict[str, Dict[str, Any]]) -> None:
    """把英文并进 TASK_TYPES 的同级键。就地改，import 期调用一次。

    `stance_labels_en` 与中文 `stance_enum` **必须等长**：这两个列表是按下标配对的，
    长度不等意味着某个立场没有英文标签，而按下标取值时它会静默取到隔壁那个立场的词
    ——界面上是一句通顺的英文，说的是相反的意思。
    """
    en = _require_same_ids("task_types", task_types)
    for task_type, info in task_types.items():
        entry = en[task_type]
        _require_fields("task_types", task_type, entry, ("name", "description", "stance_labels"))
        labels = entry["stance_labels"]
        stance_enum = list(info["stance_enum"])
        if len(labels) != len(stance_enum):
            _fail(
                f"task_types.{task_type}.stance_labels 有 {len(labels)} 个，"
                f"而 stance_enum 有 {len(stance_enum)} 个（{stance_enum}）。"
                "这两个列表按下标配对，长度不等会让某个立场显示成隔壁那个立场的词"
            )
        if len(set(labels)) != len(labels):
            _fail(f"task_types.{task_type}.stance_labels 有重复项 {labels}，立场词重复等于把两个立场画成一个")
        info["name_en"] = entry["name"]
        info["description_en"] = entry["description"]
        info["stance_labels_en"] = list(labels)


def merge_review_modes_en(review_modes: Dict[str, Dict[str, Any]]) -> None:
    """把英文并进 REVIEW_MODES 的同级键。

    只并 `description_en`：模式名（Quick / Standard / Full）的 owner 是前端
    `enum.mode_badge`，后端 REVIEW_MODES 本来就没有 name 字段。
    这里再造一份英文名就是给同一个词立第二个 owner，而两个 owner 必然漂移。
    """
    en = _require_same_ids("review_modes", review_modes)
    for mode, config in review_modes.items():
        entry = en[mode]
        _require_fields("review_modes", mode, entry, ("description",))
        config["description_en"] = entry["description"]


def assert_skills_en(skill_ids: Iterable[str]) -> None:
    en = _require_same_ids("skills", skill_ids)
    for skill_id, entry in en.items():
        _require_fields("skills", skill_id, entry, ("name", "description"))


def assert_persona_packs_en(pack_ids: Iterable[str]) -> None:
    en = _require_same_ids("persona_packs", pack_ids)
    for pack_id, entry in en.items():
        _require_fields("persona_packs", pack_id, entry, ("name", "description"))


def assert_pack_categories_en(category_ids: Iterable[str]) -> None:
    en = _require_same_ids("pack_categories", category_ids)
    for cat_id, entry in en.items():
        _require_fields("pack_categories", cat_id, entry, ("name",))


def assert_catalog_en_complete(
    *,
    task_type_ids: Iterable[str],
    review_mode_ids: Iterable[str],
    skill_ids: Iterable[str],
    pack_ids: Iterable[str],
    pack_category_ids: Iterable[str],
) -> None:
    """五个分节一起核对。测试用这一条就够，服务层按分节分别调用（时机不同）。"""
    _require_same_ids("task_types", task_type_ids)
    _require_same_ids("review_modes", review_mode_ids)
    assert_skills_en(skill_ids)
    assert_persona_packs_en(pack_ids)
    assert_pack_categories_en(pack_category_ids)


def skill_en(skill_id: str) -> Dict[str, str]:
    """技能的英文条目。查不到直接抛——import 期已经核对过 id 集，
    这里还查不到说明有人绕过注册表凭空造了个 skill_type。"""
    en = load_catalog_en()["skills"]
    if skill_id not in en:
        _fail(f"技能 {skill_id!r} 没有英文条目")
    return {"name": en[skill_id]["name"], "description": en[skill_id]["description"]}


def pack_en(pack_id: str) -> Dict[str, str]:
    en = load_catalog_en()["persona_packs"]
    if pack_id not in en:
        _fail(f"人格包 {pack_id!r} 没有英文条目")
    return {"name": en[pack_id]["name"], "description": en[pack_id]["description"]}


def pack_category_name_en(category_id: str) -> str:
    en = load_catalog_en()["pack_categories"]
    if category_id not in en:
        _fail(f"人格包分类 {category_id!r} 没有英文标题")
    return en[category_id]["name"]


def task_type_stance_labels_en(task_type: str) -> List[str]:
    en = load_catalog_en()["task_types"]
    if task_type not in en:
        _fail(f"任务类型 {task_type!r} 没有英文条目")
    return list(en[task_type]["stance_labels"])
