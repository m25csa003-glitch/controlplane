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
| Dashboard | live SSE feed, four charts, queue, cost vs limits | `dashboard/index.html` |
| Tests | 52, hermetic, no network | `pytest tests/` |

## Known gaps, measured rather than hidden

- **multi-hop grounding, 4/9.** A claim true only by combining two chunks
  entails neither alone. The joined premise recovers some of it and doubles
  tier 1 latency, so it is a policy switch, not a default.
- **quantifier flips, 47%.** "up to X" against "at least X" is one word and the
  opposite meaning; the NLI model often misses it.
- **`internal_copilot` is over its own latency budget**, 1187ms p95 against
  1000ms. Its uncertainty band is wide, so more responses reach the 1.3s judge.
- **`customer_support` runs over both its limits under live traffic** — 340ms
  p95 against a 300ms budget, and an escalation rate far above its 5% cap. The
  dashboard shows both in red. The cap is the more interesting of the two: it
  says this policy is written for cleaner traffic than it is being given.
- **`decision_support` escalates 32.3% against its declared 20% cap.** Surfaced
  by the feedback loop. Needs either reviewers or accepted risk.
- **Anthropic modelled cost is an estimate.** No Anthropic key was available to
  measure thinking-token output against. Labelled as estimated everywhere.
- **HHEM does not load** under transformers 5.x. It stays first in the
  preference list for the day that changes.

## Fixed after external testing

Three were found by someone driving the gateway rather than the library, which
is where a correct verdict and a wrong delivery diverge:

- **Streaming delivered what it blocked.** Buffered mode released each sentence
  once its check had *finished*, never checking what it *found*. A response
  ruled `block` arrived in full, followed by a message saying it was blocked.
- **`regenerate` was a no-op.** Nothing anywhere asked the model again; the
  wrong answer went out untouched. The headline demo case routes to it. The
  gateway now re-asks with the rejection, the unsupported claim and the
  sources — re-sending the original request unchanged would have been a coin
  flip on sampling noise, not a regeneration. Both the batch and the buffered
  streaming path do it; `streaming` mode cannot, having already delivered.
- **The cost column silently read zero.** The eval priced an OpenAI model
  against Anthropic, the lookup failed, and the money number became 0.000%
  without complaint.

## Not built, deliberately

Out of scope for Round 2 and in the roadmap instead: bias detection by
counterfactual probing, agent action gating, multi-tenant auth and RBAC,
multi-turn risk accumulation.

## Remaining before submission

- [x] Business proposal document — `docs/proposal.md`
- [x] README rewrite
- [x] Operator dashboard
- [x] Public GitHub repository
- [ ] Demo video — script ready in `docs/demo_video.md`

## Rules that still hold

- `controlplane/schema.py` is the contract between modules.
- Behaviour belongs in policy YAML. An `if use_case ==` outside the loader is a
  design smell.
- Everything degrades gracefully with no key and no models. That is what makes
  the demo runnable on a fresh clone.
- No API keys in code. `.env` is gitignored and stays that way.
