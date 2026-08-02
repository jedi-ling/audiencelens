import asyncio
import os
import random
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Base, Review, SkillType
from app.services.json_safe import json_safe, json_safe_key

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

# 这里只留「选人 + 算钱」两件事要用的引擎符号。
# 聚合、校准、交叉质询、提示词渲染、输出校验的那一串 import 曾经也在这里，
# 因为本模块自带一套与 runner.cli.run_panel 平行的评审实现（ReviewService.run_review）。
# 那套实现已删除，import 一并删掉——留着会让人误以为后端还有第二条执行路径。
from runner.panel_selector import select_panel
from runner.persona_agent import estimate_cost

PERSONAS_DIR = os.path.join(PROJECT_ROOT, "src", "personas")
AGENTS_DIR = os.path.join(PROJECT_ROOT, ".claude", "agents")
TRAE_PERSONAS_DIR = os.path.join(PROJECT_ROOT, ".trae", "skills", "synthetic-playtest", "personas")
PRESETS_PATH = os.path.join(PROJECT_ROOT, "src", "presets", "panel-presets.yaml")
# BUDGET_PATH 仍是全后端算钱的唯一取数口（chat_service 也读它），别再各自 open。
BUDGET_PATH = os.path.join(PROJECT_ROOT, "src", "config", "budget.yaml")


