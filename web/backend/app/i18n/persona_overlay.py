# -*- coding: utf-8 -*-
"""人格**表述层** overlay 的加载与合并（I18N_CONTRACT 10.3 / 10.3.1）。

做什么：把 `src/personas/en-US/<pack>.yaml` 里的英文表述合并成人格记录的同级键
（`archetype_en` / `identity_summary_en` / `motivations_en` / …），与目录英文（D4）
同一个口径——中英一起发，端点不协商、不加 `lang` 参数。

**身份字段一个都不碰。** 张伟在英文模式下仍叫张伟，这是 10.3 的终局结论不是本期取舍：
  · `region` / `age_range` 会被 `aggregator._panel_audience_profiles` 拼进报告的
    `recruit_types`，那段代码的口径是「可据此筛选同类真人受访者」——把「林岚 / 中国华东」
    改成「Emily / 北美」，报告就在向英文用户断言一个从未建模过的受众，而用户会照着去招人。
  · `behavior_profile` 的值是 `panel_selector.LEVEL` 的键（很低/低/中/高/很高），
    翻了直接 KeyError 硬崩（`panel_selector.py:25-31` 的注释记录过那次崩溃）。
所以禁翻键在这里是**机械卡死**：overlay 里出现一个就抛错，不是警告、不是跳过。

为什么所有异常都往外抛、一次都不回落中文：
回落的表现是英文界面里混着中文人设——接口 200、页面照渲染、日志一片干净，
只有英文用户看得见。那正是纪律 2 要消灭的形态。缺译要么被 import 期/测试拦住，
要么显式报错，不许有第三种结局。

引擎不读这里：`review_service` 把 `src/personas/<pack>.yaml` 的**路径**直接交给
`runner.cli.run_panel`（review_service.py:108-114），走文件而不是本模块的缓存。
所以这些 `_en` 键只活在展示链路上，不会漏进提示词，也不会改变任何评审结论——
这正是 10.3 第 2 条（身份不驱动判断）要求的边界。
"""

import os
from typing import Any, Dict, List, Mapping, Tuple

import yaml

from app.i18n.catalog_en import contains_cjk

# 与 app/services/__init__.py 的 PERSONAS_DIR 必须是同一个目录。
# 两处各算一遍路径是重复而不是冗余，所以有一条测试把它们钉在一起
# （test_persona_overlay.py::test_overlay_root_is_the_same_personas_dir_as_services）——
# 算岔了的表现是「overlay 读不到 → 英文人设静默缺失」，没有任何报错。
PERSONAS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "src", "personas")
)

# 本期只有 en-US 一种 overlay。落到第三种语言时这张表和后缀一起扩，
# 而不是在调用点写 `if locale == 'en-US'` ——那会让新增语言变成全站搜索替换。
SUPPORTED_OVERLAY_LOCALES = ("en-US",)

# locale → 同级键后缀。与目录英文的 `name_en` 同形（D4 接受的代价：
# 落到第三种语言时字段名会难看，届时统一重构成嵌套，不在这里提前发明）。
_LOCALE_SUFFIX = {"en-US": "_en"}

# 允许本地化的键（10.3 冻结的闭集）。不在这张表里的键一律不许进 overlay：
# 闭集的意义是「新增一个可翻字段」必须是一次显式决定，而不是某个 agent 顺手多写一行。
TRANSLATABLE_KEYS = frozenset(
    {
        # 10.3（推翻早期裁决后）新增：纯 UI 展示层的罗马音译名，与识别字段
        # `name` 是两个字段。`name` 继续是 recruit_types / 引擎 / persona_outputs
        # 落库的唯一事实源，一个字不动；`display_name` 只活在展示链路上。
        # 隔离由 test_persona_overlay.py 的
        # test_display_name_never_reaches_recruit_types_or_prompt 机械卡死。
        "display_name",
        "archetype",
        "identity_summary",
        "motivations",
        "likes",
        "dislikes",
        "decision_rules",
        "quit_triggers",
        "continue_triggers",
        "first_scan_focus",
        "review_output",
    }
)

