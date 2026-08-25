"""What tier 2 is for, and whether it earns its cost.

    python3 demo/run_judge.py            offline judge, no key needed
    python3 demo/run_judge.py --live     real judge, costs a few paise

Tier 2 runs on 2.8% of responses. This finds that 2.8% and shows what happens
inside it: what tier 1 scored, what the judge said and why, and whether the
judge changed the answer for better or worse.

The cases that land in the band are not random. They are the ones tier 1 is
worst at - multi-hop claims, quantifier flips, hedged-but-correct statements.
The band is doing its job if it selects exactly those.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane
from controlplane.schema import Category, RequestContext
from controlplane.text import sentences
from controlplane.tiers import tier1_classifiers

DATASET = Path(__file__).resolve().parents[1] / "eval" / "datasets" / "controlplane_eval_v1.jsonl"


def find_in_band(cp, cases):
    """Responses tier 1 is genuinely unsure about — the only ones tier 2 sees."""
    out = []
    for c in cases:
        policy = cp.policies[c["use_case"]]
        lo, hi = policy.band()
        combine = policy.tiers.get("tier1", {}).get("combine_sources", True)
        ctx = RequestContext(request_id="scan", use_case=c["use_case"],
                             retrieved_chunks=c["chunks"])
        sents = sentences(c["response"])
        for s, score in zip(sents, tier1_classifiers._grounding_scores(sents, ctx, combine)):
            if lo <= score < hi:
                out.append((c, round(score, 3), s.text))
                break
    return out


def main():
    live = "--live" in sys.argv
    if not live:
        for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CP_API_KEY"):
            os.environ.pop(k, None)

    print("loading tier 1 models ...", flush=True)
    tier1_classifiers.load_models()
    print(f"tier 1: {tier1_classifiers.describe()}")
    print(f"judge:  {'live API' if live else 'offline (pass --live for the real one)'}\n")

    cases = [json.loads(l) for l in DATASET.open() if l.strip()]
    cp = ControlPlane(audit_path="demo/audit_judge.jsonl")

    in_band = find_in_band(cp, cases)
    print(f"{len(in_band)} of {len(cases)} responses land inside an uncertainty "
          f"band ({len(in_band) / len(cases):.1%}) — these are the only ones "
          f"that reach tier 2.\n")

    flips = corrected = broke = 0
    for c, t1_score, claim in in_band:
        v = cp.verify(c["response"], c["use_case"], retrieved_chunks=c["chunks"],
                      allowed_chunk_ids=set(c["allowed_chunk_ids"]) if c["allowed_chunk_ids"] else None)
        judged = [s for s in v.signals if s.tier == 2 and s.category == Category.GROUNDING]
        if not judged:
            continue
        j = max(judged, key=lambda s: s.score)

        # Would tier 1 alone have flagged it? Compare against what the judge
        # decided, then against the truth.
        lo = cp.policies[c["use_case"]].band()[0]
        t1_flag = t1_score >= lo
        final_flag = v.action.value != "pass"
        moved = t1_flag != final_flag
        right = final_flag == c["should_flag"]
        if moved:
            flips += 1
            corrected += right
            broke += (not right)

        mark = "=" if not moved else ("+" if right else "-")
        print(f"[{mark}] {c['kind']:24s} {c['use_case']}")
        print(f"    claim      {claim[:88]}")
        print(f"    tier 1     {t1_score:.2f} uncertain")
        print(f"    judge      {j.score:.2f}  {j.detail[:96]}")
        print(f"    verdict    {v.action.value}   truth: "
              f"{'should flag' if c['should_flag'] else 'should pass'}"
              f"   cost {v.verification_cost_inr * 100:.3f}p")
        print()

    print(f"tier 2 changed the verdict on {flips} of {len(in_band)}: "
          f"{corrected} corrected, {broke} broken")
    print("[+] judge fixed tier 1   [-] judge made it worse   [=] agreed")
    ok, bad = cp.audit.verify()
    print(f"\naudit chain intact: {ok}" + ("" if ok else f" (broken at line {bad})"))


if __name__ == "__main__":
    main()
