# Pitch video script

This is the **pitch**. `docs/demo_video.md` is the technical walkthrough — the
one a judge opens second, to check the thing is real. Record both; lead with
this.

## How long

**Target 2:45. Hard ceiling 3:00.**

The Round 2 brief asks for a demo video without naming a length, and the team's
own Round 1 slide promised a three-minute walkthrough. Three minutes is the
convention, so going over reads as not having edited rather than as having more
to say.

The number that actually matters is not the total, it is the **first fifteen
seconds**. A judge working through a stack of submissions decides in that window
whether to watch or scrub. Everything below is built around spending those
fifteen seconds on something concrete.

Two rules that do more for retention than any amount of polish:

- **No title card.** A logo and a team name at the top is fifteen seconds spent
  on the least interesting thing in the video. Put the team name at the end.
- **Never explain what you are about to show.** "Now I'll demonstrate the policy
  layer" is dead air. Show it, then say what it was.

## The script

Timings are cumulative. Words in **bold** are the ones carrying the beat — land
them, don't rush past them.

---

### 0:00 – 0:18 · One wrong sentence

*Screen: two lines of text, nothing else.*

> The policy document says room rent is capped at **one percent**.
>
> The assistant told the customer **two percent**.

*Beat. Let both lines sit.*

> Nothing in that answer looks wrong. It is worded exactly like a correct one.
> The customer files a claim on it. We find out **two weeks later**, from a
> complaint.
>
> The model answered in two seconds. The review took two weeks. **That gap is
> the whole problem.**

*Why this opening: it is a specific sentence a specific person acts on, not a
category of risk. "Hallucination" is abstract; "one percent became two percent"
is not.*

### 0:18 – 0:35 · What we built, in one line

*Screen: the request → ControlPlane → model diagram, or just the gateway running.*

> ControlPlane closes that gap to **zero**. It sits between the application and
> the model, checks every response before it reaches anyone, and decides what to
> do about it — pass, annotate, redact, regenerate, escalate, or block.
>
> Your application changes **one line**: the base URL.

### 0:35 – 1:05 · The same answer, three different verdicts

*Screen: `python3 demo/run_pipeline.py --models`. Point at three lines.*

```
hallucinated number   customer_support  -> regenerate
                      internal_copilot  -> annotate
                      decision_support  -> escalate
```

> Same sentence. Three answers.
>
> In customer support, being wrong costs about four hundred rupees, so we ask
> the model again. In the internal copilot it costs sixty, so we flag it and
> move on. In a regulated decision it costs **fifty thousand** — so a human
> looks at it before anyone acts.
>
> Nothing in the code knows what a use case is. **All of that is a config file.**
> A new jurisdiction is a config change, not a release.

*This is the single most persuasive thirty seconds in the video. Do not rush it.*

### 1:05 – 1:35 · The number the whole design rests on

*Screen: `eval/results/report.md`, headline table.*

> Three hundred and nineteen labelled cases. Live judge model. Here is us
> against the obvious way to do this — send **every** response to a judge and
> ask if it's right.

| | catch | false positives | latency | cost |
|---|---|---|---|---|
| judge on everything | 94.6% | 15.6% | 4,071 ms | Rs 30.14 |
| **the cascade** | **94.6%** | **7.4%** | **184 ms** | **Rs 1.13** |

> Same catch rate. **Half** the false positives. **Twenty-two times** faster.
> And it costs **under four percent**.
>
> Checking everything with a big model doesn't buy you accuracy. It buys you a
> bill.

### 1:35 – 1:55 · Show it working live

*Screen: the dashboard, traffic flowing.*

> This is it running. Every response gets the cheap checks. **Under three
> percent** ever reach the judge — the ones the cheap checks were genuinely
> unsure about.
>
> And every number here is measured against a limit **that policy set for
> itself**. When customer support goes over its own latency budget, it turns
> red — nobody had to notice.

### 1:55 – 2:20 · The reframe

*Screen: the two money tiles side by side.*

> Now the part that changed how we think about this product.
>
> At the volume in the brief, verification costs about **five and a half
> thousand rupees a year**.
>
> The human review it generates, for **one** use case, costs **three point three
> six crore**.

*Beat.*

> Verification was never the expensive part. **Human attention is.**
>
> So this isn't a way to buy cheap checking. It's a way to control **how much
> review you have to buy** — and to justify every hour of it. Moving the
> escalation rate by one percentage point is worth more than the entire
> verification bill.

*This is the strongest thing in the pitch. It is a genuine insight, it came out
of the measurement, and almost no one else will say it.*

### 2:20 – 2:38 · What it can't do

*Screen: the weaknesses table in the report.*

> And here is what it gets wrong.
>
> Multi-hop claims: four out of nine. Quantifier flips — "up to" against "at
> least" — it misses **forty-seven percent** of them.
>
> We wrote this test set ourselves. An earlier version scored a hundred percent
> on everything, which is exactly why the hard cases exist.

*Counterintuitive but true: this section raises credibility, it doesn't lower
it. A judge who has watched ten flawless demos is looking for the one team that
knows where its own edges are. Say it at normal pace — no apology in the voice.*

### 2:38 – 2:45 · Close

> Regulated enterprises can't scale AI they can only audit in hindsight.
>
> ControlPlane makes oversight something you **watch**, not something you
> discover.
>
> Team Nexus, IIT Jodhpur. Repository and full benchmark in the description.

---

## Language notes

**Use.** Specific and concrete, because that is what survives a judge's third
video of the afternoon:

- "one percent became two percent" — not "hallucination risk"
- "three point three six crore" — not "significant cost savings"
- "twenty-two times faster" — not "dramatically lower latency"
- "one line: the base URL" — not "seamless integration"
- "config file, not a release" — not "highly configurable"
- "nobody had to notice" — not "automated monitoring"

**Avoid.** Every one of these makes a strong claim sound like a weak one:

- revolutionary, game-changing, cutting-edge, next-generation
- seamlessly, robustly, leveraging, empowering
- "we believe", "our solution aims to" — say what it *does*
- Any number without a unit or a source

**The rhythm that holds attention.** Every block above follows the same shape:
a concrete thing on screen, then one sentence saying what it means. Never the
reverse. A viewer who is told what they are about to see has no reason to keep
watching.

## Recording notes

- Terminal at a size that is readable on a phone. Judges scrub on phones.
- Real commands, real output. Everything in this script has been run; nothing is
  staged. `docs/commands.md` lists every command and what it costs — the whole
  recording is under a rupee.
- Do not run `eval/run_eval.py` on camera. Forty-five minutes and a dollar, and
  its output is already committed.
- One take per section, cut between. A three-minute unbroken take will have you
  rushing the 1:05 block, which is the one that has to land.

## If you run long

Cut in this order. The first two cost you almost nothing.

1. The 0:18 "what we built" block — the demo at 0:35 explains it anyway.
2. Half of 1:35 — the dashboard is a proof, not an argument.
3. Nothing else. The three-verdict demo, the comparison table, the reframe and
   the weaknesses are the pitch. Losing any of them costs more than the time
   saved.
