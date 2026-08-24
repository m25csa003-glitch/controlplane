# Assumptions

The Round 2 brief says to use reasonable assumptions and state them clearly. This file is that
statement. Anything here is a design decision we made, not a measured fact.

## Deployment shape

- The enterprise consumes foundation models over an API. We cannot see model internals, retrain
  the model, or rely on activations. Everything we do works at the input/output layer.
- Token logprobs may or may not be exposed depending on the provider. Our detection must degrade
  gracefully when they are unavailable — logprob-based uncertainty is treated as an optional
  signal, never a required one.
- Three concurrent use cases, each with its own policy:
  - customer support assistant — external users, tight latency budget, high reputational risk
  - internal knowledge assistant — employees, relaxed latency, moderate risk
  - decision support tool — regulated workflow, latency can be traded for certainty
- Combined volume: tens of thousands of interactions per week. That is roughly 2-5 requests per
  second at peak, which is well inside what a single GPU worker can verify.

## Data

- Retrieval sources are a mix of well-governed and loosely governed content. We assume some
  retrieved chunks are stale or contradictory, so a grounding check can fail for reasons other
  than model hallucination. We report these separately.
- No real enterprise data is used. Demo corpora are synthetic or public.

## Risk model

- Under-flagging and over-flagging are both failures, and they trade off against each other. We do
  not claim to solve this — we expose the operating point as a configurable knob per use case and
  report where each policy sits on the curve.
- Bias, hallucination and privacy overlap. A fabricated detail about a named person is both a
  hallucination and a privacy event. Our scoring is multi-label, not a single category.

## Regulatory

- Jurisdiction assumed: India (DPDP Act) as primary, EU AI Act treated as the stricter reference
  for audit trail requirements. Policy is data-driven so a new jurisdiction is a config change,
  not a code change.

## What we are not doing

- No multi-tenant auth, billing, or RBAC.
- No model fine-tuning from scratch. Tier 1 classifiers are off-the-shelf or lightly adapted.
- No support for every provider. One provider path is implemented properly.
