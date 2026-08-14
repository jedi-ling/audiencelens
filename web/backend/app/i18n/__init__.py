# -*- coding: utf-8 -*-
"""后端 i18n 包。当前只有一件事：目录数据的英文事实源（D4）。

这里**不做语言协商**。没有 lang 参数、没有 Accept-Language 分支——
协商会让同一个 URL 对不同客户端返回不同值，而 admin 后台与用户前端共用同一批端点，
运维在后台看到的语言会取决于他浏览器的头。所以中英同时发，客户端自己挑。
"""

from app.i18n.catalog_en import (  # noqa: F401
    CATALOG_EN_PATH,
    CatalogEnError,
    assert_catalog_en_complete,
    load_catalog_en,
    merge_review_modes_en,
    merge_task_types_en,
    pack_category_name_en,
    pack_en,
    skill_en,
)
