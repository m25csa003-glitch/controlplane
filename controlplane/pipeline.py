import time
import uuid

from .policy.loader import load_all
from .tiers import tier0_rules, tier1_classifiers, tier2_judge
from .router.router import decide
from .audit.log import AuditLog
from .cost.meter import CostMeter, CostBreakdown, CostLine
from .text import sentences as split_sentences
from .schema import RequestContext, Category, Signal


class ControlPlane:
    def __init__(self, audit_path="audit.jsonl", meter=None, listener=None):
        self.policies = load_all()
        self.audit = AuditLog(audit_path)
        self.meter = meter or CostMeter()
        # Anything that wants to watch decisions go by - the dashboard, in
        # practice. Kept off the return path so a slow listener cannot become a
        # slow request.
        self.listener = listener

    def verify(self, text, use_case, retrieved_chunks=None, allowed_chunk_ids=None,
               user_id="anon", llm_cost_inr=0.0, expects_json=False, usage=None,
               model=None, provider="anthropic", audit_mode=False):
        """audit_mode sends every sentence to tier 2 regardless of what tier 1
        thought. It is what a spot audit looks like, and it is the baseline the
        cascade is measured against."""
        policy = self.policies[use_case]
        ctx = RequestContext(
            request_id=str(uuid.uuid4())[:8],
            use_case=use_case,
            user_id=user_id,
            retrieved_chunks=retrieved_chunks or [],
            allowed_chunk_ids=allowed_chunk_ids,
        )
        ctx.expects_json = expects_json

        start = time.perf_counter()
        signals, tiers_run = [], []
        breakdown = CostBreakdown()

        if policy.tier_enabled(0):
            s, ms = tier0_rules.run(text, ctx, policy)
            signals += s
            tiers_run.append(0)
            breakdown.add(self.meter.compute_time("tier0_rules", ms, label="tier0"))

        if policy.tier_enabled(1):
            s, ms = tier1_classifiers.run(text, ctx, policy, self.meter, breakdown)
            signals += s
            tiers_run.append(1)

        lo, hi = policy.band()
        if audit_mode:
            targets = [Signal(Category.GROUNDING, 0.5, 1, s.span, s.text[:80])
                       for s in split_sentences(text)]
            signals = [x for x in signals if x.category != Category.GROUNDING]
        else:
            targets = [s for s in signals
                       if s.category == Category.GROUNDING and lo <= s.score < hi]

        if policy.tier_enabled(2) and targets:
            s, ms = tier2_judge.run(text, ctx, policy, targets, self.meter, breakdown)
            replaced = {id(x) for x in targets}
            signals = [x for x in signals if id(x) not in replaced] + s
            tiers_run.append(2)

        latency = (time.perf_counter() - start) * 1000
        llm_cost = self._llm_cost(usage, model, provider, breakdown, llm_cost_inr)

        verdict = decide(ctx, policy, signals, tiers_run, latency,
                         breakdown.verification_inr, llm_cost, breakdown.to_record())
        self.audit.append(verdict.to_record(), policy_version=policy.version)
        if self.listener is not None:
            self.listener(verdict)
        return verdict

    def _llm_cost(self, usage, model, provider, breakdown, fallback):
        """Price the upstream call itself, so the audit record shows what the
        response cost next to what verifying it cost."""
        if not usage or not model:
            return fallback
        try:
            line = self.meter.llm_call(
                provider, model,
                usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0),
                usage.get("completion_tokens", 0) or usage.get("output_tokens", 0),
            )
        except KeyError as exc:
            # A missing price used to print and return zero, so the money column
            # quietly read 0.000% and looked like a result. Book an unpriced
            # line instead: it shows up in the record, and CostBreakdown.verified
            # goes false, so the number cannot be mistaken for a measured one.
            print(f"[cost] {exc}")
            breakdown.add(CostLine(label="llm_response", inr=0.0, verified=False,
                                   method="unpriced"))
            return fallback
        breakdown.add(line)
        return line.inr
