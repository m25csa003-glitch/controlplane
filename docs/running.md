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
