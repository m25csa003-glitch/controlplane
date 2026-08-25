# What is done and what is not

Round 2 deliverable: 30 August 2026. Round 1 was pitched by Team Nexus; the
Round 2 implementation was carried out by Akshat Jain.

## Working, with evidence

| Component | State | Evidence |
|---|---|---|
| Policy layer | 3 use cases, behaviour in YAML | `configs/policies/`, `demo/run_pipeline.py` |
| Tier 0 rules | PII, ACL, schema | `eval/results/report.md`, PII recall 100% |
| Tier 1 grounding | `cross-encoder/nli-deberta-v3-base` on MPS | catch 93.5% at 7.4% FP |
| Tier 1 safety | `unitary/toxic-bert`, thresholds calibrated | separation 0.003 clean / 0.407 harmful |
| Tier 1 bias | attribute x decision heuristic | `bias_decision` 94%, `bias_benign` 100% |
| Tier 2 judge | OpenAI and Anthropic, structured output | 319 live calls, 0 failures |
| Action router | expected cost, multi-label | `controlplane/router/router.py` |
| Cost meter | verified prices, per-check attribution | cascade Rs 1.13 vs Rs 30.14 |
| Audit log | hash-chained, tamper-evident | `tests/test_pipeline.py` |
| Gateway | OpenAI-compatible, mock and live | `docs/running.md` |
| Streaming | verification beside the token stream | `demo/run_streaming.py` |
| Feedback loop | reviews retune thresholds | `demo/run_feedback.py` |
| Evaluation | 319 labelled cases, 4 configs, 2 sweeps | `eval/results/report.md` |
| Tests | 28, hermetic, no network | `pytest tests/` |

## Known gaps, measured rather than hidden

- **multi-hop grounding, 4/9.** A claim true only by combining two chunks
  entails neither alone. The joined premise recovers some of it and doubles
  tier 1 latency, so it is a policy switch, not a default.
- **quantifier flips, 47%.** "up to X" against "at least X" is one word and the
  opposite meaning; the NLI model often misses it.
- **`internal_copilot` is over its own latency budget**, 1187ms p95 against
  1000ms. Its uncertainty band is wide, so more responses reach the 1.3s judge.
- **`decision_support` escalates 32.3% against its declared 20% cap.** Surfaced
  by the feedback loop. Needs either reviewers or accepted risk.
- **Anthropic modelled cost is an estimate.** No Anthropic key was available to
  measure thinking-token output against. Labelled as estimated everywhere.
- **HHEM does not load** under transformers 5.x. It stays first in the
  preference list for the day that changes.

## Not built, deliberately

Out of scope for Round 2 and in the roadmap instead: bias detection by
counterfactual probing, agent action gating, multi-tenant auth and RBAC,
multi-turn risk accumulation.

## Remaining before submission

- [ ] Business proposal document
- [ ] README rewrite
- [ ] Public GitHub repository
- [ ] Demo video
- [ ] Operator dashboard

## Rules that still hold

- `controlplane/schema.py` is the contract between modules.
- Behaviour belongs in policy YAML. An `if use_case ==` outside the loader is a
  design smell.
- Everything degrades gracefully with no key and no models. That is what makes
  the demo runnable on a fresh clone.
- No API keys in code. `.env` is gitignored and stays that way.
