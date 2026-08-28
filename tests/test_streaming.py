import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane
from controlplane.schema import Action
from controlplane.streaming import StreamingVerifier

CHUNKS = [
    {"id": "pol-1", "text": "Room rent capping under this policy is 1 percent of sum insured per day."},
    {"id": "pol-2", "text": "Cashless treatment is available at network hospitals only."},
]

CLEAN = ("Room rent capping under this policy is 1 percent of sum insured per day. "
         "Cashless treatment is available at network hospitals only.")

DIRTY = ("Room rent capping under this policy is 1 percent of sum insured per day. "
         "Room rent capping is 2 percent, so 185000 rupees will be reimbursed.")


@pytest.fixture
def cp(tmp_path):
    return ControlPlane(audit_path=str(tmp_path / "audit.jsonl"))


async def drive(v, text):
    """Feed the text the way a model streams it: one word at a time, each
    carrying its trailing space."""
    released = []
    for word in text.split(" "):
        step = await v.feed(word + " ")
        released.append(step.release)
    step = await v.close()
    released.append(step.release)
    return "".join(released)


@pytest.mark.asyncio
async def test_a_partial_sentence_is_not_checked(cp):
    """Tokens arrive as "word ", so a naive completeness test treats the first
    word of every sentence as a finished sentence."""
    v = StreamingVerifier(cp, "customer_support", retrieved_chunks=CHUNKS)
    for word in "Room rent capping under".split(" "):
        await v.feed(word + " ")
    assert v.dispatched == []

    for word in "this policy is 1 percent of sum insured per day.".split(" "):
        await v.feed(word + " ")
    assert len(v.dispatched) == 1
    assert v.dispatched[0].text.endswith("per day.")


@pytest.mark.asyncio
async def test_streaming_verdict_matches_post_hoc(cp):
    v = StreamingVerifier(cp, "customer_support", retrieved_chunks=CHUNKS)
    await drive(v, DIRTY)
    post = cp.verify(DIRTY, "customer_support", retrieved_chunks=CHUNKS)
    assert v.verdict.action == post.action


@pytest.mark.asyncio
async def test_nothing_is_lost_or_duplicated(cp):
    for use_case in ("customer_support", "internal_copilot"):
        v = StreamingVerifier(cp, use_case, retrieved_chunks=CHUNKS)
        out = await drive(v, CLEAN)
        assert out.strip() == CLEAN.strip(), use_case


@pytest.mark.asyncio
async def test_buffered_does_not_deliver_what_it_flagged(cp):
    """The failure this mode exists to prevent: the verdict says regenerate and
    the caller has already been shown the sentence it was about."""
    v = StreamingVerifier(cp, "customer_support", retrieved_chunks=CHUNKS)
    out = await drive(v, DIRTY)
    assert v.verdict.action != Action.PASS
    assert "2 percent" not in out
    assert "1 percent" in out          # the good sentence still went out


@pytest.mark.asyncio
async def test_streaming_mode_admits_it_already_delivered(cp):
    """The other half of the contract. streaming releases immediately, so a late
    verdict is a correction - and the text is out. Pretending otherwise would be
    the lie the gateway's `advisory` label exists to avoid."""
    v = StreamingVerifier(cp, "internal_copilot", retrieved_chunks=CHUNKS)
    out = await drive(v, DIRTY)
    assert "2 percent" in out
    assert v.withheld == ""


@pytest.mark.asyncio
async def test_a_blocked_response_withholds_everything_after_the_trip(cp):
    v = StreamingVerifier(cp, "customer_support", retrieved_chunks=CHUNKS)
    out = await drive(v, "Your PAN is ABCDE1234F and the cap is 2 percent.")
    assert v.verdict.action == Action.BLOCK
    assert "ABCDE1234F" not in out
    assert v.withheld


@pytest.mark.asyncio
async def test_spans_point_into_the_whole_response(cp):
    v = StreamingVerifier(cp, "customer_support", retrieved_chunks=CHUNKS)
    await drive(v, DIRTY)
    spans = [s.span for s in v.verdict.signals if s.span]
    assert spans
    for start, end in spans:
        assert DIRTY[start:end].strip(), (start, end)
        # the offending claim, not the first sentence
        assert "2 percent" in DIRTY[start:end] or start > 0


@pytest.mark.asyncio
async def test_buffered_holds_until_the_check_lands(cp):
    """customer_support is buffered: nothing goes out ahead of its verdict."""
    v = StreamingVerifier(cp, "customer_support", retrieved_chunks=CHUNKS)
    assert v.mode == "buffered"
    early = []
    for word in DIRTY.split(" ")[:8]:
        early.append((await v.feed(word + " ")).release)
    # a whole sentence has not finished yet, so nothing is cleared
    assert "".join(early) == ""
    await v.close()


@pytest.mark.asyncio
async def test_streaming_mode_releases_immediately(cp):
    v = StreamingVerifier(cp, "internal_copilot", retrieved_chunks=CHUNKS)
    assert v.mode == "streaming"
    step = await v.feed("Room ")
    assert step.release == "Room "
    await v.close()


@pytest.mark.asyncio
async def test_lag_after_last_token_is_recorded(cp):
    v = StreamingVerifier(cp, "customer_support", retrieved_chunks=CHUNKS)
    await drive(v, CLEAN)
    stream = v.verdict.cost_detail["stream"]
    assert stream["sentences"] == 2
    assert len(stream["sentence_checks_ms"]) == 2
    assert stream["lag_after_last_token_ms"] >= 0
