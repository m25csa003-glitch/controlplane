import os
import re
import time

from ..schema import Signal, Category
from ..text import sentences as split_sentences

GROUNDING_MODEL = os.getenv("CP_GROUNDING_MODEL", "vectara/hallucination_evaluation_model")
SAFETY_MODEL = os.getenv("CP_SAFETY_MODEL", "unitary/toxic-bert")

_state = {"grounding": None, "safety": None, "device": None, "mode": "stub"}


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
    """Loads the real models if available. Falls back to the stub so the rest of
    the pipeline keeps working while models are still downloading."""
    device = device or pick_device()
    _state["device"] = device

    try:
        from transformers import AutoModelForSequenceClassification
        model = AutoModelForSequenceClassification.from_pretrained(
            GROUNDING_MODEL, trust_remote_code=True
        )
        model.eval()
        _state["grounding"] = model
        _state["mode"] = "hhem"
    except Exception as exc:
        print(f"[tier1] grounding model unavailable ({exc}); using stub")
        _state["mode"] = "stub"

    try:
        from transformers import pipeline
        _state["safety"] = pipeline(
            "text-classification", model=SAFETY_MODEL,
            device=0 if device == "cuda" else -1, top_k=None,
        )
    except Exception as exc:
        print(f"[tier1] safety model unavailable ({exc}); safety scores will be 0")

    return _state["mode"]


def run(text, ctx, policy, meter=None, breakdown=None):
    start = time.perf_counter()
    signals = []
    checks = policy.checks(1)
    sents = split_sentences(text)

    if "grounding" in checks:
        for sent, score in zip(sents, _grounding_scores(sents, ctx)):
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


def _grounding_scores(sents, ctx):
    """Ungroundedness per sentence: 0 = supported by sources, 1 = unsupported."""
    if not sents:
        return []
    premise = " ".join(c.get("text", "") for c in ctx.retrieved_chunks)
    if not premise:
        return [0.5] * len(sents)

    model = _state.get("grounding")
    if model is None:
        return [_stub_grounding(s.text, premise) for s in sents]

    try:
        pairs = [(premise, s.text) for s in sents]
        consistency = model.predict(pairs)
        return [round(1.0 - float(c), 4) for c in consistency]
    except Exception as exc:
        print(f"[tier1] grounding inference failed ({exc}); falling back")
        return [_stub_grounding(s.text, premise) for s in sents]


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


def _stub_grounding(sent, premise):
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
