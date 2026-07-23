import os
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional

import yaml
from jinja2 import Environment, FileSystemLoader

from runner.validator import check_identity_behavior_decoupling

try:
    from .similarity import get_issue_similarity
except ImportError:
    from runner.similarity import get_issue_similarity


def load_aggregation_rules(rules_path: str) -> dict:
    if not os.path.isfile(rules_path):
        raise FileNotFoundError(f"Rules file not found: {rules_path}")
    with open(rules_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_consensus(persona_outputs: List[dict], threshold: float = 0.7) -> dict:
    if not persona_outputs:
        return {"agreed_points": [], "questioned_points": [], "stance_distribution": {}}

    stances = [p.get("primary_stance", "观望") for p in persona_outputs]
    counter = Counter(stances)
    total = len(stances)
    distribution = dict(counter)

    agreed_points = []
    questioned_points = []

    for stance, count in counter.items():
        if count / total >= threshold:
            agreed_points.append(stance)
        else:
            questioned_points.append(stance)

    return {
        "agreed_points": agreed_points,
        "questioned_points": questioned_points,
        "stance_distribution": distribution,
    }


def compute_disagreements(persona_outputs: List[dict], similarity=None) -> List[dict]:
    if similarity is None:
        similarity = get_issue_similarity()

    stance_groups = {}
    for p in persona_outputs:
        stance = p.get("primary_stance", "观望")
        if stance not in stance_groups:
            stance_groups[stance] = []
        stance_groups[stance].append(p)

    unique_stances = list(stance_groups.keys())
    if len(unique_stances) <= 1:
        return []

    # 使用相似度合并议题，避免同一问题换措辞被分到不同组
    issue_clusters = []  # [{"title": str, "entries": [(pid, stance, issue)]}]
    for p in persona_outputs:
        for issue in p.get("key_issues", []):
            if not isinstance(issue, dict):
                continue
            title = issue.get("title", "")
            if not title:
                continue
            merged = False
            for cluster in issue_clusters:
                if similarity.is_same_issue(title, cluster["title"]):
                    cluster["entries"].append((p.get("persona_id",""), p.get("primary_stance","观望"), issue))
                    merged = True
                    break
            if not merged:
                issue_clusters.append({
                    "title": title,
                    "entries": [(p.get("persona_id",""), p.get("primary_stance","观望"), issue)],
                })

    issue_map = {c["title"]: c["entries"] for c in issue_clusters}

    disagreements = []

    controversial_issues = []
    for title, entries in issue_map.items():
        stances_for_issue = set(e[1] for e in entries)
        if len(stances_for_issue) > 1:
            controversial_issues.append(title)

    if controversial_issues:
        for title in controversial_issues:
            entries = issue_map[title]
            persona_stances = []
            for pid, stance, issue in entries:
                evidence_text = f"{issue.get('title', '')}: {issue.get('why_it_matters', '')}"
                persona_stances.append({
                    "persona_id": pid,
                    "stance": stance,
                    "evidence": evidence_text,
                })
            disagreements.append({
                "topic": title,
                "persona_stances": persona_stances,
                "resolution_suggestion": f"Further investigation needed on {title}",
                "dedup_method": similarity.method,
            })
    else:
        for i in range(len(unique_stances)):
            for j in range(i + 1, len(unique_stances)):
                stance_a = unique_stances[i]
                stance_b = unique_stances[j]
                persona_stances = []
                for p in stance_groups[stance_a]:
                    evidence_text = p.get("voice_sample", "")
                    persona_stances.append({
                        "persona_id": p.get("persona_id",""),
                        "stance": stance_a,
                        "evidence": evidence_text,
                    })
                for p in stance_groups[stance_b]:
                    evidence_text = p.get("voice_sample", "")
                    persona_stances.append({
                        "persona_id": p.get("persona_id",""),
                        "stance": stance_b,
                        "evidence": evidence_text,
                    })
                disagreements.append({
                    "topic": f"{stance_a} vs {stance_b}",
                    "persona_stances": persona_stances,
                    "resolution_suggestion": f"Mediate between {stance_a} and {stance_b} perspectives",
                    "dedup_method": similarity.method,
                })

    return disagreements


def compute_priority_fixes(persona_outputs: List[dict], rules: dict) -> List[dict]:
    severity_boost = rules.get("severity_boost", {})
    issue_map = {}

    for p in persona_outputs:
        for issue in p.get("key_issues", []):
            if not isinstance(issue, dict):
                continue
            title = issue.get("title", "")
            if not title:
                continue
            if title not in issue_map:
                issue_map[title] = {
                    "severity": issue.get("severity", "medium"),
                    "why_it_matters": issue.get("why_it_matters", ""),
                    "suggested_fix": issue.get("suggested_fix", ""),
                    "affected_personas": [],
                }
            issue_map[title]["affected_personas"].append(p.get("persona_id", ""))

    results = []
    for title, info in issue_map.items():
        boost = severity_boost.get(info["severity"], 1.0)
        weight = 1.0
        affected_count = len(set(info["affected_personas"]))
        score = boost * weight * affected_count
        results.append({
            "priority": 0,
            "issue": title,
            "severity": info["severity"],
            "why_it_matters": info["why_it_matters"],
            "affected_personas": list(set(info["affected_personas"])),
            "suggested_fix": info["suggested_fix"],
            "score": score,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    for i, item in enumerate(results):
        item["priority"] = i + 1

    return results


def aggregate_report(
    persona_outputs: List[dict],
    task_type: str,
    target: str,
    rules: dict,
    cross_exam_data: Optional[dict] = None,
) -> dict:
    consensus = compute_consensus(persona_outputs, threshold=rules.get("consensus_threshold", 0.7))
    disagreements = compute_disagreements(persona_outputs)
    priority_fixes = compute_priority_fixes(persona_outputs, rules)

    stance_counter = Counter(p.get("primary_stance", "观望") for p in persona_outputs)
    primary_recommendation = stance_counter.most_common(1)[0][0] if stance_counter else ""

    all_issues = []
    for p in persona_outputs:
        for issue in p.get("key_issues", []):
            if isinstance(issue, dict):
                all_issues.append(issue)
    critical_high_count = sum(1 for i in all_issues if i.get("severity") in ("critical", "high"))
    if critical_high_count >= 2:
        release_risk = "critical"
    elif critical_high_count == 1:
        release_risk = "high"
    elif any(i.get("severity") == "medium" for i in all_issues):
        release_risk = "medium"
    else:
        release_risk = "low"

    if persona_outputs:
        avg_evidence = sum(p.get("evidence_sufficiency", 0) for p in persona_outputs) / len(persona_outputs)
        if avg_evidence >= 0.8:
            evidence_quality = "strong"
        elif avg_evidence >= 0.6:
            evidence_quality = "medium"
        elif avg_evidence >= 0.4:
            evidence_quality = "weak"
        else:
            evidence_quality = "insufficient"
    else:
        evidence_quality = "insufficient"

    information_gaps = []
    seen_gaps = set()
    for p in persona_outputs:
        for gap in p.get("missing_information", []):
            if gap not in seen_gaps:
                information_gaps.append(gap)
                seen_gaps.add(gap)

    suggested_tasks = []
    recruit_types = []
    next_materials = []

    for d in disagreements:
        suggested_tasks.append(f"Test resolution of: {d['topic']}")
    for p in persona_outputs:
        recruit_types.append(p.get("persona_name", p.get("persona_id","")))
    for gap in information_gaps:
        next_materials.append(f"Provide: {gap}")

    if not suggested_tasks:
        suggested_tasks = ["General playtest validation"]
    if not recruit_types:
        recruit_types = ["General players"]
    if not next_materials:
        next_materials = ["Current build"]

    persona_notes = []
    for p in persona_outputs:
        top_evidence = [
            e.get("content", "") for e in p.get("evidence", []) if isinstance(e, dict)
        ][:3]
        top_issues = [
            i.get("title", "") for i in p.get("key_issues", []) if isinstance(i, dict)
        ]
        persona_notes.append({
            "persona_id": p.get("persona_id", ""),
            "persona_name": p.get("persona_name", p.get("persona_id", "")),
            "stance": p.get("primary_stance", "观望"),
            "evidence_top3": top_evidence,
            "top_issues": top_issues,
            "continue_triggers": p.get("continue_triggers", []),
            "quit_triggers": p.get("quit_triggers", []),
        })

    decoupling_issues = []
    for p in persona_outputs:
        result = check_identity_behavior_decoupling(p)
        if not result["decoupled"]:
            decoupling_issues.extend(result["violations"])

    ethics_score = 100
    if decoupling_issues:
        ethics_score -= len(decoupling_issues) * 10
    ethics_score = max(0, min(100, ethics_score))

    if ethics_score >= 80:
        compliance_status = "通过"
        compliance_status_class = "pass"
        score_class = "high"
    elif ethics_score >= 50:
        compliance_status = "需修订"
        compliance_status_class = "needs-revision"
        score_class = "medium"
    else:
        compliance_status = "驳回"
        compliance_status_class = "rejected"
        score_class = "low"

    recommended_steps = []
    if ethics_score < 100:
        recommended_steps.append("检查 AI 人格是否存在身份-行为耦合违规")
    if ethics_score < 80:
        recommended_steps.append("对违规人格进行修正后重新评审")
    if ethics_score < 50:
        recommended_steps.append("全部评审结果需要人工复核")
    if not recommended_steps:
        recommended_steps = ["结果可供参考，但仍建议人工抽检"]

    return {
        "meta": {
            "task_type": task_type,
            "target": target,
            "build_version": "0.1.0",
            "prompt_version": "0.1.0",
            "persona_pack_version": "0.1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "is_synthetic": True,
        },
        "executive_summary": {
            "primary_recommendation": primary_recommendation,
            "release_risk": release_risk,
            "evidence_quality": evidence_quality,
        },
        "consensus": {
            "agreed_points": consensus["agreed_points"],
            "questioned_points": consensus["questioned_points"],
        },
        "major_disagreements": disagreements,
        "priority_fixes": priority_fixes,
        "persona_notes": persona_notes,
        "information_gaps": information_gaps,
        "next_human_test": {
            "suggested_tasks": suggested_tasks,
            "recruit_types": recruit_types,
            "next_materials": next_materials,
        },
        "cross_examination": cross_exam_data,
        "compliance": {
            "status": compliance_status,
            "status_class": compliance_status_class,
            "ethics_score": ethics_score,
            "score_class": score_class,
            "recommended_steps": recommended_steps,
        },
    }


def render_markdown_report(report: dict, template_path: str) -> str:
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")

    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)

    context = {
        "task_type": report["meta"]["task_type"],
        "target": report["meta"]["target"],
        "build_version": report["meta"]["build_version"],
        "prompt_version": report["meta"]["prompt_version"],
        "persona_pack_version": report["meta"]["persona_pack_version"],
        "generated_at": report["meta"]["generated_at"],
        "primary_recommendation": report["executive_summary"]["primary_recommendation"],
        "release_risk": report["executive_summary"]["release_risk"],
        "evidence_quality": report["executive_summary"]["evidence_quality"],
        "consensus": report["consensus"],
        "major_disagreements": report["major_disagreements"],
        "priority_fixes": report["priority_fixes"],
        "persona_notes": report["persona_notes"],
        "information_gaps": report["information_gaps"],
        "next_human_test": report["next_human_test"],
        "meta": report["meta"],
    }

    return template.render(**context)


def render_html_report(report: dict, template_path: str) -> str:
    if not os.path.isfile(template_path):
        raise FileNotFoundError(f"HTML template file not found: {template_path}")

    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)
    env = Environment(loader=FileSystemLoader(template_dir))
    env.filters["mul"] = lambda value, factor: int(value) * factor
    template = env.get_template(template_name)

    positive_stances = {
        "加愿望单", "继续试玩", "值得推进", "会买", "会转发",
        "增强信心", "会支持", "会加入", "增强期待", "文化适配良好",
        "正面", "推荐", "认可", "支持", "赞同",
    }
    negative_stances = {
        "不加", "退出", "不值得", "不买", "不会",
        "降低信心", "不会支持", "不会加入", "降低期待", "存在问题",
        "负面", "不推荐", "反对", "拒绝", "批评",
    }

    persona_notes_enriched = []
    for pn in report.get("persona_notes", []):
        pid = pn.get("persona_id", "")
        pname = pn.get("persona_name", pid)
        stance = pn.get("stance", "")

        avatar_hue = hash(pid) % 360
        avatar_color = f"hsl({avatar_hue}, 65%, 55%)"
        avatar_letter = pname[0] if pname else "?"

        if stance in positive_stances:
            stance_class = "positive"
        elif stance in negative_stances:
            stance_class = "negative"
        else:
            stance_class = "neutral"

        persona_output = next(
            (p for p in report.get("_persona_outputs", []) if p.get("persona_id") == pid),
            None,
        )

        scores = []
        if persona_output:
            base = persona_output.get("scores", {}).get("base", {})
            task_specific = persona_output.get("scores", {}).get("task_specific", {})
            for dim, val in {**base, **task_specific}.items():
                scores.append({"dim": dim, "val": val})

        evidence_top3 = []
        if persona_output:
            for ev in persona_output.get("evidence", [])[:3]:
                evidence_top3.append({
                    "content": ev.get("content", ""),
                    "level": ev.get("inference_level", "inferred"),
                })
        elif isinstance(pn.get("evidence_top3"), list):
            for ev in pn["evidence_top3"]:
                if isinstance(ev, dict):
                    evidence_top3.append(ev)
                else:
                    evidence_top3.append({"content": str(ev), "level": "inferred"})

        top_issues = []
        if persona_output:
            for iss in persona_output.get("key_issues", [])[:3]:
                top_issues.append({
                    "severity": iss.get("severity", "medium"),
                    "title": iss.get("title", ""),
                    "why_it_matters": iss.get("why_it_matters", ""),
                    "suggested_fix": iss.get("suggested_fix", ""),
                })

        voice_sample = ""
        if persona_output:
            voice_sample = persona_output.get("voice_sample", "")

        persona_notes_enriched.append({
            **pn,
            "avatar_color": avatar_color,
            "avatar_letter": avatar_letter,
            "stance_class": stance_class,
            "scores": scores,
            "evidence_top3": evidence_top3,
            "top_issues": top_issues,
            "voice_sample": voice_sample,
        })

    context = {
        "meta": report["meta"],
        "executive_summary": report["executive_summary"],
        "consensus": report["consensus"],
        "major_disagreements": report["major_disagreements"],
        "priority_fixes": report["priority_fixes"],
        "persona_notes": persona_notes_enriched,
        "information_gaps": report["information_gaps"],
        "next_human_test": report["next_human_test"],
        "persona_count": len(persona_notes_enriched),
        "cross_examination": report.get("cross_examination"),
        "compliance": report.get("compliance"),
        "validation": report.get("validation"),
    }

    return template.render(**context)
