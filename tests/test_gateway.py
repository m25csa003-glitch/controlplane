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
async def test_regeneration_budget_is_finite(monkeypatch):
    """If the model keeps producing the same wrong answer, the loop has to stop
    and the answer must not be delivered anyway."""
    monkeypatch.setattr(gateway, "REGENERATED", HALLUCINATION)
    text, meta = await post("customer_support", "room rent")
    budget = gateway.cp.policies["customer_support"].raw.get("max_regenerations", 1)
    assert meta["regenerations"] == budget
    assert meta["action"] == Action.REGENERATE.value
    assert "2 percent" not in text
    assert "withheld by ControlPlane" in text


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
