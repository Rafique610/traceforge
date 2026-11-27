# Handoff to Ruhan: where TraceForge stands (27 Nov 2026)

Rafique covered both tracks 25–27 Nov while you were on break. His free AI tokens for this week are used up, so the last small A3 tasks are yours. **Nothing large is left for A3.** Don't start new features: build the slides, rehearse, and submit.

## 1. What changed while you were away (all on `main`)

| Commit | What it does | Your area? |
|---|---|---|
| 70aa43c | BeatAPI free-model calls are streamed (fixed the provider's 503 on long answers) | yes (gateway, P1-S05) |
| 7eb6487 | Per-call output cap raised to 4,096 tokens | yes (gateway) |
| ff5ca6b | **New incident → Lab bug** tab (`GET /lab-cases`); Investigate explains why a non-lab incident can't be investigated instead of a bare 422 | yes (incidents API + UI) |
| 842b760 | Report Summary shows the observed symptom instead of "No symptom recorded" | yes (reports) |
| ab499c2 | P4-S02 failure analysis: `results/analysis/a3_failure_analysis.md` (28 failures, 10 groups); owner-approved | rows A1–A3 are yours to review |
| 6732715 | BeatAPI asks for `reasoning_effort=low` by default, so answers stop getting cut off | yes (gateway) |
| tag `demo-working-2026-11-25` | A known-good demo version (on ff5ca6b) to fall back to | — |
| this commit | P5-S05 BugsInPy importer + validation, free-model results, this handoff | Rafique's P5-S05 |

Every commit was tested; the RC1 fingerprint is still `ee3d8d87…` (no locked file was touched).

## 2. Results to put on the slides

Full tables: [`results/analysis/free_model_live_runs.md`](../../results/analysis/free_model_live_runs.md). The headline numbers:

1. **Paid-model final evaluation (RC1, already in the repo):**
   - fixed 27–29 of 35 bugs across the 4 conditions;
   - refused 6/6 unfixable bugs;
   - keyword vs code-map search: **no significant difference** (p = 1.0). Present this honestly as a finding: the misses come from bug reports with no code words in them (see `a3_failure_analysis.md` section 2).
2. **Free model, repeat test (26 Nov): 18/18 correct.**
   - 6 planted bugs × 3 runs: 4 fixed and verified in the sandbox every time, with the identical patch each time;
   - the Redis outage was diagnosed 3/3 with no patch, and the low-evidence bug was declined 3/3;
   - before the 25 Nov fixes, 4 of 10 live runs ended with no result; after them, 0 of 18.
3. **Independent real bugs (BugsInPy, 27 Nov):**
   - 14 of 15 real FastAPI bugs validated in our sandbox (each fails before the real fix and passes after, twice);
   - the full pipeline verified bug 5 with a stand-in model;
   - one live free-model attempt on bug 5 gave **no result**: one provider outage, then a 25-min timeout after 6 very short AI answers. Don't show it as a result; details are in `free_model_live_runs.md` section 3.

   This answers "you planted the bugs". State the limits on the slide: code bugs only, the only evidence is the test's output, and the model may have seen these public fixes during training.
4. **Retrieval benchmark:** recall@10 = 0.556 for both search methods on 45 queries over real libraries. The gold labels are AI-drafted and not yet human-checked; say so.

Run IDs and log paths are in each results file. The A3 brief allows "slides or a dashboard" and needs **no written report**.

## 3. Small final tasks for A3 (in order)

- [ ] **Push `results/final/` from your laptop** if it isn't on `main`. Rafique's results page is empty without it (the folder is git-ignored here). If it must stay ignored, put a copy in the submission pack.
- [ ] **Slides (5–8)** from section 2: problem, how it works (evidence → search → diagnosis → patch → sandbox → human review), the RC1 table, the 18/18 repeat test, the BugsInPy pilot, honest limits, next steps (A4). Footnote the run IDs (P4-S02 checklist).
- [ ] **Click Approve on one investigated incident in the UI** and check the review is stored. It has never been done.
- [ ] **Record a backup video** of one full fix (shop_api-002 is the most reliable: 3–4 AI calls, about 6 min) plus the outage (003) and decline (004) cases. The free provider sometimes goes down for 10–20 min; we saw it twice.
- [ ] **Clean-clone dry run and 2 timed rehearsals** (P4-S03 checklist in `docs/plans/phase-4-a3-delivery/step-03-demo-and-submission-pack.md`).
- [ ] **Review rows A1–A3** in `results/analysis/a3_failure_analysis.md` (your agent/repair rows; Rafique drafted them).
- [ ] **Self-evaluation form, submission pack, then ask the owner before tagging.**

Optional, only if there is time and free tokens: run the other 13 validated BugsInPy bugs. It's one command (section 4) and takes about 3–6 h unattended (45-min limit per bug). Try bug 2 or 4 alone first: the one live attempt (bug 5) timed out without a diagnosis, so check that a single run finishes before starting the batch.

## 4. How to run things

Backend server for the UI (free model; you add your own key to `.env`, never commit it):
```
cd backend
TRACEFORGE_LLM_PROVIDER=beatapi TRACEFORGE_LLM_MODEL=glm-5.3-flash-free \
TRACEFORGE_MANIFEST="<repo>/datasets/manifests/dev.json" TRACEFORGE_EVIDENCE_DIR="<repo>/runs/evidence" \
.venv/Scripts/python.exe -m uvicorn traceforge.main:app --port 8000
pnpm --dir frontend dev          # UI on http://localhost:5173 → New incident → Lab bug
```

One investigation from the command line (default: stand-in model, 0 tokens; `REAL_MODEL=1` for the free model):
```
cd backend
python ../scripts/live_investigate.py shop_api-002
REAL_MODEL=1 TRACEFORGE_LLM_PROVIDER=beatapi TRACEFORGE_LLM_MODEL=glm-5.3-flash-free python ../scripts/live_investigate.py shop_api-002
```

BugsInPy (needs Docker and network on first use; downloads go to the git-ignored `runs/external/`):
```
cd backend
python -m traceforge.external.bugsinpy prepare fastapi 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16   # case files
python -m traceforge.external.bugsinpy validate fastapi 2 3 4 5 6 7 8 9 10 11 12 13 14 15     # red/green
cd .. && bash scripts/live_batch.sh 0 "2 3 4 6 7 8 9 10 11 12 13 14 15"                          # live batch
```
`prepare` regenerates the derived test dirs (`datasets/{reproducers,hidden_tests}/bugsinpy-*`). They are git-ignored because the BugsInPy metadata has no licence.

## 5. Rules that still hold

- Don't edit the 28 RC1-locked files (`backend/traceforge/evaluation/fingerprint.py`) or `results/final`; check that the fingerprint is still `ee3d8d87…` before you commit.
- Free-only: no AxForge spend, and don't remove its billing gate.
- Never commit `.env` or keys.
- Update `TEAM_WORK_DISTRIBUTION.md` section 0 before each commit.

## 6. Known issues (disclose, don't fix before A3)

- Symptom evidence is labelled service `lab_db` instead of the failing service. The label comes from RC1-locked `agent/symptom.py`; deferred to P6-S03.
- The free provider has had 10–20 min outages, so the demo needs the backup video.
- The 98 retrieval gold labels are AI-drafted and unchecked.
- The A3 deadline date is not recorded in the docs (Q8); confirm it with the supervisor.
- P5-S05 is a pilot, not a full experiment: 14 bugs validated, 1 live attempt without a result. The A4 plan can extend it.
