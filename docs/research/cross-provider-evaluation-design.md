# Cross-provider diagnosis evaluation: approved design and execution plan (NOT YET LAUNCHED)

Status 24 Nov 2026: the owner approved the 2x2 design with **two independent live replicates per provider/retrieval cell** and asked for an audit of reusable AxForge results and an updated execution plan **before anything is launched**. Nothing in this experiment has been run. It is a **separate experiment** from the primary dev-d1 evaluation (`dev-axforge-{L0,G0}-dd1-l1`, which stays AxForge-only, same model in both arms). L0/G0/L1/G1 definitions, the frozen test split and all existing results are unchanged; no result of this experiment is mixed into the primary comparison.

## 1. Approved decisions
1. Four cells: AxForge `glm-5.3-flash` L0 and G0; BeatAPI `glm-5.3-flash-free` L0 and G0. Same six frozen dev cases (096, 182, 014, 067, 058, 085; three independent sites), dev-d1 (pipeline v5), diagnose-only, temperature 0, live requests.
2. **Compare G0 versus L0 within each provider.** Raw accuracy is never compared between providers as if they were the same model.
3. Two independent live replicates per cell (x1, x2).
4. Reuse compatible existing AxForge results; do not duplicate compatible runs to fill a new directory.
5. Keep this experiment separate from the primary evaluation.

## 2. Model-variant confound (stated up front)
The providers serve differently named models, `glm-5.3-flash` (AxForge) and `glm-5.3-flash-free` (BeatAPI). That they are the same weights is **unverified**. Provider, model variant, serving stack, tool-call parsing (BeatAPI may return tool calls as text), output limits and rate limiting are confounded. The experiment can say whether the retrieval effect `G0 - L0` looks the same in two systems; it cannot say whether a difference between systems is due to the provider or to the model, and no sentence in a report may attribute it to either.

