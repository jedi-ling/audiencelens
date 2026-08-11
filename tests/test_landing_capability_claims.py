"""落地页上"点名了具体机制"的能力声明，每一条都要在代码里找得到对应实现。

test_public_claims.py 只核对**数字类**声明（72 人格 / 14 任务类型 / 11 Pack /
2048 测试）。但落地页上真正在卖的不是数字，是机制——"证据三级标注""推断占比
超过 40% 会被标记""改票由代码判定，阈值写在开源配置里""身份与行为解耦"。
这些声明目前**没有任何自动核对**，全靠人工抽查。

为什么这是个真问题：这个仓库在这件事上翻过车。落地页曾经写过
"实时交叉质询 / ROUND 3 / 分歧度 / 说服力 / Δc +0.34"，而当时 cross_exam.py
返回的是 is_live_debate=False、vote_changes 恒空、delta 恒 0——文案描述的东西
一个都不存在。landing-body.html 里至今留着那段注释警告后人别写回来。
"红队对抗"那张卡也是同一类事故（引擎里没有红队模式）。

这条测试把"文案 → 代码事实源"的对应关系固化下来：
  · 文案还在，但代码里的实现没了 → 红（变成虚假宣传，正是历史上翻车的形态）
  · 代码还在，但文案改了措辞      → 红（提醒人确认新措辞是否仍然属实）

刻意**不**追求覆盖每一句话——散文式的营销语句无法机械核对，硬要覆盖只会
逼出一堆假断言。只钉那些点名了具体机制、能在代码里指出确切事实源的说法。

断言粒度：文案侧认关键短语，代码侧认关键标识符。都不认完整句子——
那样正常的措辞润色就会误报，测试很快会被当成噪音关掉。
"""

import io
import os
import re

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANDING_HTML = os.path.join(
    REPO_ROOT, "web", "frontend", "src", "pages", "landing", "landing-body.html"
)


def _read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def _landing():
    return _read(LANDING_HTML)


# (人类可读的声明名, 落地页里必须出现的关键短语, [(事实源文件, 必须出现的标识符), ...])
#
# 事实源用"文件 + 标识符"而不是行号：行号会随无关改动漂移，
# 那种测试红了之后第一反应是"改行号"而不是"想想是不是真出问题了"。
CLAIMS = [
    (
        "证据三级标注（direct / inferred / gap）",
        ["direct（直接观察）", "inferred（合理推断）", "gap（信息缺口）"],
        [("src/runner/persona_agent.py", '_EVIDENCE_LEVELS = ("direct", "inferred", "gap")')],
    ),
    (
        "推断占比超过 40% 会被标记为推断过度",
        ["推断占比超过 40%", "推断过度"],
        [("src/runner/validator.py", "推断过度")],
    ),
    (
        "Top-3 争议点交叉质询",
        ["Top-3 争议点交叉质询"],
        [("src/runner/cross_exam.py", "def ")],
    ),
    (
        "改票由代码判定、阈值写在开源配置里",
        ["改票由代码判定", "阈值写在开源配置里"],
        [("src/runner/cross_exam.py", "confidence_change_threshold")],
    ),
    (
        "伦理护栏：身份与行为解耦，人口统计字段注入前剥离",
        ["身份与行为解耦", "在注入提示词前会被剥离"],
        [
            # "剥离"的实现是白名单而不是黑名单：_minify_persona 只把 CORE_FIELDS
            # 里列出的字段拼进 prompt，性别/年龄/地域根本不在名单里，所以进不去。
            ("src/runner/persona_agent.py", "CORE_FIELDS"),
            # 另有一道运行时检测：输出里出现"因为是X所以Y"式的身份→行为推理会被标记
            ("src/runner/validator.py", "check_identity_behavior_decoupling"),
        ],
    ),
    (
        "预测留档 + 真人结果回填 + 人格历史准确率（low_confidence 标注）",
        ["真人结果回填", "low_confidence"],
        [
            ("web/backend/app/services/validation_service.py", "low_confidence"),
            ("web/backend/app/api/platform.py", "/ledger/hit-rate"),
        ],
    ),
]


@pytest.mark.parametrize(
    "name,phrases,sources", CLAIMS, ids=[c[0] for c in CLAIMS]
)
def test_landing_claim_has_a_real_implementation(name, phrases, sources):
    """落地页说了这件事 ⇒ 代码里必须真有这件事。"""
    landing = _landing()

    present = [p for p in phrases if p in landing]
    if not present:
        pytest.skip(
            f"落地页当前没有『{name}』相关文案（可能已改写或删除）——"
            "没有声称就没有核对的必要。若是改了措辞，请更新本测试的关键短语。"
        )

    # 声称了就必须能落地
    for rel_path, marker in sources:
        abs_path = os.path.join(REPO_ROOT, rel_path)
        assert os.path.exists(abs_path), (
            f"落地页声称『{name}』，但事实源文件 {rel_path} 不存在了。"
            "要么这个能力被删了（文案就是虚假宣传，必须同步删），"
            "要么实现搬了家（更新本测试的事实源路径）。"
        )
        assert marker in _read(abs_path), (
            f"落地页声称『{name}』，但 {rel_path} 里已经找不到 `{marker}`。"
            "本仓历史上正因为这类漂移出过事故（落地页写着『实时交叉质询/ROUND 3/"
            "说服力』，而 cross_exam.py 当时 vote_changes 恒空、delta 恒 0）。"
            "请确认这个能力是否还在：还在就更新标识符，不在就把文案删掉。"
        )


def test_removed_claims_stay_removed():
    """反向对照：历史上因为"引擎里根本没有"而被删掉的说法，不许写回来。

    landing-body.html 里现在留着两段注释警告后人（"别把这三个写回来"、
    "引擎里没有红队模式"），但注释拦不住任何人——这条测试才拦得住。
    """
    # 必须先剥掉 HTML 注释再查：那两段警告注释本身就完整引用了这些禁用词
    # （"曾经这里写的是『实时交叉质询 / ROUND 3 / 分歧度 / 说服力』"），
    # 不剥的话这条测试会被它要保护的那段注释本身触发——写这条测试时真踩了一次。
    landing = re.sub(r"<!--.*?-->", "", _landing(), flags=re.S)
    # 禁用词必须是"指标形态"，不能是裸词。
    # 反例：最初这里写的是裸的「说服力」，结果命中了 SaaS 定价页那张卡上
    # 「CTA 说服力」——那句说的是**用户自己定价页**的说服力（评审要看的东西），
    # 不是引擎产出的分数，是完全合法的文案。对正常文案叫狼的测试活不过三次，
    # 很快会被人加 skip 关掉，那就等于这道防线从来没存在过。
    forbidden = [
        # cross_exam.py 只跑一轮，没有轮次概念
        ("ROUND 3", "引擎只跑一轮交叉质询，没有第三轮"),
        # 引擎不产出这两个指标
        ("分歧度", "引擎不产出『分歧度』这个指标"),
        ("说服力分", "引擎不计算说服力分（描述用户材料的『CTA 说服力』不在此列）"),
        ("说服力：", "同上——冒号形态是指标标签，不是描述性用语"),
        # CLI 的 red-team-audience 参数收下就丢，不影响任何一次评审
        ("红队对抗模式", "引擎里没有红队模式，也没有红队人格包"),
    ]
    for phrase, why in forbidden:
        assert phrase not in landing, (
            f"落地页里又出现了『{phrase}』——{why}。"
            "这个说法在历史上被删过一次（见 landing-body.html 里的注释），"
            "写回来就是虚假宣传。"
        )
