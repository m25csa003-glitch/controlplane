from ..schema import Action, Category, Verdict


def decide(ctx, policy, signals, tiers_run, latency_ms, verification_cost, llm_cost):
    """Expected-cost routing. Hard violations short-circuit; everything else is
    weighed as P(wrong) x cost_of_being_wrong against cost_of_human_review."""
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
    )

    if verdict.worst(Category.PII) >= 1.0:
        verdict.action = Action(actions["pii_detected"])
        verdict.reason = "pii detected"
        return verdict

    if verdict.worst(Category.ACL) >= 1.0:
        verdict.action = Action.BLOCK
        verdict.reason = "retrieved content outside user permissions"
        return verdict

    if verdict.worst(Category.SAFETY) >= 0.8:
        verdict.action = Action(actions["safety_violation"])
        verdict.reason = "safety threshold exceeded"
        return verdict

    p_wrong = verdict.worst(Category.GROUNDING)
    if p_wrong == 0.0:
        verdict.reason = "clean"
        return verdict

    expected_loss = p_wrong * policy.costs["cost_of_being_wrong"]
    review_cost = policy.costs["cost_of_human_review"]
    lo, hi = policy.band()

    if expected_loss > review_cost and p_wrong >= hi:
        verdict.action = Action(actions["low_grounding_overall"])
        verdict.reason = f"expected loss {expected_loss:.1f} > review {review_cost}"
    elif lo <= p_wrong < hi:
        verdict.action = Action(actions["uncertain"])
        verdict.reason = f"inside uncertainty band, p={p_wrong:.2f}"
    elif p_wrong >= lo:
        verdict.action = Action(actions["ungrounded_claim"])
        verdict.reason = f"ungrounded claim, p={p_wrong:.2f}"
    else:
        verdict.reason = f"below band, p={p_wrong:.2f}"

    return verdict