# 禁翻键（10.3 点名）。前四个是身份、后面几个是会被代码当**键**用的值。
FORBIDDEN_KEYS = frozenset(
    {
        "id",
        "name",
        "gender",
        "age_range",
        "region",
        "language",
        "mbti",
        "model_hint",
        "task_affinity",
        "behavior_profile",
        "gaming_profile",
    }
)

# 10.3.1 规定的文件外壳。多一个键少一个键都算形状不对：
# 形状留白的后果本仓已经吃过一次——三个并行 agent 写出三种外壳，加载器被迫同时认三种。
_REQUIRED_TOP_KEYS = ("version", "locale", "panel_id", "persona_overlays")


class PersonaOverlayError(RuntimeError):
    """overlay 与人格源对不上。故意用会把调用链炸穿的异常，见模块头。"""


_cache = {}  # type: Dict[Tuple[str, str], Dict[str, Dict[str, Any]]]


def _fail(msg, path):
    # type: (str, str) -> None
    raise PersonaOverlayError("{}\n（overlay 文件：{}）".format(msg, path))


def overlay_dir(locale="en-US"):
    # type: (str) -> str
    if locale not in SUPPORTED_OVERLAY_LOCALES:
        raise PersonaOverlayError(
            "没有 {!r} 的人格 overlay。当前只有 {}——".format(locale, list(SUPPORTED_OVERLAY_LOCALES))
            + "这里不做「最接近的语言」匹配：匹配到别的语言就是静默换语种，与缺译一样看不出来"
        )
    return os.path.join(PERSONAS_DIR, locale)


def overlay_path(pack_id, locale="en-US"):
    # type: (str, str) -> str
    return os.path.join(overlay_dir(locale), "{}.yaml".format(pack_id))


def _check_leaf(path, pack_id, persona_id, field, value):
    # type: (str, str, str, str, Any) -> None
    """叶子值的形状与「是不是真的翻了」。

    空串和中文都按硬失败处理：两者长得都和「翻好了」一模一样——字段在、断言绿，
    只有英文用户看得见那行中文（或那个空白）。
    """
    if not isinstance(value, str) or not value.strip():
        _fail("{}.{}.{} 不是非空字符串：{!r}".format(pack_id, persona_id, field, value), path)
    if contains_cjk(value):
        _fail(
            "{}.{}.{} 里有中文字符，这是照抄中文源的占位而不是英文表述：{!r}".format(
                pack_id, persona_id, field, value
            ),
            path,
        )