def load_budget_config() -> Dict[str, Any]:
    """读定价/预算配置。任何要算钱的地方都从这里拿，别再各自 open 一遍——
    路径写岔了就会静默拿到空 dict，而空 dict 意味着所有成本算成 0。"""
    with open(BUDGET_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

TASK_TYPES: Dict[str, Dict[str, Any]] = {
    "steam_page_review": {
        "name_zh": "Steam页评审",
        "description": "商店页信息架构、视觉传达、信任信号",
        "stance_enum": ["加愿望单", "不加", "观望"],
        "score_dimensions": ["differentiation", "value_for_money", "wishlist_appeal"],
    },
    "demo_first_play": {
        "name_zh": "Demo首玩",
        "description": "上手摩擦、手感、首15分钟体验",
        "stance_enum": ["继续试玩", "退出", "观望"],
        "score_dimensions": ["retention_potential", "onboarding_friendliness", "moment_to_moment_feel"],
    },
    "concept_review": {
        "name_zh": "概念评审",
        "description": "核心循环、差异化、可行性",
        "stance_enum": ["值得推进", "不值得", "观望"],
        "score_dimensions": ["differentiation", "retention_potential", "aesthetic_coherence"],
    },
    "monetization_review": {
        "name_zh": "商业化评审",
        "description": "定价、付费边界、价值感知",
        "stance_enum": ["会买", "不买", "观望"],
        "score_dimensions": ["value_for_money", "fairness", "transparency"],
    },
    "looking_for_party_post": {
        "name_zh": "找搭子帖",
        "description": "社区文案、传播性、社交吸引力",
        "stance_enum": ["会转发", "不会", "观望"],
        "score_dimensions": ["social_appeal", "friction_to_join", "shareability"],
    },
    "update_announcement_review": {
        "name_zh": "更新公告",
        "description": "版本日志、信任强化、留存信号",
        "stance_enum": ["增强信心", "降低信心", "无影响"],
        "score_dimensions": ["communication_clarity", "trust_reinforcement", "retention_signal"],
    },
    "kickstarter_review": {
        "name_zh": "众筹页评审",
        "description": "众筹页叙事、回报设计、信任建立",
        "stance_enum": ["会支持", "不会", "观望"],
        "score_dimensions": ["narrative_strength", "reward_value", "trust_signals"],
    },
    "discord_community_review": {
        "name_zh": "社区运营评审",
        "description": "社区氛围、互动设计、用户留存",
        "stance_enum": ["会加入", "不会", "观望"],
        "score_dimensions": ["community_vibe", "engagement_design", "retention_signal"],
    },
    "devlog_review": {
        "name_zh": "开发日志评审",
        "description": "叙事节奏、透明度、社区反馈",
        "stance_enum": ["增强期待", "降低期待", "无影响"],
        "score_dimensions": ["narrative_rhythm", "transparency", "community_feedback"],
    },
    "localization_review": {
        "name_zh": "本地化评审",
        "description": "文化适配、语言质量、UI适配",
        "stance_enum": ["文化适配良好", "存在问题", "观望"],
        "score_dimensions": ["cultural_adaptation", "language_quality", "ui_adaptation"],
    },
    "product_feedback_review": {
        "name_zh": "产品反馈评审",
        "description": "通用产品反馈收集与解读，不限游戏",
        "stance_enum": ["会继续用", "会流失", "观望"],
        "score_dimensions": ["usability", "value_perception", "trust_signals"],
    },
    "pricing_page_review": {
        "name_zh": "定价页评审",
        "description": "定价分层、价值传达、信任信号，不限游戏",
        "stance_enum": ["会付费", "不会", "观望"],
        "score_dimensions": ["value_for_money", "pricing_clarity", "trust_signals"],
    },
    "onboarding_review": {
        "name_zh": "新手引导评审",
        "description": "首次使用体验、上手摩擦，不限游戏",
        "stance_enum": ["会留下", "会放弃", "观望"],
        "score_dimensions": ["onboarding_friendliness", "time_to_value", "clarity"],
    },
    "pitch_review": {
        "name_zh": "创业项目评审",
        "description": "BP/路演/申报表，投资人与尽调视角",
        "stance_enum": ["值得跟进", "不投", "观望"],
        "score_dimensions": ["market_potential", "team_credibility", "evidence_quality"],
    },
}

# 展示元数据必须与引擎单一注册表（src/runner/task_types.py）完全对齐——
# 此前这里多出 4 个引擎不认的类型（前端展示了、用户选了创建必 400），
# 同时少了 4 个引擎支持的通用类型（做了功能没露出）。漂移就在导入时炸。
from runner.task_types import VALID_TASK_TYPES as _ENGINE_TASK_TYPES  # noqa: E402

assert set(TASK_TYPES) == set(_ENGINE_TASK_TYPES), (
    "services.TASK_TYPES 与 runner/task_types.py 不一致："
    f"仅元数据有 {set(TASK_TYPES) - set(_ENGINE_TASK_TYPES)}；"
    f"仅注册表有 {set(_ENGINE_TASK_TYPES) - set(TASK_TYPES)}"
)

REVIEW_MODES: Dict[str, Dict[str, Any]] = {
    "quick": {
        "persona_count_range": [3, 3],
        "cross_examination": False,
        "calibration": False,
        "description": "快速初筛，5分钟内出结果",
    },
    "standard": {
        "persona_count_range": [4, 6],
        "cross_examination": True,
        "calibration": False,
        "description": "日常评审，平衡速度和深度",
    },
    "full": {
        "persona_count_range": [6, 8],
        "cross_examination": True,
        "calibration": True,
        "description": "正式评审，完整流程",
    },
}

# 注：交叉质询的档位映射、多智能体反驳的身份前言、失败兜底区块，以前在这里
# 各有一份，供 ReviewService.run_review 这套「与引擎平行的第二实现」使用。
# run_review 已删除（POST /api/reviews 现在与 v2 同走 runner.cli.run_panel），
# 那三样的唯一权威定义在 src/runner/cli.py 下（CROSS_EXAM_MODE_BY_REVIEW_MODE、
# _rebuttal_persona_card 等）。这里不再留副本——留着只会让下一个人以为
# 「这里也要同步改」，而本轮审计里最常见的一种缺陷正是「只改了一边」。

# 实现搬到 app/services/json_safe.py：v2 的 review_service 也要用同一份口径，
# 留在这里会让 v2 要么重复实现、要么从包 __init__ 反向 import。
# 保留这两个别名，模块内既有调用点与测试不必改。
_json_safe_key = json_safe_key
_json_safe = json_safe


class PersonaService:
    _personas_cache: Dict[str, List[dict]] = {}
    _packs_cache: List[dict] = []
    _agents_cache: Dict[str, List[dict]] = {}
    _trae_cache: Dict[str, List[dict]] = {}

    PACK_CATEGORY_MAP = {
        'game-core': 'player-type',
        'competitive-esport': 'player-type',
        'family-casual': 'player-type',
        'indie-creative': 'player-type',
        'mobile-f2p': 'platform',
        'vr-immersive': 'platform',
        'accessibility': 'special',
        'educational-serious': 'special',
        'general-consumer': 'general',
        'startup-panel': 'general',
    }

    @classmethod
    def _load_pack(cls, yaml_path: str) -> List[dict]:
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("personas", [])
        except Exception:
            return []

    @classmethod
    def _parse_agent_md(cls, md_path: str) -> Optional[dict]:
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()

            frontmatter = {}
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1].strip()
                    frontmatter = yaml.safe_load(fm_text) or {}
                    content = parts[2].strip()

            persona_id = frontmatter.get("name", os.path.splitext(os.path.basename(md_path))[0])

            sections: Dict[str, str] = {}
            current_section = None
            current_lines: List[str] = []
            for line in content.split("\n"):
                heading_match = re.match(r"^##\s+(.+)$", line.strip())
                if heading_match:
                    if current_section:
                        sections[current_section] = "\n".join(current_lines).strip()
                    current_section = heading_match.group(1).strip()
                    current_lines = []
                else:
                    current_lines.append(line)
            if current_section:
                sections[current_section] = "\n".join(current_lines).strip()

            identity_summary = sections.get("Identity", "")
            name_match = re.match(r"^#\s+(.+?)\s*[—–-]\s*(.+)$", content.split("\n")[0] if content else "")
            persona_name = name_match.group(1) if name_match else persona_id
            archetype = name_match.group(2) if name_match else ""

            behavior_profile = {}
            bp_text = sections.get("Behavior Profile", "")
            for line in bp_text.split("\n"):
                line = line.strip().lstrip("- ")
                if ":" in line:
                    key, val = line.split(":", 1)
                    behavior_profile[key.strip().lower().replace(" ", "_")] = val.strip()

            motivations = []
            mot_text = sections.get("Motivations", "")
            for line in mot_text.split("\n"):
                line = line.strip().lstrip("- ")
                if line:
                    motivations.append(line)

            decision_rules = []
            dr_text = sections.get("Decision Rules", "")
            for line in dr_text.split("\n"):
                line = line.strip().lstrip("- ")
                if line:
                    decision_rules.append(line)

            continue_triggers = []
            ct_text = sections.get("Continue Triggers", "")
            for line in ct_text.split("\n"):
                line = line.strip().lstrip("- ")
                if line:
                    continue_triggers.append(line)

            quit_triggers = []
            qt_text = sections.get("Quit Triggers", "")
            for line in qt_text.split("\n"):
                line = line.strip().lstrip("- ")
                if line:
                    quit_triggers.append(line)

            evidence_types_needed = []
            ef_text = sections.get("Evidence Focus", "")
            for line in ef_text.split("\n"):
                line = line.strip().lstrip("- ")
                if line:
                    evidence_types_needed.append(line)

            review_output = {}
            ro_text = sections.get("Review Output Requirements", "")
            for line in ro_text.split("\n"):
                line = line.strip().lstrip("- ")
                if line.startswith("Must comment on:"):
                    review_output["must_comment_on"] = [x.strip() for x in line.split(":", 1)[1].split(",")]
                elif line.startswith("Evidence ceiling:"):
                    review_output["strictness"] = int(line.split(":")[1].strip().split("/")[0])
                elif line.startswith("Stance mapping:"):
                    review_output["tone"] = line.split(":", 1)[1].strip()

            return {
                "id": persona_id,
                "name": persona_name,
                "archetype": archetype,
                "identity_summary": identity_summary,
                "behavior_profile": behavior_profile,
                "gaming_profile": {},
                "motivations": motivations,
                "decision_rules": decision_rules,
                "continue_triggers": continue_triggers,
                "quit_triggers": quit_triggers,
                "evidence_types_needed": evidence_types_needed,
                "review_output": review_output,
                "model_hint": frontmatter.get("model", "sonnet"),
                "source": "agent-md",
            }
        except Exception:
            return None

    @classmethod
    def load_agents_from_md(cls) -> Dict[str, List[dict]]:
        if cls._agents_cache:
            return cls._agents_cache
        if not os.path.isdir(AGENTS_DIR):
            return {}
        for fname in os.listdir(AGENTS_DIR):
            if fname.endswith(".md"):
                path = os.path.join(AGENTS_DIR, fname)
                parsed = cls._parse_agent_md(path)
                if parsed:
                    pack_id = "claude-agents"
                    if pack_id not in cls._agents_cache:
                        cls._agents_cache[pack_id] = []
                    cls._agents_cache[pack_id].append(parsed)
        return cls._agents_cache

    @classmethod
    def load_trae_personas(cls) -> Dict[str, List[dict]]:
        if cls._trae_cache:
            return cls._trae_cache
        if not os.path.isdir(TRAE_PERSONAS_DIR):
            return {}
        for fname in os.listdir(TRAE_PERSONAS_DIR):
            if fname.endswith((".yaml", ".yml")):
                pack_id = os.path.splitext(fname)[0]
                path = os.path.join(TRAE_PERSONAS_DIR, fname)
                personas = cls._load_pack(path)
                for p in personas:
                    p["source"] = "trae-yaml"
                cls._trae_cache[pack_id] = personas
        return cls._trae_cache

    @classmethod
    def load_all_personas(cls) -> Dict[str, List[dict]]:
        if cls._personas_cache:
            return cls._personas_cache
        if not os.path.isdir(PERSONAS_DIR):
            return {}
        for fname in os.listdir(PERSONAS_DIR):
            if fname.endswith((".yaml", ".yml")):
                pack_id = os.path.splitext(fname)[0]
                path = os.path.join(PERSONAS_DIR, fname)
                cls._personas_cache[pack_id] = cls._load_pack(path)
        return cls._personas_cache

    @classmethod
    def get_all_personas(cls) -> List[dict]:
        """聚合视图只取 src/personas/*.yaml 这一份正主数据。

        .claude/agents 与 .trae 下的 persona 是开发工具链的镜像副本，id 与正主
        完全重复——混进聚合列表会让前端拿到重复 id（React key 冲突，列表 diff
        直接错乱，角色页的包筛选因此失效）。按包名直连的
        get_personas_by_pack() 仍保留对这两个来源的回落，供工具链调试用。
        """
        all_personas = []
        for pack_id, personas in cls.load_all_personas().items():
            for p in personas:
                p_copy = dict(p)
                p_copy["_pack"] = pack_id
                p_copy["source"] = p_copy.get("source", "yaml")
                all_personas.append(p_copy)
        return all_personas

    @classmethod
    def get_persona_by_id(cls, persona_id: str) -> Optional[dict]:
        for p in cls.get_all_personas():
            if p["id"] == persona_id:
                return p
        return None

    @classmethod
    def get_personas_by_pack(cls, pack_name: str) -> List[dict]:
        all_sources = [
            cls.load_all_personas(),
            cls.load_agents_from_md(),
            cls.load_trae_personas(),
        ]
        for source in all_sources:
            if pack_name in source:
                result = []
                for p in source[pack_name]:
                    p_copy = dict(p)
                    p_copy["_pack"] = pack_name
                    result.append(p_copy)
                return result
        return []

    @classmethod
    def get_persona(cls, persona_id: str) -> Optional[dict]:
        return cls.get_persona_by_id(persona_id)

    @classmethod
    def list_packs(cls) -> List[dict]:
        if cls._packs_cache:
            return cls._packs_cache
        all_packs = cls.load_all_personas()
        for pack_id, personas in all_packs.items():
            path = os.path.join(PERSONAS_DIR, f"{pack_id}.yaml")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                cls._packs_cache.append({
                    "panel_id": data.get("panel_id", pack_id),
                    "name": data.get("name", pack_id),
                    "description": data.get("description", ""),
                    "persona_count": len(personas),
                    "category": cls.PACK_CATEGORY_MAP.get(pack_id, 'special'),
                })
            except Exception:
                cls._packs_cache.append({
                    "panel_id": pack_id,
                    "name": pack_id,
                    "description": "",
                    "persona_count": len(personas),
                    "category": cls.PACK_CATEGORY_MAP.get(pack_id, 'special'),
                })

        # 注：不把 .claude/agents / .trae 的镜像副本列进包清单——
        # 它们的 panel_id 与正主 yaml 完全重复，会让前端出现同 id 的重复包。
        return cls._packs_cache

    @classmethod
    def load_presets(cls) -> dict:
        try:
            with open(PRESETS_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("presets", {})
        except Exception:
            return {}

    @classmethod
    def get_preset(cls, task_type: str) -> Optional[dict]:
        presets = cls.load_presets()
        return presets.get(task_type)

    @classmethod
    def get_task_types(cls) -> List[dict]:
        result = []
        for task_type, info in TASK_TYPES.items():
            result.append({
                "task_type": task_type,
                "name_zh": info["name_zh"],
                "description": info["description"],
                "stance_enum": info["stance_enum"],
                "score_dimensions": info["score_dimensions"],
                "base_dimensions": ["clarity", "trust"],
            })
        return result

    @classmethod
    def get_task_type(cls, task_type: str) -> Optional[dict]:
        info = TASK_TYPES.get(task_type)
        if not info:
            return None
        return {
            "task_type": task_type,
            "name_zh": info["name_zh"],
            "description": info["description"],
            "stance_enum": info["stance_enum"],
            "score_dimensions": info["score_dimensions"],
            "base_dimensions": ["clarity", "trust"],
        }

    @classmethod
    def get_review_modes(cls) -> List[dict]:
        result = []
        for mode, config in REVIEW_MODES.items():
            result.append({
                "mode": mode,
                "persona_count_range": config["persona_count_range"],
                "cross_examination": config["cross_examination"],
                "calibration": config["calibration"],
                "description": config["description"],
            })
        return result

    @classmethod
    def select_panel_by_mode(cls, task_type: str, mode: str, persona_pack: Optional[str] = None, selected_personas: Optional[List[str]] = None) -> List[dict]:
        mode_config = REVIEW_MODES.get(mode, REVIEW_MODES["standard"])
        min_count, max_count = mode_config["persona_count_range"]

        all_packs = cls.load_all_personas()
        pack_key = persona_pack or "game-core"
        personas = all_packs.get(pack_key, [])

        if selected_personas:
            selected = [p for p in personas if p["id"] in selected_personas]
            if len(selected) > max_count:
                selected = selected[:max_count]
            return selected

        presets = cls.load_presets()
        try:
            panel = select_panel(task_type, personas, presets)
            selected = panel["selected"]
        except ValueError:
            if personas:
                # random 已在模块顶部 import。此处原本是函数内 import，而下方"人数不足
                # 补人"分支同样用 random.sample —— Python 的函数级名字绑定会让 random
                # 在整个函数里都算局部名，于是走不到 except 的正常路径上它从未被赋值，
                # 补人时直接 UnboundLocalError。触发条件正是"预设选出的人数少于下限"，
                # 也就是 pitch_review / product_feedback_review / pricing_page_review
                # 这三个预设人选不在默认 game-core 包里的任务类型——它们此前 100% 失败。
                selected = random.sample(personas, min(max_count, len(personas)))
            else:
                selected = []

        if len(selected) > max_count:
            selected = selected[:max_count]
        elif len(selected) < min_count:
            remaining = [p for p in personas if p not in selected]
            needed = min_count - len(selected)
            if remaining:
                fill = random.sample(remaining, min(needed, len(remaining)))
                selected.extend(fill)

        return selected

    @classmethod
    def invalidate_cache(cls):
        cls._personas_cache = {}
        cls._packs_cache = []
        cls._agents_cache = {}
        cls._trae_cache = {}

    @classmethod
    def get_skill_types(cls) -> List[dict]:
        """获取所有可用的技能类型"""
        skill_info = {
            SkillType.SYNTHETIC_PLAYTEST: {
                "name": "合成试玩",
                "description": "使用 persona 面板模拟目标受众进行产品评审",
            },
            SkillType.AUDIENCE_PANEL: {
                "name": "受众面板",
                "description": "非游戏领域的受众面板评审，适用于通用产品评审",
            },
            SkillType.RED_TEAM_AUDIENCE: {
                "name": "红队受众",
                "description": "使用对抗性 persona 发现产品弱点和风险",
            },
            SkillType.PERSONA_GENERATE: {
                "name": "Persona 生成",
                "description": "根据领域、受众和目标自动生成 persona 定义",
            },
        }
        result = []
        for skill_type in SkillType:
            info = skill_info.get(skill_type, {"name": skill_type.value, "description": ""})
            result.append({
                "skill_type": skill_type.value,
                "name": info["name"],
                "description": info["description"],
            })
        return result

    @classmethod
    def get_skill_detail(cls, skill_type: str) -> Optional[dict]:
        """获取指定技能类型的详细信息"""
        try:
            st = SkillType(skill_type)
        except ValueError:
            return None
        skills = cls.get_skill_types()
        for s in skills:
            if s["skill_type"] == skill_type:
                detail = dict(s)
                if st == SkillType.SYNTHETIC_PLAYTEST:
                    detail["available_packs"] = [p["panel_id"] for p in cls.list_packs()]
                    detail["task_types"] = [tt["task_type"] for tt in cls.get_task_types()]
                elif st == SkillType.AUDIENCE_PANEL:
                    detail["supported_domains"] = ["product", "service", "content", "brand"]
                elif st == SkillType.RED_TEAM_AUDIENCE:
                    detail["attack_surfaces"] = ["claims", "ux_friction", "trust_gaps", "value_proposition"]
                elif st == SkillType.PERSONA_GENERATE:
                    detail["parameters"] = ["domain", "audience", "goals", "count"]
                return detail
        return None

    # 只有这两种技能对应"评审时换一种视角看"，能真正影响 prompt 取向；
    # synthetic_playtest 是默认流程（无需额外提示），persona_generate 是生成角色
    # 这个完全不同的动作，不该通过"创建评审"这个入口触发，所以不给它提示语。
    _SKILL_PROMPT_HINTS = {
        SkillType.RED_TEAM_AUDIENCE.value: (
            "本次评审请采用红队/对抗性视角：优先挖掘产品的弱点、风险和「劝退点」，"
            "而不是常规的体验反馈——目标是帮团队在正式上线前找出最容易被喷、被弃、被吐槽的地方。"
        ),
        SkillType.AUDIENCE_PANEL.value: (
            "本次评审请以非游戏、大众消费产品的视角来看——不要套用硬核玩家的评判标准，"
            "关注普通用户/消费者会不会用、看不看得懂、愿不愿意留下。"
        ),
    }

    @classmethod
    def get_skill_prompt_hint(cls, skill_type: Optional[str]) -> str:
        return cls._SKILL_PROMPT_HINTS.get(skill_type or "", "")

    @classmethod
    def generate_personas(
        cls,
        domain: str,
        audience: str = "",
        goals: str = "",
        count: int = 4,
        api_key: str = None,
        provider: str = "anthropic",
        model: str = None,
        api_base: str = None,
        usage: dict = None,
    ) -> List[dict]:
        """根据领域、受众和目标生成 persona YAML 定义列表。

        api_key 由调用方（走 resolve_llm_key）传入。以前这里是
        `os.environ.get("ANTHROPIC_API_KEY")` 直读环境变量，问题有三：
          · 完全绕过 key_service —— BYOK 用户填的 key/provider/端点一概不生效，
            配了第三方中转的人在这个功能上永远走不通；
          · 平台垫付的 key 被无身份、无配额地使用，谁调谁花运营的钱；
          · 用量记不到任何人头上，后台成本面板看不见这笔开销。
        usage 是可选出参，调用方据此把真实 token 记进 UsageRecord。
        """
        if not api_key:
            return cls._generate_personas_fallback(domain, audience, goals, count)

        try:
            import json

            prompt = f"""你是一个 persona 设计专家。请为以下场景生成 {count} 个差异化的 persona 定义。

领域: {domain}
目标受众: {audience or '通用'}
评审目标: {goals or '全面评审'}

请按以下 YAML 格式输出，每个 persona 包含 id, name, archetype, identity_summary, behavior_profile, motivations, decision_rules:

```yaml
personas:
  - id: persona_1
    name: 示例名称
    archetype: 行为原型
    identity_summary: 身份概述
    behavior_profile:
      patience: 低/中/高
      evidence_threshold: 低/中/高
      risk_tolerance: 低/中/高
    motivations:
      - 动机1
      - 动机2
    decision_rules:
      - 决策规则1
      - 决策规则2
```

确保每个 persona 有明显不同的行为特征和决策逻辑，避免刻板印象。"""

            # 统一走 runner.llm_client：与评审同一条出口，BYOK 的 provider/端点/模型
            # 全部生效（以前是手搓 anthropic.Anthropic，等于把非官方端点用户排除在外）
            effective_model = model or "claude-sonnet-4-20250514"
            content, in_tok, out_tok = chat_completion(
                model=effective_model,
                prompt=prompt,
                api_key=api_key,
                provider=provider,
                api_base=api_base,
                max_tokens=4096,
            )
            content = (content or "").strip()
            if usage is not None:
                usage["input_tokens"] = usage.get("input_tokens", 0) + int(in_tok or 0)
                usage["output_tokens"] = usage.get("output_tokens", 0) + int(out_tok or 0)
                usage["model"] = effective_model

            yaml_str = content
            if "```yaml" in yaml_str:
                yaml_str = yaml_str.split("```yaml")[1].split("```")[0].strip()
            elif "```" in yaml_str:
                yaml_str = yaml_str.split("```")[1].split("```")[0].strip()

            data = yaml.safe_load(yaml_str)
            if data and "personas" in data:
                return data["personas"]
            return []
        except Exception:
            return cls._generate_personas_fallback(domain, audience, goals, count)

    @classmethod
    def _generate_personas_fallback(cls, domain: str, audience: str, goals: str, count: int) -> List[dict]:
        """无 API key 时的 persona 生成回退方案"""
        archetypes = [
            {"archetype": "挑剔专家", "patience": "低", "evidence_threshold": "高", "risk_tolerance": "低"},
            {"archetype": "热情探索者", "patience": "高", "evidence_threshold": "低", "risk_tolerance": "高"},
            {"archetype": "务实决策者", "patience": "中", "evidence_threshold": "中", "risk_tolerance": "中"},
            {"archetype": "怀疑论者", "patience": "低", "evidence_threshold": "高", "risk_tolerance": "低"},
            {"archetype": "社交传播者", "patience": "中", "evidence_threshold": "低", "risk_tolerance": "高"},
            {"archetype": "价值敏感者", "patience": "中", "evidence_threshold": "中", "risk_tolerance": "低"},
        ]

        personas = []
        for i in range(min(count, len(archetypes))):
            a = archetypes[i]
            personas.append({
                "id": f"generated_{domain}_{i+1}",
                "name": f"{domain}{a['archetype']}",
                "archetype": a["archetype"],
                "identity_summary": f"针对{domain}领域的{a['archetype']}型受众",
                "behavior_profile": {
                    "patience": a["patience"],
                    "evidence_threshold": a["evidence_threshold"],
                    "risk_tolerance": a["risk_tolerance"],
                },
                "motivations": [f"在{domain}领域寻找{goals or '优质体验'}"],
                "decision_rules": [f"基于{a['evidence_threshold']}证据阈值做判断"],
            })
        return personas


def apply_skill_hint(artifact_bundle: dict, skill_type: Optional[str]) -> dict:
    """技能标签要真正影响评审，而不只是落库当个标签——把提示语当成一条材料，
    塞进 render_prompt 已经在读的 artifact_bundle.materials 里，每个人格都会看到。
    没有对应提示语（如 skill_type 为空、synthetic_playtest、persona_generate）时原样返回。"""
    hint = PersonaService.get_skill_prompt_hint(skill_type)
    if not hint:
        return artifact_bundle
    bundle = dict(artifact_bundle or {})
    materials = list(bundle.get("materials") or [])
    materials.insert(0, {"type": "text", "text": f"[评审技能：{skill_type}] {hint}"})
    bundle["materials"] = materials
    return bundle


class ReviewService:
    def __init__(self, session: Session):
        self.session = session

    def create_review(
        self,
        task_type: str,
        artifact_bundle: dict,
        persona_pack: Optional[str] = None,
        selected_personas: Optional[List[str]] = None,
        mode: str = "standard",
        user_id: str = "anonymous",
        skill_type: Optional[str] = None,
        project_key: Optional[str] = None,
    ) -> Review:
        review = Review(
            id=str(uuid.uuid4()),
            user_id=user_id,
            task_type=task_type,
            target_title=artifact_bundle.get("title"),
            artifact_bundle=apply_skill_hint(artifact_bundle, skill_type),
            persona_pack=persona_pack,
            selected_personas=selected_personas,
            skill_type=skill_type,
            project_key=project_key,
            mode=mode,
            status="pending",
            created_at=datetime.now(timezone.utc),
            total_cost_usd=0.0,
        )
        self.session.add(review)
        self.session.commit()
        self.session.refresh(review)
        return review

    def get_review(self, review_id: str) -> Optional[Review]:
        return self.session.get(Review, review_id)

    def list_reviews(self, offset: int = 0, limit: int = 20, user_id: Optional[str] = None) -> List[Review]:
        """user_id 传了就只列这个人的评审——不传（内部/管理用途）才是全量。
        对外的 /api/reviews 路由必须传，否则任何登录用户都能看到所有人的评审历史。"""
        stmt = select(Review).order_by(Review.created_at.desc()).offset(offset).limit(limit)
        if user_id is not None:
            stmt = stmt.where(Review.user_id == user_id)
        return list(self.session.scalars(stmt).all())

    def delete_review(self, review_id: str) -> bool:
        review = self.session.get(Review, review_id)
        if review is None:
            return False
        self.session.delete(review)
        self.session.commit()
        return True


class MaterialExtractor:
    TASK_FIELDS = {
        "concept_review": ["一句话pitch", "核心循环说明", "竞品对比", "目标受众", "定价与平台", "截图/视觉描述", "核心系统说明"],
        "demo_first_play": ["游戏名称", "核心玩法", "截图/视觉描述", "实机视频描述", "竞品参考", "已有评价"],
        "steam_page_review": ["游戏名称", "商店页截图描述", "标签/分类", "价格与平台", "简短描述", "详细描述", "系统需求"],
        "kickstarter_review": ["项目名称", "众筹目标", "项目描述", "回报层级", "团队介绍", "时间线"],
        "discord_community_review": ["社区名称", "社区规模", "主要话题", "管理策略", "活动计划", "成员反馈"],
        "devlog_review": ["项目名称", "开发阶段", "核心更新内容", "技术挑战", "社区反馈", "下一步计划"],
        "monetization_review": ["游戏名称", "付费模型", "定价策略", "内购项目", "通行证设计", "竞品对比"],
        "update_announcement_review": ["游戏名称", "更新版本", "更新内容", "已知问题", "玩家期待", "发布时间"],
        "localization_review": ["游戏名称", "源语言", "目标语言", "翻译样本", "文化敏感内容", "UI适配问题"],
        "looking_for_party_post": ["游戏名称", "组队需求", "玩家类型", "时间安排", "沟通方式", "期望队友"],
        "app_store_review": ["应用名称", "商店页截图描述", "标签/分类", "价格与平台", "简短描述", "详细描述", "系统需求"],
        "social_media_post": ["品牌名称", "帖文内容", "视觉素材描述", "目标受众", "发布平台", "互动目标"],
        "video_ad_review": ["产品名称", "视频前3秒内容", "核心卖点", "CTA", "目标受众", "投放平台"],
        "landing_page_review": ["产品名称", "首屏内容", "转化路径", "信任信号", "目标受众", "CTA"],
    }

    @classmethod
    def extract(cls, task_type: str, text: str, filename: str, resolved: Any = None) -> Dict[str, Any]:
        fields = cls.TASK_FIELDS.get(task_type, [])

        try:
            result = cls._extract_with_ai(task_type, text, fields, resolved=resolved)
            if result:
                return result
        except Exception:
            pass

        return cls._extract_fallback(task_type, text, fields, filename)

    @classmethod
    def _extract_with_ai(
        cls, task_type: str, text: str, fields: List[str], resolved: Any = None
    ) -> Optional[Dict[str, Any]]:
        """AI 抽取档。resolved 是 key_service.ResolvedKey——此前这里硬编码
        Anthropic 客户端 + os.environ 读 key，完全绕过 BYOK 体系：配了第三方
        中转/自定义模型的用户，抽取要么静默失败要么花的是环境变量里那把
        不属于他的 key。没有 resolved 时直接走 fallback，不再碰环境变量。"""
        if resolved is None:
            return None
        try:
            import json as _json

            from runner.llm_client import chat_completion

            fields_desc = "、".join(fields)

            prompt = f"""你是一个游戏评审材料提取助手。请从以下文档内容中，提取出结构化的评审材料。

任务类型：{task_type}
需要提取的字段：{fields_desc}

请按以下 JSON 格式输出，每个字段对应一段提取的内容。如果文档中没有某个字段的信息，该字段值留空字符串：
{{"title": "评审对象名称", "materials": {{"字段名1": "提取内容1", "字段名2": "提取内容2"}}}}

文档内容：
{text[:8000]}"""

            content, _in_tok, _out_tok = chat_completion(
                model=resolved.model or settings.intent_model,
                prompt=prompt,
                api_key=resolved.key,
                provider=resolved.provider,
                api_base=resolved.api_base,
                max_tokens=2000,
            )
            content = content.strip()

            json_str = content
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            parsed = _json.loads(json_str)

            return {
                "title": parsed.get("title", ""),
                "materials": parsed.get("materials", {}),
            }
        except Exception:
            return None

    @classmethod
    def _extract_fallback(cls, task_type: str, text: str, fields: List[str], filename: str) -> Dict[str, Any]:
        materials = {}
        for field in fields:
            materials[field] = ""

        if fields:
            materials[fields[0]] = text[:5000]

        title = os.path.splitext(filename)[0] if filename else ""

        return {
            "title": title,
            "materials": materials,
        }
