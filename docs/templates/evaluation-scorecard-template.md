# Evaluation Scorecard Template

This template shows the structure of an AudienceLens evaluation scorecard.

```json
{
  "evaluation_id": "[unique-id]",
  "timestamp": "[ISO timestamp]",
  "review_report": "[path to reviewed report]",
  "dimensions": {
    "input_grounding": {
      "score": [0-5],
      "label": "[Fail|Needs Improvement|Adequate|Good|Excellent]",
      "direct_evidence_ratio": [0.0-1.0],
      "fabricated_evidence_count": [number],
      "notes": "[Specific observations]"
    },
    "persona_differentiation": {
      "score": [0-5],
      "label": "[label]",
      "avg_jaccard_distance": [0.0-1.0],
      "min_jaccard_distance": [0.0-1.0],
      "notes": "[Specific observations]"
    },
    "stereotype_check": {
      "score": [0-5],
      "label": "[label]",
      "violations": [
        {
          "persona_id": "[id]",
          "severity": "[CRITICAL|HIGH|MEDIUM|LOW]",
          "pattern": "[description of violation]"
        }
      ],
      "notes": "[Specific observations]"
    },
    "calibration_honesty": {
      "score": [0-5],
      "label": "[label]",
      "high_confidence_without_direct": [number],
      "notes": "[Specific observations]"
    },
    "actionability": {
      "score": [0-5],
      "label": "[label]",
      "issues_with_concrete_fixes": [number],
      "total_issues": [number],
      "notes": "[Specific observations]"
    },
    "structure_check": {
      "score": [0-5],
      "label": "[label]",
      "missing_fields": ["[field names]"],
      "notes": "[Specific observations]"
    },
    "risk_detection": {
      "score": [0-5],
      "label": "[label]",
      "missed_risks": ["[description]"],
      "severity_misalignments": ["[description]"],
      "notes": "[Specific observations]"
    },
    "segment_conflict": {
      "score": [0-5],
      "label": "[label]",
      "dissent_preserved": [true/false],
      "averaged_positions": [number],
      "notes": "[Specific observations]"
    }
  },
  "overall": {
    "average_score": [0.0-5.0],
    "result": "[PASS|NEEDS_IMPROVEMENT|FAIL]",
    "failing_dimensions": ["[dimension names]"]
  }
}
```

## Scoring Guide

| Score | Label | Criteria |
|-------|-------|----------|
| 5 | Excellent | All criteria met, no issues |
| 4 | Good | Criteria met with minor issues |
| 3 | Adequate | Minimum criteria met |
| 2 | Needs Improvement | Below minimum in some areas |
| 1 | Poor | Significantly below standards |
| 0 | Fail | Critical failure |
