"""钉住 Review 这个资源的四条序列化路径互相对得上。

这是 error_message/skill_degraded 那个 bug 的确切成因，值得单独一个文件守着。

病理复盘：这个产品的评审资源有**两条并存的读写路径**——
    写：AskPage / review-store → apiClient.ts → POST /api/v2/reviews（v2）
    读：ReportPage            → api.ts       → GET  /api/reviews/{id}（v1）
两条路径各自有独立的序列化实现（v1 是 pydantic 的 ReviewResponse，
v2 是 platform.py 里手写的 dict），也各自对应一个前端类型
（v1 → mock-data.ts 的 Review，v2 → types.ts 的 ReviewDetail）。

四份东西描述同一个数据库表，却没有任何机制保证它们一致。实际发生的事：
后端给 ReviewResponse 加了 error_message / skill_degraded 两个字段（还专门
写了注释说明"失败原因必须能被读到""静默降级是本仓库要根除的形状"），
但前端 v1 的 Review 类型没跟上——于是报告页永远读不到失败原因，
typecheck 全绿、build 成功、没有任何一条测试红，只有用户在真出错时
看到一份"没说为什么失败"的页面。

这条测试就是那个缺失的机制。它不试图消灭双路径（v1 的 23 条路由里只有 4 条
在 v2 有对应物，其余是 personas/task-types 这类只住在 v1 的参考数据端点，
搬家没有收益），只保证：**只要还是两条路径，它们就必须对得上账。**

比对策略是源码字符串匹配，与本仓已有的 parity 测试同一风格
（test_frontend_report_field_parity.py / test_frontend_share_field_parity.py）：
前端没有测试运行器，为几个字段名引入 vitest 不合算，读源码反而最贴近事实源。
"""

import io
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BACKEND = os.path.join(REPO_ROOT, "web", "backend")
FRONTEND_SRC = os.path.join(REPO_ROOT, "web", "frontend", "src")

SCHEMAS_PY = os.path.join(BACKEND, "app", "schemas", "__init__.py")
PLATFORM_PY = os.path.join(BACKEND, "app", "api", "platform.py")
MOCK_DATA_TS = os.path.join(FRONTEND_SRC, "lib", "mock-data.ts")
TYPES_TS = os.path.join(FRONTEND_SRC, "lib", "types.ts")


def _read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def _brace_body(source, start_index):
    """从 start_index 处的第一个 '{' 起，按计数取到配对的 '}'，返回中间文本。"""
    brace_start = source.index("{", start_index)
    depth = 0
    for i in range(brace_start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start + 1 : i]
    raise AssertionError("花括号不闭合")


def _pydantic_model_fields(source, model_name):
    """取一个 pydantic BaseModel 的字段名。只认顶层 `name: type` 声明，
    跳过注释和方法。"""
    marker = "class %s(BaseModel):" % model_name
    start = source.find(marker)
    assert start != -1, "schemas 里找不到 %s" % model_name
    # 到下一个顶层 class 为止
    nxt = source.find("\nclass ", start + len(marker))
    body = source[start:nxt if nxt != -1 else len(source)]
    return set(re.findall(r"^\s{4}(\w+)\s*:", body, re.M))


def _v2_detail_keys():
    """platform.py 里 GET /v2/reviews/{review_id} 手写返回体的键名。"""
    source = _read(PLATFORM_PY)
    anchor = source.find('@router.get("/v2/reviews/{review_id}")')
    assert anchor != -1, "platform.py 里找不到 v2 评审详情端点"
    ret = source.index("return {", anchor)
    body = _brace_body(source, ret)
    return set(re.findall(r'"(\w+)":', body))


def _ts_interface_keys(source, name):
    """按接口名精确取字段。

    这里必须是带词边界的正则而不是 source.find("interface " + name)：
    朴素 find 会被前缀相同的接口抢答——实测找 `Review` 时命中的是文件里
    更早出现的 `ReviewModeConfig`，于是解析出一组风马牛不相及的字段，
    测试报出"所有字段都缺失"这种一看就不对的结论（写这条测试时真踩了一次）。
    """
    m = re.search(r"interface %s\s*(?:<[^>]*>)?\s*(?:extends [^{]+)?\{" % re.escape(name), source)
    assert m, "找不到 interface %s" % name
    body = _brace_body(source, m.start())
    return set(re.findall(r"^\s*(\w+)\??:", body, re.M))


# ---------------------------------------------------------------------------
# 每条"故意不对齐"都必须在这里显式登记，并写明理由。
# 空着的话这些测试就成了"全量 diff"，会把有意的设计取舍也报成缺口；
# 登记在案则相反——它逼着每一次不对齐都是一个**被写下来的决定**。
# ---------------------------------------------------------------------------

