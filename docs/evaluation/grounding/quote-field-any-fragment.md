### Any-fragment rule (before)

**dev split**

| Group | Grounded | Not grounded | Precision | Recall | False-accept | False-reject |
|---|---|---|---|---|---|---|
| all scored items | 42 | 104 | 38% | 95% | 63% (66/104) | 5% (2/42) |
| constructed · 1 verbatim · en | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 1 verbatim · zh | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 1 verbatim · zh+en | 12 | 0 | 100% | 100% | – | 0% (0/12) |
| constructed · 2 verbatim_punctuation_variant · en | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 2 verbatim_punctuation_variant · zh | 6 | 0 | 100% | 83% | – | 17% (1/6) |
| constructed · 2 verbatim_punctuation_variant · zh+en | 12 | 0 | 100% | 92% | – | 8% (1/12) |
| constructed · 3 framing_plus_verbatim · en | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 3 framing_plus_verbatim · zh | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| constructed · 3 framing_plus_verbatim · zh+en | 12 | 0 | 100% | 100% | – | 0% (0/12) |
| constructed · 4 half_true · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| constructed · 4 half_true · zh | 0 | 6 | 0% | – | 100% (6/6) | – |
| constructed · 4 half_true · zh+en | 0 | 12 | 0% | – | 100% (12/12) | – |
| constructed · 5 paraphrase_judgement · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| constructed · 5 paraphrase_judgement · zh | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 5 paraphrase_judgement · zh+en | 0 | 12 | 0% | – | 50% (6/12) | – |
| constructed · 6 absence_claim · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| constructed · 6 absence_claim · zh | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 6 absence_claim · zh+en | 0 | 12 | 0% | – | 50% (6/12) | – |
| constructed · 7 fabricated · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| constructed · 7 fabricated · zh | 0 | 6 | – | – | 0% (0/6) | – |
| constructed · 7 fabricated · zh+en | 0 | 12 | 0% | – | 50% (6/12) | – |
| constructed · 8 number_changed · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| constructed · 8 number_changed · zh | 0 | 6 | 0% | – | 100% (6/6) | – |
| constructed · 8 number_changed · zh+en | 0 | 12 | 0% | – | 100% (12/12) | – |
| constructed · all | 36 | 60 | 45% | 97% | 70% (42/60) | 3% (1/36) |
| constructed · en | 18 | 30 | 38% | 100% | 100% (30/30) | 0% (0/18) |
| constructed · zh | 18 | 30 | 59% | 94% | 40% (12/30) | 6% (1/18) |
| quote shape · all scored items | 24 | 60 | 25% | 50% | 60% (36/60) | 50% (12/24) |
| quote shape · en | 12 | 30 | 29% | 100% | 100% (30/30) | 0% (0/12) |
| quote shape · q1 quote_verbatim_plus_comment · en | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| quote shape · q1 quote_verbatim_plus_comment · zh | 6 | 0 | – | 0% | – | 100% (6/6) |
| quote shape · q1 quote_verbatim_plus_comment · zh+en | 12 | 0 | 100% | 50% | – | 50% (6/12) |
| quote shape · q2 quote_variant_plus_comment · en | 6 | 0 | 100% | 100% | – | 0% (0/6) |
| quote shape · q2 quote_variant_plus_comment · zh | 6 | 0 | – | 0% | – | 100% (6/6) |
| quote shape · q2 quote_variant_plus_comment · zh+en | 12 | 0 | 100% | 50% | – | 50% (6/12) |
| quote shape · q3 quote_fabricated · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| quote shape · q3 quote_fabricated · zh | 0 | 6 | – | – | 0% (0/6) | – |
| quote shape · q3 quote_fabricated · zh+en | 0 | 12 | 0% | – | 50% (6/12) | – |
| quote shape · q4 quote_half_true · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| quote shape · q4 quote_half_true · zh | 0 | 6 | – | – | 0% (0/6) | – |
| quote shape · q4 quote_half_true · zh+en | 0 | 12 | 0% | – | 50% (6/12) | – |
| quote shape · q5 quote_number_changed · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| quote shape · q5 quote_number_changed · zh | 0 | 6 | – | – | 0% (0/6) | – |
| quote shape · q5 quote_number_changed · zh+en | 0 | 12 | 0% | – | 50% (6/12) | – |
| quote shape · q6 quote_is_paraphrase · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| quote shape · q6 quote_is_paraphrase · zh | 0 | 6 | – | – | 0% (0/6) | – |
| quote shape · q6 quote_is_paraphrase · zh+en | 0 | 12 | 0% | – | 50% (6/12) | – |
| quote shape · q7 quote_missing · en | 0 | 6 | 0% | – | 100% (6/6) | – |
| quote shape · q7 quote_missing · zh | 0 | 6 | 0% | – | 100% (6/6) | – |
| quote shape · q7 quote_missing · zh+en | 0 | 12 | 0% | – | 100% (12/12) | – |
| quote shape · real quote, fabricated comment (known limit, not scored) | – | – | – | – | accepted 7/12 | – |
| quote shape · zh | 12 | 30 | 0% | 0% | 20% (6/30) | 100% (12/12) |
| real · absence_claim | 0 | 10 | 0% | – | 50% (5/10) | – |
| real · all | 6 | 44 | 17% | 83% | 55% (24/44) | 17% (1/6) |
| real · framing_plus_verbatim | 1 | 0 | – | 0% | – | 100% (1/1) |
| real · quote + commentary (mixed, not scored) | – | – | – | – | accepted 17/21 | – |
| real · restatement_or_judgement | 0 | 34 | 0% | – | 56% (19/34) | – |
| real · verbatim | 5 | 0 | 100% | 100% | – | 0% (0/5) |
| real · zh | 6 | 44 | 17% | 83% | 55% (24/44) | 17% (1/6) |

