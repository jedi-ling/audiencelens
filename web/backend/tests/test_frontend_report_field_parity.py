"""钉住 report 里"新字段"的名字在引擎与前端之间对得上。

背景：wave2 审计给 ReportPage.tsx 的 RealReport 类型补上了 shared_concerns /
recruit_types_basis / panel_selection / min_personas_for_agreement 等字段，
让页面能消费引擎新产出的内容。补完当时留了一句原话没兑现：

    "前端对新渲染行为零测试钉住：report 字段全 optional，引擎改名时
    typecheck 仍绿、区块静默消失。需要一条前后端字段名对齐测试。"

为什么这是个真问题，不是杞人忧天：RealReport 里的每个字段都是 `?:` 可选的
（因为 report 来自后端 JSON 列，运行时形状不可尽信，这个可选本身没错）。
可选带来的副作用是——引擎那边把某个 key 改了名字，前端这边一个字都不用改，
`npm run typecheck` 照样是绿的，`npm run build` 照样成功，只有打开报告页
亲眼盯着那一块才会发现它突然不见了。这条测试就是那双"亲眼盯着"的眼睛：
直接读两边的源码，比对字符串字面量，改名不同步就必须在这里先红一次。

风格与 test_frontend_report_scale_parity.py（同类"源码断言"）、
test_task_type_parity.py（先例）一致：前端没有测试运行器，引入 vitest
为几条字符串常量卡口不合算，比对源码文本反而是最贴近事实源的做法。
"""

import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FRONTEND_SRC = os.path.join(REPO_ROOT, "web", "frontend", "src")
REPORT_PAGE = os.path.join(FRONTEND_SRC, "pages", "ReportPage.tsx")
AGGREGATOR_PY = os.path.join(REPO_ROOT, "src", "runner", "aggregator.py")
CLI_PY = os.path.join(REPO_ROOT, "src", "runner", "cli.py")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _ts_interface_body(source: str, interface_name: str) -> str:
    """取一个 TS interface 的花括号内文本。用括号计数而不是非贪婪正则截到
    第一个 `}`——这些 interface 内部嵌套了别的花括号（对象类型字段、
    行内 union），非贪婪匹配会在第一层嵌套就截断，看起来像字段缺失。"""
    marker = f"interface {interface_name}"
    start = source.find(marker)
    assert start != -1, f"ReportPage.tsx 里找不到 interface {interface_name}"
    brace_start = source.index("{", start)
    depth = 0
    for i in range(brace_start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace_start + 1 : i]
    raise AssertionError(f"interface {interface_name} 的花括号不闭合")


# compute_consensus 产出但前端类型故意不接的字段——都在源码里有对应的
# "为什么不接"注释，不是遗漏。全量 diff 会把这些也算作缺口，误伤有意的设计：
#   stance_distribution —— aggregator.py 的注释明说前端自己按 persona_notes
#   重算一遍，两套口径故意并存（“引擎侧改了阈值前端不会跟着变”是已知代价，
#   不是本条测试要卡的东西）。
CONSENSUS_KNOWN_UNRENDERED = {"stance_distribution"}


def test_consensus_fields_match_compute_consensus():
    """compute_consensus 返回的每个 key，RealReport.consensus 都要能接住
    （已知有意不接的字段见 CONSENSUS_KNOWN_UNRENDERED）。"""
    agg = _read(AGGREGATOR_PY)
    # 用 compute_consensus 空面板分支的 return dict 当事实源：那里把全部
    # 字段列了一遍且没有条件分支，比非空分支的 return 更适合当"完整清单"用。
    body = agg.split("def compute_consensus", 1)[1]
    empty_return = re.search(r"if not persona_outputs:\s*return \{(.*?)\}", body, re.S)
    assert empty_return, "compute_consensus 的空面板 return 形状变了，请同步这条测试"
    engine_keys = set(re.findall(r'"(\w+)":', empty_return.group(1)))
    assert engine_keys, "没从 compute_consensus 里解析出任何字段名，正则可能失效了"

    report = _read(REPORT_PAGE)
    consensus_block = re.search(r"consensus\?:\s*\{(.*?)\}\s*\|\s*null", report, re.S)
    assert consensus_block, "RealReport.consensus 的类型声明形状变了"
    fe_keys = set(re.findall(r"(\w+)\??:", consensus_block.group(1)))

    missing = engine_keys - fe_keys - CONSENSUS_KNOWN_UNRENDERED
    assert not missing, (
        f"compute_consensus 产出了 {missing}，但 RealReport.consensus 没有声明，"
        "也不在已知的故意不接清单里——typecheck 不会报错，页面会静默少一块"
    )

    # 反向对照：已知不接的字段名必须还真的存在于引擎产出里。字段被引擎删掉后
    # 这条常量会变成死条目，掩盖"其实早就没有例外可言"的事实。
    stale_exclusions = CONSENSUS_KNOWN_UNRENDERED - engine_keys
    assert not stale_exclusions, (
        f"CONSENSUS_KNOWN_UNRENDERED 里的 {stale_exclusions} 引擎已经不产出了，"
        "请把这条从清单里删掉"
    )


