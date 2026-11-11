import json
import logging
import os
import re

import yaml
from jinja2 import Template

try:
    from .task_types import VALID_TASK_TYPES
except ImportError:  # 被当顶层模块导入时（src/harness/ablation.py 走过这条路）
    from runner.task_types import VALID_TASK_TYPES


# ---------------------------------------------------------------------------
# 任务类型 → 立场词表 / 评分维度
#
# 为什么这张表在这里：
#   报告的评分表此前恒为空，根因是提示词与 output-schema.json 互相矛盾——
#   骨架写 "scores": {"base": {}, "task_specific": {}}，schema 却要求
#   scores.base 必须含 clarity 和 trust，而提示词全文没出现过这两个词。
#   照抄骨架的输出 100% schema 不合格，评分表拿不到任何数字。
#   同理，提示词只给 10 个 task_type 列了立场词表、只给 4 个列了评分维度，
#   剩下的人格自造维度/自造立场，聚合器按 primary_stance 做立场聚类时直接失效。
#
# 值从哪来：web/backend/app/services/__init__.py 的 TASK_TYPES（stance_enum /
#   score_dimensions）**逐字复制**，不另造一套——那份是 /api/task-types 对外
#   露出的口径，前端报告页显示的就是它。两边不一致意味着"模型按 A 打分、
#   页面按 B 展示"。tests/test_persona_agent.py::TestTaskTableSingleSource
#   会直接读那个文件比对，漂移立刻红。
#
#   （后端在下游、引擎在上游，所以表放引擎侧；理想终局是 services 反过来
#    import 这份表，但 services/__init__.py 不在本次改动范围内。）
#
# 维度的中文释义是新写的——services 只有维度名，没有给模型看的定义。
# 释义只解释既有维度名的含义，不新增/改名任何维度。
# ---------------------------------------------------------------------------

# 全任务通用基础维度：报告靠它做跨人格、跨任务的横向对比，所以 schema 里是必填。
BASE_SCORE_DIMENSIONS = {
    "clarity": (
        "清晰度——看完材料，你能不能一眼说清「这是什么、给谁、凭什么值得花时间或钱」。"
        "1=看完仍不知道它是什么；3=大意能懂但关键处要靠猜；5=信息组织清楚，不必追问"
    ),
    "trust": (
        "信任度——你有多相信材料里的说法能兑现（团队、进度、数据、承诺）。"
        "1=通篇自说自话、没有可核验的东西；3=部分说法有支撑、部分是空头承诺；"
        "5=关键说法都能找到可核验的依据"
    ),
}

TASK_STANCE_ENUM = {
    "steam_page_review": ["加愿望单", "不加", "观望"],
    "demo_first_play": ["继续试玩", "退出", "观望"],
    "concept_review": ["值得推进", "不值得", "观望"],
    "monetization_review": ["会买", "不买", "观望"],
    "looking_for_party_post": ["会转发", "不会", "观望"],
    "update_announcement_review": ["增强信心", "降低信心", "无影响"],
    "devlog_review": ["增强期待", "降低期待", "无影响"],
    "kickstarter_review": ["会支持", "不会", "观望"],
    "localization_review": ["文化适配良好", "存在问题", "观望"],
    "discord_community_review": ["会加入", "不会", "观望"],
    "product_feedback_review": ["会继续用", "会流失", "观望"],
    "pricing_page_review": ["会付费", "不会", "观望"],
    "onboarding_review": ["会留下", "会放弃", "观望"],
    "pitch_review": ["值得跟进", "不投", "观望"],
}

# 维度名（键）与顺序必须与 services.TASK_TYPES[*]["score_dimensions"] 完全一致
TASK_SCORE_DIMENSIONS = {
    "steam_page_review": {
        "differentiation": "这页有没有讲清「只有它能做到什么」，与同类作品的区隔是否成立",
        "value_for_money": "按标价和页面呈现出的内容量，是否觉得值这个钱",
        "wishlist_appeal": "看完是否真的产生「先加愿望单」的冲动",
    },
    "demo_first_play": {
        "retention_potential": "按这段体验，你还愿意再玩多久",
        "onboarding_friendliness": "上手阶段是否被规则、操作或界面卡住",
        "moment_to_moment_feel": "逐秒的手感、反馈和节奏是否舒服",
    },
    "concept_review": {
        "differentiation": "概念本身是否有别人做不出来的点",
        "retention_potential": "核心循环是否撑得住反复玩",
        "aesthetic_coherence": "题材、美术与玩法气质是否是同一套东西",
    },
    "monetization_review": {
        "value_for_money": "付费点给到的东西是否配得上标价",
        "fairness": "付费与不付费之间的差距是否让人觉得被逼氪",
        "transparency": "价格、概率、续费、退款边界是否讲清楚",
    },
    "looking_for_party_post": {
        "social_appeal": "这帖子是否让你想认识发帖人、想加入",
        "friction_to_join": "加入需要的步骤、门槛和时间成本有多高（越低分越高）",
        "shareability": "你是否愿意把它转给别人",
    },
    "update_announcement_review": {
        "communication_clarity": "这次更新改了什么、影响谁，是否说清楚",
        "trust_reinforcement": "这次沟通让你更信这支团队，还是更不信",
        "retention_signal": "是否给了老玩家一个具体的回归理由",
    },
    "kickstarter_review": {
        "narrative_strength": "项目故事是否讲得让人想参与",
        "reward_value": "各档回报与出资额是否对得上",
        "trust_signals": "团队、进度、资金用途是否有可核验的交代",
    },
    "discord_community_review": {
        "community_vibe": "社区氛围是否让你愿意留下来说话",
        "engagement_design": "频道结构、活动与互动机制是否鼓励参与",
        "retention_signal": "一周之后你还会不会再打开这个社区",
    },
    "devlog_review": {
        "narrative_rhythm": "这篇日志的信息节奏是否让人读得下去",
        "transparency": "是否敢讲问题、延期和取舍，而不只是报喜",
        "community_feedback": "是否回应了社区已经在问的问题",
    },
    "localization_review": {
        "cultural_adaptation": "是否做了本地文化适配，而不是机械直译",
        "language_quality": "目标语言读起来是否自然，有无错译漏译",
        "ui_adaptation": "界面是否容纳得下目标语言的长度与排版",
    },
    "product_feedback_review": {
        "usability": "完成主要任务时是否顺手、少走弯路",
        "value_perception": "它解决的问题对你是否值得花这个时间或钱",
        "trust_signals": "隐私、数据、承诺、售后是否让你放心",
    },
    "pricing_page_review": {
        "value_for_money": "各档价格与所含权益是否对得上",
        "pricing_clarity": "分层、计费口径、超量怎么算，是否一眼看懂",
        "trust_signals": "退款、试用、隐藏费用、合同条款是否讲清楚",
    },
    "onboarding_review": {
        "onboarding_friendliness": "首次使用是否被步骤、注册或术语卡住",
        "time_to_value": "多久能第一次感到「这东西对我有用」",
        # 与 base.clarity 同名但口径不同，必须分开填——这里只看引导流程本身
        "clarity": "引导过程中每一步要你做什么、为什么，是否说清楚（只评引导流程，"
                   "整体清晰度另填 scores.base.clarity）",
    },
    "pitch_review": {
        "market_potential": "市场规模、时机与增长路径是否成立",
        "team_credibility": "这支团队凭什么能做成这件事，有无可核验的过往",
        "evidence_quality": "关键数字与结论是否有来源，还是自说自话",
    },
}

