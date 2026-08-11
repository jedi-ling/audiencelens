"""钉住报告分享链接的公开字段白名单在后端与前端之间对得上。

功能完整性审查发现的 P2 缺口：`share_service.to_public_dict`（后端公开字段
白名单，见该文件顶部注释——安全边界，故意排除 user_id/费用/原始材料等）
与前端 `types.ts` 的 `SharedReport` 接口，当时手工核对是完全一致的，但
仓库里已有的"用后端源码断言前端字段对齐"这套模式（
test_frontend_report_field_parity.py、test_frontend_report_scale_parity.py）
没有覆盖到这两个新文件——现在字段对得上纯粹是巧合的时间点吻合，没有测试
守着，后续任何一边改字段都不会被自动拦下。

这条测试补的就是这个缺口。风格与 test_frontend_report_field_parity.py 一致：
直接读两边源码、比对字符串字面量，不引入前端测试运行器。

两个方向都要测，理由不对称：
  · 后端有、前端没声明的字段 —— 前端会读不到这个数据（功能性缺口，比如
    当初就是这样漏了 error_message/skill_degraded）。
  · 前端声明了、后端白名单里没有的字段 —— 更危险：意味着白名单本身被
    悄悄放宽了却没人注意到，是本条测试真正要卡住的安全边界。
"""

import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FRONTEND_SRC = os.path.join(REPO_ROOT, "web", "frontend", "src")
TYPES_TS = os.path.join(FRONTEND_SRC, "lib", "types.ts")
SHARE_SERVICE_PY = os.path.join(
    REPO_ROOT, "web", "backend", "app", "services", "share_service.py"
)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _ts_interface_top_level_keys(source: str, interface_name: str) -> set:
    """取一个 TS interface 顶层的字段名集合。用括号计数取花括号内文本，
    再只匹配缩进一层的 `key:`/`key?:` 行——避免把嵌套类型内部的字段名
    误当成顶层字段（这个接口目前没有嵌套对象字段，但写成通用的更安全）。"""
    marker = f"interface {interface_name}"
    start = source.find(marker)
    assert start != -1, f"types.ts 里找不到 interface {interface_name}"
    brace_start = source.index("{", start)
    depth = 0
    body = None
    for i in range(brace_start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                body = source[brace_start + 1 : i]
                break
    assert body is not None, f"interface {interface_name} 的花括号不闭合"
    return set(re.findall(r"^\s*(\w+)\??:", body, re.M))


def _to_public_dict_keys() -> set:
    """从 share_service.py 的 to_public_dict 函数体里提取 return 字典的
    顶层键名——直接读源码字符串字面量，不 import 模块执行（这个仓库里
    parity 测试一贯的做法，避免把"能不能跑起来"和"字段名对不对"两件事
    混进同一条断言里）。"""
    source = _read(SHARE_SERVICE_PY)
    marker = "def to_public_dict"
    start = source.find(marker)
    assert start != -1, "share_service.py 里找不到 to_public_dict 函数"
    return_start = source.index("return {", start)
    brace_start = source.index("{", return_start)
    depth = 0
    body = None
    for i in range(brace_start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                body = source[brace_start + 1 : i]
                break
    assert body is not None, "to_public_dict 的 return 字典花括号不闭合"
    return set(re.findall(r'"(\w+)":', body))


def test_shared_report_type_matches_public_whitelist_exactly():
    """双向核对，任何一边多出来的字段都要先在这里红一次。"""
    backend_keys = _to_public_dict_keys()
    assert backend_keys, "没从 to_public_dict 解析出任何字段名，正则可能失效了"

    frontend_source = _read(TYPES_TS)
    frontend_keys = _ts_interface_top_level_keys(frontend_source, "SharedReport")

    missing_in_frontend = backend_keys - frontend_keys
    assert not missing_in_frontend, (
        f"share_service.to_public_dict 产出了 {missing_in_frontend}，"
        "但前端 SharedReport 接口没有声明——SharedReportPage.tsx 会读不到这些字段，"
        "typecheck 不会报错，页面上静默少一块"
    )

    # 这个方向更要紧：前端声明了但后端白名单里没有的字段，意味着白名单本身
    # 被放宽过但没有同步——公开分享页面可能在等一个永远不会来的字段，
    # 或者（更该警惕的情形）曾经真的返回过这个字段、后来从白名单收紧掉了，
    # 前端类型却没跟着收紧，容易让人误以为这个字段现在还在公开视图里。
    extra_in_frontend = frontend_keys - backend_keys
    assert not extra_in_frontend, (
        f"前端 SharedReport 接口声明了 {extra_in_frontend}，"
        "但 share_service.to_public_dict 的白名单里没有这些字段——"
        "要么是前端类型该收紧，要么是白名单曾经放宽过没同步，两种情况都要去确认"
    )
