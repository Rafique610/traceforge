# Bottom-up development and validation track: Level 1 plan (PROPOSAL, nothing implemented or run)

Written for: Ruhan, to approve or amend before any case, code or model call. Date: 24 Nov 2026.
This is a development-validation track, separate from the formal L0/G0/L1/G1 research. It does not change that methodology, any patch_v3 or patch_v4 artifact, or any frozen split.
Everything below was derived from manifests, mutation patches, validation records, saved results and **local, read-only analyses with no model calls** (the visible suites and reproducers were run locally on the faulty trees; ground truth was used only to score, never in a prompt).
Labels: CONFIRMED (shown by code/artifacts), LIKELY, UNKNOWN.

## 1. What the dataset actually contains (CONFIRMED)
All 184 cases (dev 33, test 151) are single-line mutations of one lab (`shop_api` and `worker`), one file and one fault each (`files=1` for every case). There is **no Level 5** case (no multi-fault or cascading case). Validation: 184/184 passed, every suite run 3x on the original, faulty and gold-fixed tree, 0 flaky, hidden inputs differ from the reproducer, leakage scan ok.

| Level (by the actual fault, not the name) | Groups / what the fault is | Dev cases | Test cases |
|---|---|---|---|
| **L1** simple code-level | `total_loop` (loop skips an item), `stock_decrement` (`=` instead of `-=`), `tax_base` (wrong variable), `ship_base` (swapped args), `grand_sum` (tax added twice), `free_threshold` (`>=` vs `<=`), `empty_order_headline` (missing empty check), `unit_aggregate` (`items[1:]`), `average_divisor` (`quantity-1`), worker `retry_budget` (wrong attribute), worker `retry_count` (range off by one) | 10 | 22 |
| **L2** small logic | `line_formula`, `tax_formula`, `discount_formula`, `discount_cap`, `rounding_mode`, `low_stock_filter`/`stock_check` (boundary), `code_lookup`/`code_table_case` (case normalisation), `quantity_upper_bound` (validation), worker `backoff_formula`, `retry_last` | 5 | 39 |
| **L3** single-service | 10 settings-default groups (wrong tax_rate, shipping_fee, coupons, queue name...) and worker `dead_letter_queue` / `malformed_route` (missing side effect on a fake queue) | 15 | 60 |
| **L4** multi-service connectivity | Redis host/port defaults, dependency stopped (lab_redis, lab_db) | 2 | 18 |
| **Abstention** (not a repair level) | intermittent/no-log groups (correct answer is to abstain) | 1 | 12 |
| **L5** | none exist | 0 | 0 |

Why these levels: the simplest are pure functions of 2 to 8 lines with no I/O (`unit_count`, `line_total`, `can_fulfil`, `order_headline`, `shipping_fee`, `average_unit_price`, `apply_discount`, `reserve`, `order_total`, `low_stock`, `tax_amount`). `quote` (24 lines, used by `tax_base`, `ship_base`, `grand_sum`) is simple but larger. Worker L1 cases call fake queue/sleep, so they are the least simple L1. A settings-default fault is mechanically a one-line constant but is **hard to diagnose** (the system must know the intended value); I place it at L3 per your taxonomy and flag the nuance.

## 2. Where our experiments have been (CONFIRMED, L0 AxForge/BeatAPI runs, patch versions not pooled)
| Level | Distinct cases run | Correct diagnoses | Notes |
|---|---|---|---|
| L1 | 3 (006, 018, 049) | **0** (3 wrong, 1 abstain) | the simplest faults failed |
| L2 | 4 (002, 008, 010, 022) | 1 case (002, dev, BeatAPI) | 010 wrong x3 runs |
| L3 | 7 | 0 (7 abstentions) | |
| L4 | 7 (4 are the Redis-host family) | 18 of 20 runs | logs carry a traceback |
So we have tested mostly L3/L4 and the easy-for-the-system L4 cases succeeded **because a traceback was in the logs**, not because they are simple. Level 1 has effectively never been given a fair test.