# 未预置的 task_type 走这条兜底：说清"没有词表"，而不是让模型自己编一套
# ——自造的立场词进不了聚合器的立场聚类，自造的维度名跨人格不可比。
_NO_STANCE_ENUM_NOTE = (
    "（本任务类型未预置立场词表：请用一个不超过 8 个字、能被归类的短语，例如「观望」）"
)
_NO_DIMENSION_NOTE = (
    "（本任务类型未预置专属评分维度：task_specific 直接留空对象 {} 即可，"
    "但 scores.base 仍然必填。不要自造维度名——自造维度在报告里无法与其他人格对比。）"
)

_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "schemas", "output-schema.json"
)


def _assert_task_tables_aligned() -> None:
    """导入时就把三处"合法任务类型"钉在一起，漂移当场炸而不是等到跑评审。

    参照 web/backend/app/services/__init__.py 里同样的导入期断言：那次漂移的
    后果是前端展示了引擎不认的任务类型，用户一选就 400。这里对应的后果是
    schema 拒掉合法输出（实测 pitch_review 的合法输出被判
    "'pitch_review' is not one of [...]"），报告直接没有评分。
    """
    registry = set(VALID_TASK_TYPES)

    missing_stance = registry - set(TASK_STANCE_ENUM)
    extra_stance = set(TASK_STANCE_ENUM) - registry
    assert not (missing_stance or extra_stance), (
        "TASK_STANCE_ENUM 与 runner/task_types.py 不一致："
        f"缺 {sorted(missing_stance)}；多 {sorted(extra_stance)}"
    )

    missing_dims = registry - set(TASK_SCORE_DIMENSIONS)
    extra_dims = set(TASK_SCORE_DIMENSIONS) - registry
    assert not (missing_dims or extra_dims), (
        "TASK_SCORE_DIMENSIONS 与 runner/task_types.py 不一致："
        f"缺 {sorted(missing_dims)}；多 {sorted(extra_dims)}"
    )

    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_enum = json.load(f)["properties"]["task_type"]["enum"]
    assert set(schema_enum) == registry, (
        "output-schema.json 的 task_type 枚举与 runner/task_types.py 不一致："
        f"仅注册表有 {sorted(registry - set(schema_enum))}；"
        f"仅 schema 有 {sorted(set(schema_enum) - registry)}"
    )


_assert_task_tables_aligned()


def stance_enum_for(task_type: str) -> list:
    """该任务类型的合法立场词表；未预置时返回空列表（不编一套出来）。"""
    return list(TASK_STANCE_ENUM.get(task_type, []))


def score_dimensions_for(task_type: str) -> list:
    """该任务类型 scores.task_specific 必须包含的维度名（有序）。"""
    return list(TASK_SCORE_DIMENSIONS.get(task_type, {}))


def _render_stance_line(task_type: str) -> str:
    stances = stance_enum_for(task_type)
    if not stances:
        return _NO_STANCE_ENUM_NOTE
    return " / ".join(stances)


def _render_score_rubric(task_type: str) -> str:
    """给提示词用的评分口径正文：基础维度 + 本任务专属维度，都带中文释义。"""
    lines = ["scores.base（全任务通用，两项都必填，缺任何一项整份输出作废）："]
    for dim, desc in BASE_SCORE_DIMENSIONS.items():
        lines.append(f"  - {dim}: {desc}")

    dims = TASK_SCORE_DIMENSIONS.get(task_type)
    lines.append("")
    if not dims:
        lines.append(f"scores.task_specific（{task_type}）：{_NO_DIMENSION_NOTE}")
        return "\n".join(lines)

    lines.append(
        f"scores.task_specific（{task_type} 专属，键名逐字照抄，一个都不能少、不能多）："
    )
    for dim, desc in dims.items():
        lines.append(f"  - {dim}: {desc}")
    return "\n".join(lines)


