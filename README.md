# ControlPlane

Team Nexus, IIT Jodhpur — Accenture Innovation Challenge 2026, Problem Track 1 (ControlPlane.ai)

A verification layer that sits between an application and any LLM API. It scores every response for
hallucination risk, cost and policy violations, then decides whether to pass, redact, regenerate,
escalate or block it — based on the risk appetite configured for that specific use case.

## Quickstart

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

    python3 demo/run_pipeline.py

That runs four responses through three different use-case policies with no API key and no models
downloaded. The same input produces different verdicts per policy.

To download the tier 1 models:

    python3 load_models.py

To run the gateway, see docs/running.md.

## Why this exists

Runtime guardrails already exist. What does not exist is a single layer that covers all three risk
dimensions, lets a different use case run a different risk policy, and can justify the cost of each
check it performs. Today a team stacks an eval framework, a grounding checker, an observability
platform and a guardrail — four products, none of which price the decision.

## How it works

A response passes through a cascade. Tier 0 is deterministic rules and costs nothing. Tier 1 is
small classifiers that score grounding and safety. Tier 2 is a judge model, called only when tier 1
lands inside the uncertainty band defined by the policy. The action router then weighs
P(wrong) x cost_of_being_wrong against cost_of_human_review and picks an action. Every verdict is
written to an append-only hash-chained log.

## Repository layout

    configs/policies/     one YAML per use case (risk appetite, latency budget, actions)
    configs/pricing.yaml  token prices used by the cost meter
    controlplane/schema.py    shared contract - do not change without telling the team
    controlplane/proxy/       OpenAI-compatible gateway, SSE streaming
    controlplane/tiers/       tier 0 rules, tier 1 classifiers, tier 2 judge
    controlplane/router/      action router and the expected-cost decision
    controlplane/audit/       append-only hash-chained decision log
    controlplane/policy/      policy loader
    dashboard/                operator UI
    eval/                     benchmark harness and results
    demo/                     seeded scenarios used in the demo video
    docs/                     architecture, assumptions, running, evaluation

## Status

Prototype for Round 2. Not production software.

Working: policy layer, tier 0 (PII, ACL, schema), action router, hash-chained audit log, gateway
with mock and real upstreams.

In progress: tier 1 real models, tier 2 judge, streaming-concurrent verification, dashboard,
evaluation harness.

See docs/assumptions.md for everything we assumed rather than measured.

## Team

- Akshat Jain — M.Tech Artificial Intelligence
- Aditya Pratap Singh — M.Tech Artificial Intelligence
- Arnesh Sanjeev Singh — M.Tech Computer Science
