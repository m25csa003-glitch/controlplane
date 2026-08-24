"""Generates the labelled eval set.

Deterministic: same seed, same file. Labels come from how a case was built, not
from anyone's reading of it, which is the only reason the metrics mean anything.

    python3 eval/build_dataset.py
"""
import json
import re
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.corpus import (USE_CASES, PII_SAMPLES, BIAS_BENIGN, BIAS_DECISION,
                         SAFETY, REFUSALS)
from eval.corpus_hard import HARD, MULTI_HOP, NUMERALS, UNITS

OUT = Path(__file__).resolve().parent / "datasets" / "controlplane_eval_v1.jsonl"
SEED = 20260825


def chunks_for(facts):
    return [{"id": f["id"], "text": f["text"]} for f in facts]


def case(cid, use_case, response, facts, labels, should_flag, kind, note="",
         allowed=None):
    return {
        "id": cid,
        "use_case": use_case,
        "response": response,
        "chunks": chunks_for(facts),
        "allowed_chunk_ids": allowed,
        "labels": sorted(labels),
        "should_flag": should_flag,
        "kind": kind,
        "note": note,
    }


def build():
    rng = random.Random(SEED)
    rows = []

    for use_case, facts in USE_CASES.items():
        tag = {"customer_support": "cs", "internal_copilot": "ic",
               "decision_support": "ds"}[use_case]
        n = 0

        def add(response, labels, should_flag, kind, note="", allowed=None):
            nonlocal n
            n += 1
            rows.append(case(f"{tag}-{n:04d}", use_case, response, facts,
                             labels, should_flag, kind, note, allowed))

        # --- clean: the model did its job -----------------------------
        for f in facts:
            add(f["text"], [], False, "grounded_exact",
                "verbatim restatement of the source")

        for f in facts:
            for p in f["paraphrases"]:
                add(p, [], False, "grounded_paraphrase",
                    "faithful restatement in different words")

        for r in REFUSALS:
            add(r, [], False, "refusal",
                "correct abstention; shares few words with the sources")

        for f in facts[:3]:
            a, b = facts[0], f
            add(f"{a['text']} {b['text']}", [], False, "multi_fact_grounded",
                "two sources combined, both faithful")

        # The statement is added to its own sources so this measures the bias
        # check in isolation. Otherwise grounding fires - correctly - because
        # the sentence is not in the policy chunks, and the case stops testing
        # what it was written to test.
        for b in BIAS_BENIGN:
            n += 1
            rows.append({
                "id": f"{tag}-{n:04d}", "use_case": use_case, "response": b,
                "chunks": chunks_for(facts) + [{"id": "ctx-1", "text": b}],
                "allowed_chunk_ids": None, "labels": [], "should_flag": False,
                "kind": "bias_benign",
                "note": "protected attribute mentioned with no decision attached",
            })

        # --- hallucination --------------------------------------------
        for f in facts:
            frm, to = f["swap"]
            add(f["text"].replace(frm, to), ["grounding"], True, "number_swap",
                f"source says '{frm}', response says '{to}'")

        for f in facts:
            add(f["fabricated"], ["grounding"], True, "fabricated_clause",
                "invents an entitlement absent from the sources")

        for f in facts:
            add(f["extrapolation"], ["grounding"], True, "unsupported_extrapolation",
                "plausible, related, not stated in the sources")

        for f in facts:
            add(f["entity"], ["grounding"], True, "entity_fabrication",
                "specific fact about a named person, not in the sources")

        # --- privacy ---------------------------------------------------
        for p in PII_SAMPLES:
            add(p, ["pii"], True, "pii_leak", "identifier in the response")

        for f in facts[:4]:
            frm, to = f["swap"]
            bad = f["text"].replace(frm, to)
            add(f"{bad} Please confirm on 9876543210.",
                ["grounding", "pii"], True, "pii_plus_hallucination",
                "wrong number and an identifier in one response")

        # --- access control --------------------------------------------
        for f in facts[1:5]:
            add(f["text"], ["acl"], True, "acl_breach",
                f"answer drawn from {f['id']}, which this user may not read",
                allowed=[facts[0]["id"]])

        # --- bias ------------------------------------------------------
        for b in BIAS_DECISION:
            add(b, ["bias"], True, "bias_decision",
                "protected attribute driving an outcome")

        # --- safety ----------------------------------------------------
        for s in SAFETY:
            add(s, ["safety"], True, "safety", "abusive language toward a person")

        # --- adversarial -----------------------------------------------
        for f in facts:
            for kind, (text, flag) in HARD.get(f["id"], {}).items():
                add(text, ["grounding"] if flag else [], flag, kind,
                    f"derived from {f['id']}")

        for text, source_ids in MULTI_HOP.get(use_case, []):
            add(text, [], False, "multi_hop",
                f"true only by combining {' and '.join(source_ids)}")

        for f in facts:
            spelled = f["text"]
            for digit, word in NUMERALS.items():
                spelled = re.sub(rf"\b{digit}\b", word, spelled)
            if spelled != f["text"]:
                add(spelled, [], False, "numeral_synonym",
                    "same figures written as words")

            for unit, wrong in UNITS:
                if unit in f["text"]:
                    add(f["text"].replace(unit, wrong), ["grounding"], True,
                        "unit_swap", f"'{unit}' changed to '{wrong}'")
                    break

    rng.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return rows


def summarise(rows):
    from collections import Counter
    kinds = Counter(r["kind"] for r in rows)
    print(f"wrote {len(rows)} cases -> {OUT.relative_to(Path.cwd())}"
          if OUT.is_relative_to(Path.cwd()) else f"wrote {len(rows)} cases -> {OUT}")
    flag = sum(r["should_flag"] for r in rows)
    print(f"  should flag: {flag}  ({flag / len(rows):.0%})")
    print(f"  should pass: {len(rows) - flag}  ({1 - flag / len(rows):.0%})")
    print("\n  by kind:")
    for k, c in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f"    {k:28s} {c:4d}")


if __name__ == "__main__":
    summarise(build())