def _render_scores_skeleton(task_type: str) -> str:
    """骨架里 scores 那一行的真身。

    历史 bug 就在这里：骨架写死 {"base": {}, "task_specific": {}}，
    照抄它必然 schema 不合格（base 缺 clarity/trust），评分表恒为空。
    现在把该任务类型真正要填的键名直接摆进骨架，照抄即合法。
    """
    base = ", ".join(f'"{dim}": 3' for dim in BASE_SCORE_DIMENSIONS)
    dims = score_dimensions_for(task_type)
    task_specific = ", ".join(f'"{dim}": 3' for dim in dims)
    return (
        '{\n'
        f'    "base": {{{base}}},\n'
        f'    "task_specific": {{{task_specific}}}\n'
        '  }'
    )


CORE_FIELDS = [
    "id",
    "name",
    "archetype",
    "methodology",  # 方法论标签：给模型一个可命名的判断框架，约束力强于抽象行为轴；不含人口学信息，进白名单是安全的
    "identity_summary",
    "behavior_profile",
    "motivations",
    "decision_rules",
    "quit_triggers",
    "continue_triggers",
    "first_scan_focus",
    "review_output",
]


def _minify_persona(persona: dict) -> str:
    minified = {k: persona[k] for k in CORE_FIELDS if k in persona}
    return yaml.dump(minified, allow_unicode=True, default_flow_style=False).strip()


def _convert_handlebars_to_jinja2(template_str: str) -> str:
    result = []
    i = 0
    in_each = False
    while i < len(template_str):
        match = re.match(r"\{\{#each\s+(\w+)\}\}", template_str[i:])
        if match:
            var_name = match.group(1)
            result.append("{% for _item in " + var_name + " %}")
            i += match.end()
            in_each = True
            continue
        if template_str[i:].startswith("{{/each}}"):
            result.append("{% endfor %}")
            i += len("{{/each}}")
            in_each = False
            continue
        if in_each:
            index_match = re.match(r"\{\{@index\}\}", template_str[i:])
            if index_match:
                result.append("{{ loop.index0 }}")
                i += index_match.end()
                continue
            this_match = re.match(r"\{\{this\}\}", template_str[i:])
            if this_match:
                result.append("{{ _item }}")
                i += this_match.end()
                continue
            var_match = re.match(r"\{\{(\w+)\}\}", template_str[i:])
            if var_match:
                prop = var_match.group(1)
                result.append("{{ _item." + prop + " }}")
                i += var_match.end()
                continue
        result.append(template_str[i])
        i += 1
    return "".join(result)


def render_prompt(
    persona: dict, task_type: str, artifact_summary: str, template_path: str, artifact_bundle: dict = None
):
    """返回纯文本 str，除非 artifact_bundle 里带了图片材料——那种情况下返回 OpenAI Vision
    格式的内容块列表 [{"type":"text",...}, {"type":"image_url",...}]，交给
    src/runner/llm_client.py 按目标 provider 转换成各自认的格式（见该模块 chat_completion）。
    文字材料（type=="text"）照旧渲染进模板正文；图片材料（type=="image"，
    image_data 是 data URI）单独拼成内容块，不进模板文本。"""
    with open(template_path, "r", encoding="utf-8") as f:
        template_str = f.read()

    template_str = _convert_handlebars_to_jinja2(template_str)

    persona_yaml_minified = _minify_persona(persona)
    mbti = persona.get("mbti", "")
    persona_name = persona.get("name", "")
    must_comment_on_items = persona.get("review_output", {}).get(
        "must_comment_on", []
    )
    decision_rules = persona.get("decision_rules", [])
    primary_decision_rule = decision_rules[0] if decision_rules else ""

    all_materials = []
    if artifact_bundle:
        all_materials = artifact_bundle.get("materials", [])
    artifact_materials = [m for m in all_materials if m.get("type") != "image"]
    image_materials = [m for m in all_materials if m.get("type") == "image" and m.get("image_data")]

    template = Template(template_str)
    text_prompt = template.render(
        persona_yaml_minified=persona_yaml_minified,
        mbti=mbti,
        persona_name=persona_name,
        persona_id=persona.get("id", ""),
        must_comment_on_items=must_comment_on_items,
        primary_decision_rule=primary_decision_rule,
        task_type=task_type,
        artifact_summary=artifact_summary,
        artifact_materials=artifact_materials,
        # 立场词表与评分维度按 task_type 现算现注入，而不是在模板里铺 14 份清单：
        # 铺清单既让提示词膨胀，又要求模型自己在表里找对行——它此前只找得到 10
        # 份立场、4 份维度，剩下的全靠自造。注入版把"你这次该填什么"直接摆到眼前。
        stance_enum_line=_render_stance_line(task_type),
        score_rubric_block=_render_score_rubric(task_type),
        scores_skeleton=_render_scores_skeleton(task_type),
    )

    if not image_materials:
        return text_prompt

    content = [{"type": "text", "text": text_prompt}]
    for m in image_materials:
        content.append({"type": "image_url", "image_url": {"url": m["image_data"]}})
    return content


