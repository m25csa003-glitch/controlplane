"""The gateway is where a verdict becomes something the caller actually sees.

Every test here exists because a verdict was correct and the delivery was not.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.proxy import gateway
from controlplane.schema import Action, Verdict

CHUNKS = [
    {"id": "pol-1", "text": "Room rent capping under this policy is 1 percent of sum insured per day."},
]
PII = "Your registered contact is 9876543210 and PAN ABCDE1234F."
HALLUCINATION = "Room rent capping is 2 percent, so 185000 rupees will be reimbursed."


async def post(uc, prompt, stream=False, chunks=CHUNKS):
    """Drive the endpoint directly, without a server."""
    body = {"model": "mock", "stream": stream,
            "messages": [{"role": "user", "content": prompt}],
            "controlplane": {"retrieved_chunks": chunks}}

    class Req:
        async def json(self):
            return dict(body)

    resp = await gateway.chat_completions(Req(), x_controlplane_use_case=uc)
    if not stream:
        return resp["choices"][0]["message"]["content"], resp["controlplane"]

    import json as _json
    text, meta = "", {}
    async for line in resp.body_iterator:
        if not line.startswith("data: "):
            continue
        raw = line[6:].strip()
        if raw == "[DONE]":
            break
        d = _json.loads(raw)
        if "choices" in d:
            text += d["choices"][0]["delta"].get("content", "")
        elif d.get("controlplane", {}).get("type") == "verdict":
            meta = d["controlplane"]
    return text, meta


# --- every action does something ----------------------------------------

def test_every_action_is_implemented():
    """regenerate used to fall through to `return text`, so the router could
    rule an answer wrong and the gateway would hand it over untouched. The
    headline demo case is a hallucination routed to regenerate."""
    v = Verdict(request_id="t", use_case="customer_support",
                action=Action.PASS, reason="because")
    for action in Action:
        v.action = action
        out = gateway._apply_action("original text", v)
        if action == Action.PASS:
            assert out == "original text"
        else:
            assert out != "original text", f"{action.value} is a no-op"


# --- streaming must not deliver what it blocked -------------------------

@pytest.mark.asyncio
async def test_buffered_stream_does_not_deliver_blocked_pii():
    """The failure this whole mode exists to prevent: the caller reads the PAN
    number and then receives a message saying it was blocked."""
    text, meta = await post("customer_support", "contact", stream=True)
    assert meta["applied"] == "block"
    assert "9876543210" not in text
    assert "ABCDE1234F" not in text


@pytest.mark.asyncio
async def test_batch_and_stream_agree_on_what_reaches_the_caller():
    for uc in ("customer_support", "decision_support"):
        batch, _ = await post(uc, "contact")
        streamed, _ = await post(uc, "contact", stream=True)
        for secret in ("9876543210", "ABCDE1234F"):
            assert secret not in batch, uc
            assert secret not in streamed, uc


@pytest.mark.asyncio
async def test_a_withheld_stream_explains_itself():
    """A client rendering deltas never looks at the trailing metadata, so an
    empty body is indistinguishable from a broken connection."""
    text, _ = await post("customer_support", "contact", stream=True)
    assert "withheld by ControlPlane" in text


# --- regenerate actually regenerates ------------------------------------

@pytest.mark.asyncio
async def test_regenerate_retries_and_delivers_the_better_answer():
    text, meta = await post("customer_support", "room rent")
    assert meta["regenerations"] >= 1
    assert "2 percent" not in text
    assert meta["action"] != Action.REGENERATE.value


@pytest.mark.asyncio
async def test_a_buffered_stream_regenerates_too():
    """Buffered held the bad text back, so there is still something to
    regenerate into. If only the batch path retried, the same request would
    return a good answer or a withheld one depending on a flag the caller set
    for unrelated reasons."""
    streamed, smeta = await post("customer_support", "room rent", stream=True)
    batch, bmeta = await post("customer_support", "room rent")
    assert smeta["regenerations"] == bmeta["regenerations"] >= 1
    assert "2 percent" not in streamed
    assert streamed.strip() == batch.strip()


@pytest.mark.asyncio
async def test_streaming_mode_cannot_regenerate_and_does_not_pretend_to():
    """internal_copilot streams tokens as they arrive, so by the time the
    verdict exists the answer is on the caller's screen. There is nothing left
    to replace."""
    text, meta = await post("internal_copilot", "room rent", stream=True)
    assert meta["regenerations"] == 0
    assert meta["applied"] == "advisory"


@pytest.mark.asyncio
async def test_the_retry_tells_the_model_what_was_wrong(monkeypatch):
    """Re-sending the original request unchanged is not a regeneration - same
    prompt, same model, most likely the same answer. The retry has to carry the
    rejection, the unsupported claim and the sources."""
    seen = []
    real = gateway._call_upstream

    async def spy(body, extras=None, correction=None):
        seen.append(correction)
        return await real(body, extras, correction)

    monkeypatch.setattr(gateway, "_call_upstream", spy)
    await post("customer_support", "room rent")

    assert seen[0] is None                       # first call is the plain request
    assert seen[1], "the retry sent no correction"
    prompt = seen[1][-1]["content"]
    assert "rejected by a verification layer" in prompt
    assert "2 percent" in prompt                 # the claim that was rejected
    assert "1 percent" in prompt                 # what the sources actually say


@pytest.mark.asyncio
async def test_regeneration_budget_is_finite(monkeypatch):
    """A model that will not correct itself must not exhaust the loop, and its
    answer must not be delivered anyway."""
    monkeypatch.setattr(gateway, "_mock_reply", lambda p, e=None: HALLUCINATION)
    text, meta = await post("customer_support", "room rent")
    budget = gateway.cp.policies["customer_support"].raw.get("max_regenerations", 1)
    assert meta["regenerations"] == budget
    assert meta["action"] == Action.REGENERATE.value
    assert "2 percent" not in text
    assert "withheld by ControlPlane" in text


@pytest.mark.asyncio
async def test_every_regeneration_is_charged_for(monkeypatch):
    """A retry is a second model call. Charging only for the last one would make
    the path that retried most look like the cheapest."""
    one, _ = await post("customer_support", "cashless")       # no retry
    monkeypatch.setattr(gateway, "_mock_reply", lambda p, e=None: HALLUCINATION)
    retried, meta = await post("customer_support", "room rent")
    assert meta["regenerations"] >= 1
    assert meta["llm_cost_inr"] > 0


# --- the cost column ----------------------------------------------------

def test_a_model_is_priced_against_its_own_provider():
    """The eval asked Anthropic what an OpenAI model costs. The lookup failed,
    the cost silently became zero, and the report's money column read 0.000%."""
    from controlplane.cost.meter import CostMeter, DEMO_UPSTREAM
    model, provider = DEMO_UPSTREAM
    line = CostMeter().llm_call(provider, model, 820, 95)
    assert line.inr > 0 and line.verified


def test_an_unpriced_call_is_recorded_not_silently_zeroed(tmp_path):
    from controlplane.pipeline import ControlPlane
    cp = ControlPlane(audit_path=str(tmp_path / "a.jsonl"))
    v = cp.verify("Room rent capping is 1 percent of sum insured per day.",
                  "customer_support", retrieved_chunks=CHUNKS,
                  usage={"prompt_tokens": 800, "completion_tokens": 90},
                  model="no-such-model", provider="openai")
    lines = [l for l in v.cost_detail["lines"] if l["label"] == "llm_response"]
    assert lines and lines[0]["method"] == "unpriced"
    assert v.cost_detail["verified"] is False
