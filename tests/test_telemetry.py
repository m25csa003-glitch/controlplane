import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane
from controlplane.telemetry import Telemetry

CHUNKS = [
    {"id": "pol-1", "text": "Room rent capping under this policy is 1 percent of sum insured per day."},
]


@pytest.fixture
def plane(tmp_path):
    t = Telemetry()
    cp = ControlPlane(audit_path=str(tmp_path / "audit.jsonl"), listener=t.record)
    return cp, t


def test_verdicts_reach_the_dashboard(plane):
    cp, t = plane
    cp.verify("Room rent capping is 2 percent per day.", "customer_support",
              retrieved_chunks=CHUNKS)
    assert len(t.recent) == 1
    assert t.recent[0]["use_case"] == "customer_support"
    assert t.recent[0]["action"] != "pass"


def test_snapshot_compares_against_the_policy_budget(plane):
    cp, t = plane
    for _ in range(3):
        cp.verify("Room rent capping is 2 percent per day.", "customer_support",
                  retrieved_chunks=CHUNKS)
    snap = t.snapshot(cp.policies)["use_cases"]["customer_support"]
    assert snap["n"] == 3
    assert snap["latency_budget_ms"] == 300
    assert snap["max_escalation_rate"] == 0.05
    assert 0.0 <= snap["escalation_rate"] <= 1.0


def test_queue_holds_only_what_a_reviewer_would_see(plane):
    cp, t = plane
    cp.verify("Room rent capping under this policy is 1 percent of sum insured per day.",
              "customer_support", retrieved_chunks=CHUNKS)          # passes
    cp.verify("Your PAN is ABCDE1234F.", "customer_support", retrieved_chunks=CHUNKS)
    assert all(r["action"] in ("escalate", "block") for r in t.queue())


def test_a_stalled_subscriber_is_dropped_not_waited_on(plane):
    """A dashboard that cannot keep up must not back-pressure the request path."""
    cp, t = plane
    q = t.subscribe(maxsize=1)
    for _ in range(4):
        cp.verify("Room rent capping is 2 percent per day.", "customer_support",
                  retrieved_chunks=CHUNKS)
    assert q not in t.subscribers
    assert len(t.recent) == 4        # verification carried on regardless


def test_listener_failure_is_not_silently_swallowed(plane):
    """If the dashboard hook raises, that is a bug worth seeing - not something
    to hide behind a bare except that also hides real errors."""
    cp, _ = plane
    cp.listener = lambda v: (_ for _ in ()).throw(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        cp.verify("Room rent capping is 2 percent per day.", "customer_support",
                  retrieved_chunks=CHUNKS)


def test_the_queue_is_priced_at_the_policy_rate(plane):
    """The dashboard showed what verification cost and never what it asked a
    human to do - the larger number by orders of magnitude, and the one the
    product exists to move."""
    cp, t = plane
    for _ in range(4):
        cp.verify("Your PAN is ABCDE1234F.", "customer_support",
                  retrieved_chunks=CHUNKS)
    snap = t.snapshot(cp.policies)["use_cases"]["customer_support"]
    rate = cp.policies["customer_support"].costs["cost_of_human_review"]
    assert snap["review_rate_inr"] == rate
    assert snap["review_inr"] == 4 * rate
    assert snap["review_inr"] > snap["verify_inr"]