def render_prompt_split(
    persona: dict,
    task_type: str,
    artifact_summary: str,
    template_dir: str,
    artifact_bundle: dict = None,
):
    """render_prompt 的可缓存版本：拆成 (shared, user) 两段而不是拼成一个整体。

    shared —— 同一次评审里对**所有人格逐字相同**的固定前缀（任务类型/评审材料/
    评分口径/输出骨架等，唯一变量只有 task_type 和材料，跟具体哪位人格无关）。
    调用方把它整段传给 llm_client.chat_completion 的 system 参数：Anthropic 路径
    打 cache_control 走 Prompt Caching（第 2 次起命中缓存只按 10% 计费），OpenAI
    兼容路径放进消息列表最前面吃第三方的隐式前缀缓存折扣——一次 full 评审 6-8
    位人格重复发送同一份材料，这是目前最大的一笔重复计费。

    user —— 人格专属部分（persona 卡 + 这位人格必答的问题），永远跟着变，不进
    共享块。返回值同 render_prompt：纯字符串，除非带图片材料则是内容块列表——
    图片必须留在这一段，Anthropic 的 system 参数只接受纯文本块，不能带图片。

    绝不能把任何 persona 相关字段（persona_id/persona_name/persona_yaml 等）
    混进 shared 的渲染变量里：混进去一个字，每位人格的 shared 文本就不再逐字
    相同，缓存永远 miss，白白多算一次"可能命中"的期望而已。

    与 render_prompt（未拆分版）相比：两者共享同一套 Jinja2/Handlebars 渲染
    逻辑与模板变量语义，只是从两个不同的模板文件里各读各的一半。render_prompt
    本身保持不变，供 src/cli.py 等历史调用方继续使用。
    """
    shared_path = os.path.join(template_dir, "persona-prompt-shared.md")
    user_path = os.path.join(template_dir, "persona-prompt-user.md")

    with open(shared_path, "r", encoding="utf-8") as f:
        shared_template_str = _convert_handlebars_to_jinja2(f.read())
    with open(user_path, "r", encoding="utf-8") as f:
        user_template_str = _convert_handlebars_to_jinja2(f.read())

    mbti = persona.get("mbti", "")
    persona_name = persona.get("name", "")
    must_comment_on_items = persona.get("review_output", {}).get("must_comment_on", [])
    decision_rules = persona.get("decision_rules", [])
    primary_decision_rule = decision_rules[0] if decision_rules else ""

    all_materials = []
    if artifact_bundle:
        all_materials = artifact_bundle.get("materials", [])
    artifact_materials = [m for m in all_materials if m.get("type") != "image"]
    image_materials = [m for m in all_materials if m.get("type") == "image" and m.get("image_data")]

    shared_prompt = Template(shared_template_str).render(
        task_type=task_type,
        artifact_summary=artifact_summary,
        artifact_materials=artifact_materials,
        stance_enum_line=_render_stance_line(task_type),
        score_rubric_block=_render_score_rubric(task_type),
        scores_skeleton=_render_scores_skeleton(task_type),
    )

    user_text = Template(user_template_str).render(
        persona_yaml_minified=_minify_persona(persona),
        mbti=mbti,
        persona_name=persona_name,
        must_comment_on_items=must_comment_on_items,
        primary_decision_rule=primary_decision_rule,
    )

    if not image_materials:
        return shared_prompt, user_text

    user_content = [{"type": "text", "text": user_text}]
    for m in image_materials:
        user_content.append({"type": "image_url", "image_url": {"url": m["image_data"]}})
    return shared_prompt, user_content


def parse_persona_output(raw_output: str) -> dict:
    json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    json_objects = []
    depth = 0
    start = None
    for i, ch in enumerate(raw_output):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                json_objects.append(raw_output[start : i + 1])
                start = None

    for obj_str in reversed(json_objects):
        try:
            return json.loads(obj_str)
        except json.JSONDecodeError:
            continue

    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        return {"parse_error": True, "raw_output": raw_output}


# 第三方模型常见的"同义字段名"——它们能理解任务但不肯照抄 schema 的字段名
# （实测 MiniMax-M3 会吐 evaluator_id / stance_rationale / dimension_analysis…）。
# prompt 里已经给了逐字骨架，这里是第二道保险：把变体名归一回规范名，
# 让报告不至于因为"名字没对上"就丢掉模型真正产出的内容。
_FIELD_ALIASES = {
    "persona_id": ("evaluator_id", "reviewer_id", "agent_id", "id"),
    "persona_name": ("evaluator_name", "reviewer_name", "agent_name", "name"),
    "primary_stance": ("stance", "overall_stance", "verdict"),
    "key_issues": ("issues", "problems", "concerns", "key_problems", "dimension_analysis"),
    "voice_sample": ("quote", "voice", "comment"),
    "missing_information": ("missing_info", "information_gaps", "gaps"),
    "evidence_sufficiency": ("evidence_score", "evidence_confidence"),
}

# key_issues 每项内部的字段变体
_ISSUE_ALIASES = {
    "title": ("issue", "problem", "name", "summary", "point"),
    "severity": ("level", "priority", "impact"),
    "why_it_matters": ("reason", "rationale", "why", "impact_description", "detail"),
    "suggested_fix": ("fix", "suggestion", "recommendation", "how_to_fix", "advice"),
}


# ---------------------------------------------------------------------------
# 子结构"形状"归一化
#
# 改名只是第一层问题。第三方模型连子结构的形状也不按 schema 给，实测三种：
#   {"evidence": ["文案不清晰"]}      → validator 里 e.get(...) 炸 AttributeError
#   {"key_issues": "无重大问题"}      → calibration 里 issue["title"] 炸 TypeError
#   {"missing_information": [{...}]}  → aggregator 的 seen_gaps.add(gap) 炸 unhashable
# 而 cli.py 的人格循环没有把 validator 调用包在 try 里，所以**一个**人格吐错形状
# 就让整个 run_panel 崩掉——前面 N 个人格的 API 钱已经花掉了，报告一个字都拿不到。
#
# 因此形状归一化只做在这一个边界上（模型输出刚解析完、还没进任何下游），
# 而不是去下游 20 个调用点各加一遍 isinstance：后者每新增一个调用点就会漏一次，
# 且 aggregator.py / cross_exam.py 也各有自己的形状假设，补不干净。
#
# 原则：归一化只改形状，不丢内容——字符串塞进该子结构语义上最贴的键里。
# ---------------------------------------------------------------------------

