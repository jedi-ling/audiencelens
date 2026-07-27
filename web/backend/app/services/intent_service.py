"""意图解析：把用户一句大白话变成结构化评审参数。

这是"对话式入口"的核心——用户在首页那个框里直接说
    "帮我看看这个 Roguelike 的 Steam 页够不够打"
系统需要推断出 task_type=steam_page_review, mode=standard, pack=game-core。

两档实现（埋线：无 key 也能用）：
  1. LLM 档：有 key 且 AL_INTENT_LLM_ENABLED=true → 用 Haiku 做结构化抽取
  2. 启发式档：关键词打分（零成本、离线、可单测）—— LLM 不可用时自动降级

无论哪档，都返回同样的 IntentResult，并带 method 字段如实声明用了哪档。
置信度低时返回 needs_clarification=True，前端应追问而不是瞎猜。
"""

import json
import os as _os
import re
import sys as _sys
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from app.config import settings

# 任务类型从单一注册表读（src/runner/task_types.py），不再本地复制一份
_SRC = _os.path.join(settings.repo_root, "src")
if _SRC not in _sys.path:
    _sys.path.insert(0, _SRC)
from runner.task_types import VALID_TASK_TYPES  # noqa: E402

# 通用任务类型没有命中任何 PACK_KEYWORDS 时的默认人格包——
# 不能落回 game-core，否则"评一下定价页"这种非游戏请求会被硬塞游戏向人格。
DEFAULT_PACK_BY_TASK_TYPE = {
    "product_feedback_review": "general-consumer",
    "pricing_page_review": "general-consumer",
    "onboarding_review": "general-consumer",
    "pitch_review": "startup-panel",
}

VALID_MODES = ["quick", "standard", "full"]

# 关键词 → 任务类型（启发式档）。命中即加分，取最高分。
TASK_KEYWORDS = {
    "steam_page_review": ["steam", "商店页", "store", "页面", "愿望单", "标签", "封面", "宣传图"],
    "demo_first_play": ["demo", "试玩", "首玩", "上手", "新手引导", "教程", "前15分钟", "前 15 分钟"],
    "concept_review": ["概念", "点子", "创意", "核心循环", "玩法设计", "立项", "idea"],
    # 注意："定价页"不放在这里——那是通用的 pricing_page_review 关键词，
    # 两者都用"定价"会打平分，而 monetization_review 定义更早、平局时总赢，
    # 导致非游戏的定价页请求被误判成游戏内购设计评审。
    "monetization_review": ["付费", "内购", "氪金", "价格", "月卡", "抽卡", "变现", "付费墙"],
    "looking_for_party_post": ["组队", "招募", "找队友", "招人"],
    "update_announcement_review": ["更新公告", "版本更新", "patch", "补丁", "更新日志"],
    "devlog_review": ["开发日志", "devlog", "开发者日志"],
    "kickstarter_review": ["众筹", "kickstarter", "回报档位", "众筹页"],
    "localization_review": ["本地化", "翻译", "汉化", "localization", "多语言"],
    "discord_community_review": ["discord", "社区运营", "社群", "频道"],
    "product_feedback_review": ["产品反馈", "用户反馈", "反馈收集", "feedback"],
    "pricing_page_review": ["定价页", "定价方案", "订阅价格", "pricing", "套餐价格"],
    "onboarding_review": ["引导流程", "onboarding", "首次使用体验", "注册后引导", "产品引导"],
    "pitch_review": ["bp", "路演", "商业计划书", "创业项目", "融资", "pitch", "孵化器", "申报表", "项目申报"],
}

MODE_KEYWORDS = {
    "quick": ["快速", "简单看看", "扫一眼", "粗略", "quick"],
    "full": ["全面", "系统", "深入", "彻底", "完整", "详细", "拍板", "full"],
}

