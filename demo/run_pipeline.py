import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane

CHUNKS = [
    {"id": "pol-1", "text": "Room rent capping under this policy is 1 percent of sum insured per day."},
    {"id": "pol-2", "text": "Cashless treatment is available at network hospitals only."},
]

CASES = [
    ("grounded answer",
     "Room rent capping under this policy is 1 percent of sum insured per day.", CHUNKS, None),
    ("hallucinated number",
     "Room rent capping is 2 percent, so approximately 185000 rupees will be reimbursed.", CHUNKS, None),
    ("pii leak",
     "Your registered contact is 9876543210 and PAN ABCDE1234F.", CHUNKS, None),
    ("acl breach",
     "Cashless treatment is available at network hospitals only.", CHUNKS, {"pol-1"}),
]


def main():
    cp = ControlPlane(audit_path="demo/audit.jsonl")
    for use_case in ["customer_support", "internal_copilot", "decision_support"]:
        print(f"\n=== {use_case} ===")
        for name, text, chunks, allowed in CASES:
            v = cp.verify(text, use_case, retrieved_chunks=chunks, allowed_chunk_ids=allowed)
            print(f"  {name:22s} -> {v.action.value:12s} tiers={v.tiers_run} "
                  f"{v.latency_ms:.2f}ms  {v.reason}")
    ok, bad = cp.audit.verify()
    print(f"\naudit chain intact: {ok}" + ("" if ok else f" (broken at line {bad})"))


if __name__ == "__main__":
    main()
