import os
import time

from ..schema import Signal, Category

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


def run(sentences, ctx, policy):
    start = time.perf_counter()
    signals = []
    checks = policy.checks(1)

    if "grounding" in checks:
        for i, (sent, score) in enumerate(zip(sentences, _grounding_scores(sentences, ctx))):
            if score > 0.0:
                signals.append(Signal(Category.GROUNDING, score, 1, None, f"sentence {i}"))

    if "safety" in checks:
        for i, score in enumerate(_safety_scores(sentences)):
            if score > 0.0:
                signals.append(Signal(Category.SAFETY, score, 1, None, f"sentence {i}"))

    elapsed = (time.perf_counter() - start) * 1000
    return signals, elapsed


def _grounding_scores(sentences, ctx):
    """Ungroundedness per sentence: 0 = supported by sources, 1 = unsupported."""
    if not sentences:
        return []
    premise = " ".join(c.get("text", "") for c in ctx.retrieved_chunks)
    if not premise:
        return [0.5] * len(sentences)

    model = _state.get("grounding")
    if model is None:
        return [_stub_grounding(s, premise) for s in sentences]

    try:
        pairs = [(premise, s) for s in sentences]
        consistency = model.predict(pairs)
        return [round(1.0 - float(c), 4) for c in consistency]
    except Exception as exc:
        print(f"[tier1] grounding inference failed ({exc}); falling back")
        return [_stub_grounding(s, premise) for s in sentences]


def _safety_scores(sentences):
    clf = _state.get("safety")
    if clf is None or not sentences:
        return [0.0] * len(sentences)
    try:
        out = clf(list(sentences))
        scores = []
        for row in out:
            worst = max((d["score"] for d in row if d["label"].lower() != "neutral"), default=0.0)
            scores.append(round(float(worst), 4))
        return scores
    except Exception:
        return [0.0] * len(sentences)


def _stub_grounding(sent, premise):
    low = premise.lower()
    words = [w.strip(".,%") for w in sent.lower().split() if len(w) > 4]
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in low)
    return round(1.0 - hits / len(words), 3)


def mode():
    return _state["mode"]
