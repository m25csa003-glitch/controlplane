# Who is doing what

Deadline: 30 August 2026.

## Akshat — tier 1 and evaluation
- replace the grounding stub with the real model, confirm scores look sane
- build a small calibration set and tune the uncertainty bands in each policy
- benchmark harness on RAGTruth: catch rate, false positive rate, latency, cost
- FP32 vs INT8 latency comparison on the lab GPU
- baseline: full judge on every response, compared against the cascade

## Aditya — gateway and tier 0
- point the gateway at the real provider, confirm streaming works end to end
- fill configs/pricing.yaml with real token prices, note source and date
- wire real token usage into the cost meter so verification_cost and llm_cost are real
- extend tier 0: schema validation and the ACL path need test cases

## Arnesh — tier 2, router, dashboard
- replace the judge stub with a real API call, return spans as JSON
- dashboard: single HTML page served by FastAPI, live feed over SSE, one tab per use case
- show running cost meter and the escalation queue
- do not use a node build pipeline, there is no time for it

## Everyone, Saturday
- business proposal document
- README complete
- demo video

## Rules
- controlplane/schema.py is the contract. Do not change it alone.
- Do not commit API keys.
- Commit often, small commits, push daily.
