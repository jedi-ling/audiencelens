import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Base, PersonaOutput, Review, SkillType

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
for p in (PROJECT_ROOT, SRC_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from runner.aggregator import aggregate_report, load_aggregation_rules, render_markdown_report
from runner.calibration import run_calibration_check
from runner.cross_exam import extract_controversy_points, parse_cross_exam_output, render_cross_exam_prompt
from runner.evidence_precheck import precheck_panel
from runner.panel_selector import load_personas, load_presets, select_panel
from runner.persona_agent import estimate_cost, parse_persona_output, render_prompt, select_model
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
    "app_store_review": {
        "name_zh": "应用商店评审",
        "description": "应用商店页、ASO、转化率",
        "stance_enum": ["会下载", "不会", "观望"],
        "score_dimensions": ["aso_effectiveness", "conversion_potential", "trust_signals"],
    },
    "social_media_post": {
        "name_zh": "社媒帖评审",
        "description": "传播性、互动潜力、品牌调性",
        "stance_enum": ["会互动", "划走", "观望"],
        "score_dimensions": ["shareability", "engagement_potential", "brand_alignment"],
    },
    "video_ad_review": {
        "name_zh": "视频广告评审",
        "description": "前3秒钩子、信息密度、CTA",
        "stance_enum": ["会看完", "跳过", "观望"],
        "score_dimensions": ["hook_strength", "message_clarity", "cta_effectiveness"],
    },
    "landing_page_review": {
        "name_zh": "落地页评审",
        "description": "转化路径、信任建立、首屏钩子",
        "stance_enum": ["会注册", "离开", "观望"],
        "score_dimensions": ["conversion_clarity", "trust_building", "first_impression"],
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
}

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
        all_personas = []
        for pack_id, personas in cls.load_all_personas().items():
            for p in personas:
                p_copy = dict(p)
                p_copy["_pack"] = pack_id
                p_copy["source"] = p_copy.get("source", "yaml")
                all_personas.append(p_copy)
        for pack_id, personas in cls.load_agents_from_md().items():
            for p in personas:
                p_copy = dict(p)
                p_copy["_pack"] = pack_id
                all_personas.append(p_copy)
        for pack_id, personas in cls.load_trae_personas().items():
            for p in personas:
                p_copy = dict(p)
                p_copy["_pack"] = pack_id
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

        agents = cls.load_agents_from_md()
        for pack_id, personas in agents.items():
            cls._packs_cache.append({
                "panel_id": pack_id,
                "name": "Claude Agent Personas",
                "description": "从 .claude/agents/*.md 加载的 persona 定义",
                "persona_count": len(personas),
                "category": "agent",
            })

        trae = cls.load_trae_personas()
        for pack_id, personas in trae.items():
            cls._packs_cache.append({
                "panel_id": pack_id,
                "name": f"Trae Persona Pack: {pack_id}",
                "description": "从 .trae/skills/synthetic-playtest/personas/*.yaml 加载的 persona 定义",
                "persona_count": len(personas),
                "category": "trae",
            })

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
                import random
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


class ReviewService:
    def __init__(self, session: Session):
        self.session = session

    def create_review(self, task_type: str, artifact_bundle: dict, persona_pack: Optional[str] = None, selected_personas: Optional[List[str]] = None, mode: str = "standard") -> Review:
        review = Review(
            id=str(uuid.uuid4()),
            task_type=task_type,
            target_title=artifact_bundle.get("title"),
            artifact_bundle=artifact_bundle,
            persona_pack=persona_pack,
            selected_personas=selected_personas,
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

    def list_reviews(self, offset: int = 0, limit: int = 20) -> List[Review]:
        stmt = select(Review).order_by(Review.created_at.desc()).offset(offset).limit(limit)
        return list(self.session.scalars(stmt).all())

    def delete_review(self, review_id: str) -> bool:
        review = self.session.get(Review, review_id)
        if review is None:
            return False
        self.session.delete(review)
        self.session.commit()
        return True

    def run_review(self, review_id: str, ws_manager: Any = None):
        review = self.session.get(Review, review_id)
        if review is None:
            return

        review.status = "running"
        self.session.commit()

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
            total_cost = 0.0

            for persona, po in persona_output_records:
                po.status = "running"
                po.started_at = datetime.now(timezone.utc)
                self.session.commit()

                if ws_manager:
                    ws_manager.broadcast_sync(review.id, {
                        "type": "persona_started",
                        "persona_id": persona["id"],
                        "persona_name": persona.get("name", persona["id"]),
                    })

                try:
                    model = select_model(persona, budget_config)
                    prompt = render_prompt(persona, review.task_type, artifact_summary, PERSONA_PROMPT_PATH, review.artifact_bundle)

                    api_key = os.environ.get("ANTHROPIC_API_KEY")
                    if api_key:
                        import anthropic
                        client = anthropic.Anthropic(api_key=api_key)
                        response = client.messages.create(
                            model=model,
                            max_tokens=4096,
                            messages=[{"role": "user", "content": prompt}],
                        )
                        raw_output = response.content[0].text
                        input_tokens = response.usage.input_tokens
                        output_tokens = response.usage.output_tokens
                        cost = estimate_cost(input_tokens, output_tokens, model, budget_config)
                        output = parse_persona_output(raw_output)
                    else:
                        from runner.cli import _build_simulated_output
                        output = _build_simulated_output(persona, review.task_type)
                        cost = 0.0

                    validation = validate_output(output, persona, output_schema, artifact_texts)

                    po.status = "completed"
                    po.output_json = output
                    po.validation_result = validation
                    po.cost_usd = cost
                    po.completed_at = datetime.now(timezone.utc)
                    total_cost += cost

                    persona_outputs_data.append(output)

                    if ws_manager:
                        ws_manager.broadcast_sync(review.id, {
                            "type": "persona_completed",
                            "persona_id": persona["id"],
                            "persona_name": persona.get("name", persona["id"]),
                            "validation_passed": validation.get("passed", False),
                            "cost_usd": cost,
                        })

                except Exception as e:
                    po.status = "failed"
                    po.output_json = {"error": str(e)}
                    po.completed_at = datetime.now(timezone.utc)

                    if ws_manager:
                        ws_manager.broadcast_sync(review.id, {
                            "type": "persona_failed",
                            "persona_id": persona["id"],
                            "persona_name": persona.get("name", persona["id"]),
                            "error": str(e),
                        })

                self.session.commit()

            cross_exam_results = []
            if persona_outputs_data and mode_config["cross_examination"]:
                if ws_manager:
                    ws_manager.broadcast_sync(review.id, {"type": "cross_exam_started"})

                try:
                    controversy_points = extract_controversy_points(persona_outputs_data)
                    if controversy_points:
                        cross_exam_prompt = render_cross_exam_prompt(
                            controversy_points, persona_outputs_data, CROSS_EXAM_PROMPT_PATH
                        )
                        api_key = os.environ.get("ANTHROPIC_API_KEY")
                        if api_key:
                            import anthropic
                            client = anthropic.Anthropic(api_key=api_key)
                            ce_response = client.messages.create(
                                model=budget_config.get("default_model", "claude-sonnet"),
                                max_tokens=4096,
                                messages=[{"role": "user", "content": cross_exam_prompt}],
                            )
                            cross_exam_results = parse_cross_exam_output(ce_response.content[0].text)
                        else:
                            cross_exam_results = [
                                {"controversy_point": cp["title"], "simulated": True}
                                for cp in controversy_points
                            ]
                except Exception:
                    pass

                if ws_manager:
                    ws_manager.broadcast_sync(review.id, {"type": "cross_exam_completed"})

            if ws_manager:
                ws_manager.broadcast_sync(review.id, {"type": "aggregation_started"})

            report = aggregate_report(
                persona_outputs_data,
                review.task_type,
                artifact_summary,
                rules,
                cross_exam_results if cross_exam_results else None,
            )

            if ws_manager:
                ws_manager.broadcast_sync(review.id, {"type": "aggregation_completed"})

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
            review.report_json = report
            review.report_markdown = markdown
            review.calibration = calibration
            self.session.commit()

            if ws_manager:
                ws_manager.broadcast_sync(review.id, {
                    "type": "review_completed",
                    "report_html_available": report_html is not None,
                })

        except Exception as e:
            review.status = "failed"
            review.report_json = {"error": str(e)}
            self.session.commit()

            if ws_manager:
                ws_manager.broadcast_sync(review.id, {"type": "review_failed", "error": str(e)})


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
    def extract(cls, task_type: str, text: str, filename: str) -> Dict[str, Any]:
        fields = cls.TASK_FIELDS.get(task_type, [])

        try:
            result = cls._extract_with_ai(task_type, text, fields)
            if result:
                return result
        except Exception:
            pass

        return cls._extract_fallback(task_type, text, fields, filename)

    @classmethod
    def _extract_with_ai(cls, task_type: str, text: str, fields: List[str]) -> Optional[Dict[str, Any]]:
        try:
            import os as _os
            api_key = _os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return None

            from anthropic import Anthropic
            import json as _json

            client = Anthropic(timeout=15.0)
            fields_desc = "、".join(fields)

            prompt = f"""你是一个游戏评审材料提取助手。请从以下文档内容中，提取出结构化的评审材料。

任务类型：{task_type}
需要提取的字段：{fields_desc}

请按以下 JSON 格式输出，每个字段对应一段提取的内容。如果文档中没有某个字段的信息，该字段值留空字符串：
{{"title": "评审对象名称", "materials": {{"字段名1": "提取内容1", "字段名2": "提取内容2"}}}}

文档内容：
{text[:8000]}"""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text.strip()

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