# 模型把文本塞进子结构时常用的键名，按"越可能是正文"排序
_TEXT_KEYS = (
    "content", "text", "description", "detail", "quote", "observation",
    "title", "name", "item", "gap", "info", "question", "summary", "value",
)


def _coerce_text(value) -> str:
    """把任意类型降成字符串，尽量不丢原文。

    下游有两类硬要求：一是 str 方法/正则（validator 的正则、模板渲染），
    二是 hashable（aggregator 用 set 给 missing_information 去重、
    用 primary_stance 当 dict 键）。dict/list 元素在这两处都会直接炸。
    """
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    if isinstance(value, dict):
        # 先找语义正文键；找不到就把整个 dict 摊平成 "键: 值"，宁可难看也不丢信息
        for key in _TEXT_KEYS:
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        return "; ".join(
            f"{k}: {_coerce_text(v)}" for k, v in value.items() if _coerce_text(v)
        )
    if isinstance(value, (list, tuple, set)):
        return "; ".join(t for t in (_coerce_text(v) for v in value) if t)
    return str(value)


def _coerce_list(value) -> list:
    """整体被吐成单个值（字符串/对象）时包成单元素列表；None 归一成空列表。"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _coerce_text_list(value) -> list:
    """schema 里声明为 array of string 的字段：逐项降成非空字符串。"""
    return [t for t in (_coerce_text(item) for item in _coerce_list(value)) if t]


def _coerce_ratio(value, default: float = 0.5) -> float:
    """0-1 的比例字段。模型爱吐 "0.8" / "80%" / 8（十分制），
    而 aggregator 直接 sum(...)、cross_exam 直接 *100，字符串会 TypeError。"""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        text = value.strip().rstrip("%")
        try:
            num = float(text)
        except ValueError:
            return default
        if value.strip().endswith("%"):
            num /= 100.0
    else:
        return default
    if 1.0 < num <= 10.0:
        num /= 10.0  # 十分制口径，按比例还原而不是直接夹到 1.0
    return max(0.0, min(1.0, num))


_EVIDENCE_TEXT_ALIASES = ("content", "text", "observation", "comment", "detail",
                          "description", "evidence", "fact")
# quote = 材料原文的逐字片段（direct 必填），和 content（人格的观察/解读）是两个字段：
# 校验器只拿 quote 对照材料。"quote" 以前被当成 content 的别名，现在不是了。
_EVIDENCE_QUOTE_ALIASES = ("quote", "source_quote", "quoted_text", "verbatim", "原文")
_EVIDENCE_LEVEL_ALIASES = ("inference_level", "level", "inference", "type", "kind")
_EVIDENCE_LEVELS = ("direct", "inferred", "gap")
# 中文/变体写法映射回 schema 枚举
_LEVEL_SYNONYMS = {
    "直接": "direct", "直接证据": "direct", "原文": "direct", "quoted": "direct",
    "推断": "inferred", "推测": "inferred", "间接": "inferred", "inference": "inferred",
    "缺口": "gap", "缺失": "gap", "missing": "gap",
}
# 归一化补出来的 inference_level 要说明来源，否则报告读者会以为是模型自己标的。
# 用 inference_basis 承载（schema 允许该键），不新造 schema 外的字段。
_LEVEL_BACKFILL_NOTE = "模型未标注推断层级，归一化时按保守口径记为 inferred"


def _normalize_level(value) -> str:
    text = _coerce_text(value).lower()
    if text in _EVIDENCE_LEVELS:
        return text
    return _LEVEL_SYNONYMS.get(_coerce_text(value), "")


def _normalize_evidence(value) -> list:
    """evidence 归一成 [{"content": str, "inference_level": 枚举, "quote"?: str, ...}]。

    元素是字符串时包成 {"content": 原文}——保留原文，不丢证据。
    层级缺失/写错一律记 inferred 而不是 direct：direct 会让 validator 的
    grounding 检查和 calibration 的幻觉率去核对"原文出处"，而我们并不知道
    这句到底是不是原文照抄，谎报 direct 会让整份报告的幻觉率虚高。
    """
    normalized = []
    for item in _coerce_list(value):
        if isinstance(item, dict):
            content = ""
            for alias in _EVIDENCE_TEXT_ALIASES:
                if isinstance(item.get(alias), str) and item[alias].strip():
                    content = item[alias].strip()
                    break
            quote = ""
            for alias in _EVIDENCE_QUOTE_ALIASES:
                if isinstance(item.get(alias), str) and item[alias].strip():
                    quote = item[alias].strip()
                    break
            if not content:
                # 只给了引用没写观察：content 用引用本身顶上（schema 要求 content 非空）；
                # 再没有就把整个 dict 摊平进 content，信息不丢
                content = quote or _coerce_text(item)
            level = ""
            for alias in _EVIDENCE_LEVEL_ALIASES:
                if alias in item:
                    level = _normalize_level(item[alias])
                    if level:
                        break
            source = _coerce_text(item.get("source_location") or item.get("source"))
            basis = _coerce_text(item.get("inference_basis") or item.get("basis"))
        else:
            content = _coerce_text(item)
            level, source, basis, quote = "", "", "", ""

        if not content:
            continue

        # 只保留 schema 允许的键，顺手把 additionalProperties 违规也一并清掉
        entry = {"content": content, "inference_level": level or "inferred"}
        if not level and not basis:
            basis = _LEVEL_BACKFILL_NOTE
        # quote 原样保留（不改写、不翻译）。只有 direct 条目带：inferred / gap 上的 quote
        # 不参与校验，留着只会让读者以为它被核对过。
        if quote and entry["inference_level"] == "direct":
            entry["quote"] = quote
        if source:
            entry["source_location"] = source
        if basis:
            entry["inference_basis"] = basis
        normalized.append(entry)
    return normalized


def _normalize_key_issues(value) -> list:
    """key_issues 归一成 [{"title": str, "severity": ..., ...}]。

    整体是字符串（"无重大问题"）→ 包成单元素列表；元素是字符串 → 塞进 title。
    """
    if isinstance(value, dict):
        # 有的模型把 issues 写成 {维度: 描述} 的字典而非数组
        value = [
            {"title": _coerce_text(k), "why_it_matters": _coerce_text(v)}
            for k, v in value.items()
        ]

    normalized = []
    for item in _coerce_list(value):
        if not isinstance(item, dict):
            # 字符串/数字/嵌套列表：原文进 title，不静默丢弃
            item = {"title": _coerce_text(item)}
        else:
            item = dict(item)
            for canonical, aliases in _ISSUE_ALIASES.items():
                if item.get(canonical):
                    continue
                for alias in aliases:
                    if item.get(alias):
                        item[canonical] = item[alias]
                        break
            if not item.get("title"):
                # 一个键都对不上（比如 {"维度": "描述"}）：整条摊平进 title
                item["title"] = _coerce_text(item)

        # 下游（aggregator 拼 evidence_text、cross_exam 取 severity）都按 str 用
        item["title"] = _coerce_text(item.get("title"))
        item["severity"] = _coerce_text(item.get("severity")) or "medium"
        item["why_it_matters"] = _coerce_text(item.get("why_it_matters"))
        item["suggested_fix"] = _coerce_text(item.get("suggested_fix"))
        if item["title"]:
            normalized.append(item)
    return normalized


# 模型把"我已覆盖了哪些必答项"写成数组时的真值/假值词
_FALSEY_CHECK_TEXTS = {"", "false", "no", "n", "0", "否", "未覆盖", "未提及", "未涉及", "无"}


def _normalize_must_comment_check(value) -> dict:
    """must_comment_on_check 必须是 {项: bool}——validator 调 .values()、
    calibration 调 len()/.values()，列表进来就 AttributeError。
    模型常吐成"已覆盖项"的数组，那种情况按已覆盖处理。"""
    if isinstance(value, dict):
        return {
            _coerce_text(k): (
                bool(v) if not isinstance(v, str)
                else v.strip().lower() not in _FALSEY_CHECK_TEXTS
            )
            for k, v in value.items()
            if _coerce_text(k)
        }
    return {item: True for item in _coerce_text_list(value)}


_BASE_SCORE_KEYS = tuple(BASE_SCORE_DIMENSIONS)  # ("clarity", "trust")
# "4/5"、"8/10" 这种自带分母的写法：按分母折算回 5 分制再取整
_FRACTION_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$")
# "4 分"、"评分：4"、"4/5 星" 这类带字的写法：取第一个数字
_FIRST_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _coerce_score(value):
    """把一个维度分降成 schema 要的 1-5 整数；实在读不出数字就返回 None。

    返回 None 而不是塞个默认值：编一个分数出来，报告里会显示成"这个人格给了 3 分"，
    那是凭空捏造的评审结论——本仓库正在系统性清除的就是这类"看起来有、其实是编的"。
    读不出来就让这一项缺席，schema 会如实报缺。
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        fraction = _FRACTION_RE.match(value)
        if fraction:
            numerator, denominator = float(fraction.group(1)), float(fraction.group(2))
            if denominator == 0:
                return None
            num = numerator / denominator * 5.0
        else:
            match = _FIRST_NUMBER_RE.search(value)
            if not match:
                return None
            num = float(match.group(0))
    else:
        return None
    num = int(round(num))
    return max(1, min(5, num))


