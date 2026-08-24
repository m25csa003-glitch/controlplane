# ControlPlane evaluation

Generated 2026-08-25 02:21  

Dataset: `controlplane_eval_v1.jsonl`, 319 cases  

Tier 1 grounding mode: **nli**  

Tier 2 judge: **offline**


> Every case is synthetic and labelled by construction. Numbers describe this set only.


## Headline

| config | catch rate | false positive rate | precision | F1 | tier 2 rate | p95 latency | verify cost (total) | verify as % of LLM spend |
|---|---|---|---|---|---|---|---|---|
| `tier0_only` | 22.8% | 0.0% | 100.0% | 37.2% | 0.0% | 0.02 ms | Rs 0.0000 | 0.000% |
| `tier1_no_judge` | 93.5% | 7.4% | 94.5% | 94.0% | 0.0% | 142.25 ms | Rs 0.3545 | 0.325% |
| `cascade` | 93.5% | 7.4% | 94.5% | 94.0% | 2.8% | 139.35 ms | Rs 21.5218 | 19.734% |
| `judge_everything` | 73.4% | 42.2% | 70.3% | 71.8% | 100.0% | 157.39 ms | Rs 815.8516 | 748.078% |

**Cascade costs 2.6% of judging everything**, at 93.5% catch rate against 73.4%. Tier 2 ran on 2.8% of responses.


**Tier 2 changed no decisions on this set.** It ran on 2.8% of responses and cost Rs 21.17 to reach the same verdicts tier 1 already had. Two things follow: the uncertainty band is currently too narrow to catch the cases that would benefit, and the offline judge is not strong enough to overturn tier 1 anyway. The band is a policy value, so this is a tuning result, not a code change — but it is not yet earning its cost.


## Where the errors are


### `tier0_only`

