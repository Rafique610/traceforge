# P5-S05 — BugsInPy subset: independent real-bug test

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 5 |
| Task ID | P5-S05 |
| Synverk card | TRAC-27 (reference only; Synverk not used) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran (contract change in section E.2 touches the shared contract) |
| Priority | High. Raised from Low on 27 Nov 2026 at the owner's request: this is the answer to "you planted the bugs" |
| Effort | 2.5 days (converter + image 1 day, red/green validation 0.5 day, runs 1 evening, write-up 0.5 day) |
| Status | PARTIALLY COMPLETE (27 Nov 2026): importer, sandbox support and validation done (14 of 15 fastapi bugs kept); 1 live free-model attempt (bug 5: no result, provider outage then a 25-min timeout without a diagnosis). The owner stopped here (free tokens used up for the week); the 13-bug live batch is optional and handed to Ruhan (`docs/plans/HANDOFF_TO_RUHAN.md`) |
| Branch | `main` (no step branches, per AGENTS.md) |

## B. Objective
Measure diagnosis and repair on **real bugs we did not write**: bugs taken from real projects' git history, each with the project's own failing test. Report the results in their own table next to RC1, never pooled with the planted-bug numbers.

This tests **application-code** bugs only. Public datasets have no Docker runtime evidence, no configuration faults and no dependency outages. Those classes stay measured on the lab only.

## C. Prerequisites
- The free model path (BeatAPI `glm-5.3-flash-free`, `reasoning_effort=low`) works. The 18/18 repeat test on 26 Nov 2026 verified it (`.memory/26-november-2026/tasks.md` row 2).
- The BugsInPy metadata repo `github.com/soarsmu/BugsInPy` (last push Feb 2026). Its GitHub API reports **no licence**, so we do not copy its files into our repo. The converter reads them at run time, and we commit only our own converter, manifests and results. FastAPI itself is MIT.
- Docker disk headroom: one `python:3.8-slim` image (~150 MB) plus a shallow FastAPI checkout.

## D. Technical background
- **What a BugsInPy bug gives us**, per `projects/<name>/bugs/<n>/`:
  - `bug.info`: `python_version`, `buggy_commit_id`, `fixed_commit_id` and `test_file`;
  - `bug_patch.txt`: the real fix, source only;
  - `requirements.txt`: the pinned dependencies;
  - `run_test.sh`: the failing test node ids.
- **Mapping to `CaseManifest`** (`contracts/case_manifest.py`):
  - `origin="bugsinpy"` already exists;
  - `cause_class="application_code"`;
  - `base_sha` = the buggy commit;
  - `gold_symbols` = the functions touched by `bug_patch.txt`;
  - `reproducer_id` = the failing test from `run_test.sh`;
  - `hidden_test_ids` = the failing tests in the fix commit's test file (the hidden suite is that whole file; the reproducer is the same file, so the hidden gate adds the file's other tests but no new behaviour; say so);
  - `distance` = 0 (not computed for external cases; results are never split by it);
  - `variant_group` = `bugsinpy:<project>-<n>`.
- **Evidence:** the only evidence is the failing test's traceback and output, collected by running the reproducer in the sandbox on the buggy commit. There are no container logs. Say this in the results.
- **Contamination:** these bugs date from 2019–2020 and are public, so the model may have seen the real fix during training. Report this plainly. Section E.7 adds an optional check with newer bugs.
- **Candidate pool, measured 27 Nov 2026** (fix size from `bug_patch.txt`; our patch limit is ≤2 files, ≤60 changed lines):

| Project | Python | Bugs within our patch limit | Excluded |
|---|---|---|---|
| fastapi (primary, same framework as the lab) | 3.8.3 | 2–16 (15 bugs, all 1 file, 2–32 lines) | 1 (5 files, 223 lines) |
| thefuck (backup) | 3.7.0 | 1–15, 17–32 (31 bugs) | 16 (4 files) |
| tqdm (backup) | 3.6.9 | 1–9 | — |

- **Security:** third-party code runs only in the sandbox, which has no network, a non-root user and memory, CPU and pid limits. It never runs on the host. Dependencies are installed at image build time; runs have no network (D30 warm image).

## E. Implementation instructions
**Rule for the whole step:** the 28 RC1-fingerprinted files (`evaluation/fingerprint.py`) and `results/final` are not edited. New behaviour goes in new modules. If a locked file blocks the live path for an external repo, stop and report to the owner. Do not change it.

**As built (27 Nov 2026).** The live path only reads and edits `lab/<service>/` (enforced in locked `agent/tools.py` and `retrieval/sources.py`). So each bug's project tree is placed at `lab/fastapi/` of the scratch repo, and the locked files run on it unchanged. Line endings are normalized to LF (the edit matcher compares text exactly); this changes no behaviour.

1. **Converter** `backend/traceforge/external/bugsinpy.py` (feature folder per `core.md`; CLI `python -m traceforge.external.bugsinpy prepare fastapi <n>...`):
   - fetches one bug's metadata (cached in git-ignored `runs/external/bugsinpy/meta/`);
   - clones the project once (`--filter=blob:none`) and exports the buggy commit to `runs/external/bugsinpy/<case>/src/`;
   - parses the fix diff into gold symbols (innermost function or class around each changed line);
   - writes `datasets/manifests/bugsinpy.json` and the derived test dirs `datasets/{reproducers,hidden_tests}/bugsinpy-*/` (git-ignored: BugsInPy has no licence; regenerate with the CLI);
   - `agent/e2e.py build_repo` (not locked) calls `materialize_case` for `origin="bugsinpy"`.
