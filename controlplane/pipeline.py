import re
import time
import uuid

from .policy.loader import load_all
from .tiers import tier0_rules, tier1_classifiers, tier2_judge
from .router.router import decide
from .audit.log import AuditLog
from .schema import RequestContext, Category

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


class ControlPlane:
    def __init__(self, audit_path="audit.jsonl"):
        self.policies = load_all()
        self.audit = AuditLog(audit_path)

    def verify(self, text, use_case, retrieved_chunks=None, allowed_chunk_ids=None,
               user_id="anon", llm_cost_inr=0.0):
        policy = self.policies[use_case]
        ctx = RequestContext(
            request_id=str(uuid.uuid4())[:8],
            use_case=use_case,
            user_id=user_id,
            retrieved_chunks=retrieved_chunks or [],
            allowed_chunk_ids=allowed_chunk_ids,
        )

        start = time.perf_counter()
        signals, tiers_run, ver_cost = [], [], 0.0

        if policy.tier_enabled(0):
            s, ms = tier0_rules.run(text, ctx, policy)
            signals += s
            tiers_run.append(0)

        if policy.tier_enabled(1):
            sentences = [x for x in SENT_SPLIT.split(text) if x.strip()]
            s, ms = tier1_classifiers.run(sentences, ctx, policy)
            signals += s
            tiers_run.append(1)
            ver_cost += 0.001 * len(sentences)

        lo, hi = policy.band()
        uncertain = [s for s in signals
                     if s.category == Category.GROUNDING and lo <= s.score < hi]

        if policy.tier_enabled(2) and uncertain:
            s, ms = tier2_judge.run(text, ctx, policy, uncertain)
            signals = [x for x in signals if x not in uncertain] + s
            tiers_run.append(2)
            ver_cost += 0.35

        latency = (time.perf_counter() - start) * 1000
        verdict = decide(ctx, policy, signals, tiers_run, latency, ver_cost, llm_cost_inr)
        self.audit.append(verdict.to_record())
        return verdict
