import json
import time
from pathlib import Path

from ..schema import Category

LABELS = ("harmful", "clean")


class FeedbackStore:
    """What a human decided about a response the system flagged.

    An escalation is only worth its cost if the answer comes back. Each record
    pairs the scores the cascade produced with the verdict a reviewer reached,
    which is the only thing that makes retuning possible: without the true
    label, a threshold sweep is guesswork about which side of the line a case
    belonged on.

    Records are also written to the audit log. A human overriding the system is
    exactly the kind of event a regulator asks to see.
    """

    def __init__(self, path="feedback.jsonl", audit=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self.audit = audit

    def record(self, verdict, label, reviewer="unknown", note="", weight=1.0):
        """weight is 1 / P(this case was reviewed). Flagged cases are always
        reviewed, so weight 1. A passed case reviewed at a 5% sample rate stands
        for 20 like it, so weight 20. Without this the reviewed set looks far
        more dangerous than production and every retune says "flag more"."""
        if label not in LABELS:
            raise ValueError(f"label must be one of {LABELS}, got {label!r}")

        entry = {
            "ts": time.time(),
            "request_id": verdict.request_id,
            "use_case": verdict.use_case,
            "action_taken": verdict.action.value,
            "label": label,
            "reviewer": reviewer,
            "note": note,
            "weight": weight,
            "scores": {c.value: verdict.worst(c) for c in Category},
        }
        with self.path.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")

        if self.audit is not None:
            self.audit.append({
                "request_id": verdict.request_id,
                "use_case": verdict.use_case,
                "action": "human_review",
                "reviewed_action": verdict.action.value,
                "label": label,
                "reviewer": reviewer,
                "tiers_run": [],
                "latency_ms": 0.0,
                "verification_cost_inr": 0.0,
                "llm_cost_inr": 0.0,
                "reason": note or f"reviewer marked {label}",
                "signals": [],
            })
        return entry

    def all(self):
        with self.path.open() as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def for_use_case(self, use_case):
        return [r for r in self.all() if r["use_case"] == use_case]

    def __len__(self):
        return len(self.all())
