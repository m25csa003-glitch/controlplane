# ControlPlane evaluation

Generated 2026-08-25 01:36  

Dataset: `controlplane_eval_v1.jsonl`, 319 cases  

Tier 1 grounding mode: **nli**  

Tier 2 judge: **offline**


> Every case is synthetic and labelled by construction. Numbers describe this set only.


## Headline

| config | catch rate | false positive rate | precision | F1 | tier 2 rate | p95 latency | verify cost (total) | verify as % of LLM spend |
|---|---|---|---|---|---|---|---|---|
| `tier0_only` | 22.8% | 0.0% | 100.0% | 37.2% | 0.0% | 0.02 ms | Rs 0.0000 | 0.000% |
| `tier1_no_judge` | 94.0% | 10.4% | 92.5% | 93.3% | 0.0% | 85.29 ms | Rs 0.2205 | 0.202% |
| `cascade` | 94.0% | 10.4% | 92.5% | 93.3% | 2.5% | 84.85 ms | Rs 21.2482 | 19.483% |
| `judge_everything` | 73.4% | 42.2% | 70.3% | 71.8% | 100.0% | 90.92 ms | Rs 815.7043 | 747.943% |

**Cascade costs 2.6% of judging everything**, at 94.0% catch rate against 73.4%. Tier 2 ran on 2.5% of responses.


**Tier 2 changed no decisions on this set.** It ran on 2.5% of responses and cost Rs 21.03 to reach the same verdicts tier 1 already had. Two things follow: the uncertainty band is currently too narrow to catch the cases that would benefit, and the offline judge is not strong enough to overturn tier 1 anyway. The band is a policy value, so this is a tuning result, not a code change — but it is not yet earning its cost.


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

true pos 173 · false pos 14 · false neg 11 · true neg 121


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 127 | 93.7% | 59 (30.7%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 88.9% | 0 (0.0%) |
| safety | 9 | 100.0% | 0 (0.0%) |

### `cascade`

true pos 173 · false pos 14 · false neg 11 · true neg 121


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 127 | 92.1% | 59 (30.7%) |
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
| hedged_correct | 15 | pass | 10 | 66.7% |
| multi_fact_grounded | 9 | pass | 9 | 100.0% |
| multi_hop | 9 | pass | 0 | 0.0% |
| number_swap | 15 | flag | 15 | 100.0% |
| numeral_synonym | 12 | pass | 12 | 100.0% |
| partial_truth | 15 | flag | 15 | 100.0% |
| pii_leak | 18 | flag | 18 | 100.0% |
| pii_plus_hallucination | 12 | flag | 12 | 100.0% |
| quantifier_flip | 15 | flag | 8 | 53.3% |
| refusal | 15 | pass | 15 | 100.0% |
| safety | 9 | flag | 9 | 100.0% |
| unit_swap | 10 | flag | 8 | 80.0% |
| unsupported_extrapolation | 15 | flag | 15 | 100.0% |

## Over-flagging against under-flagging

Tier 1 alone, threshold swept. The brief asks for this tradeoff to be exposed rather than claimed solved, so here it is.


| threshold | catch rate | false positive rate | precision |
|---|---|---|---|
| 0.05 | 96.7% | 16.3% | 89.0% |
| 0.12 | 95.7% | 12.6% | 91.2% |
| 0.20 | 95.1% | 12.6% | 91.1% |
| 0.28 | 94.6% | 12.6% | 91.1% |
| 0.35 | 94.6% | 12.6% | 91.1% |
| 0.42 | 94.6% | 11.1% | 92.1% |
| 0.50 | 94.6% | 11.1% | 92.1% |
| 0.57 | 94.0% | 11.1% | 92.0% |
| 0.65 | 93.5% | 10.4% | 92.5% |
| 0.72 | 93.5% | 10.4% | 92.5% |
| 0.80 | 93.5% | 10.4% | 92.5% |
| 0.88 | 92.9% | 10.4% | 92.4% |
| 0.95 | 91.8% | 10.4% | 92.3% |

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

