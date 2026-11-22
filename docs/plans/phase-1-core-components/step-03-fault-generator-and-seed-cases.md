# P1-S03 — Fault generator, manifest and validator; 4 seed cases

## A. Task identification
| Field | Value |
|---|---|
| Phase | 1 Core components |
| Step | 3 |
| Task ID | P1-S03 |
| Synverk card | TRAC-7 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal (critical path) |
| Effort | 3 days |
| Status | COMPLETED (approved 23 Nov 2026; 184 validated cases, see `docs/research/dataset-catalogue.md`) |
| Branch | `rafique/P1-S03-fault-generator` |

## B. Objective
A reproducible way to inject a known fault into the lab, write its ground truth automatically, and prove the fault is real (the buggy state fails its reproducer; the original passes). This is the machinery that P3-S01 scales to 144+ cases, so the design must make variants cheap. Labels come from the generator, never from agent output (`docs/invariants/ml.md`).

## C. Prerequisites
- P1-S01 (lab code), P1-S02 (`run_tests`), P0-S05 (`CaseManifest`).
- Read `docs/invariants/ml.md` (splits, leakage).

## D. Technical background
- **Case = base commit + mutation.** Each case is stored as a patch file applied to the lab at a fixed `base_sha`, so the repository itself stays healthy and cases don't conflict.
- **Four classes:**
  - *configuration*: change a value or key in settings/Compose/env (wrong host, wrong port, renamed env var, wrong queue name, invalid type);
  - *application_code*: change one guard/index/boundary/serialization/retry rule;
  - *runtime_dependency*: no code/config change; the case's runtime setup stops or breaks a dependency container (e.g. `lab_redis` stopped). Expected answer: diagnose, no patch;
  - *insufficient_evidence*: a symptom whose cause cannot be determined from available evidence (logs removed, contract silent, SHA mismatch). Expected answer: abstain.
- **Reproducer vs hidden tests:** the reproducer is a visible, minimal test showing the symptom (the agent may see its output in F1); hidden tests check the intended behaviour more broadly and are never visible.
- **Distance:** computed later with P2-S02's `distance()`. In this step, record a provisional value by hand and mark `distance_source: "manual"`; P2-S02 recomputes and P3-S01 requires the computed value.
- No network in the sandbox, so reproducers/hidden tests are unit-level (call the function or use FastAPI TestClient with an in-memory fake), not live HTTP to Compose.

## E. Implementation instructions
1. **Layout:**
   ```
   datasets/
     generation/
       templates/config.py, code.py, runtime.py, insufficient.py
       generate.py           # template + params -> case dir
     cases/<case_id>/
       mutation.patch        # empty for runtime_dependency
       runtime.yaml          # e.g. stop: [lab_redis] (runtime cases only)
       reproducer/test_*.py  # visible
     hidden_tests/<case_id>/test_*.py
     manifests/dev.jsonl, test.jsonl
     validate.py
   ```
2. **Templates:** each is a function `make(params) -> CaseDraft` producing the patch text (via `difflib.unified_diff` on the target file), gold keys/symbols with line spans, reproducer and hidden tests, and `fault_family`. Parameters (target module, key name, value, wording) are what make variants.
3. **`generate.py`:** writes the case dir and appends a `CaseManifest` line. `case_id` = `<family>-<service>-<nnn>`; `variant_group` = template + target site, so variants of one site never cross splits.
4. **`validate.py` (`task dataset:validate`):** for every manifest line:
   - schema-valid;
   - apply patch to a fresh worktree at `base_sha` (`git worktree add`);
   - reproducer: **fails** on buggy, **passes** on original (both via `run_tests`);
   - hidden suite: fails on buggy (for repairable classes), passes on original;
   - leakage scan: no gold key/symbol name or the word "bug"/"mutation" in any model-visible file of the case (reproducer, logs);
   - runtime cases: apply `runtime.yaml`, confirm the symptom appears, restore;
   - print a table: case, class, family, distance, result.
5. **Seed cases (all `split: dev` for now):**
   - config, distance ≥1: worker `ORDER_QUEUE` renamed on the worker side only → jobs never consumed;
   - code: `catalog.list_products()` indexes `[0]` → empty catalogue 500s; contract says `[]`;
   - runtime_dependency: `lab_redis` stopped → enqueue fails with connection refused;
   - insufficient_evidence: intermittent failure with logs suppressed and contract silent.
6. Unit tests for templates (patch applies cleanly; gold lines match the changed lines).

Edge cases: patch drifts when lab code changes → validator fails loudly (pin `base_sha`); Windows CRLF in patches → `.gitattributes` LF; flaky reproducer → run it 3× during validation and require consistent results.

**Additions from the feasibility review (21 Nov 2026; see D18–D24)**
- Each case records `log_format` (`plain`, `json`, `uvicorn_access`, `none`) in its manifest; the 4 seed cases use at least 3 different formats (D24).
- `task dataset:validate` runs the broken version 3 times and the original 3 times; any flip is a flaky case and is rejected (Q11).

## F. Checklist
- [ ] Case directory layout
- [ ] Config, code, runtime, insufficient templates
- [ ] `generate.py` with deterministic IDs and `variant_group`
- [ ] `validate.py`: schema, red/green reproducer, hidden suite, leakage scan, runtime cases, 3× flakiness check
- [ ] 4 seed cases generated
- [ ] Provisional distance recorded with `distance_source`
- [ ] Template unit tests
- [ ] `task dataset:validate`, `task dataset:generate`
- [ ] README dataset section
- [ ] Seed cases cover ≥3 log formats
- [ ] Validator rejects flaky cases (3× runs)

## G. Expected deliverables
New: `datasets/generation/`, `datasets/cases/<4 ids>/`, `datasets/hidden_tests/<4 ids>/`, `datasets/manifests/dev.jsonl`, `datasets/validate.py`. Modified: `Taskfile.yml`, `README.md`. Possibly a contract PR adding `distance_source` (additive).

## H. Testing and validation
- `task dataset:validate` prints all 4 as PASS with class and distance.
- Corrupt a hidden test on purpose → validator reports FAIL.
- Remove the mutation → reproducer passes on "buggy" → validator reports "fault not reproduced".
- Acceptance: a reviewer can read one case dir and understand the fault without seeing the patch name or gold labels in visible files.

## I. Dependencies and integration
- **Informed by:** P0-S06 limits report.
- **Depends on:** P1-S01, P1-S02, P0-S05.
- **Unblocks:** P1-S07 (Sync 1), P3-S01 (scale-up), P2-S04 testing on real cases.
- **Integration:** `datasets/manifests/*.jsonl` is the only thing Track B reads; hidden tests stay in `datasets/hidden_tests/` and are only mounted by the sandbox.

## J. Definition of done
Merged after Ruhan's review; 4 seed cases validate red/green on both laptops; leakage scan clean; TRAC-7 approved.
