# Ethics Report Template

This template shows the structure of an AudienceLens ethics violation report.

```yaml
ethics_report:
  report_id: "[unique-id]"
  timestamp: "[ISO timestamp]"
  review_report: "[path to reviewed report]"

  summary:
    total_personas_checked: [number]
    total_issues_found: [number]
    overall_status: "[PASS|PASS_WITH_WARNINGS|FAIL]"

  violations:
    - persona_id: "[PXX-slug]"
      issue_type: "[identity_cause|gap_filling|mbti_judgment|stereotype|vague_caveat|unmarked_inference]"
      severity: "[CRITICAL|HIGH|MEDIUM|LOW]"
      description: "[Detailed description of the violation]"
      evidence: "[The specific output text that triggered the violation]"
      resolution: "[How the violation was addressed]"

  compliance_scores:
    - persona_id: "[PXX-slug]"
      overall_score: [0-100]
      status: "[passed|needs_revision|rejected]"
      breakdown:
        behavior_over_demographics: [0-100]
        evidence_grounding: [0-100]
        gap_filling_control: [0-100]
        caveat_specificity: [0-100]
        mbti_usage_correctness: [0-100]

  stereotype_checklist:
    - check: "Judgment traces to behavior_profile?"
      result: "[pass|fail]"
      details: "[Specific observation]"
    - check: "Same demographics, different judgment possible?"
      result: "[pass|fail]"
      details: "[Specific observation]"
    - check: "Evidence exists in input material?"
      result: "[pass|fail]"
      details: "[Specific observation]"
    - check: "MBTI used only for style?"
      result: "[pass|fail]"
      details: "[Specific observation]"
    - check: "Caveat is specific, not vague?"
      result: "[pass|fail]"
      details: "[Specific observation]"
    - check: "No gap-filling detected?"
      result: "[pass|fail]"
      details: "[Specific observation]"

  recommendations:
    - "[Recommendation 1]"
    - "[Recommendation 2]"
```

## Severity Definitions

| Severity | Definition | Action Required |
|----------|-----------|----------------|
| CRITICAL | Protected characteristic used as behavioral cause | Output must be rejected and regenerated |
| HIGH | Unmarked gap-filling or MBTI-driven judgment | Must rewrite before use |
| MEDIUM | Vague caveat, weak evidence, unmarked inference | Warning, must supplement |
| LOW | Tone issues, insufficiently neutral wording | Advisory, can use with note |
