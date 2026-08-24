import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane
from controlplane.schema import Action, Category
from controlplane.text import sentences
from controlplane.tiers import tier1_classifiers as t1
from controlplane.tiers import tier2_judge as t2

CHUNKS = [
    {"id": "pol-1", "text": "Room rent capping under this policy is 1 percent of sum insured per day."},
    {"id": "pol-2", "text": "Cashless treatment is available at network hospitals only."},
]


@pytest.fixture
def cp(tmp_path):
    return ControlPlane(audit_path=str(tmp_path / "audit.jsonl"))


def verify(cp, text, use_case="customer_support", **kw):
    return cp.verify(text, use_case, retrieved_chunks=CHUNKS, **kw)


# --- spans --------------------------------------------------------------

def test_sentence_spans_index_back_into_the_original():
    text = "First claim here. Second claim follows!  Third one?"
    for s in sentences(text):
        assert text[s.start:s.end] == s.text


def test_redact_span_covers_the_offending_claim(cp):
    text = "Room rent capping is 2 percent of sum insured per day."
    v = verify(cp, text)
    spans = [s.span for s in v.signals if s.category == Category.GROUNDING]
    assert spans and all(sp is not None for sp in spans)
    assert any(text[a:b].strip() for a, b in spans)


# --- policy drives behaviour -------------------------------------------

def test_same_input_different_verdict_per_policy(cp):
    text = "Room rent capping is 2 percent, so 185000 rupees will be reimbursed."
    actions = {uc: verify(cp, text, use_case=uc).action for uc in cp.policies}
    assert len(set(actions.values())) > 1, actions


def test_decision_support_blocks_acl_breach(cp):
    v = cp.verify(CHUNKS[1]["text"], "decision_support",
                  retrieved_chunks=CHUNKS, allowed_chunk_ids={"pol-1"})
    assert v.action == Action.BLOCK
    assert any(t["category"] == "acl" for t in v.triggered)


# --- multi-label --------------------------------------------------------

def test_pii_and_grounding_both_recorded(cp):
    v = verify(cp, "Ms Sharma at 9876543210 is owed 185000 rupees under clause 7B.")
    cats = {t["category"] for t in v.triggered}
    assert "pii" in cats and "grounding" in cats


def test_router_takes_the_most_severe_action(cp):
    v = verify(cp, "Your PAN is ABCDE1234F and the cap is 2 percent.")
    assert v.action == Action.BLOCK  # pii blocks; grounding alone would redact


# --- grounding fallback -------------------------------------------------

def test_number_swap_is_not_grounded():
    premise = CHUNKS[0]["text"]
    assert t1._stub_grounding("Room rent capping is 2 percent of sum insured per day.",
                              premise) > 0.5


def test_faithful_restatement_is_grounded():
    premise = CHUNKS[0]["text"]
    assert t1._stub_grounding(CHUNKS[0]["text"], premise) < 0.2


def test_grounding_keeps_the_best_chunk_not_the_average(monkeypatch):
    """A claim is grounded if any one source supports it. Scoring against every
    source glued together is what made faithful answers look unsupported."""
    from controlplane.schema import RequestContext

    seen = {}

    def fake(pairs):
        seen["pairs"] = pairs
        # supported by the second chunk only
        return [0.95 if "Room rent" in premise else 0.02 for premise, _ in pairs]

    monkeypatch.setitem(t1._state, "score_pairs", fake)
    ctx = RequestContext(request_id="t", use_case="customer_support",
                         retrieved_chunks=CHUNKS)
    from controlplane.text import sentences
    sents = sentences("Cashless treatment is at network hospitals.")

    scores = t1._grounding_scores(sents, ctx, combine=False)
    assert len(seen["pairs"]) == 2  # one per chunk, not one joined premise
    assert scores == [0.02]

    scores = t1._grounding_scores(sents, ctx, combine=True)
    assert len(seen["pairs"]) == 3  # chunks plus the joined premise
    assert scores == [0.02]


