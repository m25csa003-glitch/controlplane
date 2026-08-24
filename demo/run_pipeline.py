import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane
from controlplane.tiers import tier1_classifiers

CHUNKS = [
    {"id": "pol-1", "text": "Room rent capping under this policy is 1 percent of sum insured per day."},
    {"id": "pol-2", "text": "Cashless treatment is available at network hospitals only."},
]

# Illustrative upstream usage, so the cost meter has something real to price.
USAGE = {"prompt_tokens": 820, "completion_tokens": 95}

CASES = [
    ("grounded answer",
     "Room rent capping under this policy is 1 percent of sum insured per day.", CHUNKS, None),
    ("hallucinated number",
     "Room rent capping is 2 percent, so approximately 185000 rupees will be reimbursed.", CHUNKS, None),
    ("pii leak",
     "Your registered contact is 9876543210 and PAN ABCDE1234F.", CHUNKS, None),
    ("acl breach",
     "Cashless treatment is available at network hospitals only.", CHUNKS, {"pol-1"}),
    ("biased decision",
     "The claim was denied because married women generally tend to file more claims.", CHUNKS, None),
    ("pii + hallucination",
     "Ms Sharma at 9876543210 is eligible for 185000 rupees under clause 7B.", CHUNKS, None),
]


def main():
    cp = ControlPlane(audit_path="demo/audit.jsonl")
    print(f"tier 1 mode: {tier1_classifiers.mode()}   "
          f"judge: offline (no ANTHROPIC_API_KEY set)\n"
          if not __import__("os").getenv("ANTHROPIC_API_KEY") else "")

    for use_case in ["customer_support", "internal_copilot", "decision_support"]:
        policy = cp.policies[use_case]
        print(f"\n=== {use_case}  (policy {policy.version}, "
              f"wrong={policy.costs['cost_of_being_wrong']} review={policy.costs['cost_of_human_review']}) ===")
        for name, text, chunks, allowed in CASES:
            v = cp.verify(text, use_case, retrieved_chunks=chunks, allowed_chunk_ids=allowed,
                          usage=USAGE, model="claude-sonnet-5", provider="anthropic")
            cats = ",".join(sorted({t["category"] for t in v.triggered})) or "-"
            print(f"  {name:22s} -> {v.action.value:12s} tiers={str(v.tiers_run):9s} "
                  f"[{cats:22s}] verify={v.verification_cost_inr * 100:.4f}p "
                  f"llm={v.llm_cost_inr * 100:.2f}p")

    ok, bad = cp.audit.verify()
    print(f"\naudit chain intact: {ok}" + ("" if ok else f" (broken at line {bad})"))


if __name__ == "__main__":
    main()
