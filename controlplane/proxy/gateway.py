import json
import re
import os
import time
import asyncio
from contextlib import asynccontextmanager

from pathlib import Path

import httpx
from fastapi import FastAPI, Request, Header
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               StreamingResponse)

from ..cost.meter import DEMO_UPSTREAM
from ..pipeline import ControlPlane
from ..tiers import tier1_classifiers
from ..streaming import StreamingVerifier
from ..telemetry import Telemetry
from ..schema import Action

UPSTREAM = os.getenv("CP_UPSTREAM", "mock")
API_KEY = os.getenv("CP_API_KEY", "")
MODEL = os.getenv("CP_MODEL", "gpt-4o-mini")
DEFAULT_USE_CASE = os.getenv("CP_DEFAULT_USE_CASE", "customer_support")

ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
}

@asynccontextmanager
async def lifespan(app):
    """Load the classifiers before serving.

    Without them grounding falls back to lexical overlap, which lands far more
    responses inside the uncertainty band - tier 2 fired on 57% of traffic
    instead of 2.8%, every one of those a paid judge call at 1.3s. A server that
    quietly does that is worse than one that takes 7s to start.

    CP_SKIP_MODELS=1 for a machine that has none; the fallback is still correct,
    just slower and dearer, and /health says which mode is live."""
    if os.getenv("CP_SKIP_MODELS"):
        print("[gateway] CP_SKIP_MODELS set; tier 1 runs on the lexical fallback")
    else:
        tier1_classifiers.load_models()
    yield


app = FastAPI(title="ControlPlane Gateway", lifespan=lifespan)
telemetry = Telemetry()
cp = ControlPlane(audit_path="audit.jsonl", listener=telemetry.record)
DASHBOARD = Path(__file__).resolve().parents[2] / "dashboard" / "index.html"


@app.get("/health")
def health():
    return {"status": "ok", "upstream": UPSTREAM, "use_cases": list(cp.policies),
            "tier1": tier1_classifiers.describe()}


@app.get("/dashboard")
def dashboard():
    return FileResponse(DASHBOARD)


@app.get("/hook")
def hook():
    """The pitch video's opening screen. Served from the gateway so the whole
    recording lives on one origin and one port."""
    return FileResponse(DASHBOARD.parent / "hook.html")


@app.get("/report")
def report():
    """The benchmark, rendered. The pitch shows this twice - the headline table
    and the weaknesses - and raw markdown on camera undersells both."""
    md = (DASHBOARD.parents[1] / "eval" / "results" / "report.md")
    if not md.exists():
        return JSONResponse({"error": "no report; run eval/run_eval.py"}, status_code=404)
    return HTMLResponse(_render_md(md.read_text()))


def _render_md(md):
    """Enough markdown for this one document: headings, tables, bold, code."""
    import html as _h
    out, rows = [], []

    def flush():
        if not rows:
            return
        head, body = rows[0], [r for r in rows[1:] if not set(r) <= set("-: ")]
        cell = lambda c, tag: f"<{tag}>{_inline(c.strip())}</{tag}>"
        out.append("<div class='sc'><table><thead><tr>"
                   + "".join(cell(c, "th") for c in head) + "</tr></thead><tbody>"
                   + "".join("<tr>" + "".join(cell(c, "td") for c in r) + "</tr>" for r in body)
                   + "</tbody></table></div>")
        rows.clear()

    def _inline(s):
        s = _h.escape(s)
        for a, b in (("**", "strong"), ("`", "code")):
            parts = s.split(a)
            s = "".join(p if i % 2 == 0 else f"<{b}>{p}</{b}>" for i, p in enumerate(parts))
        return s

    for line in md.splitlines():
        if line.strip().startswith("|"):
            rows.append([c for c in line.strip().strip("|").split("|")])
            continue
        flush()
        s = line.strip()
        if s.startswith("#"):
            n = min(len(s) - len(s.lstrip("#")), 3)
            title = s.lstrip("# ")
            # Slugged so the pitch can jump straight to a section instead of
            # scrolling for it on camera.
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            out.append(f"<h{n} id='{slug}'>{_inline(title)}</h{n}>")
        elif s.startswith("- "):
            out.append(f"<li>{_inline(s[2:])}</li>")
        elif s.startswith(">"):
            out.append(f"<blockquote>{_inline(s.lstrip('> '))}</blockquote>")
        elif s:
            out.append(f"<p>{_inline(s)}</p>")
    flush()
    return REPORT_SHELL.replace("{{body}}", "\n".join(out)).replace("{{nav}}", REPORT_NAV)