def test_combine_sources_is_a_policy_value(cp):
    """The joined premise halves false positives and doubles latency, so the
    tight-latency policy declines it and the slow one takes it."""
    tiers = {n: p.tiers["tier1"].get("combine_sources") for n, p in cp.policies.items()}
    assert tiers["customer_support"] is False
    assert tiers["decision_support"] is True


def test_abstention_is_not_scored_as_ungrounded(cp):
    v = verify(cp, "I could not find that detail in the policy documents provided.")
    assert v.action == Action.PASS, v.reason


# --- bias ---------------------------------------------------------------

def test_bias_needs_a_decision_not_just_an_attribute():
    benign, _ = t1._bias_score("Maternity cover is available to pregnant members.")
    harmful, _ = t1._bias_score("The claim was denied because married women file more claims.")
    assert benign < 0.5 < harmful


# --- offline judge ------------------------------------------------------

def test_offline_judge_catches_a_changed_number():
    score, reason = t2._offline_judge("The cap is 2 percent per day.", CHUNKS[0]["text"])
    assert score > 0.8 and "2" in reason


def test_offline_judge_accepts_a_restatement():
    score, _ = t2._offline_judge(CHUNKS[0]["text"], CHUNKS[0]["text"])
    assert score < 0.2


# --- cost ---------------------------------------------------------------

def test_verification_cost_excludes_the_upstream_call(cp):
    v = verify(cp, "Room rent capping is 2 percent per day.",
               usage={"prompt_tokens": 800, "completion_tokens": 100},
               model="claude-sonnet-5")
    assert v.llm_cost_inr > 0
    labels = [l["label"] for l in v.cost_detail["lines"]]
    assert "llm_response" in labels
    assert v.verification_cost_inr < v.llm_cost_inr


def test_unknown_model_does_not_invent_a_price():
    from controlplane.cost.meter import CostMeter
    with pytest.raises(KeyError):
        CostMeter().llm_call("anthropic", "no-such-model", 100, 100)


def test_modelled_judge_cost_is_flagged_unverified(cp):
    # Scores 0.667, inside customer_support's [0.25, 0.75] band, so tier 2 runs.
    v = verify(cp, "Cashless treatment requires prior authorisation from the insurer.")
    assert 2 in v.tiers_run, v.tiers_run
    judge = [l for l in v.cost_detail["lines"] if l["label"] == "tier2_judge"]
    assert judge, v.cost_detail
    assert all(l["method"] == "modelled" and not l["verified"] for l in judge)


@pytest.mark.live
def test_live_judge_catches_a_changed_number(cp):
    """The offline judge and the real one have to agree on the obvious case,
    or the offline fallback is not a fallback."""
    v = verify(cp, "Cashless treatment requires prior authorisation from the insurer.")
    assert 2 in v.tiers_run, v.tiers_run
    judge = [l for l in v.cost_detail["lines"] if l["label"] == "tier2_judge"]
    assert judge and all(l["method"] == "reported" and l["verified"] for l in judge)
    assert any(s.tier == 2 for s in v.signals)


def test_confident_detection_skips_the_judge(cp):
    """The point of the band: a claim tier 1 is sure about does not get paid for
    twice."""
    v = verify(cp, "Room rent capping is 2 percent of sum insured per day.")
    assert 2 not in v.tiers_run
    assert not [l for l in v.cost_detail["lines"] if l["label"] == "tier2_judge"]


# --- audit --------------------------------------------------------------

def test_audit_chain_detects_tampering(cp):
    for i in range(5):
        verify(cp, f"Statement number {i} about the cap.")
    assert cp.audit.verify() == (True, None)

    path = Path(cp.audit.path)
    lines = path.read_text().splitlines()
    lines[2] = lines[2].replace('"action"', '"actioN"', 1)
    path.write_text("\n".join(lines) + "\n")

    ok, line = cp.audit.verify()
    assert ok is False and line == 3


def test_audit_records_the_policy_version(cp):
    import json
    verify(cp, "Room rent capping is 1 percent of sum insured per day.")
    entry = json.loads(Path(cp.audit.path).read_text().splitlines()[-1])
    assert entry["policy_version"] == cp.policies["customer_support"].version