## 3. Compatibility protocol: what a result must match to be reused
A saved AxForge result fills a cell only if **all** hold (checked from the run's artifacts, `reuse audit` below):
| Field | Requirement | Evidence in the artifacts |
|---|---|---|
| Case and source tree | same case id, dataset sha, base sha | `records`, `meta.json` |
| Pipeline and prompt version | pipeline v5, prompt hash of `diagnose_v2 + patch_v5` | record `prompt_hash` equals `prompting.prompt_hash("v5")` |
| Retrieval condition | the cell's arm (L0 or G0) | record `condition`, `context_sent.json` arm |
| Model and provider | `axforge` / `glm-5.3-flash` | `run_meta.json` |
| Evidence input | the same evidence bundle | `run_meta.evidence_sha256` equals the sha of the current bundle file |
| Symptom input | **byte-identical to what the protocol now produces** (object addresses normalised) | no raw `0x...` address in the saved symptom items |
| Prompt/code state | current code reproduces the recorded prompt hash from the saved evidence | offline rebuild (below); future runs also store `code_fingerprint` |
| Generation settings | temperature 0, seed 0, live request, cache hits 0 | record |
| Replicate identity | a completed, independent live run with its own request chain | not a cache replay, not a resumed partial chain |

## 4. Reuse audit (done locally, no model request)
Existing AxForge dev-d1 runs: `dev-axforge-L0-dd1-smoke` (096, 014, 058) and `dev-axforge-L0-dd1-l1` (014; 058 only provider_error artifacts).
- **Prompt/code check:** the current code rebuilt the first diagnose request of all three smoke runs from their saved evidence and reproduced the recorded request hash **byte for byte** (058 `e39a85813fef`, 096 `5e3d091c5d60`, 014 `e64bf5520600`). So retrieval and prompt rendering are unchanged since those runs. Verified for the L arm (the arm they ran).
- **All other fields match** for every run: provider and model, pipeline v5, prompt hash `65d107ceb6...`, evidence sha equals the current bundle, temperature 0, seed 0, cache hits 0, development tier.
- **The symptom address difference:** pytest prints Python object addresses (`<Product object at 0x7dfb...>`). The symptom now normalises them to `0x...`.

| Run | Case | Address in saved symptom | Verdict |
|---|---|---|---|
| smoke | 058 (L0) | none | **compatible**: usable as AxForge-L0 replicate for 058 |
| smoke | 096 (L0) | 5 addresses | not strictly compatible (symptom differs from what the protocol now sends) |
| smoke | 014 (L0) | 1 address | not strictly compatible |
| `dd1-l1` | 014 (L0), the preserved primary result | 1 address (a different one) | not strictly compatible for this protocol; **kept** as the primary evaluation's result |
| `dd1-l1` | 058 | provider_error artifacts only | not a result |

**Decision on shop_api-014 (recorded explicitly):** the one-token difference is cosmetic in *information* (the address carries none; the two raw 014 runs differ from each other in exactly that one line and the normalised text differs from both only there), but it is **not byte-identical input**, and the model is already non-deterministic at temperature 0 (the two 014 samples used 1 and 2 tool calls), so its effect cannot be measured and is not assumed to be zero. Therefore: (a) in the **primary evaluation** the preserved 014 L0 result is kept and its pair with 014 G0 is reported as *near-paired* (one cosmetic token), with a sensitivity analysis that excludes 014; (b) in **this cross-provider experiment** the existing 014 L0 runs are **not reused**: strict pairing needs identical symptom text, so fresh 014 L0 replicates are required. The same rule excludes the smoke 096 and 014 runs here.

## 5. Replicate accounting (12 case-runs per cell, 48 in total)
A replicate counts only if it is a completed, live, uncached record from a clean request chain. Not counted: cache replays (cache is off in dev-d1), failed provider requests, a case that was interrupted by a provider failure (a resumed case restarts from its first request; the interrupted partial chain is a `provider_error` artifact, never half a replicate), incompatible historical runs (BeatAPI v4 runs, pre-normalisation symptoms). Replicates are labelled x1 and x2 by an explicit mapping file (run dir, case, replicate label), never by directory order.

| Cell | Needed | Reusable now | Expected from the pending primary evaluation (once it completes) | Still to run for this experiment |
|---|---|---|---|---|
| AxForge L0 | 12 | 1 (058 smoke) | 5 (096, 182, 067, 085, 058; normalised symptoms) | 6 (014 x2; 096, 182, 067, 085 one each) |
| AxForge G0 | 12 | 0 | 6 | 6 (one replicate for every case) |
| BeatAPI L0 | 12 | 0 | 0 | 12 |
| BeatAPI G0 | 12 | 0 | 0 | 12 |
The AxForge counts depend on the primary evaluation finishing; if a primary case fails, its replicate moves to "still to run". The primary evaluation is blocked right now by AxForge 429s (see `experiment-readiness.md` 15.1 and 16).

## 6. Pairing rules
- **Strict pair** (the unit of the within-provider effect): L0 replicate k and G0 replicate k of the same case, same provider, identical evidence sha, identical symptom sha256, same prompt version and generation settings. The arms differ only in retrieval.
- A pair that fails any of these is reported separately as non-strict and excluded from the headline effect (included in a sensitivity table).
- Within a provider the effect is `D = correct(G0) - correct(L0)` over strict pairs, reported with the paired table (both correct / only G0 / only L0 / neither) per case and per **independent site**; variants of a site are not independent confirmations.
- Across providers only the **effects** are compared (direction per site), never raw accuracy. With 3 sites no significance claim is made.
- Replicate disagreement inside a cell is the noise floor: an effect smaller than it is reported as not distinguishable from noise. Retrieval metrics (gold rank, overlap, unique hits, relevance) are provider-independent and computed once offline.

## 7. Failure-handling rules
- Halt on the first provider failure (BeatAPI: its existing halt; AxForge: dev-d1 now stops at the first failed request, no tolerance retries; tested). No automatic retry loops; a resume is a deliberate single invocation of the same run id; the runner refuses to resume a run id with a different provider/model/pipeline.
- A cell that cannot be completed is reported incomplete; it is never filled from another provider or from an incompatible run.
- Failed requests and `provider_error` case artifacts stay on disk and are never counted.
- Ledger checked before every AxForge run; ceiling 2.4M, reserve 600k; BeatAPI has its own ledger; no paid fallback.

## 8. Token and time estimates (assumptions flagged; measured AxForge dev-d1 per case: 7.6k, 15.0k, 18.0k, 25.4k tokens, mean about 16.5k, 1 to 3 requests of about 7k input)
| Provider / cell | Runs still to run | Estimate | Basis |
|---|---|---|---|
| AxForge L0 (cross-provider extra) | 6 | about 100k (50k to 150k) | measured mean x 6 |
| AxForge G0 (cross-provider extra) | 6 | about 100k (50k to 150k) | **no measurement yet** (assumed equal to L0) |
| AxForge subtotal for this experiment | 12 | about 200k (100k to 300k) | |
| AxForge: pending primary evaluation (separate) | L0 x5, G0 x6, controls x4 | about 300k | not part of this experiment |
| BeatAPI L0 and G0 | 24 | about 400k tokens each pair of cells combined (200k to 1.2M) on the BeatAPI ledger; **assumption**: same prompts, unknown verbosity of the free model | |
| BeatAPI wall time | 24 case-runs, about 48 requests | at least 72 min of pacing (90 s between requests), realistically 2 to 4 h | latency of the free model unmeasured |
AxForge after the primary evaluation and this experiment: about 938k committed now plus about 500k (range 300k to 850k) is about 1.4M of the 2.4M ceiling; the reserve is not touched.

## 9. Execution order (when approved)
1. Finish the primary AxForge evaluation first (`bash scripts/dd1_l1_eval.sh`, one invocation at a time when AxForge answers).
2. BeatAPI cells can run during AxForge outages, one BeatAPI run at a time, development tier, run ids `dev-beatapi-{L0,G0}-dd1-x{1,2}`, alternating arm order between replicates: `python -m traceforge.evaluation.runner --manifest ../datasets/manifests/dev.json --condition {L0,G0} --run-id dev-beatapi-{L0,G0}-dd1-x{1,2} --split dev --case-ids <six ids> --provider beatapi --model glm-5.3-flash-free --real --evidence-dir ../runs/evidence --out ../results/development --workers 1 --pipeline v5 --diagnose-only`.
3. AxForge extra replicates under `dev-axforge-{L0,G0}-dd1-x2` (and `...-x1` for the cases that need a fresh normalised run), then the mapping file and `diag_eval.py` scoring per cell.
4. One report: per-provider paired tables, the difference of effects, the provider-independent retrieval table, tokens and latency.
Every new run records `code_fingerprint` in its `meta`/`run_meta`, so later audits are exact rather than argued.

## 10. Risks and limits
- The model-variant confound (section 2); BeatAPI tool-call text parsing and undocumented output caps (formatting failures are recorded as such, not repaired).
- 3 independent sites: descriptive only.
- Level 1 symptoms expose the gold function name through visible test names (validity limitation); both arms see it, which limits what retrieval can show.
- Dev split only; nothing generalises to the frozen test split.
- Waiting cost: BeatAPI is slow by design; AxForge is currently unavailable.

## 11. Before launch, the owner is asked to confirm
1. This execution plan, the reuse verdicts (including the 014 decision) and the pairing/failure rules.
2. Whether the cross-provider AxForge replicates run after the primary evaluation completes (proposed) or whether the primary is declared blocked and this experiment starts first.
3. BeatAPI time window.
