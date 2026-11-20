# P1-S02 — Sandbox test runner

## A. Task identification
| Field | Value |
|---|---|
| Phase | 1 Core components |
| Step | 2 |
| Task ID | P1-S02 |
| Synverk card | TRAC-6 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal (critical path) |
| Effort | 2 days |
| Status | NOT STARTED |
| Branch | `rafique/P1-S02-sandbox-runner` |

## B. Objective
One trusted function that runs a test suite against a code checkout inside a locked-down container and returns `TestRunResult`. The dataset validator (P1-S03) uses it to prove each fault is real; the repair loop (P2-S04) uses it to prove each patch works. Because acceptance decisions rest on it, it must be isolated, deterministic and fast.

## C. Prerequisites
- P0-S05 (`TestRunRequest`/`TestRunResult`).
- P1-S01 images helpful; until then test on a tiny throwaway package with one passing and one failing test.
- Python `docker` SDK (`uv add docker`).

## D. Technical background
- **Isolation:** `network_mode="none"`, `mem_limit`, `nano_cpus`, `pids_limit`, `read_only=True` root FS with a tmpfs for `/tmp`, non-root `user`, no volumes except the checkout (read-only) and an output dir. No Docker socket mount.
- **Hidden tests:** live in `datasets/hidden_tests/<case_id>/`, mounted read-only **only** when `suite="hidden"`; never copied into the worktree, so the agent can never read them.
- **Result parsing:** pytest `--junitxml=/out/report.xml` parsed with `xml.etree` (stdlib) to per-test outcomes.
- **Speed:** container start dominates; reuse the prebuilt lab images (dependencies already installed) and avoid any build per run. Measure; A4 needs ~1,600 runs (risk T6).
- Integration tests that need Postgres/Redis are **not** run in the sandbox (no network); reproducers and hidden tests must be unit-level or use in-process fakes. P1-S03 enforces this.

## E. Implementation instructions
1. `backend/traceforge/sandbox/images.py`: map `service` → image tag (`traceforge-lab/shop_api:dev`, `traceforge-lab/worker:dev`); `ensure_images()` checks presence and tells the user to run `task lab:build` if missing.
2. `sandbox/runner.py`: `run_tests(req: TestRunRequest) -> TestRunResult`:
   - resolve the suite to pytest node IDs (visible: the service's `tests/` minus `integration`; reproducer: the case's reproducer file; hidden: the case's hidden dir);
   - `docker.containers.run(image, command=["pytest", ..., "--junitxml=/out/report.xml", "-q"], volumes={worktree: {"bind": "/work", "mode": "ro"}, out_dir: {"bind": "/out", "mode": "rw"}, hidden_dir?: {"bind": "/hidden", "mode": "ro"}}, network_mode="none", mem_limit="512m", nano_cpus=1_000_000_000, pids_limit=128, user="1000:1000", read_only=True, tmpfs={"/tmp": ""}, working_dir="/work", detach=True)`;
   - wait with `timeout_s`; on timeout kill and return `timed_out=True`;
   - parse JUnit XML; capture last 4 KB of logs; remove container; return result.
3. Paths: convert Windows paths with `pathlib` before mounting; Docker Desktop accepts `C:/...` style.
4. `sandbox/selftest.py` + `task sandbox:selftest`: runs passing suite, failing suite, a test that sleeps past the timeout, and a test that tries `socket.create_connection(("1.1.1.1", 53))` and must fail. Prints average duration.
5. Unit tests with the Docker client mocked for parsing/timeout logic; one marked `docker` test that runs for real.
6. README: what the sandbox guarantees and what it doesn't (Docker is not a hard security boundary for hostile code; we only run first-party fixtures).

Edge cases: missing image → clear error, `UNVERIFIED` upstream; pytest collection error → `error` set and `failed` counts it; JUnit file absent → `error`.

**Gap fixes (21 Nov 2026; see D26–D31)**
- Record timing per run in `TestRunResult.duration_ms` and log container start vs test time separately; build the test image once per `base_sha` and reuse it (warm image), never rebuild per attempt (D30).
- Write the measured median start + run time into the step's PR, so P5-S03 can estimate total experiment time from a real number.

## F. Checklist
- [ ] Image map + presence check
- [ ] `run_tests()` with all isolation flags
- [ ] Hidden tests mounted only for `suite="hidden"`
- [ ] Timeout handling and container cleanup
- [ ] JUnit parsing to per-test outcomes
- [ ] Windows path handling
- [ ] Selftest: pass, fail, timeout, no-network
- [ ] Unit tests (mocked) + one real Docker test
- [ ] Average duration recorded on TRAC-6
- [ ] README section
- [ ] Warm image reused across attempts
- [ ] Median container start and test time measured and recorded

## G. Expected deliverables
New: `backend/traceforge/sandbox/{__init__,images,runner,selftest}.py`, tests. Modified: `Taskfile.yml` (`sandbox:selftest`, `lab:build`), `pyproject.toml` (`docker`), `README.md`. Interface: `run_tests(TestRunRequest) -> TestRunResult`.

## H. Testing and validation
- Selftest output shows the four expected behaviours.
- Containers are gone after each run (`docker ps -a` shows none left).
- Hidden dir is not visible inside a `visible` run (test lists `/hidden` → not found).
- Acceptance: average run time measured and noted; all isolation flags asserted in a unit test.

## I. Dependencies and integration
- **Depends on:** P0-S05; P1-S01 images.
- **Unblocks:** P1-S03 (validator), P2-S04 (repair loop). Ruhan uses a fake runner returning sample `TestRunResult`s until this merges.

## J. Definition of done
Merged after Ruhan's review; selftest passes on both laptops; timing recorded; no container left behind; TRAC-6 approved.
