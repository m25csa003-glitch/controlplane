import os
import re
import time

from ..schema import Signal, Category
from ..text import sentences as split_sentences

# Tried in order. The first that loads wins; if none do, grounding falls back to
# lexical overlap plus a numeric contradiction check and says so.
#
# NLI is first because it is what actually loads. Vectara's HHEM is the better
# fit on paper - it is trained for exactly this - but its tokenizer cannot be
# instantiated under transformers 5.x, with or without sentencepiece. It stays
# in the list so the day that is fixed, it is picked up by preference; today it
# fails in about six seconds and we fall through.
GROUNDING_MODELS = [
    ("nli", os.getenv("CP_NLI_MODEL", "cross-encoder/nli-deberta-v3-base"), False),
    ("hhem", os.getenv("CP_GROUNDING_MODEL", "vectara/hallucination_evaluation_model"), True),
]
SAFETY_MODEL = os.getenv("CP_SAFETY_MODEL", "unitary/toxic-bert")
BATCH = int(os.getenv("CP_TIER1_BATCH", "16"))

_state = {"score_pairs": None, "safety": None, "device": None, "mode": "lexical",
          "model_id": None}


def pick_device():
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_models(device=None):
    """Loads whatever is available. Every failure is survivable: the pipeline
    keeps working on the lexical fallback, which is what lets the demo run on a
    machine with no models and no network."""
    device = device or pick_device()
    _state["device"] = device

    for kind, repo, remote_code in GROUNDING_MODELS:
        fn = _load_grounding(kind, repo, remote_code, device)
        if fn:
            _state["score_pairs"] = fn
            _state["mode"] = kind
            _state["model_id"] = repo
            break
    else:
        print("[tier1] no grounding model loaded; using lexical fallback")
        _state["mode"] = "lexical"

    try:
        from transformers import pipeline
        _state["safety"] = pipeline(
            "text-classification", model=SAFETY_MODEL,
            device=0 if device == "cuda" else -1, top_k=None,
        )
    except Exception as exc:
        print(f"[tier1] safety model unavailable ({exc}); safety scores will be 0")

    return _state["mode"]


def _load_grounding(kind, repo, remote_code, device):
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        model = AutoModelForSequenceClassification.from_pretrained(
            repo, trust_remote_code=remote_code)
        model.eval()

        if kind == "hhem" and hasattr(model, "predict"):
            def score_pairs(pairs):
                # HHEM returns consistency: 1 means the claim follows from the
                # premise. We report the opposite.
                out = model.predict(pairs)
                return [round(1.0 - float(c), 4) for c in out]
            return score_pairs

        entail = _entail_index(model.config)
        if entail is None:
            print(f"[tier1] {repo} has no entailment label; skipping")
            return None

        tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=remote_code)
        model.to(device if device != "mps" else "mps")

        def score_pairs(pairs):
            scores = []
            for i in range(0, len(pairs), BATCH):
                chunk = pairs[i:i + BATCH]
                enc = tok([p for p, _ in chunk], [h for _, h in chunk],
                          return_tensors="pt", padding=True, truncation=True,
                          max_length=512).to(model.device)
                with torch.no_grad():
                    probs = torch.softmax(model(**enc).logits, dim=-1)
                scores += [round(1.0 - float(p[entail]), 4) for p in probs]
            return scores

        return score_pairs
    except Exception as exc:
        print(f"[tier1] {repo} unavailable ({exc})")
        return None


def _entail_index(config):
    for i, name in (getattr(config, "id2label", None) or {}).items():
        if "entail" in str(name).lower():
            return int(i)
    return None


def run(text, ctx, policy, meter=None, breakdown=None):
    start = time.perf_counter()
    signals = []
    checks = policy.checks(1)
    sents = split_sentences(text)

    combine = policy.tiers.get("tier1", {}).get("combine_sources", True)
    if "grounding" in checks:
        for sent, score in zip(sents, _grounding_scores(sents, ctx, combine)):
            if score > 0.0:
                signals.append(Signal(Category.GROUNDING, score, 1, sent.span, sent.text[:80]))

    if "safety" in checks:
        for sent, score in zip(sents, _safety_scores([s.text for s in sents])):
            if score > 0.0:
                signals.append(Signal(Category.SAFETY, score, 1, sent.span, sent.text[:80]))

    if "bias" in checks:
        for sent in sents:
            score, detail = _bias_score(sent.text)
            if score > 0.0:
                signals.append(Signal(Category.BIAS, score, 1, sent.span, detail))

    elapsed = (time.perf_counter() - start) * 1000
    if meter is not None and breakdown is not None:
        breakdown.add(meter.compute_time("tier1_inference", elapsed, label="tier1"))
    return signals, elapsed


