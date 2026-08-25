import json
import os
import re
import statistics
import time

from ..schema import Signal

# The judge runs against whichever provider has a key. Which model each policy
# uses is a policy decision, not a code one - see tier2.models in the YAML.
DEFAULT_MODELS = {"anthropic": "claude-opus-5", "openai": "gpt-5.6-sol"}


# A judge call that fails falls back to the offline judge, quietly and by
# design. Over a whole eval run that would silently turn an API result into a
# lexical one, so the fallbacks are counted and reported.
STATS = {"api_calls": 0, "api_failures": 0, "offline": 0}


def stats():
    return dict(STATS)


def reset_stats():
    STATS.update(api_calls=0, api_failures=0, offline=0)


PROVIDERS = ("anthropic", "openai")


def _provider():
    """Which provider the judge will use, or None for the offline judge.

    CP_JUDGE_PROVIDER is validated rather than trusted. A typo there used to
    reach the cost meter as an unknown provider and take down verification with
    a KeyError - an env var should not be able to break the request path."""
    forced = os.getenv("CP_JUDGE_PROVIDER")
    if forced:
        if forced in PROVIDERS:
            return forced
        print(f"[tier2] CP_JUDGE_PROVIDER={forced!r} is not one of {PROVIDERS}; "
              "using the offline judge")
        return None
    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("CP_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return None


def _api_key(provider):
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY") or os.getenv("CP_API_KEY")
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY")
    return None


def _model_for(cfg, provider):
    models = cfg.get("models") or {}
    return models.get(provider) or DEFAULT_MODELS.get(provider)

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
    provider = _provider()
    key = _api_key(provider)
    if provider and key:
        judge = {"anthropic": _anthropic_judge, "openai": _openai_judge}.get(provider)
        out = judge(claims, sources, cfg, key, meter, breakdown) if judge else None
        if out is not None:
            STATS["api_calls"] += 1
            return out
        STATS["api_failures"] += 1
    STATS["offline"] += 1
    _model_cost(claims, sources, cfg, meter, breakdown)
    scores, reasons = zip(*(_offline_judge(c, sources) for c in claims))
    return list(scores), list(reasons), "offline"


# Output tokens per claim, used only to model what a judge call would have cost
# when no key is configured.
#
# The first version of this guessed 230 at low effort and was wrong by a factor
# of five, which made the modelled cascade cost look 19x worse than the billed
# one and led to the wrong conclusion about whether tier 2 pays for itself.
OUTPUT_TOKENS = {
    # Measured 2026-08-25 against gpt-5.6-luna and gpt-5.6-sol: 30-48 tokens
    # per claim, flat across 1, 2 and 4 claims.
    "openai": 45,
    # Not measured - there is no Anthropic key on this machine. Adaptive
    # thinking bills thinking as output, so these are deliberately the
    # pessimistic end. Measure before quoting an Anthropic number.
    "anthropic": {"low": 230, "medium": 480, "high": 980, "xhigh": 1600, "max": 2400},
}


def _output_tokens(provider, effort):
    table = OUTPUT_TOKENS.get(provider, OUTPUT_TOKENS["anthropic"])
    if isinstance(table, dict):
        return table.get(effort, 480), False       # estimated
    return table, True                             # measured


def _model_cost(claims, sources, cfg, meter, breakdown):
    """What this judge call would have cost had a key been configured.

    The offline judge is free, so without this the cascade and the
    judge-everything baseline both price at zero and the comparison the whole
    design rests on says nothing. Booked as modelled, never as billed."""
    if meter is None or breakdown is None:
        return
    provider = _provider() or "anthropic"
    model = _model_for(cfg, provider)
    if not model:
        return
    effort = cfg.get("effort", "medium")
    samples = max(1, int(cfg.get("samples", 1)))
    prompt = SYSTEM + sources + "\n".join(claims)
    in_tok, _ = meter.count_tokens(prompt, model)
    per_claim, measured = _output_tokens(provider, effort)
    out_tok = per_claim * len(claims)
    for _ in range(samples):
        try:
            line = meter.llm_call(provider, model, in_tok, out_tok, label="tier2_judge",
                                  method="modelled" if measured else "modelled_estimated")
        except KeyError as exc:
            # No price for this model. Book nothing rather than guess, and
            # certainly do not fail the verification over a costing footnote.
            print(f"[tier2] {exc}")
            return
        line.verified = False
        breakdown.add(line)


def _prompt(claims, sources):
    numbered = "\n".join(f"{i}. {c}" for i, c in enumerate(claims))
    return f"SOURCES:\n{sources or '(none provided)'}\n\nCLAIMS:\n{numbered}"


def _reduce(runs, claims, label):
    """Self-consistency: median across samples, reason from the first run."""
    scores = [statistics.median([r[i][0] for r in runs]) for i in range(len(claims))]
    reasons = [runs[0][i][1] for i in range(len(claims))]
    return scores, reasons, f"{label}x{len(runs)}"


def _openai_judge(claims, sources, cfg, api_key, meter, breakdown):
    try:
        from openai import OpenAI
    except ImportError:
        print("[tier2] openai package not installed; using offline judge")
        return None

    model = _model_for(cfg, "openai")
    samples = max(1, int(cfg.get("samples", 1)))
    client = OpenAI(api_key=api_key, timeout=cfg.get("timeout_ms", 3000) / 1000)

    runs = []
    try:
        for _ in range(samples):
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": _prompt(claims, sources)}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "grounding_verdicts", "strict": True,
                                    "schema": VERDICT_SCHEMA},
                },
            )
            runs.append(_parse_json(resp.choices[0].message.content, len(claims)))
            if meter is not None and breakdown is not None and resp.usage:
                breakdown.add(meter.llm_call(
                    "openai", model,
                    resp.usage.prompt_tokens, resp.usage.completion_tokens,
                    label="tier2_judge",
                ))
    except Exception as exc:
        print(f"[tier2] openai judge failed ({exc}); using offline judge")
        return None

    return _reduce(runs, claims, model)


def _anthropic_judge(claims, sources, cfg, api_key, meter, breakdown):
    try:
        import anthropic
    except ImportError:
        return None

    model = _model_for(cfg, "anthropic")
    samples = int(cfg.get("samples", 1))
    prompt = _prompt(claims, sources)

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
        print(f"[tier2] anthropic judge failed ({exc}); using offline judge")
        return None

    return _reduce(runs, claims, model)


def _parse(resp, n):
    return _parse_json(next(b.text for b in resp.content if b.type == "text"), n)


def _parse_json(text, n):
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
