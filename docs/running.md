# Running the gateway

## Mock mode (no API key)

    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn controlplane.proxy.gateway:app --reload --port 8000

Check it is up:

    curl localhost:8000/health

Send a request. The use case is chosen by header:

    curl -X POST localhost:8000/v1/chat/completions \
      -H 'Content-Type: application/json' \
      -H 'X-ControlPlane-Use-Case: customer_support' \
      -d '{"messages":[{"role":"user","content":"what is the room rent limit"}],
           "controlplane":{"retrieved_chunks":[
             {"id":"pol-1","text":"Room rent capping under this policy is 1 percent of sum insured per day."}]}}'

Swap the header to internal_copilot or decision_support and send the same body.
The verdict changes, the code does not.

## Real provider

    export CP_UPSTREAM=openai        # or anthropic
    export CP_API_KEY=sk-...
    export CP_MODEL=gpt-4o-mini

Never commit the key. .gitignore already excludes .env.

## Audit chain

    curl localhost:8000/audit/verify

Tamper with a line in audit.jsonl and call it again — it reports the line where
the chain breaks.

## The dashboard

    uvicorn controlplane.proxy.gateway:app --port 8000
    python3 demo/feed_dashboard.py            # another terminal, synthetic traffic
    open http://localhost:8000/dashboard

The gateway loads the tier 1 classifiers on startup, which takes a few seconds.
That is deliberate. Without them grounding falls back to lexical overlap, far
more responses land inside the uncertainty band, and tier 2 fires on 57% of
traffic instead of 2.8% — every one of those a paid judge call. `/health`
reports which mode is live. Set `CP_SKIP_MODELS=1` on a machine that has none.

What the dashboard shows:

- **Tiles** — verified count, escalation rate against the policy's own cap, tier
  2 rate, p95 against the policy's own latency budget, verification spend as a
  percentage of model spend. The escalation and latency tiles carry a meter and
  turn red when the policy exceeds a limit it set for itself.
- **Decision feed** — live over SSE, newest first, with the action, the
  categories that fired, the offending span, and what the check cost.
- **Review queue** — only what a human would actually be looking at: escalated
  and blocked.

Tabs filter to one use case. State is in memory only — restarting the gateway
clears the feed and keeps the audit log, which is the right way round.