def test_shared_concern_fields_match_engine():
    """shared_concerns 数组里每一条的字段，RealSharedConcern 要能接住。"""
    agg = _read(AGGREGATOR_PY)
    concern_literal = re.search(
        r'shared_concerns\.append\(\{(.*?)\}\)', agg, re.S
    )
    assert concern_literal, "aggregator.py 里构造 shared_concerns 单条明细的写法变了"
    engine_keys = set(re.findall(r'"(\w+)":', concern_literal.group(1)))
    assert engine_keys, "没解析出 shared_concerns 单条明细的字段名"

    report = _read(REPORT_PAGE)
    fe_body = _ts_interface_body(report, "RealSharedConcern")
    fe_keys = set(re.findall(r"(\w+)\??:", fe_body))

    missing = engine_keys - fe_keys
    assert not missing, (
        f"shared_concerns 每条明细产出了 {missing}，但 RealSharedConcern 没有声明"
    )


def test_next_human_test_fields_match_engine():
    """next_human_test 的字段，RealReport.next_human_test 要能接住。

    这里尤其容易漂：recruit_types 这个名字被人重新理解过一次
    （从"招募建议"改成"本次面板的真实受众特征串"，标题文案跟着改了），
    如果哪天连字段名也一起改了，前端会安安静静地不显示这一块。
    """
    agg = _read(AGGREGATOR_PY)
    nht_literal = re.search(
        r'"next_human_test":\s*\{(.*?)\},\s*\n\s*"cross_examination"', agg, re.S
    )
    assert nht_literal, "aggregator.py 里 next_human_test 的构造形状变了"
    engine_keys = set(re.findall(r'"(\w+)":', nht_literal.group(1)))
    assert engine_keys == {"suggested_tasks", "recruit_types", "recruit_types_basis", "next_materials"}, (
        f"next_human_test 的字段集合变成了 {engine_keys}，"
        "请同步这条测试并确认前端也跟着改了"
    )

    report = _read(REPORT_PAGE)
    nht_block = re.search(r"next_human_test\?:\s*\{(.*?)\}\s*\|\s*null", report, re.S)
    assert nht_block, "RealReport.next_human_test 的类型声明形状变了"
    fe_keys = set(re.findall(r"(\w+)\??:", nht_block.group(1)))

    missing = engine_keys - fe_keys
    assert not missing, f"next_human_test 产出了 {missing}，但前端类型没有声明"


# panel_selection 里前端类型故意不接的字段：
#   truncated_by_mode —— 已经作为可读文案拼进了同一个字典的 notice 里
#   （cli.py 里"因评审模式的人数上限被截断"那句），前端接住 notice 字符串
#   就等于间接展示了这份信息；结构化 id 列表目前没有专门的 UI 消费点。
PANEL_SELECTION_KNOWN_UNRENDERED = {"truncated_by_mode"}


def test_panel_selection_fields_match_engine():
    """panel_selection 的字段，RealPanelSelection 要能接住
    （已知有意不接的字段见 PANEL_SELECTION_KNOWN_UNRENDERED）。

    这一块的历史事故最具体：matched 曾经在截断/预检**之前**就算好了，
    点名 5 人但模式限 3 人时，页面会说 5 个都参与了。字段名对不上的话，
    连"曾经修好的这个坑有没有可能又悄悄裂开"都验证不到。
    """
    cli = _read(CLI_PY)
    ps_literal = re.search(r'report\["panel_selection"\]\s*=\s*\{(.*?)\}', cli, re.S)
    assert ps_literal, "cli.py 里 panel_selection 的构造形状变了"
    engine_keys = set(re.findall(r'"(\w+)":', ps_literal.group(1)))
    assert "matched" in engine_keys and "missing" in engine_keys and "notice" in engine_keys, (
        f"panel_selection 至少要有 matched/missing/notice，实际是 {engine_keys}"
    )

    report = _read(REPORT_PAGE)
    fe_body = _ts_interface_body(report, "RealPanelSelection")
    fe_keys = set(re.findall(r"(\w+)\??:", fe_body))

    missing = engine_keys - fe_keys - PANEL_SELECTION_KNOWN_UNRENDERED
    assert not missing, f"panel_selection 产出了 {missing}，但 RealPanelSelection 没有声明，也不在已知的故意不接清单里"

    stale_exclusions = PANEL_SELECTION_KNOWN_UNRENDERED - engine_keys
    assert not stale_exclusions, (
        f"PANEL_SELECTION_KNOWN_UNRENDERED 里的 {stale_exclusions} 引擎已经不产出了，"
        "请把这条从清单里删掉"
    )


def test_min_personas_for_agreement_is_actually_rendered():
    """字段声明了不等于渲染了——补一道"真的用在了 JSX 里"的检查。

    前三条测试只能证明"类型接得住"，接住了但没人在 JSX 里读它，
    页面上依然什么都不会显示。这条把"判定口径"这句话在报告页里出现
    的事实钉住，防止类型补了、渲染却被后续重构悄悄删掉。
    """
    report = _read(REPORT_PAGE)
    assert report.count("min_personas_for_agreement") >= 2, (
        "min_personas_for_agreement 只在类型声明里出现，没有在 JSX 里真的读它、"
        "渲染出「判定口径：同一议题被 ≥K/N 位人格各自独立提出」这句话"
    )
