import asyncio
import time
import uuid
from dataclasses import dataclass, field

from .cost.meter import CostBreakdown
from .router.router import decide
from .schema import RequestContext, Category
from .text import sentences as split_sentences
from .tiers import tier0_rules, tier1_classifiers, tier2_judge


@dataclass
class StreamStep:
    """What the gateway should do with one upstream chunk."""
    release: str = ""            # text safe to forward to the caller
    events: list = field(default_factory=list)
    held: int = 0                # characters withheld pending a check


class StreamingVerifier:
    """Verifies a response while it is still being generated.

    Sentences are checked as they complete, in parallel with the tokens still
    arriving. Tier 0 and tier 1 finish in tens of milliseconds - far inside the
    time a model takes to produce the next sentence - so on the clean path the
    verdict is ready when the last token is.

    Tier 2 is not like that. A judge call measured 1.3s on the cheap model and
    3.1s on the strong one, against a 300ms customer-support budget. It cannot
    run inline, so it runs once the stream closes and the policy decides whether
    the caller waits for it.

    Two release policies, both from `streaming_mode` in the policy YAML:

      streaming   tokens go out as they arrive. A check that trips afterwards
                  emits a correction event; the caller has already seen the text.
      buffered    a completed sentence is held until its tier 0 and tier 1
                  checks land. Nothing bad is ever shown, and the cost is one
                  sentence of added latency.
    """

    def __init__(self, plane, use_case, retrieved_chunks=None,
                 allowed_chunk_ids=None, user_id="anon", expects_json=False):
        self.plane = plane
        self.policy = plane.policies[use_case]
        self.ctx = RequestContext(
            request_id=str(uuid.uuid4())[:8],
            use_case=use_case,
            user_id=user_id,
            retrieved_chunks=retrieved_chunks or [],
            allowed_chunk_ids=allowed_chunk_ids,
        )
        self.ctx.expects_json = expects_json

        self.mode = self.policy.streaming_mode
        self.buffer = ""
        self.released = 0            # chars already forwarded
        self.dispatched = []         # sentences sent for checking, in order
        self.done = set()            # indices whose checks have landed
        self.signals = []
        self.tiers_run = set()
        self.breakdown = CostBreakdown()
        self.tasks = []

        self.started = None
        self.last_token_at = None
        self.verdict = None
        self.sentence_checks = []

    # --- driving the stream --------------------------------------------

    async def feed(self, chunk):
        if self.started is None:
            self.started = time.perf_counter()
        self.buffer += chunk
        self.last_token_at = time.perf_counter()

        for idx, sent in self._newly_complete():
            self.tasks.append(asyncio.create_task(self._check(idx, sent)))

        # Give any check that has finished a chance to land before deciding
        # what may be released.
        await asyncio.sleep(0)
        events = self._collect(only_done=True)

        return StreamStep(release=self._release(), events=events,
                          held=len(self.buffer) - self.released)

    async def close(self):
        """Drain outstanding checks, run tier 2 if the policy asks for it, and
        produce the final verdict."""
        for idx, sent in self._newly_complete(closing=True):
            self.tasks.append(asyncio.create_task(self._check(idx, sent)))

        events = []
        if self.tasks:
            await asyncio.gather(*self.tasks)
            events = self._collect()

        stream_done = time.perf_counter()
        inline_ms = (stream_done - (self.started or stream_done)) * 1000

        judged = await self._tier2()
        if judged:
            events.append({"type": "tier2", "claims": len(judged)})

        latency = (time.perf_counter() - (self.started or stream_done)) * 1000
        self.verdict = decide(
            self.ctx, self.policy, self.signals, sorted(self.tiers_run),
            latency, self.breakdown.verification_inr, 0.0,
            self.breakdown.to_record(),
        )

        # The number this whole design exists for: how long after the last token
        # the caller waited for a verdict.
        self.verdict.cost_detail["stream"] = {
            "mode": self.mode,
            "lag_after_last_token_ms": round(
                (time.perf_counter() - (self.last_token_at or stream_done)) * 1000, 2),
            "inline_check_ms": round(inline_ms, 2),
            "sentences": len(self.dispatched),
            "sentence_checks_ms": self.sentence_checks,
            "tier2_ran": bool(judged),
        }

        return StreamStep(release=self._release(final=True), events=events)

    # --- internals ------------------------------------------------------

    def _newly_complete(self, closing=False):
        sents = split_sentences(self.buffer)
        if not closing and sents and not self._boundary_after(sents[-1]):
            sents = sents[:-1]      # still being written
        new = sents[len(self.dispatched):]
        first = len(self.dispatched)
        self.dispatched += new
        return list(enumerate(new, start=first))

    def _boundary_after(self, sent):
        """A sentence is finished only once the buffer shows a boundary after
        it. Tokens arrive as "word ", so trailing whitespace alone means
        nothing - without this check every first word looks like a sentence."""
        if sent.end >= len(self.buffer):
            return False
        return self.buffer[sent.end - 1] in ".!?" and self.buffer[sent.end].isspace()

    def _collect(self, only_done=False):
        events = []
        remaining = []
        for t in self.tasks:
            if t.done():
                events += t.result()
            elif only_done:
                remaining.append(t)
        self.tasks = remaining if only_done else []
        return events

    async def _check(self, idx, sent):
        """Tier 0 and tier 1 on one sentence, off the event loop."""
        started = time.perf_counter()
        signals = await asyncio.to_thread(self._check_sync, sent)
        self.sentence_checks.append(round((time.perf_counter() - started) * 1000, 2))

        self.signals += signals
        self.done.add(idx)
        if not signals:
            return []
        return [{
            "type": "signal",
            "span": list(sent.span),
            "text": sent.text[:80],
            "findings": [{"category": s.category.value, "score": round(s.score, 3),
                          "detail": s.detail} for s in signals],
        }]

    def _check_sync(self, sent):
        out = []
        if self.policy.tier_enabled(0):
            s, ms = tier0_rules.run(sent.text, self.ctx, self.policy)
            out += [self._shift(x, sent.start) for x in s]
            self.tiers_run.add(0)
            self.breakdown.add(self.plane.meter.compute_time("tier0_rules", ms, label="tier0"))
        if self.policy.tier_enabled(1):
            s, ms = tier1_classifiers.run(sent.text, self.ctx, self.policy,
                                          self.plane.meter, self.breakdown)
            out += [self._shift(x, sent.start) for x in s]
            self.tiers_run.add(1)
        return out

    @staticmethod
    def _shift(signal, offset):
        """Spans come back relative to the sentence; the caller needs them
        relative to the whole response."""
        if signal.span:
            signal.span = (signal.span[0] + offset, signal.span[1] + offset)
        return signal

    async def _tier2(self):
        lo, hi = self.policy.band()
        uncertain = [s for s in self.signals
                     if s.category == Category.GROUNDING and lo <= s.score < hi]
        if not (self.policy.tier_enabled(2) and uncertain):
            return []

        judged, _ = await asyncio.to_thread(
            tier2_judge.run, self.buffer, self.ctx, self.policy, uncertain,
            self.plane.meter, self.breakdown)
        replaced = {id(x) for x in uncertain}
        self.signals = [x for x in self.signals if id(x) not in replaced] + judged
        self.tiers_run.add(2)
        return judged

    def _verified_prefix(self):
        """Index of the first sentence whose check has not landed. Everything
        before it is cleared for release."""
        i = 0
        while i in self.done:
            i += 1
        return i

    def _release(self, final=False):
        """How much of the buffer the policy allows out right now."""
        if self.mode == "streaming" or final:
            out = self.buffer[self.released:]
            self.released = len(self.buffer)
            return out

        cleared = self._verified_prefix()
        if cleared == 0:
            return ""
        safe_to = self.dispatched[cleared - 1].end
        if safe_to <= self.released:
            return ""
        out = self.buffer[self.released:safe_to]
        self.released = safe_to
        return out