def _coerce_score_map(value) -> dict:
    """一层评分字典：键降成字符串，值降成 1-5 整数，读不出数字的整项丢掉。"""
    if not isinstance(value, dict):
        return {}
    coerced = {}
    for key, raw in value.items():
        name = _coerce_text(key)
        if not name:
            continue
        score = _coerce_score(raw)
        if score is not None:
            coerced[name] = score
    return coerced


def _normalize_scores(value) -> dict:
    """scores 归一成 {"base": {...}, "task_specific": {...}}——
    aggregator 对这两层是 .get() 链式取值，形状错了会 AttributeError。

    除形状外还做三件事，全是为了让"模型真给了分"不至于在校验这一关丢掉：
      1. 分值降成 1-5 整数（模型爱吐 4.5 / "4" / "4/5" / "8/10"）；
      2. base 里的非法键搬去 task_specific——schema 的 base 是
         additionalProperties:false，多一个键整份输出就不合格，而那个键
         承载的往往是真实评分，直接丢掉等于丢内容；
      3. clarity/trust 被塞进 task_specific 时提回 base——这两项是 schema 必填，
         位置错了会被报成"缺 clarity"，报告的横向对比列因此整列空掉。
    缺的分不补：没给就是没给，schema 如实报缺。
    """
    if not isinstance(value, dict):
        return {"base": {}, "task_specific": {}}
    scores = dict(value)
    base = scores.get("base")
    task_specific = scores.get("task_specific")
    if not isinstance(base, dict) or not isinstance(task_specific, dict):
        # 模型把维度分数直接平铺在 scores 顶层（没分 base/task_specific 两层）。
        # 排掉 base / task_specific 这两个键本身：它们此时是坏形状（比如 base 是字符串），
        # 收进来会变成一个叫 "base" 的假维度进报告。
        flat = {
            k: v
            for k, v in scores.items()
            if k not in ("base", "task_specific") and isinstance(v, (int, float, str))
        }
        base = base if isinstance(base, dict) else {
            k: flat[k] for k in _BASE_SCORE_KEYS if k in flat
        }
        task_specific = task_specific if isinstance(task_specific, dict) else {
            k: v for k, v in flat.items() if k not in _BASE_SCORE_KEYS
        }

    base = _coerce_score_map(base)
    task_specific = _coerce_score_map(task_specific)

    # base 的越界键搬进 task_specific（不覆盖那边已有的同名项）
    for key in [k for k in base if k not in _BASE_SCORE_KEYS]:
        task_specific.setdefault(key, base.pop(key))
    # 基础维度被放错层时提回 base。
    # 唯一会误伤的情况是 onboarding_review——它的专属维度里恰好也有 clarity
    # （口径不同：一个评整体清晰度、一个评引导流程）。但只有 base.clarity 缺席时
    # 才会提，而 base.clarity 缺席本身就是 schema 不合格；且 aggregator 是把
    # base 与 task_specific 合并成一张表展示的，提上去不会让这个分从报告里消失。
    for key in _BASE_SCORE_KEYS:
        if key not in base and key in task_specific:
            base[key] = task_specific.pop(key)

    return {"base": base, "task_specific": task_specific}


