import json
import re
from typing import List

from difflib import SequenceMatcher
from jinja2 import Template


SEVERITY_MAP = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _variance(values: List[float]) -> float:
    if len(values) == 0:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def extract_controversy_points(
    persona_outputs: List[dict], top_n: int = 3
) -> List[dict]:
    all_issues = []
    for output in persona_outputs:
        persona_id = output.get("persona_id", "")
        for issue in output.get("key_issues", []):
            all_issues.append(
                {
                    "persona_id": persona_id,
                    "title": issue.get("title", ""),
                    "severity": issue.get("severity", "low"),
                }
            )

    unique_issues = []
    for issue in all_issues:
        merged = False
        for ui in unique_issues:
            if _similarity(issue["title"], ui["title"]) > 0.7:
                ui["views"].append(
                    {
                        "persona_id": issue["persona_id"],
                        "severity": issue["severity"],
                        "title": issue["title"],
                    }
                )
                merged = True
                break
        if not merged:
            unique_issues.append(
                {
                    "title": issue["title"],
                    "views": [
                        {
                            "persona_id": issue["persona_id"],
                            "severity": issue["severity"],
                            "title": issue["title"],
                        }
                    ],
                }
            )

    results = []
    for ui in unique_issues:
        severity_values = [
            SEVERITY_MAP.get(v["severity"], 1) for v in ui["views"]
        ]
        var = _variance(severity_values)
        results.append(
            {
                "title": ui["title"],
                "severity_variance": var,
                "persona_views": ui["views"],
            }
        )

    results.sort(key=lambda x: x["severity_variance"], reverse=True)
    return results[:top_n]


def find_opposing_stances(
    controversy_point: dict, persona_outputs: List[dict]
) -> dict:
    views = controversy_point.get("persona_views", [])
    severity_scores = [
        SEVERITY_MAP.get(v["severity"], 1) for v in views
    ]

    if len(views) < 2:
        return {
            "pro": {"persona_id": views[0]["persona_id"], "argument": ""},
            "con": {"persona_id": views[0]["persona_id"], "argument": ""},
        }

    max_idx = severity_scores.index(max(severity_scores))
    min_idx = severity_scores.index(min(severity_scores))

    if max_idx == min_idx:
        stance_map = {}
        for output in persona_outputs:
            pid = output.get("persona_id", "")
            stance = output.get("primary_stance", "")
            stance_map[pid] = stance

        stance_values = {}
        for v in views:
            stance = stance_map.get(v["persona_id"], "")
            stance_values[v["persona_id"]] = stance

        pro_view = views[0]
        con_view = views[-1]
    else:
        pro_view = views[max_idx]
        con_view = views[min_idx]

    issue_title = controversy_point.get("title", "")

    pro_argument = ""
    con_argument = ""
    for output in persona_outputs:
        for issue in output.get("key_issues", []):
            if _similarity(issue.get("title", ""), issue_title) > 0.5:
                if output.get("persona_id") == pro_view["persona_id"]:
                    pro_argument = issue.get("why_it_matters", "")
                if output.get("persona_id") == con_view["persona_id"]:
                    con_argument = issue.get("why_it_matters", "")

    return {
        "pro": {"persona_id": pro_view["persona_id"], "argument": pro_argument},
        "con": {"persona_id": con_view["persona_id"], "argument": con_argument},
    }


def render_cross_exam_prompt(
    controversy_points: List[dict],
    persona_outputs: List[dict],
    template_path: str,
) -> str:
    with open(template_path, "r", encoding="utf-8") as f:
        template_str = f.read()

    template_str = _convert_handlebars_to_jinja2(template_str)

    rendered_points = []
    for cp in controversy_points:
        opposing = find_opposing_stances(cp, persona_outputs)
        pro_persona_name = ""
        con_persona_name = ""
        for output in persona_outputs:
            if output.get("persona_id") == opposing["pro"]["persona_id"]:
                pro_persona_name = output.get("persona_name", "")
            if output.get("persona_id") == opposing["con"]["persona_id"]:
                con_persona_name = output.get("persona_name", "")

        rendered_points.append(
            {
                "title": cp.get("title", ""),
                "pro_persona_name": pro_persona_name,
                "pro_argument": opposing["pro"]["argument"],
                "con_persona_name": con_persona_name,
                "con_argument": opposing["con"]["argument"],
            }
        )

    template = Template(template_str)
    return template.render(controversy_points=rendered_points)


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


def run_cross_exam_protocol(
    persona_outputs: List[dict],
    controversy_points: List[dict],
    num_rounds: int = 3,
) -> dict:
    rounds = []
    for round_num in range(1, num_rounds + 1):
        is_current = round_num == num_rounds
        rounds.append({"round_num": round_num, "is_current": is_current})

    disputes = []
    for cp in controversy_points:
        opposing = find_opposing_stances(cp, persona_outputs)
        pro_pid = opposing["pro"]["persona_id"]
        con_pid = opposing["con"]["persona_id"]
        pro_name = pro_pid
        con_name = con_pid
        for output in persona_outputs:
            if output.get("persona_id") == pro_pid:
                pro_name = output.get("persona_name", pro_pid)
            if output.get("persona_id") == con_pid:
                con_name = output.get("persona_name", con_pid)

        pro_args = []
        if opposing["pro"]["argument"]:
            pro_args.append({
                "point": opposing["pro"]["argument"],
                "persona_id": pro_name,
            })
        else:
            pro_args.append({
                "point": f"支持方观点（{pro_name}）",
                "persona_id": pro_name,
            })

        con_args = []
        if opposing["con"]["argument"]:
            con_args.append({
                "point": opposing["con"]["argument"],
                "persona_id": con_name,
            })
        else:
            con_args.append({
                "point": f"反对方观点（{con_name}）",
                "persona_id": con_name,
            })

        disputes.append({
            "topic": cp.get("title", ""),
            "pro_args": pro_args,
            "con_args": con_args,
        })

    vote_changes = []
    confidence_changes = []
    for p in persona_outputs:
        initial_confidence = p.get("confidence", 0.5)
        after_pct = round(initial_confidence * 100)
        delta = 0
        confidence_changes.append({
            "persona_id": p.get("persona_name", p["persona_id"]),
            "after": after_pct,
            "delta": delta,
        })

    return {
        "rounds": rounds,
        "disputes": disputes,
        "vote_changes": vote_changes,
        "confidence_changes": confidence_changes,
    }


def parse_cross_exam_output(raw_output: str) -> List[dict]:
    json_match = re.search(r"```json\s*(.*?)\s*```", raw_output, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except json.JSONDecodeError:
            pass

    try:
        parsed = json.loads(raw_output)
        if isinstance(parsed, list):
            return parsed
        return [parsed]
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

    results = []
    for obj_str in json_objects:
        try:
            parsed = json.loads(obj_str)
            if isinstance(parsed, list):
                return parsed
            results.append(parsed)
        except json.JSONDecodeError:
            continue

    if results:
        return results

    return []
