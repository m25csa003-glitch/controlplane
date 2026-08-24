import json
import os
import re
import statistics
import time

from ..schema import Signal

DEFAULT_MODEL = os.getenv("CP_JUDGE_MODEL", "claude-opus-5")

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "ungroundedness": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["index", "ungroundedness", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

SYSTEM = """You are a grounding judge inside an enterprise verification layer.

For each numbered claim, decide how well the SOURCES support it, and return an
ungroundedness score in [0,1]:
  0.0  fully stated in the sources
  0.3  a fair paraphrase or a safe inference
  0.7  goes beyond the sources; plausible but unsupported
  1.0  contradicts the sources, or invents a specific fact not present

A claim that changes a number, date, name or entitlement from the sources scores
at least 0.9. Judge only against the sources given; do not use outside knowledge.
Keep each reason under 20 words."""


def run(text, ctx, policy, uncertain_signals, meter=None, breakdown=None):
    """Judge the claims tier 1 was unsure about. Falls back to a deterministic
    offline judge when no API key is configured, so the demo always runs."""
    start = time.perf_counter()
    cfg = policy.tiers.get("tier2", {})
    claims = [_claim_text(s, text) for s in uncertain_signals]
    sources = "\n".join(
        f"[{c.get('id', i)}] {c.get('text','')}" for i, c in enumerate(ctx.retrieved_chunks)
    )

    scores, reasons, mode = _judge(claims, sources, cfg, meter, breakdown)

    signals = []
    for s, score, reason in zip(uncertain_signals, scores, reasons):
        signals.append(Signal(s.category, score, 2, s.span, f"{mode}: {reason}"))

    return signals, (time.perf_counter() - start) * 1000


def _judge(claims, sources, cfg, meter, breakdown):
    if not claims:
        return [], [], "judge"
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CP_API_KEY")
    if api_key:
        out = _api_judge(claims, sources, cfg, api_key, meter, breakdown)
        if out is not None:
            return out
    scores, reasons = zip(*(_offline_judge(c, sources) for c in claims))
    return list(scores), list(reasons), "offline"


def _api_judge(claims, sources, cfg, api_key, meter, breakdown):
    try:
        import anthropic
    except ImportError:
        return None

    model = cfg.get("model", DEFAULT_MODEL)
    samples = int(cfg.get("samples", 1))
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(claims))
    prompt = f"SOURCES:\n{sources or '(none provided)'}\n\nCLAIMS:\n{numbered}"

    client = anthropic.Anthropic(api_key=api_key, timeout=cfg.get("timeout_ms", 3000) / 1000)
    runs = []
    try:
        for _ in range(max(1, samples)):
            resp = client.messages.create(
                model=model,
                max_tokens=4000,
                system=SYSTEM,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": cfg.get("effort", "medium"),
                    "format": {"type": "json_schema", "schema": VERDICT_SCHEMA},
                },
                messages=[{"role": "user", "content": prompt}],
            )
            runs.append(_parse(resp, len(claims)))
            if meter is not None and breakdown is not None:
                breakdown.add(meter.llm_call(
                    "anthropic", model,
                    resp.usage.input_tokens, resp.usage.output_tokens,
                    label="tier2_judge",
                ))
    except Exception as exc:
        print(f"[tier2] judge call failed ({exc}); using offline judge")
        return None

    # self-consistency: median across samples, reason from the first run
    scores = [statistics.median([r[i][0] for r in runs]) for i in range(len(claims))]
    reasons = [runs[0][i][1] for i in range(len(claims))]
    return scores, reasons, f"{model}x{len(runs)}"


def _parse(resp, n):
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    out = [(0.5, "no verdict returned")] * n
    for v in data.get("verdicts", []):
        i = v.get("index", -1)
        if 0 <= i < n:
            out[i] = (max(0.0, min(1.0, float(v["ungroundedness"]))), v.get("reason", ""))
    return out


NUM = re.compile(r"\d+(?:\.\d+)?")
NEGATION = re.compile(r"\b(not|no|never|cannot|without|excluded|denied)\b", re.I)


def _offline_judge(claim, sources):
    """Deterministic judge for when no key is configured. Weaker than the model,
    but it reasons about contradiction rather than just overlap: a claim that
    changes a number the sources state is the most common hallucination shape."""
    if not sources.strip():
        return 0.5, "no sources to judge against"

    src_nums = set(NUM.findall(sources))
    claim_nums = set(NUM.findall(claim))
    novel_nums = claim_nums - src_nums
    if novel_nums and src_nums:
        return 0.95, f"numbers not in sources: {', '.join(sorted(novel_nums)[:3])}"

    low = sources.lower()
    content = [w.strip(".,%()") for w in claim.lower().split() if len(w) > 4]
    if not content:
        return 0.2, "no substantive content to verify"
    hits = sum(1 for w in content if w in low)
    overlap = hits / len(content)

    if NEGATION.search(claim) != NEGATION.search(sources) and overlap > 0.5:
        return 0.85, "polarity differs from sources"
    if overlap >= 0.8:
        return 0.05, "closely tracks the sources"
    if overlap >= 0.5:
        return 0.35, "partially supported paraphrase"
    return 0.8, f"only {overlap:.0%} of content words appear in sources"


def _claim_text(signal, text):
    if signal.span:
        return text[signal.span[0]:signal.span[1]]
    return text