def _grounding_scores(sents, ctx, combine=True):
    """Ungroundedness per sentence: 0 = supported by sources, 1 = unsupported.

    combine adds the joined premise as an extra candidate. It roughly halves the
    false positive rate and rescues multi-hop claims, and it roughly doubles
    tier 1 latency. Which is why it is a policy value: a 300 ms customer-support
    budget and a 3 s decision-support budget do not want the same answer."""
    if not sents:
        return []
    chunks = [c.get("text", "") for c in ctx.retrieved_chunks if c.get("text")]
    if not chunks:
        return [0.5] * len(sents)
    premise = " ".join(chunks)

    # An abstention asserts nothing, so there is nothing to ground. Scoring it
    # against the sources is how a checker ends up punishing the model for the
    # one behaviour we want when the answer is not in the documents.
    scored = [None if ABSTAIN.search(s.text) else s for s in sents]
    live = [s for s in scored if s is not None]

    fn = _state.get("score_pairs")
    if fn is None or not live:
        return [0.0 if s is None else _stub_grounding(s.text, premise) for s in scored]

    try:
        # Each claim is scored against each chunk separately and keeps its best
        # match. A claim is grounded if any one source supports it - scoring it
        # against every source glued together instead makes an entailment model
        # read one long unrelated passage and call a good answer unsupported.
        #
        # The joined premise is kept as one extra candidate rather than dropped,
        # because a claim can be true only by combining two chunks and match
        # neither alone. Per-chunk alone scored every such claim at 0.99.
        premises = chunks + ([premise] if combine and len(chunks) > 1 else [])
        values = fn([(p, s.text) for s in live for p in premises])
        n = len(premises)
        best = [min(values[i * n:(i + 1) * n]) for i in range(len(live))]
        it = iter(best)
        return [0.0 if s is None else next(it) for s in scored]
    except Exception as exc:
        print(f"[tier1] grounding inference failed ({exc}); falling back")
        return [0.0 if s is None else _stub_grounding(s.text, premise) for s in scored]


def _safety_scores(texts):
    clf = _state.get("safety")
    if clf is None or not texts:
        return [0.0] * len(texts)
    try:
        out = clf(list(texts))
        scores = []
        for row in out:
            worst = max((d["score"] for d in row if d["label"].lower() != "neutral"), default=0.0)
            scores.append(round(float(worst), 4))
        return scores
    except Exception:
        return [0.0] * len(texts)


NUM = re.compile(r"\d+(?:\.\d+)?")

ABSTAIN = re.compile(
    r"(i (?:could not|couldn't|cannot|can't|do not|don't|am not able to|would rather not)"
    r"|not (?:covered|mentioned|available|found|stated) in the (?:document|policy|source|wording)"
    r"|documents?(?: available to me)? do not mention"
    r"|no source for that"
    r"|please check with)",
    re.I,
)


def _stub_grounding(sent, premise):
    """Lexical fallback for when no grounding model is loaded.

    Numbers are checked apart from words. Swapping one figure for another is the
    most common and most expensive hallucination in a policy answer, and it
    barely moves a bag-of-words score - every other word still matches."""
    src_nums = set(NUM.findall(premise))
    novel = set(NUM.findall(sent)) - src_nums
    if novel and src_nums:
        return 0.9

    low = premise.lower()
    words = [w.strip(".,%") for w in sent.lower().split() if len(w) > 4]
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in low)
    return round(1.0 - hits / len(words), 3)


# --- bias ---------------------------------------------------------------
# Round 2 puts counterfactual probing out of scope, so this is the shallow
# version: a protected attribute is only a bias signal when the sentence also
# carries decision or generalisation language. Mentioning a group is not bias;
# deciding something about a person because of the group is. Limits are written
# up in docs/assumptions.md.

PROTECTED = re.compile(
    r"\b(wom[ae]n|m[ae]n|male|female|girl|boy|"
    r"muslim|hindu|christian|sikh|jain|buddhist|dalit|brahmin|caste|"
    r"black|white|asian|african|hispanic|latino|"
    r"young|elderly|old(?:er)?|aged|disabled|handicapped|pregnant|"
    r"married|unmarried|widow(?:ed)?|"
    r"immigrant|foreigner|refugee|tribal|minority)\b",
    re.I,
)

GENERALISATION = re.compile(
    r"\b(all|every|most|typically|usually|generally|tend to|always|never|"
    r"naturally|inherently|by nature|less likely|more likely|prone to|"
    r"not suited|unsuitable|incapable|unreliable|risky)\b",
    re.I,
)

DECISION = re.compile(
    r"\b(reject|deny|denied|decline|approve|approved|ineligible|eligible|"
    r"disqualif\w+|prioritis\w+|prioritiz\w+|recommend|score|rate|premium|"
    r"interest rate|credit limit|should not|cannot be|will not be)\b",
    re.I,
)


def _bias_score(sent):
    attr = PROTECTED.search(sent)
    if not attr:
        return 0.0, ""
    found = attr.group(0)
    gen = GENERALISATION.search(sent)
    dec = DECISION.search(sent)

    if dec and gen:
        return 0.9, f"decision '{dec.group(0)}' tied to '{found}' with generalisation"
    if dec:
        return 0.75, f"decision '{dec.group(0)}' mentions protected attribute '{found}'"
    if gen:
        return 0.6, f"generalisation '{gen.group(0)}' about '{found}'"
    return 0.15, f"protected attribute '{found}' mentioned, no decision language"


def mode():
    return _state["mode"]


def describe():
    return {"mode": _state["mode"], "model": _state["model_id"],
            "device": _state["device"], "safety": bool(_state["safety"])}
