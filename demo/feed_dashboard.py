"""Drives realistic traffic at a running gateway so the dashboard has something
to show.

    uvicorn controlplane.proxy.gateway:app --port 8000     # terminal 1
    python3 demo/feed_dashboard.py                         # terminal 2
    open http://localhost:8000/dashboard

Replays the eval set through the gateway at a human pace. The verdicts are real
- the same cascade, the same policies - only the arrival times are synthetic.

One thing to say out loud when demoing: the eval set is 58% harmful by
construction, so the escalation rates on screen are far above what production
traffic would produce. The rates are honest for this input; the input is not
representative, and it is not meant to be.
"""
import json
import random
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval" / "datasets" / "controlplane_eval_v1.jsonl"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
RATE = float(sys.argv[2]) if len(sys.argv) > 2 else 1.6      # responses/second


def main():
    if not DATASET.exists():
        sys.exit("dataset missing. Run: python3 eval/build_dataset.py")
    cases = [json.loads(l) for l in DATASET.open() if l.strip()]
    rng = random.Random()

    try:
        httpx.get(f"{BASE}/health", timeout=5).raise_for_status()
    except Exception as exc:
        sys.exit(f"no gateway at {BASE} ({exc}).\n"
                 "Start it with: uvicorn controlplane.proxy.gateway:app --port 8000")

    print(f"feeding {BASE} at ~{RATE}/s from {len(cases)} cases. Ctrl-C to stop.")
    sent = 0
    with httpx.Client(timeout=60) as client:
        while True:
            c = rng.choice(cases)
            try:
                r = client.post(
                    f"{BASE}/v1/chat/completions",
                    headers={"X-ControlPlane-Use-Case": c["use_case"]},
                    json={
                        "model": "mock",
                        "messages": [{"role": "user", "content": c["response"]}],
                        "controlplane": {
                            "retrieved_chunks": c["chunks"],
                            "allowed_chunk_ids": c["allowed_chunk_ids"],
                            "mock_response": c["response"],
                        },
                    },
                )
                r.raise_for_status()
                sent += 1
                if sent % 25 == 0:
                    print(f"  {sent} sent")
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"  send failed: {exc}")
            time.sleep(max(0.0, rng.expovariate(RATE)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nstopped")
