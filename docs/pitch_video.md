# Pitch video script

This is the **pitch**. `docs/demo_video.md` is the technical walkthrough — the
one a judge opens second, to check the thing is real. Record both; lead with
this.

## How long

**2:35 of script. About 2:55 delivered, with the beats.**

The Round 2 brief asks for a demo video without naming a length, and the team's
own Round 1 slide promised a three-minute walkthrough. Three minutes is the
convention, so going over reads as not having edited rather than as having more
to say.

Measured, not guessed: the spoken text below is **401 words**. At 140–150 words
a minute — a clear technical pace, not a rush — that is 2:40 to 2:52, plus about
fifteen seconds of deliberate pauses. Read it aloud once with a timer before you
record; if you land over 3:10 you are pausing too long, not saying too much.

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

### 0:18 – 0:50 · The same answer, three different verdicts

*Screen: the terminal, already showing the output of*
`python3 demo/run_pipeline.py --models --compare`

**Run it before you hit record.** It takes about ten seconds, seven of them
loading models with nothing on screen. Film the finished output, not the wait.*

> ControlPlane sits between the application and the model and checks every
> response before it reaches anyone. Your app changes **one line** — the base
> URL.

*Point at one row:*

```
                       customer support  internal copilot  decision support
  being wrong costs    Rs 400            Rs 60             Rs 50,000

* hallucinated number  regenerate        annotate          escalate
```

> Same sentence. Three answers.
>
> In customer support, being wrong costs four hundred rupees — so we ask again.
> In a regulated decision it costs **fifty thousand** — so a human looks first.
>
> Nothing in the code knows what a use case is. **All of it is a config file.**

*The most persuasive thirty seconds in the video. Do not rush it.*

### 0:50 – 1:20 · The number the whole design rests on

*Screen: `localhost:8000/report#headline`*

> Three hundred and nineteen labelled cases, live judge. Us against the obvious
> way to do this — send **every** response to a judge.

| | catch | false positives | latency | cost |
|---|---|---|---|---|
| judge on everything | 94.6% | 15.6% | 4,071 ms | Rs 30.14 |
| **the cascade** | **94.6%** | **7.4%** | **184 ms** | **Rs 1.13** |

> Same catch rate. **Half** the false positives. **Twenty-two times** faster.
> Under **four percent** of the cost.
>
> Checking everything with a big model doesn't buy accuracy. It buys a bill.

### 1:20 – 1:38 · Show it working live

*Screen: the dashboard, traffic flowing.*

> Running live. Every response gets the cheap checks; **under three percent**
> reach the judge — the ones tier one was genuinely unsure about.
>
> Every number is measured against a limit **that policy set for itself**. Go
> over your own budget and it turns red. Nobody had to notice.

### 1:38 – 2:05 · The reframe

*Screen: the two money tiles side by side.*

> Then the measurement changed how we think about the product.
>
> At the brief's volume, verification costs about **five and a half thousand
> rupees a year**. The human review it generates, for **one** use case, costs
> **three point three six crore**.

*Beat. Let that sit.*

> Verification was never the expensive part. **Human attention is.**
>
> So this isn't cheap checking. It's a way to control **how much review you have
> to buy**. Moving the escalation rate one percentage point is worth more than
> the entire verification bill.

*This is the strongest thing in the pitch. It is a genuine insight, it came out
of the measurement, and almost no one else will say it.*

### 2:05 – 2:25 · What it can't do

*Screen: `localhost:8000/report#by-case-type-cascade`*

*The rate column is what it got **right**, so quantifier_flip at 53% means it
misses nearly half. The jump links in the corner get there in one click —
do not scroll for it on camera.*

> And here is what it gets wrong.
>
> Claims that need two sources: it gets **three of nine**. Quantifier flips —
> "up to" against "at least" — it catches eight of fifteen.
>
> We wrote this test set. An earlier version scored a hundred percent on
> everything, which is exactly why the hard cases exist.

*Counterintuitive but true: this section raises credibility, it doesn't lower
it. A judge who has watched ten flawless demos is looking for the one team that
knows where its own edges are. Say it at normal pace — no apology in the voice.*

### 2:25 – 2:35 · Close

> Enterprises can't scale AI they can only audit in hindsight.
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
- `run_pipeline.py` is not a server. It prints and exits. Run it before
  recording; the seven seconds it spends loading models is dead air.
- `--compare` pivots the demo so one input's three verdicts sit on one row. The
  default view groups by use case, which reads better but puts those three
  lines nine apart - wrong for showing that the policy is what changed.
- One take per section, cut between. A three-minute unbroken take will have you
  rushing the 1:05 block, which is the one that has to land.

## "Can three minutes cover everything?"

No. And it should not try.

The system has a policy layer, three tiers, an economics router, a cost meter, a
hash-chained audit log, streaming-concurrent verification, a feedback loop, a
dashboard, a 319-case benchmark and an OpenAI-compatible gateway. Narrated
properly that is fifteen minutes. Compressed into three it becomes twelve
seconds a topic, nothing lands, and the pace itself signals panic.

**The video is not the submission.** The repository, the README,
`eval/results/report.md` and `docs/proposal.md` are. The video's job is to make a
judge open them, and to leave them with four things they could repeat afterwards:

1. One response, three policies, three verdicts — behaviour lives in config.
2. Same catch rate as judging everything, under four percent of the cost.
3. Verification is cheap; human review is the real bill.
4. This team published what its system gets wrong.

A judge who remembers those four scores you well. A judge who was shown eleven
features and remembers none scores you badly, however complete the coverage was.

Everything cut has a home: the cascade internals and the audit chain are in
`docs/demo_video.md`, the economics in `docs/proposal.md`, the failure modes in
the report. Say "full benchmark in the repository" once, at the end, and let the
artefacts do the work they were built to do.

## If you still run long

Cut in this order. The first two cost you almost nothing.

1. The one-line "what it is" at 0:18 — the demo that follows explains it anyway.
2. Half of the dashboard block — it is a proof, not an argument.
3. Nothing else. The three-verdict demo, the comparison table, the reframe and
   the weaknesses are the pitch. Losing any of them costs more than the time
   saved.
