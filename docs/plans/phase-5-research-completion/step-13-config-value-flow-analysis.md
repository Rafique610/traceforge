# P5-S13 — Config value-flow analysis (Tier 2)

Follow-up study **Root-cause and impact analysis** (added 2026-11-25, PROPOSED, pending owner approval Q18). Design: [root-cause-impact-regression-design.md](../../research/root-cause-impact-regression-design.md) section 4 (and section 8 for secrets). Decision D37 (proposed); assumption AS12 (feasibility unmeasured). Zero tokens.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 13 |
| Task ID | P5-S13 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Tier 2 (start only after the MVP shows a measurable gain) |
| Effort | 3 days (ASSUMPTION, not measured) |
| Status | NOT STARTED (Tier 2; gated on the S12 MVP showing a gain, which it did not for call chains) |
| Branch | none (commit on `main`, D33) |

**Status sync 2026-11-25.** Evidence: No code. Code implemented by Ruhan's Claude-assisted session at the owner's direction on 2026-11-25; NOT reviewed by Rafique; the task stays Rafique's.

## B. Objective
Add values to the overlay so configuration root causes (wrong hostname, port or default) become representable, with model-free mismatch checks. Kept only if P5-S16 shows it localizes configuration causes better than the graph alone.

## C. Prerequisites
- P5-S12 (overlay, evidence classes).
- Gate: MVP results (P5-S12, S15, S16-reduced) show a gain; otherwise stop.

## D. Technical background
- Today `.env` reads key names only and compose edges carry the key, not its value (design section 1).
- Scope (section 4): stdlib `ast` plus `symbols.py` by default. `jedi`, `libcst`, `pycg` / `pyan` are **TO EVALUATE** (not tried); adopting any is an owner decision (new dependency).
- Non-goals: sound points-to analysis, dynamic imports, metaprogramming, flow through containers, interprocedural flow beyond one hop.
- Secret handling: `.env` stays name-only; secret-named keys are never stored; reports redact.
- Feasibility on the evaluation fixtures is unmeasured: AS12.

## E. Implementation instructions
1. Value extraction in the overlay: compose literals (`environment:`, `ports`, `command`, service names), settings defaults (`Field(default=...)`, `os.getenv("X", "d")`, `os.environ.get`). Do not read `.env` values; denylist of secret-name patterns (e.g. KEY, TOKEN, SECRET, PASSWORD) never stored, redacted in output.
2. One config chain: env name -> compose entry -> settings field -> attribute read -> constructor/client argument; constant propagation over names and attributes, one interprocedural hop and simple wrapper returns.
3. Model-free checks: hostname matching no compose service; key read but absent from compose; key set but read by nothing; case/prefix mismatch; code default vs compose; client port vs service port. Each finding `static` or `inferred` with file:line on both sides.
4. Limited exception propagation: direct `raise`/`except`/re-raise within a function plus one call hop.
5. Dependency injection: constructor arguments one hop; FastAPI `Depends` only via explicit parameter default; else `unknown`.
6. Short TO EVALUATE note comparing stdlib `ast` with `jedi`/`libcst`/`pycg` on three fixtures; default stays `ast`.

## F. Checklist
- [ ] MVP gain confirmed (gate)
- [ ] Value extraction with secret denylist; test that no secret-named value is stored or printed
- [ ] Config chain and one-hop propagation
- [ ] Four mismatch checks on fixtures
- [ ] Exception propagation (one hop)
- [ ] TO EVALUATE note on jedi/libcst/pycg
- [ ] RC1 fingerprint unchanged

## G. Expected deliverables
New modules under `backend/traceforge/analysis/`, tests, evaluation note, secret-leak test.

## H. Testing and validation
- Unit: each mismatch check has a positive and a negative fixture; secret-named keys absent from graph, reports and logs; deterministic output.
- Acceptance: scenario D and E results from P5-S16 against preregistered thresholds; otherwise dropped.

## I. Dependencies and integration
- **Informed by:** design sections 4, 8.
- **Depends on:** P5-S12.
- **Unblocks:** P5-S16 full set (scenario D, E).

## J. Definition of done
Reviewed by Ruhan; secret test green; findings labelled `static`/`inferred`; limits stated; no claim of complete data-flow or root-cause coverage.