PACK_KEYWORDS = {
    "mobile-f2p": ["手游", "手机游戏", "f2p", "免费游戏", "内购", "月卡"],
    "vr-immersive": ["vr", "虚拟现实", "头显"],
    "accessibility": ["无障碍", "色盲", "残障", "辅助功能"],
    "educational-serious": ["教育", "教学", "课堂", "严肃游戏"],
    "competitive-esport": ["电竞", "竞技", "排位", "对战"],
    "family-casual": ["家庭", "亲子", "休闲", "派对"],
    "indie-creative": ["独立游戏", "indie", "艺术向"],
    "general-consumer": ["saas", "企业软件", "toB", "toC", "定价页", "产品反馈", "app", "网站"],
    "startup-panel": ["投资人", "vc", "路演", "孵化器", "商业计划书", "融资"],
    # 放在最后是有意的：pack 取最高分，平局时 max() 取先出现的那个。
    # "手游内购要不要合规" 应该走 mobile-f2p（命中 手游+内购 = 2 分）而不是本包（1 分），
    # 只有"能不能过审 / 版号下来没"这种没有其它包信号的请求才落到这里。
    # 刻意不收 "审核"：用户说"帮我审核一下商店页"是"评审"的意思，不是平台送审。
    # 同理用 "隐私政策" 而不是裸的 "隐私"。
    "launch-compliance": [
        "过审", "送审", "上架", "版号", "isbn", "分级", "合规",
        "隐私政策", "防沉迷", "退款", "机型适配", "适配",
    ],
}


@dataclass
class IntentResult:
    task_type: Optional[str]
    mode: str = "standard"
    persona_pack: str = "game-core"
    artifact_text: str = ""
    confidence: float = 0.0
    needs_clarification: bool = False
    clarifying_question: Optional[str] = None
    method: str = "heuristic"  # heuristic | llm
    candidates: List[str] = field(default_factory=list)
    # 插入技能：只有 red_team_audience / audience_panel 真正改变 prompt 取向
    # （见 web/backend/app/services/__init__.py 的 get_skill_prompt_hint）。
    skill_type: Optional[str] = None
    # 呼叫角色：用户点名想要的具体人格 id（必须落在 persona_pack 对应的包内）。
    matched_personas: List[str] = field(default_factory=list)
    # 长期评审项目：用户给的项目名，前端按它把历次评审聚合成时间线（纯字符串分组，无独立实体）。
    project_key: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


# 只有这两种技能能通过对话触发——synthetic_playtest 是默认流程，persona_generate
# 是"生成角色"这个完全不同的动作，不该借评审创建这个入口触发。
CHAT_SKILL_TYPES = ["red_team_audience", "audience_panel"]

SKILL_KEYWORDS = {
    "red_team_audience": ["红队", "找茬", "挑刺", "对抗性", "唱反调", "使劲喷", "往死里挑", "红队受众"],
    "audience_panel": ["大众消费者视角", "非游戏受众", "普通消费者视角", "受众面板"],
}

_PERSONA_CALL_TRIGGERS = ["叫上", "带上", "召唤", "呼叫角色", "指定角色", "这几个角色", "这个角色来", "加上这个角色"]

_PROJECT_TRIGGER_RE = re.compile(r"长期评审项目|长期项目|评审项目")
_QUOTED_NAME_RE = re.compile(r"[「『\"“']([^」』\"”']{1,30})[」』\"”']")
_PROJECT_NAME_RE = re.compile(r"([^\s，。！？,\.!?]{2,20})(?:的)?(?:长期评审项目|长期项目|评审项目)")


def _match_skill_heuristic(text: str) -> Optional[str]:
    for skill_type, words in SKILL_KEYWORDS.items():
        if any(w in text for w in words):
            return skill_type
    return None


def _match_personas(hint_text: str, pack_key: str) -> List[str]:
    """拿一段文字（用户原话，或 LLM 抽出来的短语）去匹配 pack_key 对应人格包里
    每个角色的 archetype/name 字段——命中即视为"点名要这个角色"。"""
    if not hint_text:
        return []
    try:
        from app.services import PersonaService

        packs = PersonaService.load_all_personas()
    except Exception:
        return []
    personas = packs.get(pack_key, [])
    matched = []
    for p in personas:
        archetype = (p.get("archetype") or "").strip()
        name = (p.get("name") or "").strip()
        if archetype and archetype in hint_text:
            matched.append(p["id"])
        elif name and len(name) >= 2 and name in hint_text:
            matched.append(p["id"])
    return matched