# 声明为 array of string、下游按字符串用（去重/渲染/join）的字段
_TEXT_LIST_FIELDS = (
    "missing_information",      # aggregator: seen_gaps.add(gap) 要求 hashable
    "continue_triggers",
    "quit_triggers",
    "first_scan_observations",
)
# 声明为 string、下游拿去当 dict 键或直接拼字符串的字段
_TEXT_FIELDS = ("persona_id", "persona_name", "persona_version",
                "primary_stance", "voice_sample", "task_type")
# 声明为 0-1 number、下游直接参与算术的字段
_RATIO_FIELDS = ("confidence", "evidence_sufficiency")


def normalize_persona_output(output: dict) -> dict:
    """把模型吐回来的输出归一成 output-schema 的规范"名字"和规范"形状"。

    两层归一：
      1. 字段改名——只在规范名缺失时才从别名回填；
      2. 子结构形状——evidence / key_issues / missing_information 等按 schema
         声明的形状重建，元素类型不对时把原文塞进语义最贴的键。

    模型老实照抄骨架时此函数等于空操作，所以对 Claude 这类守规矩的模型零影响。
    """
    if not isinstance(output, dict) or output.get("parse_error"):
        return output

    for canonical, aliases in _FIELD_ALIASES.items():
        if output.get(canonical):
            continue
        for alias in aliases:
            if output.get(alias):
                output[canonical] = output[alias]
                break

    # 工具输入损坏（字段值是一段 <invoke>/<parameter> 标记字符串）时**不归一化**：
    # 原样留给 schema 校验判 schema_failure 并走修复轮。包成一条 inferred 证据会把它
    # 伪装成"推断过度"（role_drift，不重试）。
    from .validator import is_tool_markup_string

    if "evidence" in output and not is_tool_markup_string(output["evidence"]):
        output["evidence"] = _normalize_evidence(output["evidence"])
    if "key_issues" in output and not is_tool_markup_string(output["key_issues"]):
        output["key_issues"] = _normalize_key_issues(output["key_issues"])
    if "must_comment_on_check" in output:
        output["must_comment_on_check"] = _normalize_must_comment_check(
            output["must_comment_on_check"]
        )
    if "scores" in output:
        output["scores"] = _normalize_scores(output["scores"])

    for field in _TEXT_LIST_FIELDS:
        if field in output:
            output[field] = _coerce_text_list(output[field])
    for field in _TEXT_FIELDS:
        if field in output and not isinstance(output[field], str):
            output[field] = _coerce_text(output[field])
    for field in _RATIO_FIELDS:
        if field in output and not isinstance(output[field], (int, float)):
            output[field] = _coerce_ratio(output[field])

    meta = output.get("meta")
    if isinstance(meta, dict) and "caveats" in meta:
        meta["caveats"] = _coerce_text_list(meta["caveats"])

    return output


_warned_unpriced_models = set()


