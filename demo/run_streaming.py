"""Shows verification running beside the token stream rather than after it.

    python3 demo/run_streaming.py            lexical tier 1
    python3 demo/run_streaming.py --models   real tier 1 models

The number that matters is the lag between the last token and the verdict. Post
hoc verification pays the full check after the stream ends; running beside it,
the check is already done.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane
from controlplane.streaming import StreamingVerifier
from controlplane.tiers import tier1_classifiers

CHUNKS = [
    {"id": "pol-1", "text": "Room rent capping under this policy is 1 percent of sum insured per day."},
    {"id": "pol-2", "text": "Cashless treatment is available at network hospitals only."},
    {"id": "pol-3", "text": "Ambulance charges are reimbursed up to 2000 rupees per hospitalisation."},
]

RESPONSE = (
    "Room rent capping under this policy is 1 percent of sum insured per day. "
    "Cashless treatment is available at network hospitals only. "
    "Room rent capping is 2 percent, so 185000 rupees will be reimbursed. "
    "Ambulance charges are reimbursed up to 2000 rupees per hospitalisation."
)

TOKEN_MS = 25          # ~40 tokens/sec, a normal streaming rate


async def token_stream(text, delay_ms=TOKEN_MS):
    for word in text.split(" "):
        await asyncio.sleep(delay_ms / 1000)
        yield word + " "


async def run_streaming(cp, use_case):
    v = StreamingVerifier(cp, use_case, retrieved_chunks=CHUNKS)
    first_token = None
    async for chunk in token_stream(RESPONSE):
        if first_token is None:
            first_token = time.perf_counter()
        await v.feed(chunk)
    last_token = time.perf_counter()
    await v.close()
    done = time.perf_counter()

    return {
        "stream_ms": (last_token - first_token) * 1000,
        "lag_ms": (done - last_token) * 1000,
        "verdict": v.verdict,
    }


def run_posthoc(cp, use_case):
    """What it costs to wait for the stream and then check."""
    stream_ms = len(RESPONSE.split(" ")) * TOKEN_MS
    started = time.perf_counter()
    verdict = cp.verify(RESPONSE, use_case, retrieved_chunks=CHUNKS)
    return {"stream_ms": stream_ms,
            "lag_ms": (time.perf_counter() - started) * 1000,
            "verdict": verdict}


async def main():
    if "--models" in sys.argv:
        print("loading tier 1 models ...", flush=True)
        tier1_classifiers.load_models()
    print(f"tier 1: {tier1_classifiers.describe()}\n")

    cp = ControlPlane(audit_path="demo/audit_streaming.jsonl")

    for use_case in ["customer_support", "internal_copilot", "decision_support"]:
        policy = cp.policies[use_case]
        print(f"=== {use_case}  (streaming_mode: {policy.streaming_mode}, "
              f"budget {policy.latency_budget_ms}ms) ===")

        conc = await run_streaming(cp, use_case)
        post = run_posthoc(cp, use_case)
        s = conc["verdict"].cost_detail.get("stream", {})

        print(f"  stream took            {conc['stream_ms']:7.0f} ms")
        print(f"  beside the stream      {conc['lag_ms']:7.1f} ms after last token"
              f"   -> {conc['verdict'].action.value}")
        print(f"  post hoc               {post['lag_ms']:7.1f} ms after last token"
              f"   -> {post['verdict'].action.value}")
        saved = post["lag_ms"] - conc["lag_ms"]
        print(f"  saved                  {saved:7.1f} ms"
              f"   ({saved / max(post['lag_ms'], 1e-9) * 100:.0f}% of the wait)")
        print(f"  {s.get('sentences', 0)} sentences checked inline, "
              f"each {s.get('sentence_checks_ms', [])} ms")
        print(f"  within budget: {conc['lag_ms'] <= policy.latency_budget_ms}\n")

    ok, bad = cp.audit.verify()
    print(f"audit chain intact: {ok}" + ("" if ok else f" (broken at line {bad})"))


if __name__ == "__main__":
    asyncio.run(main())
