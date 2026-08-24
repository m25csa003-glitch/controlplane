from ..schema import Action, Category, Verdict

# How much each action costs the user if we are wrong to take it. The router
# picks the most severe action any single category asked for, so this ordering
# is the tie-break, not a preference.
SEVERITY = {
    Action.PASS: 0,
    Action.ANNOTATE: 1,
    Action.REDACT_SPAN: 2,
    Action.REGENERATE: 3,
    Action.ESCALATE: 4,
    Action.BLOCK: 5,
}


def decide(ctx, policy, signals, tiers_run, latency_ms, verification_cost, llm_cost,
           cost_detail=None):
    """Expected-cost routing.

    Every category is evaluated, not just the first one that trips. Bias,
    hallucination and privacy overlap by design, so a response can be flagged
    under several at once; we keep all of them on the verdict and act on the
    most severe. Grounding is the one weighed economically —
    P(wrong) x cost_of_being_wrong against cost_of_human_review.
    """
    actions = policy.actions
    verdict = Verdict(
        request_id=ctx.request_id,
        use_case=ctx.use_case,
        action=Action.PASS,
        signals=signals,
        tiers_run=tiers_run,
        latency_ms=latency_ms,
        verification_cost_inr=verification_cost,
        llm_cost_inr=llm_cost,
        cost_detail=cost_detail or {},
    )

    triggered = []

    if verdict.worst(Category.PII) >= 1.0:
        triggered.append((Action(actions["pii_detected"]), "pii", "pii detected in response"))

    if verdict.worst(Category.ACL) >= 1.0:
        triggered.append((Action.BLOCK, "acl", "retrieved content outside user permissions"))

    if verdict.worst(Category.SCHEMA) >= 1.0:
        triggered.append((Action(actions.get("schema_violation", "regenerate")),
                          "schema", "response did not match the required schema"))

    safety = verdict.worst(Category.SAFETY)
    if safety >= policy.threshold("safety", 0.8):
        triggered.append((Action(actions["safety_violation"]),
                          "safety", f"safety score {safety:.2f}"))

    bias = verdict.worst(Category.BIAS)
    if bias >= policy.threshold("bias", 0.7):
        triggered.append((Action(actions.get("bias_detected", "escalate")),
                          "bias", f"bias score {bias:.2f}"))

    triggered += _grounding(verdict, policy, actions)

    if triggered:
        action, _, _ = max(triggered, key=lambda t: SEVERITY[t[0]])
        verdict.action = action
        verdict.reason = "; ".join(r for _, _, r in triggered)
        verdict.triggered = [
            {"category": cat, "action": a.value, "reason": r} for a, cat, r in triggered
        ]
    else:
        verdict.reason = "clean"

    return verdict


def _grounding(verdict, policy, actions):
    p_wrong = verdict.worst(Category.GROUNDING)
    if p_wrong == 0.0:
        return []

    expected_loss = p_wrong * policy.costs["cost_of_being_wrong"]
    review_cost = policy.costs["cost_of_human_review"]
    lo, hi = policy.band()

    if p_wrong >= hi and expected_loss > review_cost:
        return [(Action(actions["low_grounding_overall"]), "grounding",
                 f"expected loss {expected_loss:.0f} > review {review_cost}")]
    if lo <= p_wrong < hi:
        return [(Action(actions["uncertain"]), "grounding",
                 f"inside uncertainty band, p={p_wrong:.2f}")]
    if p_wrong >= hi:
        # Above the band but the claim is cheap to be wrong about — reviewing it
        # would cost more than the mistake. Say so rather than silently passing.
        return [(Action(actions["ungrounded_claim"]), "grounding",
                 f"ungrounded p={p_wrong:.2f}, but review costs more than the error")]
    return []
