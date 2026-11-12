### Current validator

**dev split**

| Group | Grounded | Not grounded | Precision | Recall | False-accept | False-reject |
|---|---|---|---|---|---|---|
| all scored items | 42 | 104 | 100% | 100% | 0% (0/104) | 0% (0/42) |
| constructed · 1 verbatim · en | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 1 verbatim · zh | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 1 verbatim · zh+en | 12 | 0 | 100% | 100% | – | 0% (0/12) |
| constructed · 2 verbatim_punctuation_variant · en | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 2 verbatim_punctuation_variant · zh | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 2 verbatim_punctuation_variant · zh+en | 12 | 0 | 100% | 100% | – | 0% (0/12) |
| constructed · 3 framing_plus_verbatim · en | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 3 framing_plus_verbatim · zh | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 3 framing_plus_verbatim · zh+en | 12 | 0 | 100% | 100% | – | 0% (0/12) |
| constructed · 4 half_true · en | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 4 half_true · zh | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 4 half_true · zh+en | 0 | 12 | – | – | 0% (0/12) | – |
| constructed · 5 paraphrase_judgement · en | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 5 paraphrase_judgement · zh | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 5 paraphrase_judgement · zh+en | 0 | 12 | – | – | 0% (0/12) | – |
| constructed · 6 absence_claim · en | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 6 absence_claim · zh | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 6 absence_claim · zh+en | 0 | 12 | – | – | 0% (0/12) | – |
| constructed · 7 fabricated · en | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 7 fabricated · zh | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 7 fabricated · zh+en | 0 | 12 | – | – | 0% (0/12) | – |
| constructed · 8 number_changed · en | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 8 number_changed · zh | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 8 number_changed · zh+en | 0 | 12 | – | – | 0% (0/12) | – |
| constructed · all | 36 | 60 | 100% | 100% | 0% (0/60) | 0% (0/36) |
| constructed · en | 18 | 30 | 100% | 100% | 0% (0/30) | 0% (0/18) |
| constructed · zh | 18 | 30 | 100% | 100% | 0% (0/30) | 0% (0/18) |
| real · absence_claim | 0 | 10 | – | – | 0% (0/10) | – |
| real · all | 6 | 44 | 100% | 100% | 0% (0/44) | 0% (0/6) |
| real · framing_plus_verbatim | 1 | 0 | 100% | 100% | – | 0% (0/1) |
| real · quote + commentary (mixed, not scored) | – | – | – | – | accepted 0/21 | – |
| real · restatement_or_judgement | 0 | 34 | – | – | 0% (0/34) | – |
| real · verbatim | 5 | 0 | 100% | 100% | – | 0% (0/5) |
| real · zh | 6 | 44 | 100% | 100% | 0% (0/44) | 0% (0/6) |

**test split**

| Group | Grounded | Not grounded | Precision | Recall | False-accept | False-reject |
|---|---|---|---|---|---|---|
| all scored items | 27 | 69 | 96% | 96% | 1% (1/69) | 4% (1/27) |
| constructed · 1 verbatim · en | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 1 verbatim · zh | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 1 verbatim · zh+en | 8 | 0 | 100% | 100% | – | 0% (0/8) |
| constructed · 2 verbatim_punctuation_variant · en | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 2 verbatim_punctuation_variant · zh | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 2 verbatim_punctuation_variant · zh+en | 8 | 0 | 100% | 100% | – | 0% (0/8) |
| constructed · 3 framing_plus_verbatim · en | 4 | 0 | 100% | 75% | – | 25% (1/4) |
| constructed · 3 framing_plus_verbatim · zh | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 3 framing_plus_verbatim · zh+en | 8 | 0 | 100% | 88% | – | 12% (1/8) |
| constructed · 4 half_true · en | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 4 half_true · zh | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 4 half_true · zh+en | 0 | 8 | – | – | 0% (0/8) | – |
| constructed · 5 paraphrase_judgement · en | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 5 paraphrase_judgement · zh | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 5 paraphrase_judgement · zh+en | 0 | 8 | – | – | 0% (0/8) | – |
| constructed · 6 absence_claim · en | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 6 absence_claim · zh | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 6 absence_claim · zh+en | 0 | 8 | – | – | 0% (0/8) | – |
| constructed · 7 fabricated · en | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 7 fabricated · zh | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 7 fabricated · zh+en | 0 | 8 | – | – | 0% (0/8) | – |
| constructed · 8 number_changed · en | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 8 number_changed · zh | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 8 number_changed · zh+en | 0 | 8 | – | – | 0% (0/8) | – |
| constructed · all | 24 | 40 | 100% | 96% | 0% (0/40) | 4% (1/24) |
| constructed · en | 12 | 20 | 100% | 92% | 0% (0/20) | 8% (1/12) |
| constructed · zh | 12 | 20 | 100% | 100% | 0% (0/20) | 0% (0/12) |
| real · absence_claim | 0 | 7 | – | – | 0% (0/7) | – |
| real · all | 3 | 29 | 75% | 100% | 3% (1/29) | 0% (0/3) |
| real · quote + commentary (mixed, not scored) | – | – | – | – | accepted 0/14 | – |
| real · restatement_or_judgement | 0 | 22 | 0% | – | 5% (1/22) | – |
| real · verbatim | 3 | 0 | 100% | 100% | – | 0% (0/3) |
| real · zh | 3 | 29 | 75% | 100% | 3% (1/29) | 0% (0/3) |

