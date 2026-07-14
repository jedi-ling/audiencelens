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
import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from app.config import settings

VALID_TASK_TYPES = [
    "steam_page_review",
    "demo_first_play",
    "concept_review",
    "monetization_review",
    "looking_for_party_post",
    "update_announcement_review",
    "devlog_review",
    "kickstarter_review",
    "localization_review",
    "discord_community_review",
]

VALID_MODES = ["quick", "standard", "full"]

# 关键词 → 任务类型（启发式档）。命中即加分，取最高分。
TASK_KEYWORDS = {
    "steam_page_review": ["steam", "商店页", "store", "页面", "愿望单", "标签", "封面", "宣传图"],
    "demo_first_play": ["demo", "试玩", "首玩", "上手", "新手引导", "教程", "前15分钟", "前 15 分钟"],
    "concept_review": ["概念", "点子", "创意", "核心循环", "玩法设计", "立项", "idea"],
    "monetization_review": ["付费", "定价", "内购", "氪金", "价格", "月卡", "抽卡", "变现", "付费墙"],
    "looking_for_party_post": ["组队", "招募", "找队友", "招人"],
    "update_announcement_review": ["更新公告", "版本更新", "patch", "补丁", "更新日志"],
    "devlog_review": ["开发日志", "devlog", "开发者日志"],
    "kickstarter_review": ["众筹", "kickstarter", "回报档位", "众筹页"],
    "localization_review": ["本地化", "翻译", "汉化", "localization", "多语言"],
    "discord_community_review": ["discord", "社区运营", "社群", "频道"],
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

    def to_dict(self) -> dict:
        return asdict(self)


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

    needs_clarification = task_type is None or confidence < 0.5
    question = None
    if needs_clarification:
        question = (
            "没能确定你想做哪种评审。是想评 Steam 商店页、Demo 首玩体验、"
            "游戏概念，还是付费设计？"
        )

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
    )


# ---------------- LLM 档 ----------------

_LLM_PROMPT = """你是评审系统的意图解析器。把用户的一句话映射成结构化参数。

可选 task_type（必须从中选一个，选不出则填 null）：
{task_types}

可选 mode：quick（快速扫一眼）| standard（默认）| full（全面深入/要拍板）
可选 persona_pack：game-core（默认）| mobile-f2p | vr-immersive | accessibility |
  educational-serious | competitive-esport | family-casual | indie-creative

用户输入：
{text}

只输出 JSON，不要其他内容：
{{"task_type": "...", "mode": "...", "persona_pack": "...", "confidence": 0.0, "clarifying_question": null}}
confidence 是你对 task_type 判断的把握（0-1）。若无法确定，task_type 填 null，
并在 clarifying_question 里写一句要问用户的话。"""


def parse_intent_llm(text: str, api_key: str) -> Optional[IntentResult]:
    """LLM 档。任何异常返回 None，由调用方降级到启发式。"""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=settings.intent_model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": _LLM_PROMPT.format(
                        task_types="\n".join(f"- {t}" for t in VALID_TASK_TYPES), text=text
                    ),
                }
            ],
        )
        raw = resp.content[0].text.strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))

        task_type = data.get("task_type")
        if task_type not in VALID_TASK_TYPES:
            task_type = None
        mode = data.get("mode") if data.get("mode") in VALID_MODES else "standard"
        pack = data.get("persona_pack") or "game-core"
        confidence = float(data.get("confidence") or 0.0)

        return IntentResult(
            task_type=task_type,
            mode=mode,
            persona_pack=pack,
            artifact_text=text,
            confidence=round(min(max(confidence, 0.0), 1.0), 2),
            needs_clarification=task_type is None,
            clarifying_question=data.get("clarifying_question"),
            method="llm",
        )
    except Exception:
        return None


def parse_intent(text: str, api_key: Optional[str] = None) -> IntentResult:
    """对外入口：优先 LLM，失败自动降级启发式（永不因为解析失败而阻断用户）。"""
    if api_key and settings.intent_llm_enabled:
        result = parse_intent_llm(text, api_key)
        if result is not None:
            return result
    return parse_intent_heuristic(text)