## 3. Evidence that Level 1 is solvable with the right input (offline, no model)
For one representative case per test code group plus four dev cases (23 faulty trees), I ran the visible suite locally, took the failing visible test ids and assertion lines as the query, and checked where the gold function lands:
- **The visible suite fails on 22 of 23** (exception: `stock_check`, where only the reproducer fails). So the bug is exposed by visible tests in nearly every case.
- **Graph:** the gold function is exactly **1 hop** (`tests_covers`) from a failing visible test in 21 of 22 (the other is 2 hops).
- **Lexical:** BM25 over the failing-test text places the gold function in the top 50 in 22 of 23 but in the **top 10 in only 15** (ranks 2, 4, 4, 5, 5, 5, 5, 8, 8, 9, 9, ...; worst 36 and 38 for `total_loop`).
- The current prompt contains none of this (no symptom, no failing tests): CONFIRMED in `diagnosis-root-cause-report.md`. So whether graph helps is **UNKNOWN until tested**, but this is the first concrete mechanism by which G could beat L (failing test, then `tests_covers`, then function), and L1 is where it can be measured cleanly.

## 4. Are ground truth and visible tests adequate?
- Ground truth: **adequate** (validated 3x on three trees, hidden inputs differ, leakage scan, gold fix = reverse of mutation). Hidden tests live only in `datasets/hidden_tests`.
- Visible tests: expose the fault in 22 of 23 sampled; dev `tax_base` has one variant (011) where the visible suite is green (reproducer only). Dataset notes also record 8 dropped variants nobody could observe.
- Weak points to report as validity threats: all sites were written by one session (author bias, D28 open); variants of one site are near-duplicates, so **independent sites matter, not case count**; graph `distance` is a manual estimate; reproducer and hidden tests share test names (guard issue); live-lab evidence is the same healthy bundle for every code fault (root-cause report); evidence bundles exist for only 4 dev and 19 test cases (collection needs Docker, minutes per case).

## 5. Are new cases needed?
**Not for the first gate.** The dev split has 3 independent L1 sites and 2 L2 sites:
- `code:total_loop` (096, 168, 182), `code:stock_decrement` (014, 027, 067, 173), `code:tax_base` (011*, 058, 085), L2: `code:discount_formula` (039, 097, 113, 140), `code:quantity_upper_bound` (002). (*visible suite green.)
- The test split has 8 more L1 sites, but it is frozen and official-tier runs have already touched it; I propose **not** using it for development. I only read it offline for the numbers above (no tuning).
- Three sites is enough to find gross failures but not to claim a level passes broadly. If the gate passes, I propose (decision D-A) adding at most 6 new dev-only L1 cases in a **separate dev-track manifest**, each: one fault, one function, an independent hidden suite, validated 3x by the existing validator, no new service dependency (pure functions through the existing in-process test client). Candidate fault types not yet covered: missing None check, wrong comparison operator, wrong return value in a pure helper. Not created until you approve.

## 6. Proposed initial batch (6 cases, 3 independent sites, dev split)
`shop_api-096`, `shop_api-182` (total_loop), `shop_api-014`, `shop_api-067` (stock_decrement), `shop_api-058`, `shop_api-085` (tax_base). All have a failing visible suite. `011` (visible green) is held for a later robustness check. L2 (`039`, `002`) is held until L1 passes.

## 7. Success criteria for Level 1 (fixed before any run)
Stage D, diagnosis only (no patches generated; run to `submit_diagnosis`):
- class correct on **6/6**; exact function (`path::qualname`) correct on **>= 5/6** and on every site at least once;
- abstention **<= 1/6**; every cited evidence id supports the claim (checked by a script, 0 unsupported claims);
- **>= 1 correct source localisation per site at both L and G**; report relevant vs irrelevant retrieved chunks (gold-in-context, overlap L vs G) for every case.
Stage P, patch (only cases with a correct diagnosis): patch applies **100%** of attempted; targets the gold file **100%**; visible pass **>= 5/6**; hidden pass **>= 5/6**; **0 regressions** (no previously passing visible test fails); hidden run once, never fed back.
Stage F, feedback (only after D and P pass): only visible output delivered, provenance recorded, attempt-2 request logged with the feedback; report change in patch and outcome; **no improvement claimed unless a case moves from fail to pass with feedback and not without**; expect few opportunities.
Level gate: all of D and P thresholds met, token cost reported, and no unexplained cache replay counted as independent. With 3 sites the conclusion is limited to "works on these 3 sites". Failing a gate means stop and investigate before any new level.

