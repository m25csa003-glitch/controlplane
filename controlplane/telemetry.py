import asyncio
import time
from collections import deque

from .schema import Action, Category


class Telemetry:
    """In-memory view of what the plane has been doing.

    Deliberately not a database. An operator dashboard needs the last few
    hundred decisions and running totals, and a prototype that ships a
    persistence layer for that is answering a question nobody asked. Restarting
    the gateway loses the feed and keeps the audit log, which is the right way
    round: the log is the record, this is a window onto it.
    """

    def __init__(self, keep=250):
        self.recent = deque(maxlen=keep)
        self.subscribers = []
        self.started = time.time()
        self.totals = {}

    # --- ingest ---------------------------------------------------------

    def record(self, verdict):
        row = self._row(verdict)
        self.recent.appendleft(row)
        self._tally(verdict, row)
        for q in list(self.subscribers):
            try:
                q.put_nowait(row)
            except asyncio.QueueFull:
                # A dashboard that cannot keep up is dropped rather than
                # allowed to back-pressure the request path.
                self.subscribers.remove(q)
        return row

    def _row(self, verdict):
        return {
            "ts": time.time(),
            "request_id": verdict.request_id,
            "use_case": verdict.use_case,
            "action": verdict.action.value,
            "reason": verdict.reason,
            "tiers_run": verdict.tiers_run,
            "latency_ms": round(verdict.latency_ms, 2),
            "verification_cost_inr": verdict.verification_cost_inr,
            "llm_cost_inr": verdict.llm_cost_inr,
            "categories": sorted({t["category"] for t in verdict.triggered}),
            "spans": [
                {"category": s.category.value, "score": round(s.score, 3),
                 "detail": s.detail[:90]}
                for s in verdict.signals if s.score > 0
            ][:6],
        }

    def _tally(self, verdict, row):
        t = self.totals.setdefault(verdict.use_case, {
            "n": 0, "actions": {}, "categories": {}, "tier2": 0,
            "verify_inr": 0.0, "llm_inr": 0.0, "latency": deque(maxlen=250),
        })
        t["n"] += 1
        t["actions"][row["action"]] = t["actions"].get(row["action"], 0) + 1
        for c in row["categories"]:
            t["categories"][c] = t["categories"].get(c, 0) + 1
        if 2 in verdict.tiers_run:
            t["tier2"] += 1
        t["verify_inr"] += verdict.verification_cost_inr
        t["llm_inr"] += verdict.llm_cost_inr
        t["latency"].append(verdict.latency_ms)

    # --- read -----------------------------------------------------------

    def snapshot(self, policies=None):
        out = {"uptime_s": round(time.time() - self.started, 1), "use_cases": {}}
        for name, t in self.totals.items():
            lat = sorted(t["latency"])
            policy = (policies or {}).get(name)
            escalated = sum(t["actions"].get(a, 0)
                            for a in ("escalate", "block", "regenerate", "redact_span"))
            out["use_cases"][name] = {
                "n": t["n"],
                "actions": t["actions"],
                "categories": t["categories"],
                "tier2_rate": t["tier2"] / t["n"] if t["n"] else 0,
                "escalation_rate": escalated / t["n"] if t["n"] else 0,
                "max_escalation_rate": (
                    policy.tiers.get("tier2", {}).get("max_escalation_rate") if policy else None),
                "verify_inr": round(t["verify_inr"], 4),
                "llm_inr": round(t["llm_inr"], 4),
                "verify_pct_of_llm": (100 * t["verify_inr"] / t["llm_inr"]) if t["llm_inr"] else 0,
                "p50_ms": _pct(lat, 50),
                "p95_ms": _pct(lat, 95),
                "latency_budget_ms": policy.latency_budget_ms if policy else None,
                "over_budget": bool(policy and _pct(lat, 95) > policy.latency_budget_ms),
            }
        return out

    def queue(self, limit=40):
        """What a reviewer would actually be looking at."""
        return [r for r in self.recent if r["action"] in ("escalate", "block")][:limit]

    # --- live feed ------------------------------------------------------

    def subscribe(self, maxsize=100):
        q = asyncio.Queue(maxsize=maxsize)
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        if q in self.subscribers:
            self.subscribers.remove(q)


def _pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 2)