true pos 42 · false pos 0 · false neg 142 · true neg 135


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 127 | 0.0% | 0 (0.0%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 0.0% | 0 (0.0%) |
| safety | 9 | 0.0% | 0 (0.0%) |

### `tier1_no_judge`

true pos 172 · false pos 10 · false neg 12 · true neg 125


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 127 | 92.1% | 57 (29.7%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 88.9% | 0 (0.0%) |
| safety | 9 | 100.0% | 0 (0.0%) |

### `cascade`

true pos 172 · false pos 10 · false neg 12 · true neg 125


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 127 | 90.6% | 57 (29.7%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 88.9% | 0 (0.0%) |
| safety | 9 | 100.0% | 0 (0.0%) |

### `judge_everything`

true pos 135 · false pos 57 · false neg 49 · true neg 78


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 127 | 75.6% | 133 (69.3%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 88.9% | 0 (0.0%) |
| safety | 9 | 100.0% | 0 (0.0%) |

## By case type — cascade

| case type | n | expected | correct | rate |
|---|---|---|---|---|
| acl_breach | 12 | flag | 12 | 100.0% |
| bias_benign | 15 | pass | 15 | 100.0% |
| bias_decision | 18 | flag | 18 | 100.0% |
| conditional_flip | 15 | flag | 13 | 86.7% |
| entity_fabrication | 15 | flag | 15 | 100.0% |
| fabricated_clause | 15 | flag | 15 | 100.0% |
| grounded_exact | 15 | pass | 15 | 100.0% |
| grounded_paraphrase | 45 | pass | 45 | 100.0% |
| hedged_correct | 15 | pass | 11 | 73.3% |
| multi_fact_grounded | 9 | pass | 9 | 100.0% |
| multi_hop | 9 | pass | 3 | 33.3% |
| number_swap | 15 | flag | 15 | 100.0% |
| numeral_synonym | 12 | pass | 12 | 100.0% |
| partial_truth | 15 | flag | 15 | 100.0% |
| pii_leak | 18 | flag | 18 | 100.0% |
| pii_plus_hallucination | 12 | flag | 12 | 100.0% |
| quantifier_flip | 15 | flag | 7 | 46.7% |
| refusal | 15 | pass | 15 | 100.0% |
| safety | 9 | flag | 9 | 100.0% |
| unit_swap | 10 | flag | 8 | 80.0% |
| unsupported_extrapolation | 15 | flag | 15 | 100.0% |

## Over-flagging against under-flagging

Tier 1 alone, threshold swept. The brief asks for this tradeoff to be exposed rather than claimed solved, so here it is.


| threshold | catch rate | false positive rate | precision |
|---|---|---|---|
| 0.05 | 95.7% | 14.8% | 89.8% |
| 0.12 | 94.6% | 11.1% | 92.1% |
| 0.20 | 94.6% | 10.4% | 92.6% |
| 0.28 | 94.0% | 10.4% | 92.5% |
| 0.35 | 94.0% | 9.6% | 93.0% |
| 0.42 | 94.0% | 8.1% | 94.0% |
| 0.50 | 94.0% | 8.1% | 94.0% |
| 0.57 | 94.0% | 8.1% | 94.0% |
| 0.65 | 93.5% | 8.1% | 94.0% |
| 0.72 | 93.5% | 8.1% | 94.0% |
| 0.80 | 93.5% | 7.4% | 94.5% |
| 0.88 | 92.9% | 7.4% | 94.5% |
| 0.95 | 90.8% | 7.4% | 94.4% |

## What tier 2 buys, by band width

`[0.5, 0.5]` is an empty band, so the judge never runs. `[0.0, 1.01]` sends everything tier 1 flagged at all.


| band | tier 2 rate | catch rate | false positive rate | verify cost |
|---|---|---|---|---|
| `[0.5, 0.5]` | 0.0% | 94.0% | 8.1% | Rs 0.50 |
| `[0.4, 0.6]` | 0.3% | 94.0% | 8.1% | Rs 0.60 |
| `[0.3, 0.7]` | 1.6% | 93.5% | 9.6% | Rs 21.18 |
| `[0.25, 0.75]` | 2.5% | 94.0% | 9.6% | Rs 21.55 |
| `[0.2, 0.8]` | 2.8% | 94.0% | 9.6% | Rs 21.66 |
| `[0.1, 0.9]` | 4.4% | 92.9% | 8.9% | Rs 35.65 |
| `[0.05, 0.95]` | 7.8% | 94.0% | 12.6% | Rs 83.84 |
| `[0.0, 1.01]` | 95.0% | 78.3% | 58.5% | Rs 767.22 |

## Audit chain

- `tier0_only`: chain intact = **True** (319 records)
- `tier1_no_judge`: chain intact = **True** (319 records)
- `cascade`: chain intact = **True** (319 records)
- `judge_everything`: chain intact = **True** (319 records)

## Reading this honestly

- Tier 1 grounding ran on **cross-encoder/nli-deberta-v3-base** (`nli`) on mps.

- Tier 2 ran its **offline** judge, not a model. The offline judge reasons about numeric and polarity contradiction only.

- `judge_everything` is therefore not an upper bound on quality. Its catch rate is capped by the same offline judge, and it inherits that judge's habit of scoring paraphrase as unsupported - which is why its false positive rate is worse than the cascade's here. With a real judge behind a key, expect it to beat the cascade on catch rate and still cost roughly six times as much. The cost ratio is the durable finding; the quality ordering is not.

- `multi_hop` cases fail by construction. Each claim is scored against each chunk separately, which is what keeps faithful paraphrase from being flagged, but a claim that is true only by combining two chunks matches neither one alone. A judge that sees all sources at once is the right place to fix this, which is an argument for widening the band on retrieval-heavy use cases.

- The set is synthetic and was written by the same person who tuned the checker. An earlier version of it scored 100% on every case type, which is why the adversarial cases exist. Treat these numbers as a lower bound on difficulty, not an upper bound on quality.

- Base rate here is 57.7% harmful, far above production. Catch rate and false positive rate are unaffected by that; precision is not, and would fall in production.

