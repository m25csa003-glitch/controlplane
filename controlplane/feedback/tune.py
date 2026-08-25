"""Retune thresholds from reviewed cases.

The router picks an action by weighing P(wrong) x cost_of_being_wrong against
cost_of_human_review. The tuner uses the same arithmetic, on real labels instead
of a guessed threshold: for each candidate cut-off, what did it actually cost to
run this policy over the cases a human has reviewed?

That keeps the loop honest in a way an F1 sweep does not. F1 treats a missed
hallucination in a regulated decision as equal to a false alarm on an internal
chatbot. These policies do not, and neither does the business.
"""
from ..schema import Category

MIN_RECORDS = 20

# Reviewed cases that scored below the current threshold. Without these the
# sweep has no evidence about the region it would be moving into.
MIN_BELOW = 10


def expected_cost(records, threshold, wrong_cost, review_cost, category="grounding"):
    """Rupees this policy would have spent over these cases at this threshold.

    Above the threshold we act, and pay for a review. Below it we pass, and pay
    the cost of being wrong on anything that was actually harmful."""
    total = 0.0
    for r in records:
        score = r["scores"].get(category, 0.0)
        w = r.get("weight", 1.0)
        if score >= threshold:
            total += review_cost * w
        elif r["label"] == "harmful":
            total += wrong_cost * w
    return total


def escalation_rate(records, threshold, category="grounding"):
    """Share of traffic a threshold sends to a human, weighted back to what
    production would actually look like."""
    total = sum(r.get("weight", 1.0) for r in records)
    if not total:
        return 0.0
    flagged = sum(r.get("weight", 1.0) for r in records
                  if r["scores"].get(category, 0.0) >= threshold)
    return flagged / total


def sweep(records, wrong_cost, review_cost, category="grounding", points=41):
    out = []
    for i in range(points):
        t = round(i / (points - 1), 3)
        out.append((t, expected_cost(records, t, wrong_cost, review_cost, category)))
    return out


def recommend(records, policy, category="grounding"):
    """Best threshold for this policy given what reviewers have said so far."""
    if len(records) < MIN_RECORDS:
        return {
            "status": "insufficient",
            "records": len(records),
            "needed": MIN_RECORDS,
        }

    wrong = policy.costs["cost_of_being_wrong"]
    review = policy.costs["cost_of_human_review"]
    current_t = policy.band()[0]

    # Reviewers only see what the system flagged, so the reviewed set is
    # censored: almost nothing in it scored below the current threshold. Fit a
    # threshold to that and the answer is always "flag everything", because on
    # this evidence passing is never observed to be safe. The cure is to review
    # a random sample of what was passed too - audit_sample_rate in the policy -
    # and refuse to recommend until that sample exists.
    below = [r for r in records if r["scores"].get(category, 0.0) < current_t]
    sampled = [r for r in records if r.get("weight", 1.0) > 1.0]
    if len(below) < MIN_BELOW or not sampled:
        return {
            "status": "censored",
            "records": len(records),
            "below_threshold": len(below),
            "needed_below": MIN_BELOW,
            "current_threshold": current_t,
            "sample_rate": policy.raw.get("audit", {}).get("audit_sample_rate", 0.0),
        }

    curve = sweep(records, wrong, review, category)

    # Cost alone says "review everything" whenever being wrong is much dearer
    # than a review - at 50000 against 200 it always will. That is arithmetically
    # right and operationally useless: a review queue has people in it, and the
    # policy already states how much of the traffic they can absorb. The tuner
    # optimises inside that capacity rather than pretending it is unlimited.
    cap = policy.tiers.get("tier2", {}).get("max_escalation_rate")
    feasible = [(t, c) for t, c in curve
                if cap is None or escalation_rate(records, t, category) <= cap]
    capped = bool(cap) and len(feasible) < len(curve)
    if not feasible:
        feasible = curve

    best_t, best_cost = min(feasible, key=lambda x: x[1])
    current_cost = expected_cost(records, current_t, wrong, review, category)

    missed = sum(1 for r in records
                 if r["label"] == "harmful" and r["scores"].get(category, 0) < current_t)
    false_alarms = sum(1 for r in records
                       if r["label"] == "clean" and r["scores"].get(category, 0) >= current_t)

    return {
        "status": "ok",
        "records": len(records),
        "category": category,
        "current_threshold": current_t,
        "current_cost_inr": round(current_cost, 2),
        "recommended_threshold": best_t,
        "recommended_cost_inr": round(best_cost, 2),
        "saving_inr": round(current_cost - best_cost, 2),
        "saving_pct": round(100 * (current_cost - best_cost) / current_cost, 1) if current_cost else 0.0,
        "reviewed_flagged": sum(1 for r in records if r.get("weight", 1.0) == 1.0),
        "reviewed_sampled": len(sampled),
        "missed_at_current": missed,
        "false_alarms_at_current": false_alarms,
        "escalation_rate_now": round(escalation_rate(records, current_t, category), 4),
        "escalation_rate_recommended": round(escalation_rate(records, best_t, category), 4),
        "max_escalation_rate": cap,
        "capacity_bound": capped,
        "curve": curve,
    }


def recommend_all(store, policies, category="grounding"):
    return {
        name: recommend(store.for_use_case(name), policy, category)
        for name, policy in policies.items()
    }


def as_policy_patch(rec):
    """The YAML change a recommendation implies. Applying it is a human's call:
    this is a config edit with a cost attached, not something a prototype should
    do to itself while nobody is looking."""
    if rec.get("status") != "ok":
        return None
    lo = rec["recommended_threshold"]
    return {"tiers": {"tier1": {"uncertainty_band": [lo, max(lo + 0.05, 0.95)]}}}
