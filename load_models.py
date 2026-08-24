"""Downloads the tier 1 models and reports which mode the pipeline will run in.

    python3 load_models.py

Nothing here is required. The pipeline runs without any of it, on lexical
fallbacks, and says so. This just makes tier 1 good rather than indicative.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from controlplane.tiers import tier1_classifiers as t1

if __name__ == "__main__":
    device = t1.pick_device()
    print(f"device: {device}\n")

    started = time.perf_counter()
    mode = t1.load_models(device)
    elapsed = time.perf_counter() - started

    print(f"\ngrounding: {mode}")
    print(f"safety:    {'loaded' if t1._state.get('safety') else 'unavailable'}")
    print(f"took {elapsed:.1f}s")

    if mode == "lexical":
        print("\nNo grounding model loaded. The pipeline still runs; grounding "
              "falls back to lexical overlap plus a numeric contradiction check. "
              "eval/results/report.md records which mode produced its numbers.")
