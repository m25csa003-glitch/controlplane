"""Runs the eval set through several configurations and writes a report.

    python3 eval/run_eval.py

Configurations compared:
  tier0_only        deterministic rules, no models at all
  tier1_no_judge    rules plus classifiers, never escalate to a judge
  cascade           what the product actually does
  judge_everything  a judge call on every sentence of every response

The last one is the baseline the cost claim rests on. It is the honest
comparison: not "we are cheap" but "we are this much cheaper than checking
everything the obvious way, and here is what that costs in catch rate".
"""
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from controlplane.pipeline import ControlPlane
from controlplane.cost.meter import DEMO_UPSTREAM
from controlplane.policy.loader import Policy
from controlplane.tiers import tier1_classifiers, tier2_judge
from eval.metrics import summarize, per_category, per_kind

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "eval" / "datasets" / "controlplane_eval_v1.jsonl"
RESULTS = ROOT / "eval" / "results"

# Illustrative upstream usage per response, so verification cost has something
# to be a percentage of. Stated in docs/assumptions.md.
USAGE = {"prompt_tokens": 820, "completion_tokens": 95}
UPSTREAM_MODEL, UPSTREAM_PROVIDER = DEMO_UPSTREAM


def disable(raw, *tiers):
    for t in tiers:
        raw["tiers"][f"tier{t}"]["enabled"] = False
    return raw


CONFIGS = {
    "tier0_only": {"mutate": lambda raw: disable(raw, 1, 2), "audit_mode": False},
    "tier1_no_judge": {"mutate": lambda raw: disable(raw, 2), "audit_mode": False},
    "cascade": {"mutate": lambda raw: raw, "audit_mode": False},
    "judge_everything": {"mutate": lambda raw: raw, "audit_mode": True},
}


def load_cases():
    if not DATASET.exists():
        sys.exit("dataset missing. Run: python3 eval/build_dataset.py")
    with DATASET.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def make_plane(mutate, audit_path):
    cp = ControlPlane(audit_path=str(audit_path))
    cp.policies = {
        name: Policy(mutate(copy.deepcopy(p.raw)))
        for name, p in cp.policies.items()
    }
    return cp


def run_config(name, cfg, cases):
    audit_path = RESULTS / f"audit_{name}.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    cp = make_plane(cfg["mutate"], audit_path)
    tier2_judge.reset_stats()

    rows = []
    started = time.perf_counter()
    for c in cases:
        v = cp.verify(
            c["response"], c["use_case"],
            retrieved_chunks=c["chunks"],
            allowed_chunk_ids=set(c["allowed_chunk_ids"]) if c["allowed_chunk_ids"] else None,
            usage=USAGE, model=UPSTREAM_MODEL, provider="anthropic",
            audit_mode=cfg["audit_mode"],
        )
        rows.append({
            "id": c["id"],
            "use_case": c["use_case"],
            "kind": c["kind"],
            "labels": c["labels"],
            "should_flag": c["should_flag"],
            "action": v.action.value,
            "flagged": v.action.value != "pass",
            "triggered_categories": sorted({t["category"] for t in v.triggered}),
            "tiers_run": v.tiers_run,
            "latency_ms": v.latency_ms,
            "verification_cost_inr": v.verification_cost_inr,
            "llm_cost_inr": v.llm_cost_inr,
        })
    wall = time.perf_counter() - started
    chain_ok, _ = cp.audit.verify()
    return rows, wall, chain_ok, tier2_judge.stats()


def sweep(cases, points=13):
    """Tier 1 sensitivity curve. Collapsing the band to a single threshold
    removes the judge, so this is the operating curve the cascade improves on -
    it is what you get if you have to pick one number and live with it."""
    out = []
    for i in range(points):
        t = round(0.05 + i * (0.90 / (points - 1)), 3)

        def mutate(raw, t=t):
            raw["tiers"]["tier1"]["uncertainty_band"] = [t, t]
            raw["tiers"]["tier2"]["enabled"] = False
            return raw

        rows, *_ = run_config(f"sweep_{t}", {"mutate": mutate, "audit_mode": False}, cases)
        s = summarize(rows)
        out.append({"threshold": t,
                    "catch_rate": s["catch_rate"],
                    "false_positive_rate": s["false_positive_rate"],
                    "precision": s["precision"]})
        (RESULTS / f"audit_sweep_{t}.jsonl").unlink(missing_ok=True)
    return out


