# ControlPlane evaluation

Generated 2026-08-30 01:26  

Dataset: `controlplane_eval_v1.jsonl`, 319 cases  

Tier 1 grounding mode: **nli**  

Tier 2 judge: **mixed (327 api, 1 offline, 1 failed)** — openai/gpt-5.6-sol  

Upstream priced as: **gpt-5.6-terra** — the cost column is a percentage of this, so it moves if the application runs a different model.


> Every case is synthetic and labelled by construction. Numbers describe this set only.


## Headline

| config | catch rate | false positive rate | precision | F1 | tier 2 rate | p95 latency | verify cost (total) | verify as % of LLM spend |
|---|---|---|---|---|---|---|---|---|
| `tier0_only` | 22.8% | 0.0% | 100.0% | 37.2% | 0.0% | 0.02 ms | Rs 0.0000 | 0.000% |
| `tier1_no_judge` | 93.5% | 7.4% | 94.5% | 94.0% | 0.0% | 139.78 ms | Rs 0.3477 | 0.446% |
| `cascade` | 94.6% | 7.4% | 94.6% | 94.6% | 2.8% | 174.87 ms | Rs 1.1023 | 1.413% |
| `judge_everything` | 92.4% | 14.8% | 89.5% | 90.9% | 100.0% | 5534.46 ms | Rs 30.0111 | 38.456% |

**Cascade costs 3.7% of judging everything**, at 94.6% catch rate against 92.4%. Tier 2 ran on 2.8% of responses.


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

true pos 174 · false pos 10 · false neg 10 · true neg 125


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 127 | 92.1% | 56 (29.2%) |
| pii | 30 | 100.0% | 0 (0.0%) |
| acl | 12 | 100.0% | 0 (0.0%) |
| bias | 18 | 88.9% | 0 (0.0%) |
| safety | 9 | 100.0% | 0 (0.0%) |

### `judge_everything`

true pos 170 · false pos 20 · false neg 14 · true neg 115


| category | labelled | recall | co-fires on unlabelled |
|---|---|---|---|
| grounding | 127 | 96.9% | 80 (41.7%) |
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
| conditional_flip | 15 | flag | 14 | 93.3% |
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
| quantifier_flip | 15 | flag | 8 | 53.3% |
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
| `[0.5, 0.5]` | 0.0% | 94.0% | 8.1% | Rs 0.40 |
| `[0.4, 0.6]` | 0.3% | 94.0% | 8.1% | Rs 0.39 |
| `[0.3, 0.7]` | 1.6% | 94.0% | 8.9% | Rs 1.16 |
| `[0.25, 0.75]` | 2.5% | 94.6% | 8.1% | Rs 1.19 |
| `[0.2, 0.8]` | 2.8% | 94.6% | 8.1% | Rs 1.14 |
| `[0.1, 0.9]` | 4.4% | 94.0% | 8.1% | Rs 1.64 |
| `[0.05, 0.95]` | 7.8% | 94.0% | 10.4% | Rs 3.51 |
| `[0.0, 1.01]` | 95.0% | 77.2% | 16.3% | Rs 27.81 |

## Latency against the policy budget

`latency_budget_ms` is the ceiling each policy sets on added latency for the clean path. p95 below is measured across all responses in that use case, judge calls included.


| use case | budget | p95 measured | p95 when tier 2 ran | verdict |
|---|---|---|---|---|
| customer_support | 300 ms | 88 ms | n/a | within budget |
| decision_support | 3000 ms | 190 ms | 3914 ms | **over budget** |
| internal_copilot | 1000 ms | 1225 ms | 3216 ms | **over budget** |

A judge call is 1.3 s on the cheap model and 3.1 s on the strong one. No amount of tuning fits that inside a 300 ms customer-support budget. Tier 2 is therefore not an inline step for a latency-bound use case - it has to run beside the response or after it, which is what the streaming path has to solve. The clean path, where tier 2 does not run at all, stays inside budget; it is only the escalated few percent that blow it.


## Judge calls

A judge call that fails falls back to the offline judge silently, so the fallbacks are counted. 1 of 328 calls (0.3%) fell back, so that share of the grounding scores below came from the offline judge rather than the model. Named because a silent fallback turns an API result into a lexical one with no trace.


| config | api calls | failed | offline |
|---|---|---|---|
| `tier0_only` | 0 | 0 | 0 |
| `tier1_no_judge` | 0 | 0 | 0 |
| `cascade` | 9 | 0 | 0 |
| `judge_everything` | 318 | 1 | 1 |

## Audit chain

- `tier0_only`: chain intact = **True** (319 records)
- `tier1_no_judge`: chain intact = **True** (319 records)
- `cascade`: chain intact = **True** (319 records)
- `judge_everything`: chain intact = **True** (319 records)

## Reading this honestly

- Tier 1 grounding ran on **cross-encoder/nli-deberta-v3-base** (`nli`) on mps.

- Tier 2 ran a **live judge** (openai/gpt-5.6-sol), with 1 of 328 calls falling back to the offline judge (0.3%) — see the judge-call table. So the ordering against `judge_everything` is a real result, not an artefact of a weak stand-in: sending every response to the same judge scored worse on both catch rate and false positives. It is one judge on one synthetic set, which is the limit worth stating; it is not a caveat that the comparison was unfair.

- `multi_hop` cases fail by construction. Each claim is scored against each chunk separately, which is what keeps faithful paraphrase from being flagged, but a claim that is true only by combining two chunks matches neither one alone. A judge that sees all sources at once is the right place to fix this, which is an argument for widening the band on retrieval-heavy use cases.

- The set is synthetic and was written by the same person who tuned the checker. An earlier version of it scored 100% on every case type, which is why the adversarial cases exist. Treat these numbers as a lower bound on difficulty, not an upper bound on quality.

- Base rate here is 57.7% harmful, far above production. Catch rate and false positive rate are unaffected by that; precision is not, and would fall in production.

