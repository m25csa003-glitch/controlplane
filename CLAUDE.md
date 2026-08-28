# ControlPlane

## What this is

A verification layer between an application and any LLM API. It scores every
response for hallucination, bias, privacy and cost, then decides whether to
pass, annotate, redact, regenerate, escalate or block it — according to the risk
policy of the use case the request came from.

Accenture Innovation Challenge 2026, Problem Track 1, Team Nexus at IIT Jodhpur.
Round 2 is due **30 August 2026**. Round 2 implementation by Akshat Jain.

Repo: https://github.com/m25csa003-glitch/controlplane

## Read these first

- `docs/tasks.md` — what works, with evidence; what is broken, with numbers
- `docs/commands.md` — every runnable command and what it costs
- `eval/results/report.md` — the benchmark, including its failure modes
- `docs/assumptions.md` — every number nobody measured

## State as of 26 August 2026

Working and measured: policy layer, tier 0 rules, tier 1 (NLI grounding +
toxic-bert safety + bias heuristic), tier 2 judge (OpenAI verified live,
Anthropic written but unrun), expected-cost router, cost meter, hash-chained
audit, OpenAI-compatible gateway, streaming-concurrent verification, feedback
loop, operator dashboard, 319-case benchmark, 52 tests.

Cascade: **94.6% catch, 7.4% false positives, Rs 1.13** against **Rs 30.14** for
judging every response at the same catch rate.

Remaining: **the video**. Scripts are written: `docs/pitch_video.md` is the
pitch, `docs/demo_video.md` the technical walkthrough. That is the only
outstanding deliverable.

Known open items, all recorded in `docs/tasks.md`: multi-hop grounding is 4/9,
quantifier flips 47%, `internal_copilot` and `customer_support` run over limits
they set for themselves, and multi-turn risk accumulation is not built at all.

## How to verify a change

    source .venv/bin/activate
    python3 demo/run_pipeline.py
    python3 -m pytest tests/ -q

Both must pass **with no API key and no models downloaded**. That property is
the reason the demo runs on a fresh clone, and a change that breaks it is wrong.

`python3 eval/run_eval.py` costs about a dollar and 45 minutes. Its results are
committed. Do not re-run it casually — the user has said so explicitly.

## Conventions

- `controlplane/schema.py` is the contract between modules. Adding a field is
  fine; changing one is not, without saying so.
- Tier functions keep `run(...) -> (signals, elapsed_ms)`. Swap internals, not
  the shape.
- **Behaviour belongs in policy YAML.** An `if use_case ==` anywhere outside the
  loader is a design smell. Thresholds, bands, models, actions, budgets, review
  capacity and jurisdiction are all config.
- Everything degrades gracefully: no key, no models, no network. Every fallback
  reports which mode it ended up in rather than pretending.
- Never hardcode API keys. `.env` is gitignored and must stay that way.
- Code style: short, plain Python. Comments explain *why*, not *what*.

## What this project has learned the hard way

Written down because each of these cost real time and would be repeated.

- **A number without provenance is a liability.** Cost lines carry
  `measured` / `reported` / `modelled` / `estimated`. An early guess at judge
  output tokens was wrong by 5x, which made modelled cost read 19x the billed
  one and produced a confidently wrong conclusion about whether tier 2 pays for
  itself.
- **A benchmark that scores 100% is broken, not finished.** The first eval set
  did. `eval/corpus_hard.py` exists because of that.
- **Report what the system cannot do.** The eval names multi-hop at 4/9 and
  quantifier flips at 47%. Judges and reviewers trust a published weakness more
  than an unpublished strength.
- **Fallbacks must be counted.** A judge call that silently falls back to the
  offline judge turns an API result into a lexical one with no trace. The
  counter found 2 of 3 calls timing out on its first run.
- **Selectivity beat volume.** Judging every response scored the same catch rate
  with double the false positives and 27x the cost — a judge asked to re-rule on
  claims tier 1 already had right sometimes overrules them .
- **The expensive thing is human review, not verification.** Verification is
  Rs 5,537 a year at the brief's volume; one use case's review queue is
  Rs 3.36 crore. That reframes what the product is for.