BANDS = [(0.5, 0.5), (0.4, 0.6), (0.3, 0.7), (0.25, 0.75), (0.2, 0.8),
         (0.1, 0.9), (0.05, 0.95), (0.0, 1.01)]


def band_sweep(cases):
    """Widen the uncertainty band and watch what tier 2 buys.

    At the configured band the judge runs on a few percent of responses and
    changes nothing, which reads as the cascade not earning its keep. The
    question is whether any band does, and at what price. This answers it with
    a curve instead of an opinion."""
    out = []
    for lo, hi in BANDS:
        def mutate(raw, lo=lo, hi=hi):
            raw["tiers"]["tier1"]["uncertainty_band"] = [lo, hi]
            return raw

        name = f"band_{lo}_{hi}"
        rows, *_ = run_config(name, {"mutate": mutate, "audit_mode": False}, cases)
        s = summarize(rows)
        out.append({"band": f"[{lo}, {hi}]",
                    "catch_rate": s["catch_rate"],
                    "false_positive_rate": s["false_positive_rate"],
                    "tier2_rate": s["tier2_rate"],
                    "cost_inr": s["verification_cost_total_inr"]})
        (RESULTS / f"audit_{name}.jsonl").unlink(missing_ok=True)
    return out


def pct(x):
    return f"{100 * x:.1f}%"


