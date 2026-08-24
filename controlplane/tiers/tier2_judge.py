import time
from ..schema import Signal, Category

# STUB. Replace with a real judge call against the paid API.
# Only invoked when tier 1 lands inside the policy's uncertainty band.


def run(text, ctx, policy, uncertain_signals):
    start = time.perf_counter()
    signals = []
    for s in uncertain_signals:
        signals.append(Signal(s.category, _stub_judge(s.score), 2, s.span, "judge stub"))
    elapsed = (time.perf_counter() - start) * 1000
    return signals, elapsed


def _stub_judge(prior):
    return 1.0 if prior >= 0.5 else 0.0