def _has_persona_call_trigger(text: str) -> bool:
    return any(w in text for w in _PERSONA_CALL_TRIGGERS)


def _extract_project_key(text: str) -> Optional[str]:
    if not _PROJECT_TRIGGER_RE.search(text):
        return None
    m = _QUOTED_NAME_RE.search(text)
    if m:
        key = m.group(1).strip()
        if key:
            return key
    m2 = _PROJECT_NAME_RE.search(text)
    if m2:
        key = m2.group(1).strip()
        if key:
            return key
    return None


# ---------------- 启发式档（零成本、离线、可单测）----------------

def _score_keywords(text: str, table: dict) -> dict:
    low = text.lower()
    scores = {}
    for key, words in table.items():
        hit = sum(1 for w in words if w.lower() in low)
        if hit:
            scores[key] = hit
    return scores


def parse_intent_heuristic(text: str) -> IntentResult:
    text = (text or "").strip()
    if not text:
        return IntentResult(
            task_type=None,
            confidence=0.0,
            needs_clarification=True,
            clarifying_question="请贴上你要评审的材料，或说明你想评审什么。",
        )

    task_scores = _score_keywords(text, TASK_KEYWORDS)
    mode_scores = _score_keywords(text, MODE_KEYWORDS)
    pack_scores = _score_keywords(text, PACK_KEYWORDS)

    task_type = None
    confidence = 0.0
    candidates = []
    if task_scores:
        ranked = sorted(task_scores.items(), key=lambda kv: kv[1], reverse=True)
        task_type = ranked[0][0]
        candidates = [k for k, _ in ranked[:3]]
        top = ranked[0][1]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        # 置信度：命中数越多、与第二名差距越大越自信
        confidence = min(0.95, 0.45 + 0.15 * top + 0.1 * (top - runner_up))

    mode = "standard"
    if mode_scores:
        mode = max(mode_scores.items(), key=lambda kv: kv[1])[0]

    pack = "game-core"
    if pack_scores:
        pack = max(pack_scores.items(), key=lambda kv: kv[1])[0]
    elif task_type in DEFAULT_PACK_BY_TASK_TYPE:
        pack = DEFAULT_PACK_BY_TASK_TYPE[task_type]

    needs_clarification = task_type is None or confidence < 0.5
    question = None
    if needs_clarification:
        question = (
            "没能确定你想做哪种评审。是想评 Steam 商店页、Demo 首玩体验、"
            "游戏概念，还是付费设计？"
        )

    skill_type = _match_skill_heuristic(text)
    matched_personas = _match_personas(text, pack) if _has_persona_call_trigger(text) else []
    project_key = _extract_project_key(text)

    return IntentResult(
        task_type=task_type,
        mode=mode,
        persona_pack=pack,
        artifact_text=text,
        confidence=round(confidence, 2),
        needs_clarification=needs_clarification,
        clarifying_question=question,
        method="heuristic",
        candidates=candidates,
        skill_type=skill_type,
        matched_personas=matched_personas,
        project_key=project_key,
    )


# ---------------- LLM 档 ----------------

