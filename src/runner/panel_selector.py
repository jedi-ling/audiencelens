import yaml
from typing import List, Optional

LEVEL_5 = {"很低": 1, "低": 2, "中": 3, "高": 4, "很高": 5}
LEVEL_4 = {"低": 1, "中": 2, "高": 3, "很高": 4}
LEVEL_3 = {"低": 1, "中": 2, "高": 3}

AXIS_MAP = {
    "patience": LEVEL_5,
    "genre_literacy": LEVEL_5,
    "novelty_seeking": LEVEL_5,
    "risk_tolerance": LEVEL_3,
    "social_influence": LEVEL_4,
    "completion_drive": LEVEL_5,
    "price_sensitivity": LEVEL_5,
    "emotional_engagement": LEVEL_3,
    "agency_preference": LEVEL_3,
    "tolerance_for_ambiguity": LEVEL_3,
    "platform_loyalty": LEVEL_3,
}

DISTANCE_AXES = [k for k in AXIS_MAP]

MAX_POSSIBLE_DISTANCE = sum(
    max(AXIS_MAP[axis].values()) - min(AXIS_MAP[axis].values())
    for axis in DISTANCE_AXES
)

DISSENTER_PREFIXES = ("P15", "P16")


def load_personas(yaml_path: str) -> List[dict]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["personas"]


def load_presets(yaml_path: str) -> dict:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["presets"]


def _match_persona(short_id: str, personas: List[dict]) -> Optional[dict]:
    for p in personas:
        if p["id"].startswith(short_id + "-"):
            return p
    return None


def _is_dissenter(persona: dict) -> bool:
    return any(persona["id"].startswith(prefix) for prefix in DISSENTER_PREFIXES)


def select_panel(
    task_type: str,
    personas: List[dict],
    presets: dict,
    artifact_evidence_types: Optional[List[str]] = None,
) -> dict:
    if task_type not in presets:
        raise ValueError(f"Unknown task type: {task_type}")

    preset = presets[task_type]
    default_ids = preset["default_personas"]

    selected = []
    skipped = []

    for short_id in default_ids:
        persona = _match_persona(short_id, personas)
        if persona is None:
            skipped.append({"persona_id": short_id, "reason": "Persona not found"})
            continue

        if artifact_evidence_types is not None:
            needed = set(persona.get("evidence_types_needed", []))
            available = set(artifact_evidence_types)
            if needed and not (needed & available):
                skipped.append({
                    "persona_id": persona["id"],
                    "reason": "No evidence type overlap",
                })
                continue

        selected.append(persona)

    has_dissenter = any(_is_dissenter(p) for p in selected)
    if not has_dissenter:
        p15 = _match_persona("P15", personas)
        if p15 is not None:
            selected.append(p15)

    return {
        "selected": selected,
        "skipped": skipped,
        "task_type": task_type,
    }


def _axis_value(persona: dict, axis: str) -> int:
    raw = persona["behavior_profile"][axis]
    return AXIS_MAP[axis][raw]


def compute_behavioral_distance(p1: dict, p2: dict) -> float:
    total = 0
    for axis in DISTANCE_AXES:
        v1 = _axis_value(p1, axis)
        v2 = _axis_value(p2, axis)
        total += abs(v1 - v2)
    return total / MAX_POSSIBLE_DISTANCE


def ensure_diversity(
    selected: List[dict], min_distance: float = 0.2
) -> List[dict]:
    redundant_pairs = []
    for i in range(len(selected)):
        for j in range(i + 1, len(selected)):
            dist = compute_behavioral_distance(selected[i], selected[j])
            if dist < min_distance:
                redundant_pairs.append({
                    "persona_1": selected[i]["id"],
                    "persona_2": selected[j]["id"],
                    "distance": dist,
                })
    return redundant_pairs
