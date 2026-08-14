# -*- coding: utf-8 -*-
"""后端 i18n 包。两件事：目录数据的英文事实源（D4）+ 人格表述层 overlay（10.3）。

这里**不做语言协商**。没有 lang 参数、没有 Accept-Language 分支——
协商会让同一个 URL 对不同客户端返回不同值，而 admin 后台与用户前端共用同一批端点，
运维在后台看到的语言会取决于他浏览器的头。所以中英同时发，客户端自己挑。

两个模块的分工：
  · `catalog_en` —— 任务类型 / 评审模式 / 技能 / 人格包 / 分类，值来自旁挂的
    `catalog.en-US.json`，在 import 期合并成 `name_en` 等同级键。
  · `persona_overlay` —— 人格的**表述层**，值来自 `src/personas/en-US/*.yaml`，
    合并成 `archetype_en` 等同级键。身份字段一个都不碰（10.3）。
"""

from app.i18n.catalog_en import (  # noqa: F401
    CATALOG_EN_PATH,
    CatalogEnError,
    assert_catalog_en_complete,
    assert_pack_categories_en,
    assert_persona_packs_en,
    assert_skills_en,
    contains_cjk,
    load_catalog_en,
    merge_review_modes_en,
    merge_task_types_en,
    pack_category_name_en,
    pack_en,
    skill_en,
    task_type_stance_labels_en,
)
from app.i18n.persona_overlay import (  # noqa: F401
    FORBIDDEN_KEYS,
    SUPPORTED_OVERLAY_LOCALES,
    TRANSLATABLE_KEYS,
    PersonaOverlayError,
    load_overlay,
    merge_persona_overlay,
    overlay_path,
)
