import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PRICING_PATH = Path(__file__).resolve().parents[2] / "configs" / "pricing.yaml"

# What the demos assume the application itself is running on. ControlPlane does
# not care - it prices whatever the caller reports - but the demo has to pick
# something, and picking it in one place stops three files disagreeing.
DEMO_UPSTREAM = (os.getenv("CP_DEMO_UPSTREAM_MODEL", "gpt-5.6-terra"), "openai")


@dataclass
class CostLine:
    """One priced item. `verified` is false when the price came from the
    unverified table or the token count was estimated rather than counted."""
    label: str
    inr: float
    tokens: int = 0
    verified: bool = True
    method: str = ""


@dataclass
class CostBreakdown:
    lines: list = field(default_factory=list)

    def add(self, line: CostLine):
        self.lines.append(line)

    @property
    def total_inr(self) -> float:
        return sum(l.inr for l in self.lines)

    @property
    def verification_inr(self) -> float:
        """What checking cost, excluding the upstream response we were checking."""
        return sum(l.inr for l in self.lines if l.label != "llm_response")

    @property
    def verified(self) -> bool:
        return all(l.verified for l in self.lines)

    def of(self, label: str) -> float:
        return sum(l.inr for l in self.lines if l.label == label)

    def to_record(self) -> dict:
        return {
            "total_inr": round(self.total_inr, 6),
            "verified": self.verified,
            "lines": [
                {
                    "label": l.label,
                    "inr": round(l.inr, 6),
                    "tokens": l.tokens,
                    "verified": l.verified,
                    "method": l.method,
                }
                for l in self.lines
            ],
        }


class CostMeter:
    def __init__(self, pricing_path=PRICING_PATH):
        raw = yaml.safe_load(Path(pricing_path).read_text())
        self.usd_to_inr = raw["usd_to_inr"]
        self.providers = raw.get("providers") or {}
        self.unverified = raw.get("unverified") or {}
        self.compute = raw.get("compute") or {}
        self._counter = None

    # --- token counting -------------------------------------------------

    def count_tokens(self, text, model=None):
        """Exact count when an Anthropic key is configured, heuristic otherwise.
        Returns (tokens, method) so the caller can report which one was used."""
        exact = self._count_exact(text, model)
        if exact is not None:
            return exact, "counted"
        # ~4 chars per token for English prose. Good to roughly +/-15%, which is
        # why anything derived from it is flagged unverified.
        return max(1, math.ceil(len(text) / 4)), "estimated"

    def _count_exact(self, text, model):
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("CP_API_KEY")):
            return None
        try:
            if self._counter is None:
                import anthropic
                self._counter = anthropic.Anthropic(
                    api_key=os.getenv("ANTHROPIC_API_KEY") or os.getenv("CP_API_KEY")
                )
            resp = self._counter.messages.count_tokens(
                model=model or "claude-opus-5",
                messages=[{"role": "user", "content": text}],
            )
            return resp.input_tokens
        except Exception:
            return None

    # --- pricing --------------------------------------------------------

    def _rate(self, provider, model):
        """Returns (input_usd_per_1m, output_usd_per_1m, verified)."""
        entry = self.providers.get(provider, {}).get(model)
        if entry:
            return entry["input"], entry["output"], True
        entry = self.unverified.get(provider, {}).get(model)
        if entry:
            return entry["input"], entry["output"], False
        raise KeyError(
            f"no price for {provider}/{model} in configs/pricing.yaml. "
            "Add it with a source and date rather than guessing."
        )

    def llm_call(self, provider, model, prompt_tokens, completion_tokens,
                 label="llm_response", method="reported"):
        in_usd, out_usd, verified = self._rate(provider, model)
        usd = (prompt_tokens * in_usd + completion_tokens * out_usd) / 1_000_000
        return CostLine(
            label=label,
            inr=usd * self.usd_to_inr,
            tokens=prompt_tokens + completion_tokens,
            verified=verified and method != "estimated",
            method=method,
        )

    def compute_time(self, key, elapsed_ms, label=None):
        rate = self.compute.get(key, {}).get("inr_per_hour", 0.0)
        return CostLine(
            label=label or key,
            inr=rate * elapsed_ms / 3_600_000,
            verified=True,
            method="measured",
        )

    def known_models(self):
        return {p: sorted(m) for p, m in self.providers.items()}
