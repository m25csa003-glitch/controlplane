# Publishing the repository

The repo is committed and clean. `gh` is not installed on this machine, so
create the remote in the browser and push.

## Before you push — verified already

- `.env` is gitignored and untracked. Confirmed.
- No API key appears in any tracked file. Confirmed by scan.
- `.venv/`, `__pycache__/` and per-run audit logs are ignored.

Re-run the check yourself any time:

    git ls-files | xargs grep -lEi "sk-proj-|sk-ant-" ; echo "^ empty means clean"

## Create and push

1. Go to https://github.com/new
2. Name it `controlplane`, set it **Public**, and do **not** tick
   "Add a README" or "Add .gitignore" — the repo already has both, and an
   initial commit on the remote will make the first push conflict.
3. Then:

```
cd ~/Downloads/Accenture_Hackaton/controlplane
git remote add origin https://github.com/<your-username>/controlplane.git
git branch -M main
git push -u origin main
```

If it asks for a password, GitHub wants a personal access token, not your
account password: https://github.com/settings/tokens → generate a classic token
with `repo` scope, and paste that as the password.

## After pushing

- Add the demo video link to the top of `README.md` and push again.
- Check that `eval/results/report.md` renders — it is the strongest single
  artefact in the repo and a judge will open it first.
- The submission needs the repo URL, the video, and `docs/proposal.md`.

## What a reviewer should be able to do on a fresh clone

```
git clone <url> && cd controlplane
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 demo/run_pipeline.py
```

That must work with no API key and no models downloaded. It is the property the
whole codebase is built around — if a change ever breaks it, the change is
wrong.
