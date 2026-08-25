# ControlPlane

Team Nexus, IIT Jodhpur — Accenture Innovation Challenge 2026, Problem Track 1

A verification layer between an application and any LLM API. It scores every
response for hallucination, bias, privacy and cost, then decides whether to
pass, annotate, redact, regenerate, escalate or block it — according to the risk
policy of the specific use case the request came from.

## Quickstart

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python3 demo/run_pipeline.py

That runs eight responses through three use-case policies. **No API key and no
models needed** — grounding falls back to a lexical check and the judge to an
offline one, and the output says which mode produced it. That property is
deliberate: nothing here is a demo that only works on the author's laptop.

For the real thing:

    python3 load_models.py                  # tier 1 models, ~500MB
    cp .env.example .env                    # then add OPENAI_API_KEY
    python3 demo/run_pipeline.py --models

Other entry points:

    python3 demo/run_streaming.py --models  # verification beside the token stream
    python3 demo/run_feedback.py            # reviews retuning thresholds
    python3 eval/run_eval.py                # the full benchmark, ~45 min with a key
    pytest tests/                           # 28 tests, no network

## What it does

A response passes through a cascade, and each tier only runs when the one before
it was not confident enough.

| Tier | What | Cost | Latency |
|---|---|---|---|
| 0 | Deterministic rules: PII, ACL, schema | free | <1 ms |
| 1 | NLI grounding, toxicity, bias heuristic | GPU seconds | ~85 ms |
| 2 | LLM judge, only inside the uncertainty band | tokens | 1.3–3.1 s |

The **action router** then weighs `P(wrong) × cost_of_being_wrong` against
`cost_of_human_review` and picks an action. Every category is evaluated, not
just the first one that trips — a response can be a hallucination *and* a
privacy event, and the verdict records both.

Every verdict, and every human override, goes to an append-only hash-chained
log.

## Measured results

319 labelled cases, live judge, `eval/results/report.md`:

| config | catch | false positives | tier 2 rate | p95 | cost |
|---|---|---|---|---|---|
| rules only | 22.8% | 0.0% | 0% | 0.01 ms | Rs 0 |
| rules + classifiers | 93.5% | 7.4% | 0% | 163 ms | Rs 0.39 |
| **the cascade** | **94.6%** | **7.4%** | **2.8%** | **184 ms** | **Rs 1.13** |
| a judge on every response | 94.6% | 15.6% | 100% | 4071 ms | Rs 30.14 |

**The cascade reaches the same catch rate as judging everything, at 3.8% of the
cost, with half the false positives and 22× lower latency.** That is the whole
argument, and it is measured rather than asserted.

The report also states what the system cannot do — multi-hop grounding at 4/9,
quantifier flips at 47%, one policy over its own latency budget. Those are in
`docs/tasks.md` under known gaps.

## Why a policy layer

The same response, three policies, three verdicts:

```
hallucinated number  customer_support  -> regenerate   (wrong costs Rs 400)
                     internal_copilot  -> annotate     (wrong costs Rs 60)
                     decision_support  -> escalate     (wrong costs Rs 50,000)
```

Nothing in the Python knows what a use case is. Risk appetite, latency budget,
uncertainty band, thresholds, actions, retention and jurisdiction all live in
`configs/policies/*.yaml`. A new jurisdiction is a config change.

## Layout

    configs/policies/     one YAML per use case — this is where behaviour lives
    configs/pricing.yaml  token prices, with source and capture date
    controlplane/schema.py    the contract between modules
    controlplane/tiers/       tier 0 rules, tier 1 classifiers, tier 2 judge
    controlplane/router/      expected-cost action decision
    controlplane/cost/        prices every check and every upstream call
    controlplane/streaming.py verification beside the token stream
    controlplane/feedback/    reviews retuning thresholds
    controlplane/audit/       hash-chained decision log
    controlplane/proxy/       OpenAI-compatible gateway
    eval/                     benchmark harness, dataset and results
    demo/                     runnable scenarios
    docs/                     assumptions, status, running

## Gateway

    uvicorn controlplane.proxy.gateway:app --reload --port 8000
    curl localhost:8000/health

OpenAI-compatible, so an existing client points at it by changing a base URL.
Streaming works; verification runs beside the stream rather than after it. See
`docs/running.md`.

## Honest notes

- The eval set is synthetic and was written by the same person who tuned the
  checker. An earlier version scored 100% on everything, which is why the
  adversarial cases exist.
- Every rupee figure rests on assumed costs, listed in `docs/assumptions.md`.
- Grounding checks the answer against the retrieved sources, not the sources
  against the world. Bad retrieval still produces a confidently grounded wrong
  answer.

## Team

Nexus — Akshat Jain, Aditya Pratap Singh, Arnesh Sanjeev Singh.
Round 2 implementation by Akshat Jain.