def resolve_model_pricing(model: str, budget_config: dict):
    """查某个模型的单价，返回 (输入单价, 输出单价, 是否有登记价)。

    为什么不能对没登记的模型按 0 算（原来的行为）：
    budget.yaml 的 model_pricing 只列了 3 个 Anthropic 模型，而后台面板允许把
    平台垫付密钥配成**任意** OpenAI 兼容模型（key_service 甚至强制这类必须填
    模型名）。于是只要运营换了个模型，每次调用的成本都记成 0.0，后果是：
      · quota_service 的 `if cost >= cost_limit` 永远不成立 —— 24 小时成本硬闸
        彻底失效，平台垫付的钱没有任何上限；
      · admin 成本面板与 usage_summary 恒显示 $0，运营看不出在烧钱。
    而且它不报错、不告警，是一个纯静默的失效。

    也不能改成抛异常：BYOK 用户填自己的第三方模型是正常用法，价格表里没有它
    再正常不过，为此让评审跑不起来是本末倒置。

    所以取中间路线：**没登记就按最贵的一档估，并如实告诉调用方这是估的**。
    宁可高估——高估只会让成本闸提前触发（保守、安全），低估则等于没有闸。
    运营想要准确数字，就去 budget.yaml 里补一条真实单价。
    """
    table = (budget_config or {}).get("model_pricing") or {}
    priced = table.get(model)
    if priced:
        return (
            float(priced.get("input_per_mtok", 0.0)),
            float(priced.get("output_per_mtok", 0.0)),
            True,
        )

    fallback = (budget_config or {}).get("unknown_model_pricing") or {}
    if not fallback and table:
        # 没配兜底价就取表里最贵的一档
        fallback = max(table.values(), key=lambda p: float(p.get("output_per_mtok", 0.0) or 0.0))

    if model not in _warned_unpriced_models:
        _warned_unpriced_models.add(model)
        logging.getLogger("audiencelens").warning(
            "模型 %r 不在 budget.yaml 的 model_pricing 里，成本按最贵一档估算"
            "（输入 %.2f / 输出 %.2f 每百万 token）。成本闸与后台统计据此计算，"
            "数字会偏高；要准确请在 budget.yaml 补一条真实单价。",
            model,
            float(fallback.get("input_per_mtok", 0.0) or 0.0),
            float(fallback.get("output_per_mtok", 0.0) or 0.0),
        )

    return (
        float(fallback.get("input_per_mtok", 0.0) or 0.0),
        float(fallback.get("output_per_mtok", 0.0) or 0.0),
        False,
    )


# Anthropic Prompt Caching 的**计费**倍率（官方 5 分钟 TTL）：首次写入按 1.25 倍
# 全价、命中读取按 0.1 倍全价。
#
# 不变式：倍率只在这一层（算钱）生效。llm_client 返回的 input_tokens 必须保持
# "真实 token 数"——那个数字会被 web 后端原样落库，终身 token 上限和后台用量面板
# 都读它；把折扣折进 token 数会让命中缓存的 1000 个 token 在用量统计里变成 100 个。
# 反过来，算钱时若忽略折扣，缓存省下的钱在账单上就体现不出来。两头都要对。
CACHE_WRITE_PRICE_MULTIPLIER = 1.25
CACHE_READ_PRICE_MULTIPLIER = 0.1


def billable_input_tokens(input_tokens: int, cache_breakdown: dict = None) -> float:
    """把真实 input token 数折算成**计费等价** token 数。

    cache_breakdown 就是 llm_client.chat_completion 的 usage_details 出参
    （uncached_input_tokens / cache_creation_input_tokens / cache_read_input_tokens）。
    为空（非 Anthropic 路径、没开缓存、或从数据库读历史用量重算）时原样返回，
    等于按满价算——宁可高估，不会让成本闸失灵。
    """
    if not cache_breakdown:
        return float(input_tokens)
    creation = float(cache_breakdown.get("cache_creation_input_tokens") or 0)
    read = float(cache_breakdown.get("cache_read_input_tokens") or 0)
    uncached = cache_breakdown.get("uncached_input_tokens")
    if uncached is None:
        uncached = float(input_tokens) - creation - read
    uncached = max(0.0, float(uncached))
    return (
        uncached
        + creation * CACHE_WRITE_PRICE_MULTIPLIER
        + read * CACHE_READ_PRICE_MULTIPLIER
    )


def estimate_cost_detailed(
    input_tokens: int,
    output_tokens: int,
    model: str,
    budget_config: dict = None,
    cache_breakdown: dict = None,
):
    """同 estimate_cost，但一并返回「这个价格是查表查到的还是估的」。

    需要如实标注成本可信度的地方（后台面板、成本闸的告警文案）用这个。

    cache_breakdown：见 billable_input_tokens。不传 = 按满价算。
    """
    if budget_config is None:
        # 相对路径 "src/config/budget.yaml" 只对"恰好在仓库根目录启动"的进程有效——
        # 从别的 cwd 调 estimate_cost_detailed（后台面板、调度脚本、测试）就 FileNotFoundError。
        # 基于 __file__ 推导：src/runner/persona_agent.py → 仓库根 → src/config/budget.yaml。
        _base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(_base, "src", "config", "budget.yaml"), "r", encoding="utf-8") as f:
            budget_config = yaml.safe_load(f)

    input_price, output_price, priced = resolve_model_pricing(model, budget_config)
    billable_in = billable_input_tokens(input_tokens, cache_breakdown)
    cost = (billable_in / 1_000_000) * input_price + (
        output_tokens / 1_000_000
    ) * output_price
    return cost, priced


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str,
    budget_config: dict = None,
    cache_breakdown: dict = None,
) -> float:
    cost, _priced = estimate_cost_detailed(
        input_tokens, output_tokens, model, budget_config, cache_breakdown
    )
    return cost


def select_model(persona: dict, budget_config: dict) -> str:
    """按人格的 model_hint 分级选真实 Anthropic 模型 ID（不是 "claude-sonnet" 这种占位别名——
    那种字符串传给 Anthropic API 会直接 404，见 budget.yaml 历史遗留的写法）。"""
    model_hint = persona.get("model_hint")
    if model_hint:
        # 字面量兜底与 budget.yaml 保持一致（Sonnet 4 / Opus 4 已在官方 API 退役，
        # 见该文件头部注释）。正常情况下 budget.yaml 一定有这三个键，兜底只防
        # 调用方传了个残缺的 budget_config。
        model_map = {
            "haiku": budget_config.get("fallback_model", "claude-haiku-4-5-20251001"),
            "sonnet": budget_config.get("default_model", "claude-sonnet-5"),
            "opus": budget_config.get("premium_model", "claude-opus-5"),
        }
        return model_map.get(model_hint, f"claude-{model_hint}")
    return budget_config.get("default_model", "claude-sonnet-5")