**test split**

| Group | Grounded | Not grounded | Precision | Recall | False-accept | False-reject |
|---|---|---|---|---|---|---|
| all scored items | 27 | 69 | 38% | 96% | 62% (43/69) | 4% (1/27) |
| constructed · 1 verbatim · en | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 1 verbatim · zh | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 1 verbatim · zh+en | 8 | 0 | 100% | 100% | – | 0% (0/8) |
| constructed · 2 verbatim_punctuation_variant · en | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 2 verbatim_punctuation_variant · zh | 4 | 0 | 100% | 75% | – | 25% (1/4) |
| constructed · 2 verbatim_punctuation_variant · zh+en | 8 | 0 | 100% | 88% | – | 12% (1/8) |
| constructed · 3 framing_plus_verbatim · en | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 3 framing_plus_verbatim · zh | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| constructed · 3 framing_plus_verbatim · zh+en | 8 | 0 | 100% | 100% | – | 0% (0/8) |
| constructed · 4 half_true · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| constructed · 4 half_true · zh | 0 | 4 | 0% | – | 100% (4/4) | – |
| constructed · 4 half_true · zh+en | 0 | 8 | 0% | – | 100% (8/8) | – |
| constructed · 5 paraphrase_judgement · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| constructed · 5 paraphrase_judgement · zh | 0 | 4 | – | – | 0% (0/4) | – |
| constructed · 5 paraphrase_judgement · zh+en | 0 | 8 | 0% | – | 50% (4/8) | – |
| constructed · 6 absence_claim · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| constructed · 6 absence_claim · zh | 0 | 4 | 0% | – | 25% (1/4) | – |
| constructed · 6 absence_claim · zh+en | 0 | 8 | 0% | – | 62% (5/8) | – |
| constructed · 7 fabricated · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| constructed · 7 fabricated · zh | 0 | 4 | 0% | – | 25% (1/4) | – |
| constructed · 7 fabricated · zh+en | 0 | 8 | 0% | – | 62% (5/8) | – |
| constructed · 8 number_changed · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| constructed · 8 number_changed · zh | 0 | 4 | 0% | – | 100% (4/4) | – |
| constructed · 8 number_changed · zh+en | 0 | 8 | 0% | – | 100% (8/8) | – |
| constructed · all | 24 | 40 | 43% | 96% | 75% (30/40) | 4% (1/24) |
| constructed · en | 12 | 20 | 38% | 100% | 100% (20/20) | 0% (0/12) |
| constructed · zh | 12 | 20 | 52% | 92% | 50% (10/20) | 8% (1/12) |
| quote shape · all scored items | 16 | 40 | 25% | 50% | 60% (24/40) | 50% (8/16) |
| quote shape · en | 8 | 20 | 29% | 100% | 100% (20/20) | 0% (0/8) |
| quote shape · q1 quote_verbatim_plus_comment · en | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| quote shape · q1 quote_verbatim_plus_comment · zh | 4 | 0 | – | 0% | – | 100% (4/4) |
| quote shape · q1 quote_verbatim_plus_comment · zh+en | 8 | 0 | 100% | 50% | – | 50% (4/8) |
| quote shape · q2 quote_variant_plus_comment · en | 4 | 0 | 100% | 100% | – | 0% (0/4) |
| quote shape · q2 quote_variant_plus_comment · zh | 4 | 0 | – | 0% | – | 100% (4/4) |
| quote shape · q2 quote_variant_plus_comment · zh+en | 8 | 0 | 100% | 50% | – | 50% (4/8) |
| quote shape · q3 quote_fabricated · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| quote shape · q3 quote_fabricated · zh | 0 | 4 | – | – | 0% (0/4) | – |
| quote shape · q3 quote_fabricated · zh+en | 0 | 8 | 0% | – | 50% (4/8) | – |
| quote shape · q4 quote_half_true · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| quote shape · q4 quote_half_true · zh | 0 | 4 | – | – | 0% (0/4) | – |
| quote shape · q4 quote_half_true · zh+en | 0 | 8 | 0% | – | 50% (4/8) | – |
| quote shape · q5 quote_number_changed · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| quote shape · q5 quote_number_changed · zh | 0 | 4 | – | – | 0% (0/4) | – |
| quote shape · q5 quote_number_changed · zh+en | 0 | 8 | 0% | – | 50% (4/8) | – |
| quote shape · q6 quote_is_paraphrase · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| quote shape · q6 quote_is_paraphrase · zh | 0 | 4 | – | – | 0% (0/4) | – |
| quote shape · q6 quote_is_paraphrase · zh+en | 0 | 8 | 0% | – | 50% (4/8) | – |
| quote shape · q7 quote_missing · en | 0 | 4 | 0% | – | 100% (4/4) | – |
| quote shape · q7 quote_missing · zh | 0 | 4 | 0% | – | 100% (4/4) | – |
| quote shape · q7 quote_missing · zh+en | 0 | 8 | 0% | – | 100% (8/8) | – |
| quote shape · real quote, fabricated comment (known limit, not scored) | – | – | – | – | accepted 4/8 | – |
| quote shape · zh | 8 | 20 | 0% | 0% | 20% (4/20) | 100% (8/8) |
| real · absence_claim | 0 | 7 | 0% | – | 86% (6/7) | – |
| real · all | 3 | 29 | 19% | 100% | 45% (13/29) | 0% (0/3) |
| real · quote + commentary (mixed, not scored) | – | – | – | – | accepted 13/14 | – |
| real · restatement_or_judgement | 0 | 22 | 0% | – | 32% (7/22) | – |
| real · verbatim | 3 | 0 | 100% | 100% | – | 0% (0/3) |
| real · zh | 3 | 29 | 19% | 100% | 45% (13/29) | 0% (0/3) |