def load_overlay(pack_id, source_panel_id, locale="en-US"):
    # type: (str, str, str) -> Dict[str, Dict[str, Any]]
    """读一个包的 overlay，逐条校形状，返回 `{persona_id: {字段: 英文}}`。

    `source_panel_id` 传的是**源 yaml 的 panel_id**，必须与 overlay 里的逐字相等。
    这是唯一能机械发现「overlay 抄串了包」的手段：overlay 内容全是英文散文，
    人眼看不出 family-casual 的文件里混进了 mobile-f2p 的条目（10.3.1）。
    """
    key = (pack_id, locale)
    if key in _cache:
        return _cache[key]

    path = overlay_path(pack_id, locale)
    if not os.path.isfile(path):
        _fail(
            "人格包 {!r} 没有 {} overlay。缺 overlay 不是「暂时没翻」，"
            "它的实际表现是英文界面上这一包人设整段是中文，而且没有任何报错".format(pack_id, locale),
            path,
        )

    with open(path, "r", encoding="utf-8") as f:
        try:
            doc = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            # 带上原始异常：YAML 报错里有行号，只说「读不了」会让人去翻整份文件
            raise PersonaOverlayError("overlay 不是合法 YAML：{}\n（{}）".format(exc, path)) from exc

    if not isinstance(doc, dict):
        _fail("overlay 顶层必须是 10.3.1 规定的对象（version / locale / panel_id / persona_overlays）", path)

    if "personas" in doc:
        _fail(
            "overlay 里出现了 `personas:`。源文件的 personas 是**完整人格记录的列表**，"
            "overlay 是以 id 为键的 mapping，容器必须叫 `persona_overlays`（10.3.1）——"
            "同名不同形状是最容易看错的组合",
            path,
        )

    unknown = set(doc) - set(_REQUIRED_TOP_KEYS)
    missing = [k for k in _REQUIRED_TOP_KEYS if k not in doc]
    if missing or unknown:
        _fail(
            "overlay 顶层形状不对（10.3.1）：缺 {}；多出 {}".format(missing, sorted(unknown)),
            path,
        )

    if doc["locale"] != locale:
        _fail("overlay 自称 locale={!r}，但它放在 {} 目录下".format(doc["locale"], locale), path)

    if doc["panel_id"] != source_panel_id:
        _fail(
            "overlay 的 panel_id 是 {!r}，源包是 {!r}——这两个必须逐字相等，"
            "对不上说明这份 overlay 抄的是另一个包（10.3.1）".format(doc["panel_id"], source_panel_id),
            path,
        )

    overlays = doc["persona_overlays"]
    if not isinstance(overlays, dict) or not overlays:
        _fail("persona_overlays 必须是非空 mapping（键是人格 id）", path)

    for persona_id, entry in overlays.items():
        if not isinstance(entry, dict) or not entry:
            _fail("{} 的 overlay 条目必须是非空对象".format(persona_id), path)

        banned = sorted(set(entry) & FORBIDDEN_KEYS)
        if banned:
            _fail(
                "{} 的 overlay 里出现禁翻键 {}（10.3）。"
                "身份字段会被拼进报告的 recruit_types，用户照着去招真人受访者；"
                "behavior_profile 的值是 panel_selector.LEVEL 的键，翻了直接 KeyError 硬崩".format(
                    persona_id, banned
                ),
                path,
            )

        outside = sorted(set(entry) - TRANSLATABLE_KEYS)
        if outside:
            _fail(
                "{} 的 overlay 里有闭集之外的键 {}（10.3 允许本地化的只有 {}）。"
                "要加新字段就改 TRANSLATABLE_KEYS，这必须是一次显式决定".format(
                    persona_id, outside, sorted(TRANSLATABLE_KEYS)
                ),
                path,
            )

        for field, value in entry.items():
            if field == "review_output":
                if not isinstance(value, dict) or not value:
                    _fail("{}.review_output 必须是非空对象".format(persona_id), path)
                for sub, sub_value in value.items():
                    if isinstance(sub_value, list):
                        if not sub_value:
                            _fail("{}.review_output.{} 是空列表".format(persona_id, sub), path)
                        for i, item in enumerate(sub_value):
                            _check_leaf(path, pack_id, persona_id, "review_output.{}[{}]".format(sub, i), item)
                    else:
                        _check_leaf(path, pack_id, persona_id, "review_output.{}".format(sub), sub_value)
            elif isinstance(value, list):
                if not value:
                    _fail("{}.{} 是空列表".format(persona_id, field), path)
                for i, item in enumerate(value):
                    _check_leaf(path, pack_id, persona_id, "{}[{}]".format(field, i), item)
            else:
                _check_leaf(path, pack_id, persona_id, field, value)

    _cache[key] = overlays
    return overlays


