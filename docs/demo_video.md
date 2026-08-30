# Demo video script

The technical walkthrough — the video a judge opens second, to check the
thing is real. The pitch is `docs/pitch_video.md`; record that one first.

Three minutes. Everything below is a real command with real output — nothing is
staged, and the recording should show the terminal.

Set up before recording:

    source .venv/bin/activate
    python3 load_models.py          # so tier 1 is real on camera
    # .env has OPENAI_API_KEY

---

## 0:00 — The gap (20s)

*Slide or voiceover, no terminal.*

> An enterprise runs AI across customer support, an internal copilot, and a
> decision tool inside a regulated workflow. Each one can be confidently wrong,
> quietly expensive, or subtly biased. The response reaches the user in two
> seconds. The review reaches the enterprise in two weeks.

## 0:20 — One response, three verdicts (40s)

    python3 demo/run_pipeline.py --models

Point at these three lines:

```
hallucinated number  customer_support  -> regenerate
                     internal_copilot  -> annotate
                     decision_support  -> escalate
```

> Same input, three answers. Nothing in the Python knows what a use case is —
> risk appetite, latency budget and thresholds are all YAML.

Then point at the multi-label line:

```
pii + hallucination  -> block  [grounding,pii]
```

> One response flagged as both a privacy event and a hallucination. The brief
> says these overlap. They do, and the verdict keeps both.

And the cost column:

> Verification on the clean path costs effectively nothing. Only the genuinely
> uncertain response pays for a judge.

## 1:00 — Verification beside the stream (35s)

    python3 demo/run_streaming.py --models

> Sentences are checked as they complete, while the model is still writing the
> next one. The verdict is ready when the last token is.
>
> The judge is different — 1.3 to 3 seconds, against a 300 millisecond budget.
> It cannot run inline, so it runs after the stream and the gateway labels a
> late verdict advisory rather than applied. Calling it enforcement would be a
> lie.

## 1:35 — The evidence (50s)

    cat eval/results/report.md      # or show it rendered

Show the headline table:

| config | catch | FP | tier 2 | p95 | cost |
|---|---|---|---|---|---|
| the cascade | 94.6% | 7.4% | 2.8% | 175 ms | Rs 1.10 |
| judge on everything | 92.4% | 14.8% | 100% | 5534 ms | Rs 30.01 |

> Higher catch rate than judging every response — 94.6 against 92.4 — at under
> four percent of the cost, half the false positives, thirty-two times faster.
> 319 labelled cases against a live judge; one call in 328 fell back, and the
> report says so.

Then scroll to the weaknesses section:

> And here is what it cannot do. Multi-hop claims, three of nine. Quantifier
> flips, eight of fifteen. One policy is over its own latency budget. We
> wrote this test set ourselves — an earlier version scored a hundred percent on
> everything, which is why the adversarial cases exist.

## 2:10 — What the judge is for (20s)

    python3 demo/run_judge.py --live

> Tier 2 runs on under three percent of responses — the ones tier 1 is
> genuinely unsure about. Here it is on those: it changed three verdicts, all
> three corrections, and it says why. "Source requires sign-off only for claims
> above five lakh, not claims up to it." That is the quantifier flip tier 1
> misses half the time.

## 2:25 — The loop closing (25s)

    python3 demo/run_feedback.py

> Reviewed cases retune thresholds using the same economics the router uses. It
> found that decision support escalates thirty-two percent of traffic against
> its own twenty percent cap — and it reports that instead of quietly moving the
> threshold, because the fix is more reviewers or more accepted risk, and that
> is a business decision.

Show the audit line:

```
audit chain intact: True
human reviews are in the audit chain too: 614 entries
```

## 2:50 — Close (10s)

> Verification costs about five thousand rupees a year at this volume. One use
> case, reviewing the twenty percent it declared it can, costs two crore.
> ControlPlane isn't a way to buy
> cheap checking — it's a way to control how much review you have to buy, and
> to justify every unit of it.

---

## If a command fails on camera

Every demo runs with no key and no models — grounding falls back to a lexical
check and the judge to an offline one, and the output says which mode it used.
Drop `--models`, keep going, and say so.
