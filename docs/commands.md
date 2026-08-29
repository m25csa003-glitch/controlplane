# Every command, and what it costs

Cost column is real money against the configured API key. Anything marked free
makes no network call at all — verified by running the demos with sockets
blocked.

## Before anything

    cd ~/Downloads/Accenture_Hackaton/controlplane
    source .venv/bin/activate

Every command below assumes those two lines have run. If you see
`command not found: python3`, the venv is not active.

---

## One-time setup, on a fresh machine only

| Command | What | Cost |
|---|---|---|
| `python3 -m venv .venv` | create the environment | free |
| `source .venv/bin/activate` | activate it | free |
| `pip install -r requirements.txt` | dependencies, ~1.2 GB | free |
| `python3 load_models.py` | tier 1 models, ~500 MB | free |
| `cp .env.example .env` | then paste your key into it | free |

Nothing here is required to run the demo. Without models and without a key the
pipeline still runs end to end on its fallbacks and says which mode it used.

---

## The demos

| Command | What it shows | Cost |
|---|---|---|
| `python3 demo/run_pipeline.py` | 8 responses, 3 policies, 3 verdicts | free |
| `python3 demo/run_pipeline.py --models` | same, with the real classifiers | free |
| `python3 demo/run_streaming.py --models` | verdict ready when the last token is | free |
| `python3 demo/run_feedback.py` | reviews retuning thresholds | free |
| `python3 demo/run_judge.py` | tier 2, offline judge | free |
| `python3 demo/run_judge.py --live` | tier 2 with real judge calls and reasons | **~10 paise** |

`--models` loads the classifiers, which takes about 7 seconds and makes the
numbers real. Without it grounding is a lexical fallback — correct, but weaker,
and the output says so.

---

## The gateway and dashboard

Two terminals.

**Terminal 1:**

    uvicorn controlplane.proxy.gateway:app --port 8000

Takes ~7s to start — it loads the tier 1 classifiers first. That is deliberate:
without them far more responses land inside the uncertainty band and tier 2
fires on 57% of traffic instead of 2.8%, every one a paid judge call.

`CP_SKIP_MODELS=1 uvicorn ...` skips the load on a machine with no models.

**Terminal 2:**

    python3 demo/feed_dashboard.py

Then open <http://localhost:8000/dashboard>.

| Variant | What changes | Cost |
|---|---|---|
| `python3 demo/feed_dashboard.py` | random replay, tier 2 rarely fires | **a few paise** |
| `python3 demo/feed_dashboard.py --uncertain` | biased to cases that reach the judge | **~20-40 paise** |
| `python3 demo/feed_dashboard.py http://localhost:8001 3` | different port, 3 responses/sec | same |

Stop both with `Ctrl-C`. If a gateway is left running:

    pkill -f uvicorn

Other endpoints:

    curl localhost:8000/health          # which tier 1 mode is live
    curl localhost:8000/audit/verify    # is the hash chain intact
    curl localhost:8000/dashboard/stats # the numbers behind the tiles

---

## Tests

| Command | What | Cost |
|---|---|---|
| `python3 -m pytest tests/ -q` | all 57, no network | free |
| `python3 -m pytest tests/ -v` | same, one line per test | free |
| `python3 -m pytest tests/ -m live` | only the tests that need a real API | **~5 paise** |
| `python3 -m pytest tests/test_streaming.py -q` | one file | free |

Provider keys are stripped for the whole suite by `tests/conftest.py`. A test
that genuinely needs the API marks itself `@pytest.mark.live` and skips without
one. That is why the suite is free even with a key in `.env`.

---

## The benchmark

| Command | What | Cost |
|---|---|---|
| `python3 eval/build_dataset.py` | regenerate the 319-case set | free |
| `python3 eval/run_eval.py --lexical` | full benchmark, no models, no API | free |
| `python3 eval/run_eval.py` | **the real one** | **~$1, 45 min** |

Results are already committed in `eval/results/report.md` and
`eval/results/summary.json`. There is no reason to re-run unless the detection
code changed.

The dataset is deterministic — same seed, same 319 cases — so rebuilding it
never invalidates a result.

---

## Which provider gets used

The judge picks whichever key is present. No code change switches it.

| In `.env` | Judge runs on |
|---|---|
| `OPENAI_API_KEY` | `gpt-5.6-luna` / `gpt-5.6-sol` per policy |
| `ANTHROPIC_API_KEY` | `claude-haiku-4-5` / `claude-opus-5` per policy |
| both | Anthropic, unless `CP_JUDGE_PROVIDER=openai` |
| neither | the offline judge — everything still runs |

Useful overrides:

    CP_JUDGE_PROVIDER=openai          # force one when both keys exist
    CP_DEMO_UPSTREAM_MODEL=claude-sonnet-5   # what the demos assume the app runs
    CP_SKIP_MODELS=1                  # gateway starts without classifiers

---

## Recording the demo video

The order in `docs/demo_video.md`, with costs:

    python3 demo/run_pipeline.py --models        # free
    # gateway + feed_dashboard.py --uncertain    # ~30 paise
    # show eval/results/report.md                # free, already committed
    python3 demo/run_judge.py --live             # ~10 paise
    python3 demo/run_feedback.py                 # free

Under a rupee for the whole recording. Do not run `eval/run_eval.py` on camera —
it takes 45 minutes and about a dollar, and its output is already in the repo.

---

## If something breaks

| Symptom | Cause |
|---|---|
| `command not found: python3` | venv not activated |
| `no gateway at http://localhost:8000` | feeder started before the gateway |
| `Address already in use` | old gateway still running — `pkill -f uvicorn` |
| dashboard empty | no traffic yet, or gateway on a different port |
| `[tier2] ... judge failed` | key missing or wrong; it falls back and keeps going |
| `tier 1: {'mode': 'lexical'...}` | models not loaded — pass `--models`, or run `load_models.py` |

Nothing in this list stops the pipeline. Every failure path falls back to
something that still works and reports which mode it ended up in.
