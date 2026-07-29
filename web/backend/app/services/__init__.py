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
from app.models import Base, PersonaOutput, Review, SkillType
from app.services.json_safe import json_safe, json_safe_key

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from runner.aggregator import aggregate_report, load_aggregation_rules, render_markdown_report
from runner.calibration import run_calibration_check
from runner.cross_exam import (
    MODE_DERIVED,
    MODE_MODERATED,
    MODE_MULTI_AGENT,
    extract_controversy_points,
    run_cross_exam_protocol,
)
from runner.evidence_precheck import precheck_panel
from runner.panel_selector import load_personas, load_presets, select_panel
# _minify_persona 是人格身份卡的唯一裁剪口径（人格评审那一轮渲染
# persona-prompt.md 的 [PERSONA CARD] 用的就是它）。full 档重新调用人格做反驳时
# 复用它，避免在后端另开一套人格提示词——引擎链路（runner/cli.py）同样这么做。
from runner.persona_agent import (
    _minify_persona,
    estimate_cost,
    normalize_persona_output,
    parse_persona_output,
    render_prompt,
    select_model,
)
from runner.validator import load_schema, validate_output

PERSONAS_DIR = os.path.join(PROJECT_ROOT, "src", "personas")
AGENTS_DIR = os.path.join(PROJECT_ROOT, ".claude", "agents")
TRAE_PERSONAS_DIR = os.path.join(PROJECT_ROOT, ".trae", "skills", "synthetic-playtest", "personas")
PRESETS_PATH = os.path.join(PROJECT_ROOT, "src", "presets", "panel-presets.yaml")
RULES_PATH = os.path.join(PROJECT_ROOT, "src", "config", "aggregation-rules.yaml")
BUDGET_PATH = os.path.join(PROJECT_ROOT, "src", "config", "budget.yaml")
OUTPUT_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "schemas", "output-schema.json")
REPORT_SCHEMA_PATH = os.path.join(PROJECT_ROOT, "src", "schemas", "report-schema.json")
PERSONA_PROMPT_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "persona-prompt.md")
CROSS_EXAM_PROMPT_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "cross-exam-prompt.md")
REPORT_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.md")

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

# 交叉质询按档位选模式，与引擎链路（runner/cli.py）用同一套映射——
# 同一个档位在两条链路上必须发生同一件事，否则"standard 到底反驳了没有"
# 会因为用户走的是向导页还是 v2 而不同，那种不一致比功能缺失更难排查。
#   standard → moderated_rebuttal：一次仲裁式反驳（+1 次模型调用）
#   full     → multi_agent_rebuttal：每位涉事人格各被重新调用一次
# quick 档在 REVIEW_MODES["quick"]["cross_examination"]=False 处就被挡掉，走不到这里。
CROSS_EXAM_MODE_BY_REVIEW_MODE = {
    "standard": MODE_MODERATED,
    "full": MODE_MULTI_AGENT,
}


def _persona_identity_preamble(persona: dict) -> str:
    """多智能体反驳（full 档）给人格带上"你是谁"。

    为什么要有这段：不带身份，"每位人格各自反驳"就只是 N 次无身份的匿名调用，
    配不上 multi_agent_rebuttal 这个名字。

    身份卡本体复用 persona_agent._minify_persona —— 与人格评审那一轮渲染
    persona-prompt.md 的 [PERSONA CARD] 是**同一份卡、同一套裁剪口径**，
    不在这里另写一套人格描述（那样人格定义加字段时两边就会不一致）。
    反驳的任务说明、输出格式、匿名化口径全在 cross-exam-prompt.md 的 rebutter 段里，
    这里只补身份。

    但 id / name 必须摘掉：交叉质询提示词里不出现人格名是这个环节的匿名化底线。
    自己的名字露出来虽然谈不上"按身份结盟"，却会让"提示词里不含人格名"这条
    可测的不变量破掉，也给模型留下自称身份、顺势把对手也往身份上带的口子。
    """
    anonymous = {k: v for k, v in (persona or {}).items() if k not in ("id", "name")}
    return "[你的身份]\n" + _minify_persona(anonymous) + "\n\n"


