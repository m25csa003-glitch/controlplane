import re
import time
from ..schema import Signal, Category

PII_PATTERNS = {
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "phone_in": re.compile(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b"),
    "email": re.compile(r"\b[\w.\-]+@[\w\-]+\.[A-Za-z]{2,}\b"),
    "card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}


def run(text, ctx, policy):
    """Deterministic checks. No model call, sub-millisecond."""
    start = time.perf_counter()
    signals = []
    checks = policy.checks(0)

    if "pii" in checks:
        for name, pat in PII_PATTERNS.items():
            for m in pat.finditer(text):
                signals.append(Signal(Category.PII, 1.0, 0, (m.start(), m.end()), name))

    if "acl_check" in checks and ctx.allowed_chunk_ids is not None:
        for chunk in ctx.retrieved_chunks:
            cid = chunk.get("id")
            if cid not in ctx.allowed_chunk_ids:
                signals.append(Signal(Category.ACL, 1.0, 0, None, f"chunk {cid} not permitted"))

    if "schema" in checks and getattr(ctx, "expects_json", False):
        import json
        try:
            json.loads(text)
        except Exception:
            signals.append(Signal(Category.SCHEMA, 1.0, 0, None, "invalid json"))

    elapsed = (time.perf_counter() - start) * 1000
    return signals, elapsed
