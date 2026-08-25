"""The loop closing: flagged cases come back as labels, labels move thresholds.

    python3 demo/run_feedback.py            lexical tier 1
    python3 demo/run_feedback.py --models   real tier 1 models

Runs the eval set, has a reviewer label every case the system acted on, then
asks what threshold those labels imply. The labels are the eval set's own
ground truth, standing in for a human queue - stated plainly because a
simulated reviewer who is always right is not a real one.
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane
from controlplane.feedback.store import FeedbackStore
from controlplane.feedback.tune import recommend_all, as_policy_patch
from controlplane.tiers import tier1_classifiers

DATASET = Path(__file__).resolve().parents[1] / "eval" / "datasets" / "controlplane_eval_v1.jsonl"
FEEDBACK = Path(__file__).resolve().parent / "feedback.jsonl"


def main():
    if "--models" in sys.argv:
        print("loading tier 1 models ...", flush=True)
        tier1_classifiers.load_models()
    print(f"tier 1: {tier1_classifiers.describe()}\n")

    if not DATASET.exists():
        sys.exit("dataset missing. Run: python3 eval/build_dataset.py")
    cases = [json.loads(l) for l in DATASET.open() if l.strip()]

    cp = ControlPlane(audit_path="demo/audit_feedback.jsonl")
    FEEDBACK.unlink(missing_ok=True)
    store = FeedbackStore(FEEDBACK, audit=cp.audit)

    rng = random.Random(7)
    flagged = sampled = 0
    for c in cases:
        v = cp.verify(c["response"], c["use_case"], retrieved_chunks=c["chunks"],
                      allowed_chunk_ids=set(c["allowed_chunk_ids"]) if c["allowed_chunk_ids"] else None)
        label = "harmful" if c["should_flag"] else "clean"

        if v.action.value != "pass":
            store.record(v, label, reviewer="demo", note=c["kind"])
            flagged += 1
            continue

        # A reviewer would only ever see what was flagged, and fitting a
        # threshold to that says "flag everything" every time - on that evidence
        # passing is never observed to be safe. So a slice of what passed goes
        # to review too. It is the only way the loop learns what it let through.
        rate = cp.policies[c["use_case"]].raw.get("audit", {}).get("audit_sample_rate", 0.0)
        if rng.random() < rate:
            store.record(v, label, reviewer="demo-audit-sample",
                         note=f"sampled:{c['kind']}", weight=1.0 / rate)
            sampled += 1

    total = flagged + sampled
    print(f"{len(cases)} responses verified\n"
          f"  {flagged} flagged and reviewed\n"
          f"  {sampled} passed but sampled for review\n"
          f"  {total} reviewed in total ({total / len(cases):.0%})\n")

    for name, rec in recommend_all(store, cp.policies).items():
        policy = cp.policies[name]
        print(f"=== {name} ===")
        if rec["status"] == "insufficient":
            print(f"  only {rec['records']} reviewed cases, need {rec['needed']}. "
                  "No recommendation.\n")
            continue
        if rec["status"] == "censored":
            print(f"  {rec['records']} reviewed, but only {rec['below_threshold']} "
                  f"scored below the current {rec['current_threshold']:.2f} "
                  f"(need {rec['needed_below']}).")
            print(f"  Refusing to recommend: with no evidence about what was passed, "
                  f"the sweep can only say 'flag everything'.")
            print(f"  audit_sample_rate is {rec['sample_rate']}; raise it or wait "
                  f"for more traffic.\n")
            continue

        print(f"  reviewed             {rec['records']} "
              f"({rec['reviewed_flagged']} flagged, {rec['reviewed_sampled']} sampled)")
        print(f"  at current {rec['current_threshold']:.2f}      "
              f"Rs {rec['current_cost_inr']:>10,.0f}   "
              f"({rec['missed_at_current']} missed, {rec['false_alarms_at_current']} false alarms)")
        print(f"  at suggested {rec['recommended_threshold']:.2f}    "
              f"Rs {rec['recommended_cost_inr']:>10,.0f}")
        print(f"  escalation rate      {rec['escalation_rate_now']:.1%} now -> "
              f"{rec['escalation_rate_recommended']:.1%}   "
              f"(policy cap {rec['max_escalation_rate']:.0%})")
        if rec["escalation_rate_now"] > (rec["max_escalation_rate"] or 1):
            print(f"  OVER CAPACITY: this policy escalates "
                  f"{rec['escalation_rate_now']:.1%} against its own "
                  f"{rec['max_escalation_rate']:.0%} cap. Either the queue needs "
                  f"more reviewers or the policy accepts more risk - a business "
                  f"decision, not a threshold this tool should quietly move.")
        if rec["capacity_bound"]:
            print("  bound by review capacity, not by cost: without the cap the "
                  "economics say review nearly everything")
        if rec["saving_inr"] > 0:
            print(f"  saving               Rs {rec['saving_inr']:>10,.0f}  "
                  f"({rec['saving_pct']}%)")
            print(f"  policy patch         {as_policy_patch(rec)['tiers']['tier1']}")
        else:
            print("  current threshold is already the cheapest on this evidence")
        print(f"  wrong={policy.costs['cost_of_being_wrong']} "
              f"review={policy.costs['cost_of_human_review']}\n")

    ok, bad = cp.audit.verify()
    print(f"audit chain intact: {ok}" + ("" if ok else f" (broken at line {bad})"))
    print(f"human reviews are in the audit chain too: "
          f"{sum(1 for l in open('demo/audit_feedback.jsonl') if 'human_review' in l)} entries")


if __name__ == "__main__":
    main()