def write_report(results, sweep_rows, band_rows, cases, meta):
    RESULTS.mkdir(parents=True, exist_ok=True)
    L = []
    L.append("# ControlPlane evaluation\n")
    L.append(f"Generated {meta['generated']}  \n")
    L.append(f"Dataset: `{DATASET.name}`, {len(cases)} cases  \n")
    L.append(f"Tier 1 grounding mode: **{meta['tier1_mode']}**  \n")
    L.append(f"Tier 2 judge: **{meta['judge_mode']}**  \n")
    L.append(f"Upstream priced as: **{UPSTREAM_MODEL}** — the cost column is a "
             f"percentage of this, so it moves if the application runs a "
             f"different model.\n")
    L.append("\n> Every case is synthetic and labelled by construction. "
             "Numbers describe this set only.\n")

    L.append("\n## Headline\n")
    L.append("| config | catch rate | false positive rate | precision | F1 | tier 2 rate | p95 latency | verify cost (total) | verify as % of LLM spend |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for name, r in results.items():
        s = r["summary"]
        L.append(f"| `{name}` | {pct(s['catch_rate'])} | {pct(s['false_positive_rate'])} | "
                 f"{pct(s['precision'])} | {pct(s['f1'])} | {pct(s['tier2_rate'])} | "
                 f"{s['latency_p95_ms']:.2f} ms | Rs {s['verification_cost_total_inr']:.4f} | "
                 f"{s['verification_overhead_pct']:.3f}% |")

    base = results.get("judge_everything", {}).get("summary")
    casc = results.get("cascade", {}).get("summary")
    if base and casc and base["verification_cost_total_inr"]:
        ratio = casc["verification_cost_total_inr"] / base["verification_cost_total_inr"]
        L.append(f"\n**Cascade costs {pct(ratio)} of judging everything**, "
                 f"at {pct(casc['catch_rate'])} catch rate against "
                 f"{pct(base['catch_rate'])}. Tier 2 ran on "
                 f"{pct(casc['tier2_rate'])} of responses.\n")

    solo = results.get("tier1_no_judge", {}).get("summary")
    if base and casc and solo:
        same = (round(casc["catch_rate"], 4) == round(solo["catch_rate"], 4)
                and round(casc["false_positive_rate"], 4) == round(solo["false_positive_rate"], 4))
        if same:
            L.append(f"\n**Tier 2 changed no decisions on this set.** It ran on "
                     f"{pct(casc['tier2_rate'])} of responses and cost "
                     f"Rs {casc['verification_cost_total_inr'] - solo['verification_cost_total_inr']:.2f} "
                     "to reach the same verdicts tier 1 already had. Two things "
                     "follow: the uncertainty band is currently too narrow to "
                     "catch the cases that would benefit, and the offline judge "
                     "is not strong enough to overturn tier 1 anyway. The band "
                     "is a policy value, so this is a tuning result, not a code "
                     "change — but it is not yet earning its cost.\n")

    L.append("\n## Where the errors are\n")
    for name, r in results.items():
        s = r["summary"]
        L.append(f"\n### `{name}`\n")
        L.append(f"true pos {s['tp']} · false pos {s['fp']} · "
                 f"false neg {s['fn']} · true neg {s['tn']}\n")
        L.append("\n| category | labelled | recall | co-fires on unlabelled |")
        L.append("|---|---|---|---|")
        for cat, c in r["per_category"].items():
            rec = pct(c["recall"]) if c["recall"] is not None else "-"
            L.append(f"| {cat} | {c['labelled']} | {rec} | {c['cofire_on_unlabelled']} ({pct(c['cofire_rate'])}) |")

    L.append("\n## By case type — cascade\n")
    L.append("| case type | n | expected | correct | rate |")
    L.append("|---|---|---|---|---|")
    for kind, k in results["cascade"]["per_kind"].items():
        L.append(f"| {kind} | {k['n']} | {'flag' if k['should_flag'] else 'pass'} | "
                 f"{k['correct']} | {pct(k['rate'])} |")

    L.append("\n## Over-flagging against under-flagging\n")
    L.append("Tier 1 alone, threshold swept. The brief asks for this tradeoff to "
             "be exposed rather than claimed solved, so here it is.\n")
    L.append("\n| threshold | catch rate | false positive rate | precision |")
    L.append("|---|---|---|---|")
    for s in sweep_rows:
        L.append(f"| {s['threshold']:.2f} | {pct(s['catch_rate'])} | "
                 f"{pct(s['false_positive_rate'])} | {pct(s['precision'])} |")

    L.append("\n## What tier 2 buys, by band width\n")
    L.append("`[0.5, 0.5]` is an empty band, so the judge never runs. "
             "`[0.0, 1.01]` sends everything tier 1 flagged at all.\n")
    L.append("\n| band | tier 2 rate | catch rate | false positive rate | verify cost |")
    L.append("|---|---|---|---|---|")
    for b in band_rows:
        L.append(f"| `{b['band']}` | {pct(b['tier2_rate'])} | {pct(b['catch_rate'])} | "
                 f"{pct(b['false_positive_rate'])} | Rs {b['cost_inr']:.2f} |")

    L.append("\n## Latency against the policy budget\n")
    L.append("`latency_budget_ms` is the ceiling each policy sets on added "
             "latency for the clean path. p95 below is measured across all "
             "responses in that use case, judge calls included.\n")
    L.append("\n| use case | budget | p95 measured | p95 when tier 2 ran | verdict |")
    L.append("|---|---|---|---|---|")
    for uc, budget in meta["budgets"].items():
        rows_uc = [r for r in results["cascade"]["rows"] if r["use_case"] == uc]
        if not rows_uc:
            continue
        from eval.metrics import percentile
        p95 = percentile([r["latency_ms"] for r in rows_uc], 95)
        judged = [r["latency_ms"] for r in rows_uc if 2 in r["tiers_run"]]
        p95j = percentile(judged, 95) if judged else None
        over = (p95j or p95) > budget
        L.append(f"| {uc} | {budget} ms | {p95:.0f} ms | "
                 f"{f'{p95j:.0f} ms' if p95j is not None else 'n/a'} | "
                 f"{'**over budget**' if over else 'within budget'} |")
    L.append("\nA judge call is 1.3 s on the cheap model and 3.1 s on the "
             "strong one. No amount of tuning fits that inside a 300 ms "
             "customer-support budget. Tier 2 is therefore not an inline step "
             "for a latency-bound use case - it has to run beside the response "
             "or after it, which is what the streaming path has to solve. The "
             "clean path, where tier 2 does not run at all, stays inside "
             "budget; it is only the escalated few percent that blow it.\n")

    L.append("\n## Judge calls\n")
    L.append("A judge call that fails falls back to the offline judge silently. "
             "If `failed` is not zero, the numbers above are a blend of two "
             "different judges and should not be read as an API result.\n")
    L.append("\n| config | api calls | failed | offline |")
    L.append("|---|---|---|---|")
    for name, r in results.items():
        j = r.get("judge_stats", {})
        L.append(f"| `{name}` | {j.get('api_calls', 0)} | {j.get('api_failures', 0)} | {j.get('offline', 0)} |")

    L.append("\n## Audit chain\n")
    for name, r in results.items():
        L.append(f"- `{name}`: chain intact = **{r['chain_ok']}** ({r['n']} records)")

    L.append("\n## Reading this honestly\n")
    if meta["tier1_mode"] == "lexical":
        L.append("- Tier 1 grounding ran on the **lexical fallback**, not a "
                 "trained model: word overlap plus a numeric contradiction "
                 "check. Treat grounding recall as a floor, not a result.\n")
    else:
        L.append(f"- Tier 1 grounding ran on **{meta['tier1_model']}** "
                 f"(`{meta['tier1_mode']}`) on {meta['device']}.\n")
    if meta["judge_mode"] == "offline":
        L.append("- Tier 2 ran its **offline** judge, not a model. The offline judge "
                 "reasons about numeric and polarity contradiction only.\n")
        L.append("- `judge_everything` is therefore not an upper bound on quality. "
                 "Its catch rate is capped by the same offline judge, and it "
                 "inherits that judge's habit of scoring paraphrase as "
                 "unsupported - which is why its false positive rate is worse "
                 "than the cascade's here. With a real judge behind a key, "
                 "expect it to beat the cascade on catch rate and still cost "
                 "roughly six times as much. The cost ratio is the durable "
                 "finding; the quality ordering is not.\n")
    if meta["safety_model"] is None:
        L.append("- No safety model is loaded, so safety recall is 0 by "
                 "construction. The safety cases are in the set to keep that "
                 "gap visible rather than hidden.\n")
    L.append("- `multi_hop` cases fail by construction. Each claim is scored "
             "against each chunk separately, which is what keeps faithful "
             "paraphrase from being flagged, but a claim that is true only by "
             "combining two chunks matches neither one alone. A judge that sees "
             "all sources at once is the right place to fix this, which is an "
             "argument for widening the band on retrieval-heavy use cases.\n")
    L.append("- The set is synthetic and was written by the same person who "
             "tuned the checker. An earlier version of it scored 100% on every "
             "case type, which is why the adversarial cases exist. Treat these "
             "numbers as a lower bound on difficulty, not an upper bound on "
             "quality.\n")
    L.append("- Base rate here is "
             f"{pct(sum(c['should_flag'] for c in cases) / len(cases))} harmful, "
             "far above production. Catch rate and false positive rate are "
             "unaffected by that; precision is not, and would fall in production.\n")

    (RESULTS / "report.md").write_text("\n".join(L) + "\n")


def main():
    if "--lexical" in sys.argv:
        print("tier 1: lexical fallback (models not loaded)")
    else:
        print("loading tier 1 models ...", end=" ", flush=True)
        tier1_classifiers.load_models()
        print(tier1_classifiers.describe())

    cases = load_cases()
    results = {}
    for name, cfg in CONFIGS.items():
        print(f"running {name} ...", end=" ", flush=True)
        rows, wall, chain_ok, jstats = run_config(name, cfg, cases)
        results[name] = {
            "summary": summarize(rows),
            "per_category": per_category(rows),
            "per_kind": per_kind(rows),
            "chain_ok": chain_ok,
            "n": len(rows),
            "wall_s": wall,
            "judge_stats": jstats,
            "rows": rows,
        }
        s = results[name]["summary"]
        print(f"catch {pct(s['catch_rate'])}  fpr {pct(s['false_positive_rate'])}  "
              f"cost Rs{s['verification_cost_total_inr']:.4f}  ({wall:.1f}s)  "
              f"judge={jstats['api_calls']}ok/{jstats['api_failures']}fail/{jstats['offline']}offline")

    print("sweeping tier 1 threshold ...", end=" ", flush=True)
    sweep_rows = sweep(cases)
    print("done")

    print("sweeping tier 2 band ...", end=" ", flush=True)
    band_rows = band_sweep(cases)
    print("done")

    import os
    described = tier1_classifiers.describe()
    meta = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "tier1_mode": described["mode"],
        "tier1_model": described["model"],
        "device": described["device"],
        "judge_mode": "api" if (os.getenv("ANTHROPIC_API_KEY") or os.getenv("CP_API_KEY")) else "offline",
        "safety_model": described["safety"],
        "budgets": {n: p.latency_budget_ms for n, p in ControlPlane().policies.items()},
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "summary.json").write_text(json.dumps(
        {"meta": meta | {"safety_model": bool(meta["safety_model"])},
         "configs": {k: v["summary"] for k, v in results.items()},
         "per_category": {k: v["per_category"] for k, v in results.items()},
         "sweep": sweep_rows,
         "band_sweep": band_rows}, indent=2))
    write_report(results, sweep_rows, band_rows, cases, meta)
    print(f"\nwrote {RESULTS / 'report.md'}")
    print(f"wrote {RESULTS / 'summary.json'}")


if __name__ == "__main__":
    main()