def _merge_one(path, pack_id, persona, entry, suffix):
    # type: (str, str, Mapping[str, Any], Mapping[str, Any], str) -> Dict[str, Any]
    persona_id = persona.get("id", "<无 id>")
    merged = dict(persona)
    for field, value in entry.items():
        if field == "display_name":
            # `display_name` 是 10.3（推翻早期裁决后）新增的纯展示字段，
            # 它不是任何源字段的翻译——源人格从来只有 `name`，从未有过
            # `display_name` 这个键。所以它是这张表里唯一一个**允许在源侧
            # 不存在**的 overlay 字段，故意在这里显式分支写出来，而不是把
            # 下面「源里没这个字段」的通用校验放宽掉：放宽会连带放过
            # 「overlay 抄错了人格」这种真正的错误，显式分支才不是静默兜底。
            if not isinstance(value, str) or not value.strip():
                _fail("{}.display_name 必须是非空字符串".format(persona_id), path)
            merged[field + suffix] = value
            continue

        if field not in persona:
            _fail(
                "{}.{} 在源人格里根本没有这个字段——overlay 不能凭空多出一层内容，"
                "多半是抄了别的人格".format(persona_id, field),
                path,
            )
        source_value = persona[field]

        if field == "review_output":
            if not isinstance(source_value, dict):
                _fail("{}.review_output 源侧不是对象，overlay 却给了对象".format(persona_id), path)
            unknown = sorted(set(value) - set(source_value))
            if unknown:
                _fail(
                    "{}.review_output 的 {} 在源侧不存在".format(persona_id, unknown),
                    path,
                )
        elif isinstance(source_value, list):
            if not isinstance(value, list):
                _fail("{}.{} 源侧是列表，overlay 侧不是".format(persona_id, field), path)
            # 逐条对齐只在源有多条时强制：源是**单条**时允许拆开——中文里
            # "看懂、做到、不要丢脸" 这种顿号串在英文里拆成三条是正常译法，
            # 而源有 5 条 overlay 只有 3 条就是漏译，那种漏在界面上完全看不出来。
            if len(source_value) > 1 and len(value) != len(source_value):
                _fail(
                    "{}.{} 源侧 {} 条、overlay 侧 {} 条。源是多条时必须逐条对齐，"
                    "少的那几条在英文界面上不会留下任何痕迹".format(
                        persona_id, field, len(source_value), len(value)
                    ),
                    path,
                )
        elif not isinstance(value, str):
            _fail("{}.{} 源侧是文本，overlay 侧是 {}".format(persona_id, field, type(value).__name__), path)

        merged[field + suffix] = value
    return merged


def merge_persona_overlay(pack_id, personas, source_panel_id, locale="en-US"):
    # type: (str, List[dict], str, str) -> List[dict]
    """把 overlay 并成同级键，返回**新的**人格列表（不改传进来的 dict）。

    覆盖率是逐一对应的：overlay 的 id 集必须与源包的 id 集完全相等。
    少一个 = 那个人在英文界面上整条是中文；多一个 = overlay 抄了别的包（或源里删了人没跟）。
    两种都没有任何运行期症状，所以只能在这里拦。
    """
    if locale not in SUPPORTED_OVERLAY_LOCALES:
        raise PersonaOverlayError("没有 {!r} 的人格 overlay，支持的是 {}".format(locale, list(SUPPORTED_OVERLAY_LOCALES)))
    suffix = _LOCALE_SUFFIX[locale]

    if not personas:
        # 源包读出来是空的（文件损坏或真的没人）。这里不去读 overlay：
        # 空包本身就是另一个缺陷，用「overlay 覆盖率不匹配」去报它只会指错方向。
        # 「每个源包都必须有完整 overlay」由 test_persona_overlay.py 直读文件保证，
        # 那条断言不经过本函数，吞不掉。
        return list(personas)

    if not isinstance(source_panel_id, str) or not source_panel_id.strip():
        raise PersonaOverlayError(
            "人格包 {!r} 的源 yaml 没给 panel_id（拿到的是 {!r}）。"
            "没有它就没法证明 overlay 不是抄的别的包，而这里绝不用 pack_id 兜底——"
            "兜底会让防抄串校验变成一次必然通过的空转".format(pack_id, source_panel_id)
        )

    path = overlay_path(pack_id, locale)
    overlays = load_overlay(pack_id, source_panel_id, locale)

    source_ids = [p.get("id") for p in personas]
    missing = [pid for pid in source_ids if pid not in overlays]
    extra = [pid for pid in overlays if pid not in set(source_ids)]
    if missing or extra:
        _fail(
            "{} 的 overlay 与源包人数对不上：缺英文（这些人在英文界面上是中文）{}；"
            "多出的英文（源包里没有这个 id）{}".format(pack_id, missing, extra),
            path,
        )

    return [_merge_one(path, pack_id, p, overlays[p["id"]], suffix) for p in personas]


def invalidate_cache():
    # type: () -> None
    """给 PersonaService.invalidate_cache() 用：人格库热重载时 overlay 也要跟着重读，
    否则改了 overlay 却还在发旧英文，而这种不一致查起来会一路查到前端去。"""
    _cache.clear()
