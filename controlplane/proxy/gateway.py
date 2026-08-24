import json
import os
import time
import asyncio

import httpx
from fastapi import FastAPI, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse

from ..pipeline import ControlPlane
from ..streaming import StreamingVerifier
from ..schema import Action

UPSTREAM = os.getenv("CP_UPSTREAM", "mock")
API_KEY = os.getenv("CP_API_KEY", "")
MODEL = os.getenv("CP_MODEL", "gpt-4o-mini")
DEFAULT_USE_CASE = os.getenv("CP_DEFAULT_USE_CASE", "customer_support")

ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
}

app = FastAPI(title="ControlPlane Gateway")
cp = ControlPlane(audit_path="audit.jsonl")


@app.get("/health")
def health():
    return {"status": "ok", "upstream": UPSTREAM, "use_cases": list(cp.policies)}


@app.get("/audit/verify")
def audit_verify():
    ok, line = cp.audit.verify()
    return {"chain_intact": ok, "broken_at_line": line}


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    x_controlplane_use_case: str = Header(default=None),
):
    body = await request.json()
    use_case = x_controlplane_use_case or body.pop("controlplane_use_case", DEFAULT_USE_CASE)
    extras = body.pop("controlplane", {}) or {}
    stream = body.get("stream", False)

    if use_case not in cp.policies:
        return JSONResponse({"error": f"unknown use_case '{use_case}'"}, status_code=400)

    if stream:
        return StreamingResponse(
            _stream_and_verify(body, use_case, extras),
            media_type="text/event-stream",
        )

    upstream_start = time.perf_counter()
    text, usage = await _call_upstream(body)
    upstream_ms = (time.perf_counter() - upstream_start) * 1000

    verdict = cp.verify(
        text,
        use_case,
        retrieved_chunks=extras.get("retrieved_chunks"),
        allowed_chunk_ids=set(extras["allowed_chunk_ids"]) if extras.get("allowed_chunk_ids") else None,
        user_id=extras.get("user_id", "anon"),
    )

    delivered = _apply_action(text, verdict)

    return {
        "id": f"cp-{verdict.request_id}",
        "object": "chat.completion",
        "model": body.get("model", MODEL),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": delivered},
            "finish_reason": "stop",
        }],
        "usage": usage,
        "controlplane": {
            **verdict.to_record(),
            "upstream_ms": round(upstream_ms, 2),
            "overhead_pct": round(100 * verdict.latency_ms / max(upstream_ms, 1e-6), 2),
        },
    }


def _apply_action(text, verdict):
    if verdict.action == Action.BLOCK:
        return "[withheld by ControlPlane: " + verdict.reason + "]"
    if verdict.action == Action.REDACT_SPAN:
        spans = sorted([s.span for s in verdict.signals if s.span], reverse=True)
        out = text
        for start, end in spans:
            out = out[:start] + "[redacted]" + out[end:]
        return out
    if verdict.action == Action.ANNOTATE:
        return text + f"\n\n[ControlPlane: {verdict.reason}]"
    if verdict.action == Action.ESCALATE:
        return text + "\n\n[flagged for human review before this is acted on]"
    return text


async def _call_upstream(body):
    if UPSTREAM == "mock":
        await asyncio.sleep(0.4)
        msgs = body.get("messages", [])
        last = msgs[-1]["content"] if msgs else ""
        return _mock_reply(last), {"prompt_tokens": 0, "completion_tokens": 0}

    headers = {"Content-Type": "application/json"}
    if UPSTREAM == "openai":
        headers["Authorization"] = f"Bearer {API_KEY}"
        payload = body
    else:
        headers["x-api-key"] = API_KEY
        headers["anthropic-version"] = "2023-06-01"
        payload = body

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(ENDPOINTS[UPSTREAM], headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    if UPSTREAM == "openai":
        return data["choices"][0]["message"]["content"], data.get("usage", {})
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "".join(parts), data.get("usage", {})


MOCK_REPLIES = {
    "room rent": "Room rent capping is 2 percent, so approximately 185000 rupees will be reimbursed.",
    "contact": "Your registered contact is 9876543210 and PAN ABCDE1234F.",
}


def _mock_reply(prompt):
    low = prompt.lower()
    for key, reply in MOCK_REPLIES.items():
        if key in low:
            return reply
    return "Room rent capping under this policy is 1 percent of sum insured per day."


async def _stream_and_verify(body, use_case, extras):
    """Verification runs beside the stream, not after it.

    Each sentence is checked as it completes while the model is still writing
    the next one, so on the clean path the verdict is ready when the last token
    is. Whether a sentence waits for its check before going out is
    `streaming_mode` in the policy."""
    verifier = StreamingVerifier(
        cp, use_case,
        retrieved_chunks=extras.get("retrieved_chunks"),
        allowed_chunk_ids=set(extras["allowed_chunk_ids"]) if extras.get("allowed_chunk_ids") else None,
        user_id=extras.get("user_id", "anon"),
    )

    async for chunk in _stream_upstream(body):
        step = await verifier.feed(chunk)
        if step.release:
            yield _sse({"choices": [{"delta": {"content": step.release}, "index": 0}]})
        for event in step.events:
            yield _sse({"controlplane": event})

    step = await verifier.close()
    if step.release:
        yield _sse({"choices": [{"delta": {"content": step.release}, "index": 0}]})
    for event in step.events:
        yield _sse({"controlplane": event})

    verdict = verifier.verdict
    cp.audit.append(verdict.to_record(), policy_version=cp.policies[use_case].version)

    # In streaming mode the caller has already seen the text, so a late verdict
    # is a correction rather than a gate. Say which it was.
    yield _sse({"controlplane": {
        "type": "verdict",
        "applied": verdict.action.value if verifier.mode == "buffered" else "advisory",
        **verdict.to_record(),
    }})
    yield "data: [DONE]\n\n"


def _sse(payload):
    return f"data: {json.dumps(payload)}\n\n"


async def _stream_upstream(body):
    if UPSTREAM == "mock":
        for word in _mock_reply(body.get("messages", [{}])[-1].get("content", "")).split(" "):
            await asyncio.sleep(0.05)
            yield word + " "
        return

    headers = {"Content-Type": "application/json"}
    if UPSTREAM == "openai":
        headers["Authorization"] = f"Bearer {API_KEY}"
    else:
        headers["x-api-key"] = API_KEY
        headers["anthropic-version"] = "2023-06-01"

    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", ENDPOINTS[UPSTREAM], headers=headers, json=body) as r:
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                raw = line[6:]
                if raw.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                piece = _extract_delta(data)
                if piece:
                    yield piece


def _extract_delta(data):
    if UPSTREAM == "openai":
        return data.get("choices", [{}])[0].get("delta", {}).get("content", "")
    if data.get("type") == "content_block_delta":
        return data.get("delta", {}).get("text", "")
    return ""