@app.get("/dashboard/stats")
def dashboard_stats():
    return {
        "snapshot": telemetry.snapshot(cp.policies),
        "queue": telemetry.queue(),
        "recent": list(telemetry.recent)[:120],
    }


@app.get("/dashboard/events")
async def dashboard_events():
    """One SSE stream per connected operator."""
    async def feed():
        q = telemetry.subscribe()
        try:
            while True:
                try:
                    row = await asyncio.wait_for(q.get(), timeout=20)
                    yield f"data: {json.dumps(row)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            telemetry.unsubscribe(q)

    return StreamingResponse(feed(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


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

    policy = cp.policies[use_case]
    upstream_start = time.perf_counter()

    def _verify(t, u):
        return cp.verify(
            t, use_case,
            retrieved_chunks=extras.get("retrieved_chunks"),
            allowed_chunk_ids=set(extras["allowed_chunk_ids"]) if extras.get("allowed_chunk_ids") else None,
            user_id=extras.get("user_id", "anon"),
            usage=u, model=extras.get("price_as", DEMO_UPSTREAM[0]),
            provider=extras.get("price_provider", DEMO_UPSTREAM[1]),
        )

    text, usage = await _call_upstream(body, extras)
    verdict = _verify(text, usage)

    # regenerate means ask the model again with what was wrong, not "deliver it
    # anyway". Without this the action was a no-op: the router ruled the answer
    # wrong and the gateway handed it over untouched.
    attempts = 0
    upstream_inr = verdict.llm_cost_inr
    budget = policy.raw.get("max_regenerations", 1)
    while verdict.action == Action.REGENERATE and attempts < budget:
        attempts += 1
        text, usage = await _call_upstream(
            body, extras, correction=_correction_turns(text, verdict, extras))
        verdict = _verify(text, usage)
        # Each attempt is a real model call. Charging only for the last one
        # would make the cheapest-looking path the one that retried most.
        upstream_inr += verdict.llm_cost_inr
    verdict.llm_cost_inr = upstream_inr

    upstream_ms = (time.perf_counter() - upstream_start) * 1000
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
            "regenerations": attempts,
            "upstream_ms": round(upstream_ms, 2),
            "overhead_pct": round(100 * verdict.latency_ms / max(upstream_ms, 1e-6), 2),
        },
    }


def _apply_action(text, verdict):
    if verdict.action == Action.BLOCK:
        return "[withheld by ControlPlane: " + verdict.reason + "]"
    if verdict.action == Action.REGENERATE:
        # Only reachable once the regeneration budget is spent. The answer is
        # still wrong, so it is not delivered - the caller gets the reason.
        return ("[withheld by ControlPlane: regeneration did not produce a "
                f"grounded answer. {verdict.reason}]")
    if verdict.action == Action.REDACT_SPAN:
        spans = sorted([s.span for s in verdict.signals if s.span], reverse=True)
        if not spans:
            # Something tripped or the router would not have chosen redaction,
            # but nothing carried a span to redact. Delivering the text
            # unchanged would silently turn the strictest available edit into a
            # pass, so withhold instead.
            return ("[withheld by ControlPlane: flagged for redaction but the "
                    f"span could not be located. {verdict.reason}]")
        out = text
        for start, end in spans:
            out = out[:start] + "[redacted]" + out[end:]
        return out
    if verdict.action == Action.ANNOTATE:
        return text + f"\n\n[ControlPlane: {verdict.reason}]"
    if verdict.action == Action.ESCALATE:
        return text + "\n\n[flagged for human review before this is acted on]"
    return text


CORRECTION = """Your previous answer was rejected by a verification layer.

REJECTED ANSWER:
{answer}

WHY: {reason}
{claims}
SOURCES — every claim you make must be supported by these:
{sources}

Rewrite the answer using only what the sources support. Do not restate the
rejected claim. If the sources do not answer the question, say so plainly
rather than filling the gap."""


