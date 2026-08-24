"""Downloads the tier 1 models and reports which mode the pipeline will run in."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from controlplane.tiers import tier1_classifiers as t1

if __name__ == "__main__":
    device = t1.pick_device()
    print(f"device: {device}")
    mode = t1.load_models(device)
    print(f"grounding mode: {mode}")
    if mode == "stub":
        print("models did not load. pipeline still runs, scores are heuristic.")
    else:
        print("real grounding model active.")