# v1 ReviewResponse 有、v2 详情故意不回的字段
V1_ONLY = {
    # 用户自己上传的原始材料。v1 详情端点回它（那是用户自己的东西），
    # v2 的对话式链路不需要把它再吐回来一遍——AskPage 手上本来就有。
    "artifact_bundle",
    # v1 独有的整份 markdown 镜像与人格明细；v2 走 /v2/reviews/{id}/chat
    # 和报告里的 persona_notes 取，不在详情端点重复一份。
    "report_markdown",
    "persona_outputs",
    # v1 的 report_json 在 v2 里叫 report（见下面 FIELD_ALIASES）
    "report_json",
    # 高级技能降级说明。它不是 Review 表的列，由 v1 端点 model_copy 填入；
    # v2 在创建评审的响应里回（CreateReviewResponse.skill_degraded），
    # 不在详情端点重复。前端两处都读得到，见 test_v1_type_covers_backend_schema。
    "skill_degraded",
}

# v2 详情有、v1 ReviewResponse 没有的字段
V2_ONLY = set()

# 两边叫法不同但指同一个东西
FIELD_ALIASES = {"report_json": "report"}


def test_v1_and_v2_agree_on_review_fields():
    """两条后端序列化路径描述同一张表，字段集合的差异必须是登记在案的。"""
    v1 = _pydantic_model_fields(_read(SCHEMAS_PY), "ReviewResponse")
    v2 = _v2_detail_keys()
    assert v1, "没解析出 ReviewResponse 的字段，正则可能失效了"
    assert v2, "没解析出 v2 详情返回体的键，正则可能失效了"

    v1_normalized = {FIELD_ALIASES.get(f, f) for f in v1}
    v2_normalized = {FIELD_ALIASES.get(f, f) for f in v2}

    only_v1 = v1_normalized - v2_normalized - {FIELD_ALIASES.get(f, f) for f in V1_ONLY}
    assert not only_v1, (
        "v1 ReviewResponse 有 %s，v2 详情端点没有，且没登记在 V1_ONLY 里。"
        "要么给 v2 补上，要么在 V1_ONLY 里写明为什么不补——"
        "两条路径无声地长歪正是 error_message 那个 bug 的成因。" % only_v1
    )

    only_v2 = v2_normalized - v1_normalized - V2_ONLY
    assert not only_v2, (
        "v2 详情端点有 %s，v1 ReviewResponse 没有，且没登记在 V2_ONLY 里。"
        "走 v1 读评审的页面（ReportPage）会读不到这些字段。" % only_v2
    )


def test_v1_type_covers_backend_schema():
    """v1 后端 schema 的字段，前端 v1 类型（mock-data.ts 的 Review）都要声明。

    这条就是当初漏掉 error_message / skill_degraded 的那个口子。
    """
    backend = _pydantic_model_fields(_read(SCHEMAS_PY), "ReviewResponse")
    frontend = _ts_interface_keys(_read(MOCK_DATA_TS), "Review")

    missing = backend - frontend
    assert not missing, (
        "后端 v1 ReviewResponse 会返回 %s，但前端 mock-data.ts 的 Review 类型"
        "没有声明——走 api.ts::fetchReview 的页面（ReportPage 等）读不到这些字段，"
        "而 typecheck 不会报错。" % missing
    )


def test_v2_type_covers_backend_detail():
    """v2 详情端点返回的键，前端 v2 类型（types.ts 的 ReviewDetail）都要声明。"""
    backend = _v2_detail_keys()
    frontend = _ts_interface_keys(_read(TYPES_TS), "ReviewDetail")

    missing = backend - frontend
    assert not missing, (
        "v2 详情端点返回 %s，但前端 ReviewDetail 类型没有声明。" % missing
    )


def test_the_two_fields_that_bit_us_are_actually_read_not_just_declared():
    """反向对照：光在类型里声明不等于页面真的用了。

    这两个字段的价值全在"用户能看到"上——声明了却没人读，等于没修。
    所以这里直接断言报告页源码里真的引用了它们，不只是类型对齐。
    """
    report_page = _read(os.path.join(FRONTEND_SRC, "pages", "ReportPage.tsx"))

    assert "error_message" in report_page, (
        "ReportPage.tsx 没有任何一处引用 review.error_message——"
        "后端专门为『引擎写了半份报告又失败』这个场景准备了这个字段"
        "（见 schemas/__init__.py 上的注释），前端不读就等于这个兜底不存在。"
    )
    assert "skill_degraded" in report_page, (
        "ReportPage.tsx 没有引用 skill_degraded——高级技能/红队被降级这件事，"
        "用户过后从历史记录点进报告就再也看不到了。静默降级是本仓库明确要根除的形状。"
    )