def _correction_turns(text, verdict, extras):
    """The retry prompt.

    Re-sending the original request unchanged is not a regeneration - same
    prompt, same model, most likely the same wrong answer. The model is told
    what was rejected, which spans were unsupported, and what the sources
    actually say."""
    flagged = [text[s.span[0]:s.span[1]] for s in verdict.signals
               if s.span and s.score >= 0.5][:4]
    claims = ("\nUNSUPPORTED:\n" + "\n".join(f"- {c}" for c in flagged) + "\n") if flagged else ""
    sources = "\n".join(f"[{c.get('id', i)}] {c.get('text','')}"
                        for i, c in enumerate(extras.get("retrieved_chunks") or [])) or "(none)"
    return [
        {"role": "assistant", "content": text},
        {"role": "user", "content": CORRECTION.format(
            answer=text, reason=verdict.reason, claims=claims, sources=sources)},
    ]


async def _call_upstream(body, extras=None, correction=None):
    """correction is the extra turns a regeneration adds. Passing them is the
    whole difference between asking again and asking better."""
    payload = dict(body)
    if correction:
        payload["messages"] = list(payload.get("messages", [])) + correction

    if UPSTREAM == "mock":
        await asyncio.sleep(0.05)
        # A caller replaying a fixture supplies the response it wants checked.
        # Without this the mock answers everything with the same sentence and
        # the dashboard shows one verdict repeated.
        canned = (extras or {}).get("mock_response")
        if canned and not correction:
            return canned, {"prompt_tokens": 820, "completion_tokens": 95}
        msgs = payload.get("messages", [])
        last = msgs[-1]["content"] if msgs else ""
        return _mock_reply(last, extras), {"prompt_tokens": 820, "completion_tokens": 95}

    headers = {"Content-Type": "application/json"}
    if UPSTREAM == "openai":
        headers["Authorization"] = f"Bearer {API_KEY}"
    else:
        headers["x-api-key"] = API_KEY
        headers["anthropic-version"] = "2023-06-01"

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(ENDPOINTS[UPSTREAM], headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    if UPSTREAM == "openai":
        return data["choices"][0]["message"]["content"], data.get("usage", {})
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    return "".join(parts), data.get("usage", {})



# The two sections the pitch cuts to, plus the honesty section they sit inside.
# Fixed to the corner so a jump is one click mid-take rather than a scroll.
REPORT_NAV = ("<nav class=jump>"
              "<a href='#headline'>headline</a>"
              "<a href='#by-case-type-cascade'>what it gets wrong</a>"
              "<a href='#reading-this-honestly'>caveats</a>"
              "<a href='#latency-against-the-policy-budget'>latency</a>"
              "</nav>")

REPORT_SHELL = """<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>ControlPlane evaluation</title>
<link rel=preconnect href="https://fonts.googleapis.com">
<link rel=preconnect href="https://fonts.gstatic.com" crossorigin>
<link rel=stylesheet href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{--ground:#F7F8FA;--surface:#fff;--raised:#EEF1F5;--ink:#16202B;--body:#2E3C49;
 --muted:#5C6B7A;--faint:#8A97A3;--rule:#DCE2E8;--strong:#C3CDD6;--accent:#0E7C86;--soft:#E2F1F2}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--ground:#0E1519;
 --surface:#16202B;--raised:#1D2A36;--ink:#E7EDF1;--body:#C3CFD8;--muted:#8FA0AD;
 --faint:#6B7B88;--rule:#26333F;--strong:#374654;--accent:#45B3BD;--soft:#123238}}
:root[data-theme=dark]{--ground:#0E1519;--surface:#16202B;--raised:#1D2A36;--ink:#E7EDF1;
 --body:#C3CFD8;--muted:#8FA0AD;--faint:#6B7B88;--rule:#26333F;--strong:#374654;
 --accent:#45B3BD;--soft:#123238}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--body);
 font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:14px;line-height:1.6}
.w{max-width:900px;margin:0 auto;padding:36px 24px 80px}
h1{font-family:Archivo,system-ui,sans-serif;font-size:28px;font-weight:700;color:var(--ink);
 letter-spacing:-.02em;margin:0 0 18px;padding-bottom:14px;border-bottom:2px solid var(--ink)}
h2{font-family:Archivo,system-ui,sans-serif;font-size:17px;font-weight:600;color:var(--ink);
 margin:38px 0 12px;padding-top:16px;border-top:1px solid var(--strong)}
h3{font-family:Archivo,system-ui,sans-serif;font-size:14px;font-weight:600;color:var(--ink);margin:24px 0 8px}
p{margin:0 0 12px;max-width:74ch}
li{margin:0 0 8px;max-width:74ch;margin-left:20px}
blockquote{margin:14px 0;padding:10px 16px;border-left:3px solid var(--accent);
 background:var(--surface);color:var(--muted);border-radius:0 4px 4px 0}
strong{color:var(--ink);font-weight:600}
code{background:var(--raised);padding:1px 5px;border-radius:3px;font-size:13px}
.sc{overflow-x:auto;margin:0 0 20px;border:1px solid var(--rule);border-radius:5px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;
 color:var(--muted);padding:10px 14px;background:var(--raised);
 border-bottom:1px solid var(--strong);white-space:nowrap}
td{padding:10px 14px;border-bottom:1px solid var(--rule);font-variant-numeric:tabular-nums;
 vertical-align:top}
tr:last-child td{border-bottom:none}
tr:has(strong) td{background:var(--soft)}
.jump{position:fixed;top:14px;right:16px;display:flex;gap:4px;flex-wrap:wrap;
 background:var(--surface);border:1px solid var(--rule);border-radius:5px;padding:5px;
 box-shadow:0 1px 3px rgba(0,0,0,.06);z-index:5}
.jump a{font-size:10.5px;letter-spacing:.03em;color:var(--muted);text-decoration:none;
 padding:4px 8px;border-radius:3px}
.jump a:hover{background:var(--raised);color:var(--ink)}
h1,h2,h3{scroll-margin-top:64px}
@media (max-width:820px){.jump{display:none}}
</style></head><body>{{nav}}<div class=w>{{body}}</div></body></html>"""

MOCK_REPLIES = {
    "room rent": "Room rent capping is 2 percent, so approximately 185000 rupees will be reimbursed.",
    "contact": "Your registered contact is 9876543210 and PAN ABCDE1234F.",
}


def _mock_reply(prompt, extras=None):
    """The mock answers a correction the way a cooperative model would: from
    the sources it was handed. It is not given a canned "good answer" for the
    retry - that would make the demo pass on a path the real one fails."""
    if "rejected by a verification layer" in prompt:
        chunks = (extras or {}).get("retrieved_chunks") or []
        return chunks[0].get("text", "") if chunks else (
            "I could not find that detail in the documents provided.")
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
    telemetry.record(verdict)

    # Buffered mode held the bad text back, so there is still something to
    # regenerate into. Streaming mode already delivered it and cannot.
    attempts = 0
    budget = cp.policies[use_case].raw.get("max_regenerations", 1)
    while (verifier.mode == "buffered" and verdict.action == Action.REGENERATE
           and attempts < budget):
        attempts += 1
        yield _sse({"controlplane": {"type": "regenerating", "attempt": attempts}})
        text, _ = await _call_upstream(
            body, extras, correction=_correction_turns(verifier.buffer, verdict, extras))

        retry = StreamingVerifier(
            cp, use_case,
            retrieved_chunks=extras.get("retrieved_chunks"),
            allowed_chunk_ids=set(extras["allowed_chunk_ids"]) if extras.get("allowed_chunk_ids") else None,
            user_id=extras.get("user_id", "anon"),
        )
        for word in text.split(" "):
            await retry.feed(word + " ")
        step = await retry.close()
        verifier, verdict = retry, retry.verdict
        cp.audit.append(verdict.to_record(), policy_version=cp.policies[use_case].version)
        telemetry.record(verdict)
        if step.release:
            yield _sse({"choices": [{"delta": {"content": step.release}, "index": 0}]})

    # A buffered stream that withheld the tail leaves the caller with a partial
    # answer and no explanation. Say what happened in the body, not only in the
    # metadata, because a client rendering deltas will never look at the latter.
    if verifier.withheld:
        yield _sse({"choices": [{"delta": {"content":
                    f"\n\n[withheld by ControlPlane: {verdict.reason}]"}, "index": 0}]})

    # In streaming mode the caller has already seen the text, so a late verdict
    # is a correction rather than a gate. Say which it was.
    yield _sse({"controlplane": {
        "type": "verdict",
        "applied": verdict.action.value if verifier.mode == "buffered" else "advisory",
        "regenerations": attempts,
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
