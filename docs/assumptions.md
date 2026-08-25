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

## Numbers we assumed rather than measured

- **Rs 88 to the US dollar.** Not a live rate. Every rupee figure moves with it.
- **Cost of being wrong: Rs 400 / Rs 60 / Rs 50,000** per use case, and **Rs 25
  / Rs 25 / Rs 200** for a human review. These drive every routing decision and
  none of them came from a customer. They are the first thing a real deployment
  would replace, and the whole router is built so that replacing them is a
  config edit.
- **Rs 45 per hour** for the GPU tier 1 runs on.
- **820 prompt tokens and 95 completion tokens** for a typical upstream
  response, used so verification cost has something to be a percentage of.
- **Anthropic judge output tokens.** No Anthropic key was available, so the
  per-claim output figure is an estimate at the pessimistic end. OpenAI's is
  measured. Anything derived from the Anthropic figure is labelled estimated.

## Limits of what we built

- **Bias detection is shallow by design.** It fires when a protected attribute
  appears alongside decision or generalisation language. It will miss bias
  expressed without either, and it cannot detect disparate impact across a
  population - that needs counterfactual probing, which Round 2 puts out of
  scope. It catches the shape that matters most in a claims or credit answer:
  a decision justified by group membership.
- **Grounding is entailment, not verification.** The model judges whether the
  retrieved text supports the claim. If retrieval returned the wrong chunk, or
  a stale one, a confidently wrong answer can still be scored as grounded. We
  check the answer against the sources, not the sources against the world.
- **Multi-hop claims are the known weak point**, 4 of 9 on the eval set.
- **The eval set is synthetic and was written by the same person who tuned the
  checker.** An earlier version of it scored 100% on every case type, which is
  why the adversarial cases exist. It is a floor on difficulty, not a ceiling
  on quality.
- **The simulated reviewer in the feedback demo is always right.** A real review
  queue disagrees with itself, and that noise is not modelled.

## What we are not doing

- No multi-tenant auth, billing, or RBAC.
- No model fine-tuning from scratch. Tier 1 classifiers are off-the-shelf or lightly adapted.
- No support for every provider. Two provider paths are implemented; OpenAI is
  the one verified against a live key.
- No multi-turn risk accumulation. The brief names it; we verify one response at
  a time and say so.
