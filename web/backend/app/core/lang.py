"""语种定义与缺译标记 —— 后端唯一的语言事实源。

docs/I18N_CONTRACT.md §9.1 把这个模块列为「语种定义与缺译标记（后端唯一）」，
但它此前**从未被实现**：契约写着它存在、前端 `lib/types.ts` 为 `error.message_lang`
写好了完整的接收逻辑（还注明"本期后端恒给 zh-CN"），而后端的错误信封里
从来没有过这个字段——`message_lang` 在整个后端零命中。

后果不是崩溃：前端显式把 `undefined` 归为"老响应/语种未知"并走 D2 兜底分支。
真正的代价是**那套防止"英文界面混中文"的机制从来没有启用过**，前端永久跑在
兜底路径上。这与 `session_expired` 是同一类前后端契约漂移，只是方向相反——
那次是后端有码、前端类型缺；这次是文档和前端都有、后端没实现。

设计边界（与契约逐字对齐，别在这里自创）：
  · 语种标注**不是协商结果**，就是一句事实陈述：「这条 message 是中文」。
    前端据此决定"直接显示后端原文"还是"出前端译文、把后端原文降级成 detail"。
  · 缺译**绝不回落成另一种语言**——回落的表现是"英文界面里混中文且没人发现"，
    这正是契约 D8 点名禁止的。缺了就显式标记出来。
  · marker 形态与前端 `i18n/runtime.ts::missingMarker` 完全一致，
    这样一条 grep 就能同时覆盖前后端。
"""

from typing import Literal, Tuple

Lang = Literal["zh-CN", "en-US"]

SUPPORTED_LANGS: Tuple[Lang, ...] = ("zh-CN", "en-US")

DEFAULT_LANG: Lang = "zh-CN"

# 后端产出物（错误消息、报告正文）目前只有中文一种。
# 引擎侧英文链路就绪后再往这里加 "en-US" —— 在此之前多写一个值就是撒谎：
# 界面会以为可以要英文报告，而引擎根本产不出来。
SUPPORTED_REPORT_LANGS: Tuple[Lang, ...] = ("zh-CN",)

# 后端 message 的语种。当前所有 raise 点写的都是中文，所以这是一句事实陈述，
# 不是配置项——哪天真有英文错误消息了，是在 raise 那一侧标注，不是改这个默认值。
BACKEND_MESSAGE_LANG: Lang = "zh-CN"


def missing_marker(key: str, lang: Lang) -> str:
    """缺译时返回它，绝不回落成另一种语言。

    形态与前端完全一致（见 docs/I18N_CONTRACT.md D8）：
    一条 grep / 一条断言就能覆盖前后端两侧。
    """
    return f"⟦missing:{lang}:{key}⟧"
