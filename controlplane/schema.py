from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Action(str, Enum):
    PASS = "pass"
    ANNOTATE = "annotate"
    REDACT_SPAN = "redact_span"
    REGENERATE = "regenerate"
    ESCALATE = "escalate"
    BLOCK = "block"


class Category(str, Enum):
    PII = "pii"
    SCHEMA = "schema"
    ACL = "acl"
    GROUNDING = "grounding"
    SAFETY = "safety"
    BIAS = "bias"
    COST = "cost"


@dataclass
class Signal:
    """One finding from one check. Multi-label by design: the same span can be
    both a hallucination and a privacy event."""
    category: Category
    score: float
    tier: int
    span: Optional[tuple] = None
    detail: str = ""


@dataclass
class RequestContext:
    request_id: str
    use_case: str
    user_id: str = "anon"
    retrieved_chunks: list = field(default_factory=list)
    allowed_chunk_ids: Optional[set] = None
    prompt_tokens: int = 0


@dataclass
class Verdict:
    request_id: str
    use_case: str
    action: Action
    signals: list = field(default_factory=list)
    tiers_run: list = field(default_factory=list)
    latency_ms: float = 0.0
    verification_cost_inr: float = 0.0
    llm_cost_inr: float = 0.0
    reason: str = ""
    cost_detail: dict = field(default_factory=dict)
    triggered: list = field(default_factory=list)

    def worst(self, category: Category) -> float:
        vals = [s.score for s in self.signals if s.category == category]
        return max(vals) if vals else 0.0

    def to_record(self) -> dict:
        return {
            "request_id": self.request_id,
            "use_case": self.use_case,
            "action": self.action.value,
            "tiers_run": self.tiers_run,
            "latency_ms": round(self.latency_ms, 2),
            "verification_cost_inr": round(self.verification_cost_inr, 4),
            "llm_cost_inr": round(self.llm_cost_inr, 4),
            "reason": self.reason,
            "cost_detail": self.cost_detail,
            "triggered": self.triggered,
            "signals": [
                {
                    "category": s.category.value,
                    "score": round(s.score, 4),
                    "tier": s.tier,
                    "span": list(s.span) if s.span else None,
                    "detail": s.detail,
                }
                for s in self.signals
            ],
        }
