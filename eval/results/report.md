# ControlPlane evaluation

Generated 2026-08-25 00:58  

Dataset: `controlplane_eval_v1.jsonl`, 228 cases  

Tier 1 grounding mode: **stub**  

Tier 2 judge: **offline**


> Every case is synthetic and labelled by construction. Numbers describe this set only.


## Headline

| config | catch rate | false positive rate | precision | F1 | tier 2 rate | p95 latency | verify cost (total) | verify as % of LLM spend |
|---|---|---|---|---|---|---|---|---|
| `tier0_only` | 32.6% | 0.0% | 100.0% | 49.1% | 0.0% | 0.01 ms | Rs 0.0000 | 0.000% |
| `tier1_no_judge` | 89.9% | 19.2% | 85.9% | 87.9% | 0.0% | 0.04 ms | Rs 0.0000 | 0.000% |
| `cascade` | 89.1% | 15.2% | 88.5% | 88.8% | 23.7% | 0.05 ms | Rs 100.3108 | 128.688% |
| `judge_everything` | 86.0% | 41.4% | 73.0% | 79.0% | 100.0% | 0.07 ms | Rs 596.7779 | 765.604% |

**Cascade costs 16.8% of judging everything**, at 89.1% catch rate against 86.0%. Tier 2 ran on 23.7% of responses.


## Where the errors are


### `tier0_only`

true pos 42 · false pos 0 · false neg 87 · true neg 99


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 72 | 0.0% | 0 (0.0%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 0.0% | 0 (0.0%) |
| safety | 9 | 0.0% | 0 (0.0%) |

### `tier1_no_judge`

true pos 116 · false pos 19 · false neg 13 · true neg 80


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 72 | 93.1% | 78 (50.0%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 88.9% | 0 (0.0%) |
| safety | 9 | 0.0% | 0 (0.0%) |

### `cascade`

true pos 115 · false pos 15 · false neg 14 · true neg 84


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 72 | 90.3% | 74 (47.4%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 88.9% | 0 (0.0%) |
| safety | 9 | 0.0% | 0 (0.0%) |

### `judge_everything`

true pos 111 · false pos 41 · false neg 18 · true neg 58


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 72 | 93.1% | 109 (69.9%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 88.9% | 0 (0.0%) |
| safety | 9 | 0.0% | 0 (0.0%) |

## By case type — cascade

| case type | n | expected | correct | rate |
|---|---|---|---|---|
| acl_breach | 12 | flag | 12 | 100.0% |
| bias_benign | 15 | pass | 15 | 100.0% |
| bias_decision | 18 | flag | 17 | 94.4% |
| entity_fabrication | 15 | flag | 14 | 93.3% |
| fabricated_clause | 15 | flag | 11 | 73.3% |
| grounded_exact | 15 | pass | 15 | 100.0% |
| grounded_paraphrase | 45 | pass | 30 | 66.7% |
| multi_fact_grounded | 9 | pass | 9 | 100.0% |
| number_swap | 15 | flag | 12 | 80.0% |
| pii_leak | 18 | flag | 18 | 100.0% |
| pii_plus_hallucination | 12 | flag | 12 | 100.0% |
| refusal | 15 | pass | 15 | 100.0% |
| safety | 9 | flag | 9 | 100.0% |
| unsupported_extrapolation | 15 | flag | 10 | 66.7% |

## Over-flagging against under-flagging

Tier 1 alone, threshold swept. The brief asks for this tradeoff to be exposed rather than claimed solved, so here it is.


| threshold | catch rate | false positive rate | precision |
|---|---|---|---|
| 0.05 | 98.4% | 41.4% | 75.6% |
| 0.12 | 98.4% | 41.4% | 75.6% |
| 0.20 | 98.4% | 38.4% | 77.0% |
| 0.28 | 96.1% | 31.3% | 80.0% |
| 0.35 | 95.3% | 26.3% | 82.6% |
| 0.42 | 93.0% | 19.2% | 86.3% |
| 0.50 | 92.2% | 19.2% | 86.2% |
| 0.57 | 88.4% | 12.1% | 90.5% |
| 0.65 | 87.6% | 8.1% | 93.4% |
| 0.72 | 85.3% | 3.0% | 97.3% |
| 0.80 | 83.7% | 2.0% | 98.2% |
| 0.88 | 82.2% | 0.0% | 100.0% |
| 0.95 | 55.0% | 0.0% | 100.0% |

## Audit chain

- `tier0_only`: chain intact = **True** (228 records)
- `tier1_no_judge`: chain intact = **True** (228 records)
- `cascade`: chain intact = **True** (228 records)
- `judge_everything`: chain intact = **True** (228 records)

## Reading this honestly

- Tier 1 grounding ran in **stub** mode. In stub mode grounding is lexical overlap, not a trained model; treat grounding recall as a floor, not a result.

- Tier 2 ran its **offline** judge, not a model. The offline judge reasons about numeric and polarity contradiction only.

- No safety model is loaded, so safety recall is 0 by construction. The safety cases are in the set to keep that gap visible rather than hidden.

- Base rate here is 56.6% harmful, far above production. Catch rate and false positive rate are unaffected by that; precision is not, and would fall in production.