# 实现搬到 app/services/json_safe.py：v2 的 review_service 也要用同一份口径，
# 留在这里会让 v2 要么重复实现、要么从包 __init__ 反向 import。
# 保留这两个别名，模块内既有调用点与测试不必改。
_json_safe_key = json_safe_key
_json_safe = json_safe


def _degraded_cross_exam_block(
    persona_outputs: List[dict], rules: dict, requested_mode: str, reason: str
) -> dict:
    """交叉质询在进入协议核心之前/之外就挂了时的**诚实**兜底区块。

    形状仍然由协议核心生成（不注入 llm_call，因此是 derived_summary），这样字段
    与正常路径逐字相同，前端不必为"失败"再写一套读法；只把失败原因补进
    failures 和 limitation。

    为什么不是 `except Exception: pass`：那正是这个仓库在系统性清除的模式——
    它曾经让"全盘失败"输出成一份"没发现风险"的报告。交叉质询挂了不该让整份
    评审作废，但必须在报告里看得见"这一步没完成，以及为什么"。
    """
    block = run_cross_exam_protocol(persona_outputs, [], mode=MODE_DERIVED, rules=rules)
    # requested_mode 记的是"本来想跑哪种"，保留它才能从报告里看出落差
    block["requested_mode"] = requested_mode
    block["failures"].append({"stage": "cross_examination", "error": reason})
    block["limitation"] = (
        f"本次交叉质询未能完成（{reason}）。报告其余部分照常给出，"
        "但人格之间没有发生实际反驳，也没有人因此改票。"
    )
    return block


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
    def generate_personas(cls, domain: str, audience: str = "", goals: str = "", count: int = 4) -> List[dict]:
        """根据领域、受众和目标生成 persona YAML 定义列表"""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return cls._generate_personas_fallback(domain, audience, goals, count)

        try:
            import anthropic
            import json

            client = anthropic.Anthropic(api_key=api_key)
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

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text.strip()

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

    @staticmethod
    def _ws_emit(ws_manager: Any, review_id: str, event: str, data: dict) -> None:
        """v1 引擎的 WS 广播出口——信封统一成与 v2 相同的 {event, data} 结构。
        此前 v1 发 {type: ...} 老格式，前端 ws.ts 的终态判断（payload.event）
        识别不了，导致 v1 评审结束后 socket 不会自动关闭。"""
        if ws_manager:
            ws_manager.broadcast_sync(review_id, {"event": event, "data": data})

    def _run_cross_examination(
        self,
        persona_outputs_data: List[dict],
        persona_defs_by_output_id: Dict[str, dict],
        review_mode: str,
        rules: dict,
        resolved: Any,
        ce_model: str,
    ) -> Optional[dict]:
        """执行交叉质询，返回可直接进报告的 cross_examination 区块。

        没有任何争议点时返回 None（与引擎链路一致：不出这个区块，也不发调用）。

        与引擎链路共用同一个协议核心 run_cross_exam_protocol —— 两条链路产出的
        mode / is_live_debate / vote_changes / disputes 字段名与语义因此完全一致。
        改票判定、θ 阈值读取、token 归一都在核心里做，这里只负责把"怎么调模型"
        注入进去。

        失败一律不吞：反驳调用失败由核心回落成 derived_summary 并把原因写进
        limitation/failures；核心之外的意外由 _degraded_cross_exam_block 兜成
        同样形状的诚实区块。两种情况下报告其余部分都照常给出。
        """
        # 函数级导入：测试用 monkeypatch 打在 runner.llm_client.chat_completion
        # 这个模块属性上，调用时才取才能拿到补丁（与 run_review 同一处理）。
        from runner.llm_client import chat_completion

        requested_mode = CROSS_EXAM_MODE_BY_REVIEW_MODE.get(review_mode, MODE_MODERATED)

        def _cross_exam_llm(prompt: str, persona_id: str = ""):
            """协议核心注入的模型出口。

            原样返回 chat_completion 的 (text, input_tokens, output_tokens) 三元组——
            核心据此把用量累进 usage，run_review 再计进本次评审的 token 与成本。
            只返回字符串的话这笔钱就会从账上消失（核心会把
            token_counts_available 置 False 并在 limitation 里声明，但账还是少的）。

            persona_id 只在 multi_agent_rebuttal 档非空：给提示词前面接上这位人格的
            身份，让它按自己的判断标准反驳，而不是变成 N 次无身份的匿名调用。
            """
            body = prompt
            persona_def = persona_defs_by_output_id.get(persona_id)
            if persona_def:
                body = _persona_identity_preamble(persona_def) + prompt
            return chat_completion(
                model=ce_model,
                prompt=body,
                api_key=resolved.key,
                provider=resolved.provider,
                api_base=resolved.api_base,
            )

        try:
            controversy_points = extract_controversy_points(persona_outputs_data)
        except Exception as e:
            # 争议点连提取都失败（相似度模型加载异常等）。以前这类异常被 pass 吞掉，
            # 报告里连"这一步存在过"都看不出来。
            return _degraded_cross_exam_block(
                persona_outputs_data,
                rules,
                requested_mode,
                f"争议点提取失败（{type(e).__name__}: {e}）",
            )

        if not controversy_points:
            # 真的没有分歧：不发调用、不出区块，与引擎链路同样处理
            return None

        try:
            return run_cross_exam_protocol(
                persona_outputs_data,
                controversy_points,
                llm_call=_cross_exam_llm,
                mode=requested_mode,
                template_path=CROSS_EXAM_PROMPT_PATH,
                rules=rules,
            )
        except Exception as e:
            # 反驳调用本身失败（超时/401/输出解析不了）核心内部已经转成 failures 了；
            # 能抛到这里的是它没预料到的问题（数据形状异常、模板文件缺失等）。
            # 一次评审不该因为交叉质询整份作废，但也绝不能静默。
            return _degraded_cross_exam_block(
                persona_outputs_data,
                rules,
                requested_mode,
                f"交叉质询执行失败（{type(e).__name__}: {e}）",
            )

    def run_review(self, review_id: str, ws_manager: Any = None):
        review = self.session.get(Review, review_id)
        if review is None:
            return

        # BYOK：与 v2 同一套 key 解析。此前这里直接读 os.environ 的
        # ANTHROPIC_API_KEY——用户在设置页保存的 key 在 v1（Wizard/直接调 API）
        # 评审里完全无效；没有环境变量时更是静默把模拟占位数据当真实报告入库。
        from app.services import key_service

        try:
            resolved = key_service.resolve_key(self.session, review.user_id or "anonymous")
        except Exception:
            resolved = None

        if resolved is None:
            review.status = "failed"
            review.error_message = (
                "未配置 API Key——评审必须使用真实模型，模拟数据没有评审价值，已拒绝执行。"
                "请在设置页填写 API Key 后重新发起。"
            )
            self.session.commit()
            self._ws_emit(ws_manager, review.id, "review.failed", {
                "review_id": review.id, "error": review.error_message,
            })
            return

        from runner.llm_client import chat_completion

        review.status = "running"
        self.session.commit()
        self._ws_emit(ws_manager, review.id, "review.started", {"review_id": review.id})

        try:
            with open(BUDGET_PATH, "r", encoding="utf-8") as f:
                budget_config = yaml.safe_load(f)

            rules = load_aggregation_rules(RULES_PATH)
            output_schema = load_schema(OUTPUT_SCHEMA_PATH)

            mode = getattr(review, 'mode', 'standard') or 'standard'
            mode_config = REVIEW_MODES.get(mode, REVIEW_MODES["standard"])

            selected = PersonaService.select_panel_by_mode(
                task_type=review.task_type,
                mode=mode,
                persona_pack=review.persona_pack,
                selected_personas=review.selected_personas,
            )

            precheck = precheck_panel(selected, review.artifact_bundle)
            valid_personas = precheck["valid_personas"]

            artifact_texts = [
                m.get("description", "") for m in review.artifact_bundle.get("materials", [])
            ]
            artifact_summary = review.artifact_bundle.get("title", "")

            persona_output_records = []
            for persona in valid_personas:
                po = PersonaOutput(
                    id=str(uuid.uuid4()),
                    review_id=review.id,
                    persona_id=persona["id"],
                    persona_name=persona.get("name", persona["id"]),
                    status="pending",
                    cost_usd=0.0,
                )
                self.session.add(po)
                persona_output_records.append((persona, po))
            self.session.commit()

            persona_outputs_data = []
            # 逐个人格的失败原因。以前失败只写进 po.output_json 就没人再看了，
            # 于是"全员失败"和"全员通过"在后面的聚合阶段长得一模一样（见循环之后的检查）。
            persona_failures: List[tuple] = []
            # full 档的多智能体反驳要按 persona_id 找回人格定义（把"你是谁"接回反驳提示词）。
            # 键用**模型回报的** persona_id 而不是定义里的 id：交叉质询全程按输出里的
            # persona_id 认人，万一模型没照抄（改写/漏字），按定义 id 建索引就查不到了。
            persona_defs_by_output_id: Dict[str, dict] = {}
            total_cost = 0.0
            total_input_tokens = 0
            total_output_tokens = 0

            for persona, po in persona_output_records:
                po.status = "running"
                po.started_at = datetime.now(timezone.utc)
                self.session.commit()

                self._ws_emit(ws_manager, review.id, "review.persona_started", {
                    "persona_id": persona["id"],
                    "persona_name": persona.get("name", persona["id"]),
                })

                try:
                    # 用户显式指定了模型（openai_compatible 档必填）就用它，
                    # 否则按人格分级选型——与 v2 引擎同一规则
                    model = resolved.model or select_model(persona, budget_config)
                    prompt = render_prompt(persona, review.task_type, artifact_summary, PERSONA_PROMPT_PATH, review.artifact_bundle)

                    # 统一走 runner.llm_client：BYOK key + provider + 自定义端点全部生效
                    raw_output, input_tokens, output_tokens = chat_completion(
                        model=model,
                        prompt=prompt,
                        api_key=resolved.key,
                        provider=resolved.provider,
                        api_base=resolved.api_base,
                    )
                    try:
                        cost = estimate_cost(input_tokens, output_tokens, model, budget_config)
                    except Exception:
                        cost = 0.0  # 第三方模型不在预算价目表里——记 0 不阻断
                    output = normalize_persona_output(parse_persona_output(raw_output))

                    validation = validate_output(output, persona, output_schema, artifact_texts)

                    po.status = "completed"
                    po.output_json = output
                    po.validation_result = validation
                    po.cost_usd = cost
                    po.input_tokens = input_tokens
                    po.output_tokens = output_tokens
                    po.completed_at = datetime.now(timezone.utc)
                    total_cost += cost
                    total_input_tokens += input_tokens
                    total_output_tokens += output_tokens

                    persona_outputs_data.append(output)
                    output_pid = str(output.get("persona_id") or "").strip() or persona["id"]
                    persona_defs_by_output_id[output_pid] = persona

                    self._ws_emit(ws_manager, review.id, "review.persona_completed", {
                        "persona_id": persona["id"],
                        "persona_name": persona.get("name", persona["id"]),
                        "validation_passed": validation.get("passed", False),
                        "cost_usd": cost,
                    })

                except Exception as e:
                    po.status = "failed"
                    po.output_json = {"error": str(e)}
                    po.completed_at = datetime.now(timezone.utc)
                    persona_failures.append(
                        (persona["id"], persona.get("name", persona["id"]), str(e))
                    )

                    self._ws_emit(ws_manager, review.id, "review.persona_failed", {
                        "persona_id": persona["id"],
                        "persona_name": persona.get("name", persona["id"]),
                        "error": str(e),
                    })

                self.session.commit()

            # ---- 失败必须是失败，不能伪装成"没发现问题" ----
            #
            # 以前这里什么都不检查：全部人格挂掉 → persona_outputs_data 为空 →
            # aggregate_report([]) 产出 release_risk="low"、0 条修复项 → 状态还被
            # 无条件置成 completed。用户看到的是"评审跑完了，没发现风险"，
            # 实际是一个人格都没跑成（key 过期/欠费/模型名写错都会这样）。
            # 这类失败比崩溃危险得多——它伪装成正常结果，用户会据此做决定。
            if not persona_outputs_data:
                # 两种成因要分清楚，否则报错会把排查引到错误方向：
                #   A. 有人格入场但全挂了 → key/模型/网络问题
                #   B. 压根没人入场（面板为空，或证据预检把人全跳过）→ 材料或选人问题
                if persona_failures:
                    detail = "；".join(f"{name}: {err}" for _pid, name, err in persona_failures[:3])
                    more = (
                        f"（另有 {len(persona_failures) - 3} 位同样失败）"
                        if len(persona_failures) > 3
                        else ""
                    )
                    raise RuntimeError(
                        f"全部 {len(persona_failures)} 位人格都没能完成评审，未生成任何报告。"
                        f"常见原因：API Key 失效/欠费、模型名不被服务商识别、中转地址不可达。"
                        f"错误详情——{detail}{more}"
                    )
                skipped = len(selected) - len(valid_personas)
                raise RuntimeError(
                    "没有任何人格进入本次评审，未生成报告。"
                    + (
                        f"评审团选出了 {len(selected)} 位，但全部 {skipped} 位都因"
                        f"材料里缺少他们需要的证据而被跳过——请补充更完整的材料"
                        f"（如截图、核心玩法说明、定价信息等）后重试。"
                        if selected
                        else "当前任务类型与人格包的组合没有匹配到任何人格，请换一个人格包或指定角色。"
                    )
                )

            # ---- 交叉质询：真反驳，token 进账，失败如实标注 ----
            #
            # 三处历史问题一起修（都逐条核实过）：
            #   1. 整段被 `except Exception: pass` 包着——反驳失败后报告里看不出
            #      "这一步跑过且失败了"，与"本来就没有争议点"长得一模一样；
            #   2. ce_in/ce_out 只加进了 token 总数，**成本一分没算**，
            #      total_cost_usd 因此系统性低于实际支出（本仓库刚修过一批同类漏洞）；
            #   3. 产出形状与引擎链路不一致：这里把 parse_cross_exam_output 的原始
            #      列表直接当 cross_examination 塞进报告，引擎给的却是带
            #      mode/limitation/vote_changes 的 dict。同一个概念两种形状，
            #      前端就得写两套读法——degradation 字段刚吃过这个亏。
            #      现在两条链路共用 run_cross_exam_protocol，字段名与语义完全一致。
            cross_exam_data = None
            if persona_outputs_data and mode_config["cross_examination"]:
                self._ws_emit(ws_manager, review.id, "review.cross_exam_started", {})

                # 交叉质询用哪个模型：用户显式指定优先，否则取预算表的默认模型
                #（不写 "claude-sonnet" 这种占位别名——它传给 Anthropic API 直接 404）
                ce_model = resolved.model or budget_config.get(
                    "default_model", "claude-sonnet-4-20250514"
                )

                cross_exam_data = self._run_cross_examination(
                    persona_outputs_data=persona_outputs_data,
                    persona_defs_by_output_id=persona_defs_by_output_id,
                    review_mode=mode,
                    rules=rules,
                    resolved=resolved,
                    ce_model=ce_model,
                )

                # 反驳是真花钱的模型调用：token 和成本都得进账，缺一样就是计费漏洞。
                ce_usage = (cross_exam_data or {}).get("usage") or {}
                ce_in = int(ce_usage.get("input_tokens") or 0)
                ce_out = int(ce_usage.get("output_tokens") or 0)
                total_input_tokens += ce_in
                total_output_tokens += ce_out
                if ce_in or ce_out:
                    try:
                        ce_cost = estimate_cost(ce_in, ce_out, ce_model, budget_config)
                    except Exception:
                        # 与人格调用同一口径：第三方模型不在预算价目表里就记 0，不阻断评审
                        ce_cost = 0.0
                    total_cost += ce_cost

                self._ws_emit(ws_manager, review.id, "review.cross_exam_completed", {
                    # 如实播报：到底跑成没有、是哪种反驳、有没有人改票。
                    # 以前这个事件是空 payload，前端只能显示"交叉质询完成"——
                    # 即使一次调用都没成功也照样这么显示。
                    "mode": (cross_exam_data or {}).get("mode", MODE_DERIVED),
                    "is_live_debate": bool((cross_exam_data or {}).get("is_live_debate")),
                    "vote_change_count": len((cross_exam_data or {}).get("vote_changes") or []),
                    "failure_count": len((cross_exam_data or {}).get("failures") or []),
                    "input_tokens": ce_in,
                    "output_tokens": ce_out,
                })

            self._ws_emit(ws_manager, review.id, "review.aggregation_started", {})

            report = aggregate_report(
                persona_outputs_data,
                review.task_type,
                artifact_summary,
                rules,
                cross_exam_data,
            )

            # 部分失败：出报告，但必须如实标注结论是据几位人格得出的。
            # 8 位挂 6 位时共识度和 release_risk 完全按剩下 2 位算，不标注
            # 就等于把"两个人的看法"包装成"评审团的结论"。
            # 字段名/结构必须和引擎链路（runner/cli.py 的 report["degradation"]）**完全一致**，
            # 否则前端要为两条链路各写一套读法——那正是本仓库"同一概念两处定义"的老毛病。
            if persona_failures and isinstance(report, dict):
                report["degradation"] = {
                    "degraded": True,
                    "attempted_count": len(persona_output_records),
                    "succeeded_count": len(persona_outputs_data),
                    "failed_count": len(persona_failures),
                    "failed_personas": [
                        {"persona_id": pid, "persona_name": name, "error": err}
                        for pid, name, err in persona_failures
                    ],
                    "notice": (
                        f"本次有 {len(persona_failures)} 位人格未能完成，"
                        f"以下结论仅据 {len(persona_outputs_data)} 位得出。"
                    ),
                }

            self._ws_emit(ws_manager, review.id, "review.aggregation_completed", {})

            calibration = None
            if mode_config["calibration"]:
                calibration = run_calibration_check(persona_outputs_data, artifact_texts)

            markdown = render_markdown_report(report, REPORT_TEMPLATE_PATH)

            report_html = None
            try:
                html_template_path = os.path.join(PROJECT_ROOT, "src", "templates", "report-template.html")
                if os.path.isfile(html_template_path):
                    from runner.html_report import generate_html_report
                    report_html = generate_html_report(report, html_template_path)
            except Exception:
                pass

            review.status = "completed"
            review.completed_at = datetime.now(timezone.utc)
            review.total_cost_usd = total_cost
            review.input_tokens = total_input_tokens
            review.output_tokens = total_output_tokens
            review.report_json = report
            review.report_markdown = markdown
            # 元组键洗成字符串再落库，否则 full 档整条 UPDATE 会炸（见 _json_safe）
            review.calibration = _json_safe(calibration)
            self.session.commit()

            # 计量事实源：v1 此前完全没记 usage_records，token 报表看不到 v1 评审。
            # 补上，让后台 token 聚合覆盖两条链路。失败不拖垮已完成的评审。
            try:
                from app.services import quota_service

                quota_service.record_usage(
                    self.session,
                    review.user_id or "anonymous",
                    review_id=review.id,
                    # 真实成功数，不是尝试数：token 只在成功分支累加，
                    # 这里若记尝试数就会出现"6 位人格却只有 2 位的 token"的对不上账。
                    persona_count=len(persona_outputs_data),
                    cost_usd=total_cost,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    key_source=resolved.source,
                )
            except Exception:
                import logging

                logging.getLogger("audiencelens").warning(
                    "v1 review %s 记 usage 失败（评审不受影响）", review.id
                )

            self._ws_emit(ws_manager, review.id, "review.completed", {
                "review_id": review.id,
                "cost_usd": total_cost,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "report_html_available": report_html is not None,
            })

        except Exception as e:
            review.status = "failed"
            review.error_message = str(e)[:2000]
            review.report_json = {"error": str(e)}
            self.session.commit()

            self._ws_emit(ws_manager, review.id, "review.failed", {
                "review_id": review.id, "error": str(e),
            })


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
