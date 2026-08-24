"""Metrics for the eval harness.

The headline numbers are response-level: did we flag what should have been
flagged, and how often did we flag something that was fine. Accuracy is
deliberately not reported - it moves with the base rate of the test set and
tells a stakeholder nothing useful.
"""
from collections import defaultdict

CATEGORIES = ["grounding", "pii", "acl", "bias", "safety", "schema"]


def percentile(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def confusion(rows):
    tp = sum(1 for r in rows if r["should_flag"] and r["flagged"])
    fn = sum(1 for r in rows if r["should_flag"] and not r["flagged"])
    fp = sum(1 for r in rows if not r["should_flag"] and r["flagged"])
    tn = sum(1 for r in rows if not r["should_flag"] and not r["flagged"])
    return tp, fp, fn, tn


def summarize(rows):
    tp, fp, fn, tn = confusion(rows)
    catch = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    f1 = 2 * prec * catch / (prec + catch) if (prec + catch) else 0.0

    lat = [r["latency_ms"] for r in rows]
    ver = [r["verification_cost_inr"] for r in rows]
    llm = [r["llm_cost_inr"] for r in rows]

    return {
        "n": len(rows),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "catch_rate": catch,
        "false_positive_rate": fpr,
        "precision": prec,
        "f1": f1,
        "escalation_rate": sum(1 for r in rows if r["action"] == "escalate") / len(rows),
        "block_rate": sum(1 for r in rows if r["action"] == "block") / len(rows),
        "tier2_rate": sum(1 for r in rows if 2 in r["tiers_run"]) / len(rows),
        "latency_p50_ms": percentile(lat, 50),
        "latency_p95_ms": percentile(lat, 95),
        "latency_p99_ms": percentile(lat, 99),
        "verification_cost_total_inr": sum(ver),
        "verification_cost_mean_inr": sum(ver) / len(rows),
        "llm_cost_total_inr": sum(llm),
        "verification_overhead_pct": (100 * sum(ver) / sum(llm)) if sum(llm) else 0.0,
    }


def per_category(rows):
    """Recall per category, plus how often a category fires on cases not
    labelled with it. Grounding co-fires on PII and bias cases by design - a
    response that leaks an identifier is usually also unsupported by the
    sources - so co-fire is reported separately from false positives."""
    out = {}
    for cat in CATEGORIES:
        labelled = [r for r in rows if cat in r["labels"]]
        unlabelled = [r for r in rows if cat not in r["labels"]]
        hit = sum(1 for r in labelled if cat in r["triggered_categories"])
        cofire = sum(1 for r in unlabelled if cat in r["triggered_categories"])
        if not labelled and not cofire:
            continue
        out[cat] = {
            "labelled": len(labelled),
            "recall": hit / len(labelled) if labelled else None,
            "cofire_on_unlabelled": cofire,
            "cofire_rate": cofire / len(unlabelled) if unlabelled else 0.0,
        }
    return out


def per_kind(rows):
    buckets = defaultdict(list)
    for r in rows:
        buckets[r["kind"]].append(r)
    out = {}
    for kind, rs in sorted(buckets.items()):
        caught = sum(1 for r in rs if r["flagged"])
        expected = rs[0]["should_flag"]
        out[kind] = {
            "n": len(rs),
            "should_flag": expected,
            "flagged": caught,
            "correct": caught if expected else len(rs) - caught,
            "rate": (caught if expected else len(rs) - caught) / len(rs),
        }
    return out