_LLM_PROMPT = """你是评审系统的意图解析器。把用户的一句话映射成结构化参数。

可选 task_type（必须从中选一个，选不出则填 null）：
{task_types}

可选 mode：quick（快速扫一眼）| standard（默认）| full（全面深入/要拍板）
可选 persona_pack：game-core（游戏类任务默认）| mobile-f2p | vr-immersive | accessibility |
  educational-serious | competitive-esport | family-casual | indie-creative |
  general-consumer（非游戏的通用产品任务用这个，如 product_feedback_review /
  pricing_page_review / onboarding_review）|
  startup-panel（创业项目/BP/路演评审 pitch_review 用这个——投资人/尽调/孵化器视角）

可选 skill_type（用户明确要求某种特殊评审方式才填，不确定就填 null，不要瞎猜）：
  red_team_audience —— 用户要求"红队""找茬""对抗性""专挑毛病"式评审
  audience_panel —— 用户明确要求"非游戏/大众消费者视角"而非硬核玩家视角

persona_hint：用户如果明确点名想要某类具体角色参与评审（如"叫上毒舌差评的""带上价格敏感的买家"），
  提取一段能匹配角色特征的短语放这里；没有明确点名就填 null。

project_key：用户如果明确说要创建/延续一个"长期评审项目"并给出了项目名，把项目名放这里；
  没有明确提到"项目"概念就填 null。

用户输入：
{text}

只输出 JSON，不要其他内容：
{{"task_type": "...", "mode": "...", "persona_pack": "...", "confidence": 0.0, "clarifying_question": null,
  "skill_type": null, "persona_hint": null, "project_key": null}}
confidence 是你对 task_type 判断的把握（0-1）。若无法确定，task_type 填 null，
并在 clarifying_question 里写一句要问用户的话。"""


def parse_intent_llm(
    text: str,
    api_key: str,
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_base: Optional[str] = None,
) -> Optional[IntentResult]:
    """LLM 档。任何异常返回 None，由调用方降级到启发式。

    走 runner.llm_client 统一出口——不再假定官方 Anthropic 端点。此前这里直接
    anthropic.Anthropic(api_key=api_key) 手搓调用，完全没用到用户 BYOK 配的
    provider/api_base/model：配了第三方中转（DeepSeek/Kimi/MiniMax 等 Anthropic
    兼容中转）的用户，key 拿去打官方 api.anthropic.com 必然认证失败被吞掉，
    静默退化成启发式档，界面上完全看不出发生了什么——像是"填了 key 也没用"。
    """
    try:
        import os
        import sys

        _src = os.path.join(settings.repo_root, "src")
        if _src not in sys.path:
            sys.path.insert(0, _src)
        from runner.llm_client import chat_completion

        effective_model = model or settings.intent_model
        raw, _in_tok, _out_tok = chat_completion(
            model=effective_model,
            prompt=_LLM_PROMPT.format(
                task_types="\n".join(f"- {t}" for t in VALID_TASK_TYPES), text=text
            ),
            api_key=api_key,
            provider=provider,
            api_base=api_base,
            max_tokens=512,
        )
        raw = raw.strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))

        task_type = data.get("task_type")
        if task_type not in VALID_TASK_TYPES:
            task_type = None
        mode = data.get("mode") if data.get("mode") in VALID_MODES else "standard"
        pack = data.get("persona_pack") or DEFAULT_PACK_BY_TASK_TYPE.get(task_type, "game-core")
        confidence = float(data.get("confidence") or 0.0)

        skill_type = data.get("skill_type")
        if skill_type not in CHAT_SKILL_TYPES:
            skill_type = None
        persona_hint = (data.get("persona_hint") or "").strip()
        matched_personas = _match_personas(persona_hint, pack) if persona_hint else []
        project_key = data.get("project_key")
        if isinstance(project_key, str):
            project_key = project_key.strip()[:60] or None
        else:
            project_key = None

        return IntentResult(
            task_type=task_type,
            mode=mode,
            persona_pack=pack,
            artifact_text=text,
            confidence=round(min(max(confidence, 0.0), 1.0), 2),
            needs_clarification=task_type is None,
            clarifying_question=data.get("clarifying_question"),
            method="llm",
            skill_type=skill_type,
            matched_personas=matched_personas,
            project_key=project_key,
        )
    except Exception:
        return None


def parse_intent(
    text: str,
    api_key: Optional[str] = None,
    provider: str = "anthropic",
    model: Optional[str] = None,
    api_base: Optional[str] = None,
) -> IntentResult:
    """对外入口：优先 LLM，失败自动降级启发式（永不因为解析失败而阻断用户）。"""
    if api_key and settings.intent_llm_enabled:
        result = parse_intent_llm(text, api_key, provider=provider, model=model, api_base=api_base)
        if result is not None:
            return result
    return parse_intent_heuristic(text)