## 8. Workflow and commands (nothing run yet)
0. Verify the AxForge ledger (`python -m traceforge.evaluation.usage_report`; committed now 872,241, ceiling 2,400,000).
1. **Zero-token offline step** (needs approval to add a small script to the repo, otherwise stays in the scratchpad): retrieval comparison L vs G vs union for the 6 cases, per-case gold-in-context, overlap, irrelevant fraction.
2. **Evidence:** `python -m traceforge.agent.lab_collect --case shop_api-096 --case shop_api-182 --case shop_api-014 --case shop_api-067 --case shop_api-058 --case shop_api-085 --manifest ../datasets/manifests/dev.json` (Docker, no tokens, a few minutes per case).
3. **Code changes needed first (need approval; versioned as dev-track config `dev-d1`, not the formal pipeline):** (a) diagnose prompt gets the symptom and the baseline visible-failure output (run the visible suite on the base before diagnosis; today only the reproducer is run); (b) evidence rendering with path:line and "declared default" labels; (c) a diagnosis-only switch so no patch is generated after Stage D; (d) fix the submit-length/budget defect. There is currently **no diagnosis-only option and no "combined" (union) retrieval mode** in `runner.py` (only L and G); union would be computed offline or added behind a dev flag.
4. **Stage D (model):** `python -m traceforge.evaluation.runner --manifest ../datasets/manifests/dev.json --condition L0 --run-id dev-axforge-L0-dtL1-d1 --split dev --case-ids <6 ids> --provider axforge --model glm-5.3-flash --real --evidence-dir ../runs/evidence --out ../results/development --workers 1 --axforge-billing-verified`, then the same with `--condition G0` and a `-G0-` run id. Records land in `results/development`; the runs are labelled development tier, never official.
5. Stage P and F only for cases that pass D, with new run ids; the in-place scripts (`classify.py`, `audit.py`) already tabulate per-layer outcomes.
6. Report per level: cases, diagnosis accuracy, localisation, patch application, visible, hidden, abstention, graph contribution, feedback contribution, tokens.

## 9. Token cost estimate (hypotheses; measured baselines: about 30k per case for an abstaining diagnosis, 2k in and 0.1 to 8k out per patch attempt)
- Offline steps and evidence collection: **0 tokens**.
- Stage D: 6 cases x 2 arms (L0, G0) x about 30k = **about 360k** worst case. A staged start of 3 cases at L0 only is **about 90k** and serves as a go/no-go.
- Stage P: up to 6 cases x 3 attempts x up to about 10k = **about 180k** worst case, typically far less (patch replies are usually 100 to 300 tokens).
- Stage F: **about 60k**, only on failures.
- Worst case total about 600k (39% of the 1,527,759 remaining before the ceiling; the 600k reserve is untouched). Recommended spend before the first review: about 90k.

## 10. Risks to the existing research
- **Contamination:** none if only the dev split is used and the test split stays unseen. I read test-split cases offline for analysis only (no tuning, no prompt use). Do not add a test-split L1 site to the dev track.
- **Methodology separation:** dev-track config `dev-d1` changes diagnosis inputs (symptom, visible-failure output). That is Decision D1 from the earlier plan, now scoped to the development track only. It must not be silently adopted by the formal L0/G0/L1/G1 pipeline; adopting it there needs a documented new pipeline version.
- **Evidence mismatch:** dev bundles exist for 4 cases only; collecting needs Docker and the same lab base sha (`5ec94a43f8b9...`); a stale bundle is rejected by `bundle_current`.
- **Interim code:** the uncommitted guard narrowing, 8192 patch cap and no-cache rule stay in the working tree; they would apply to dev-track runs. They should be listed as part of `dev-d1`, not hidden.
- **Provider:** AxForge has been intermittent (429/502/504). The workflow halts after the first failure and does not retry in a loop.
- **Statistics:** 3 sites, 6 cases cannot support generalisation; near-duplicate variants must not be counted as independent.

## 11. Decisions needed
1. Approve the dev-split-only L1 batch of 6 cases (section 6).
2. Approve the dev-track config `dev-d1` (symptom + baseline visible-failure output in the diagnose prompt, honest evidence labels, diagnosis-only switch, submit fix) as separate from the formal pipeline.
3. Approve the staged spend (3 cases, L0 only, about 90k tokens) as the first model call.
4. Decide D-A: whether to create up to 6 new dev-only L1 cases after the gate.