2. **Contract:** `CaseManifest.service` accepts `"fastapi"` as well as `"shop_api"` and `"worker"`. It is the folder name under `lab/`, so the locked files need no change. This is a shared contract, so flag it to Ruhan, and run the full test suite to show existing manifests still validate.
3. **Sandbox image per Python version:**
   - `SandboxConfig.base_image` (default `python:3.12-slim`); `images.dockerfile(cfg)` swaps the `FROM` line in memory, so the Dockerfile and every existing image tag stay unchanged;
   - the image is `python:3.8-slim` plus the bug's pinned requirements, minus the project itself and dev tooling, plus our `pytest==8.3.4`;
   - the tag hash covers the base image. The 15 candidates need 5 images.
4. **Red/green validation:**
   - for each candidate, run the reproducer on the buggy commit (it must fail), then apply the real fix and run it again (it must pass);
   - run each check twice to catch flaky tests;
   - the visible suite is pruned to the project test files that are fully green with the fix (files that fail to import, such as fastapi's tutorial tests that need its docs on the path, are dropped first), then re-checked green;
   - `python -m traceforge.external.bugsinpy validate fastapi <n>...` (`external/validate.py`) writes `runs/external/bugsinpy/validation.json`; the drop list with reasons goes in the results write-up;
   - keep going until **10 fastapi bugs** pass; use thefuck or tqdm only if fewer than 10 fastapi bugs survive.
5. **Evidence bundles:** each kept case gets an empty bundle `runs/evidence/bugsinpy-<project>-<n>.json` (no Docker runtime evidence exists). Pipeline v5's symptom step runs the reproducer on the buggy tree, so the failing test's output becomes the observed evidence, the same way as for lab bugs.
6. **Runs:**
   - one run per bug, free model, through the same pipeline and checks as the lab, in the graph + feedback condition (G1, the full system);
   - reuse `repeat_runner.sh` (it pauses on provider errors and stops after 3 tries) in one evening batch, about 10 × 4–14 min;
   - **outcomes:** each bug ends as TEST_VERIFIED, wrong fix, abstained or inconclusive;
   - **recorded per bug:** symbol hit, tokens, wall time.
7. **Optional contamination check:** two or three bugs from SWE-bench-Live (issues from 2024 or later), only if their repo is small and builds within disk limits. Report them as a footnote, not as a rate.
8. **Results:** write `results/external/bugsinpy_pilot.md` as a separate table with these columns:
   - bug;
   - what the real fix touched;
   - our diagnosis target, and whether it matches;
   - outcome;
   - calls/tokens/time.

   Add the limits (code-only, traceback-only evidence, contamination) and a link to the drop list.

## F. Checklist
- [x] Owner approved this revised plan
- [x] Converter + `bugsinpy.json` manifest (14 validated fastapi bugs)
- [x] Contract widened; full test suite green (1150 + 12 docker); Ruhan informed via `HANDOFF_TO_RUHAN.md`
- [x] Per-version sandbox image; tag hash covers the base image
- [x] Red/green validation twice per bug; drop list (fastapi-16) in `results/analysis/free_model_live_runs.md`
- [x] Evidence bundles saved
- [ ] 10 runs done on the free model (1 attempted: bug 5, no result; rest optional, handed over)
- [x] Separate results table with limits and contamination note
- [x] RC1 fingerprint unchanged (`ee3d8d87…`), checked before hand-off

## G. Expected deliverables
- `backend/traceforge/external/{bugsinpy,validate}.py` and `backend/tests/test_bugsinpy.py`;
- `datasets/manifests/bugsinpy.json`;
- the sandbox base-image option;
- `results/external/bugsinpy_pilot.md`.

Run logs stay in the git-ignored `runs/`.

## H. Testing and validation
- Unit tests cover the converter (diff → gold symbols, `bug.info` parsing) on one saved real bug fixture and the image-tag hash change.
- Every included bug validates red/green twice. Acceptance: the results appear only in their own table, the RC1 fingerprint is unchanged, and `ruff`, `pytest` and the frontend checks are green.

## I. Dependencies and integration
- **Depends on:** the sandbox, the Investigate path and the free-model profile (all working as of 26 Nov 2026).
- **Feeds:** the A3 results slide (independent test), the P6-S04 threats-to-validity section, and the ≥50 held-out examples per component the supervisor asked for. If the pilot works, extend it to more bugs.
- **Scope note:** the supervisor-agreed scope is the Compose lab. This is reported as an external-validity check, not a scope change; tell the supervisor in one line.

## J. Definition of done
Pilot complete, the results table is reviewed by the owner, the status is set to NEEDS REVIEW with check output in chat, and the step is logged in that day's `.memory/<date>/tasks.md`. If the pilot fails (fewer than 5 bugs reproduce), record that result and the reason in [DECISIONS_AND_OPEN_QUESTIONS.md](../DECISIONS_AND_OPEN_QUESTIONS.md) instead of forcing it.
