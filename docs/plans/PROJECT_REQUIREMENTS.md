# Project requirements

IDs: `FR-` functional, `NFR-` non-functional, `SR-` security, `IR-` integration, `ER-` evaluation. The step that delivers each requirement is in brackets.

## Functional requirements
| ID | Requirement | Delivered by |
|---|---|---|
| FR-01 | Create an incident from a lab fault case (`case_id`) or free-text symptom + service. | P1-S04 |
| FR-02 | Create an incident from a GitHub issue URL; issue text stored as untrusted evidence. | P2-S06 |
| FR-03 | Pin each incident to a Git SHA and Compose file hash before any analysis. | P2-S01 |
| FR-04 | Collect read-only evidence: container status/health/exit code, capped log window, redacted effective config, parsed traceback frames, Compose services/env keys. | P2-S01 |
| FR-05 | Build a code/config dependency graph with typed nodes and provenance-carrying edges; unresolved edges kept as `UNKNOWN`. | P2-S02 |
| FR-06 | Retrieve a ranked, cited `ContextBundle` in mode L (lexical + trace anchor) or G (L + graph features) under an identical token budget. | P2-S03 |
| FR-07 | Diagnose into exactly one of `configuration`, `application_code`, `runtime_dependency`, `insufficient_evidence`, with target and supporting/contradicting evidence IDs. | P1-S06 |
| FR-08 | No patch for `runtime_dependency` or `insufficient_evidence`. | P1-S06, P2-S04 |
| FR-09 | Generate a unified diff; enforce path allowlist, no test-file edits, size limit. | P1-S06, P2-S04 |
| FR-10 | Verify: reproducer fails on base, passes on patch; hidden suite and existing tests pass; outcome `TEST_VERIFIED_IN_LAB`, `REJECTED` or `UNVERIFIED`. | P2-S04 |
| FR-11 | Feedback conditions F0/F1, both with up to 3 attempts; F1 sees visible test output only. | P2-S04 |
| FR-12 | Deterministic report from stored records; every claim links to an evidence or test ID. | P2-S05 |
| FR-13 | Approve/reject bound to the frozen patch SHA-256; mismatched hash rejected; review immutable. | P2-S05 |
| FR-14 | Reviewer UI: list, create, investigate, timeline, evidence, ranked hits, hypotheses, diff, tests, cost, review. | P0-S03, P3-S03 |
| FR-15 | Experiment runner: run a condition over a frozen manifest, resumable, saving one `AgentRunRecord` per case. | P3-S04 |
| FR-16 | Results page rendering metrics computed from saved runs. | P3-S04, P3-S02 |

## Non-functional requirements
| ID | Requirement | Target / check |
|---|---|---|
| NFR-01 | Reproducibility: temperature 0, pinned model ID, prompt hashes, LLM response cache, dataset hash per run. | Rerunning a finished experiment from cache gives identical records. |
| NFR-02 | Cost: USD 0 actual spend. | Gateway logs show free-tier/local providers only. |
| NFR-03 | Latency recorded per case (median, P95). | Present in every run record; no fixed target until measured (see open questions). |
| NFR-04 | Sandbox test run fast enough for ~1,600 A4 runs. | Measured in P1-S02; budget derived in P5-S03. |
| NFR-05 | Code quality: files ≤ ~300 lines, feature folders, ruff clean, tests for every non-trivial unit. | `task lint`, `task test`, review. |
| NFR-06 | Real data only in UI, reports and slides. | Review checklist in every UI/report step. |
| NFR-07 | Runs on Windows + Docker Desktop with a 6 GB GPU. | Both members can run `task dev`, `task lab:up`. |

## Security requirements
| ID | Requirement | Delivered by |
|---|---|---|
| SR-01 | LLM gets typed tools only; no shell, no `docker exec`. Arguments validated. | P1-S06 |
| SR-02 | Everything model-visible (logs, code, comments, issues) is data, not instructions. | P1-S06, P2-S06, P6-S01 |
| SR-03 | Secrets and env values redacted before prompts, indexes, reports. | P2-S01 |
| SR-04 | Hidden tests never reach the model, directly or via feedback. | P2-S04 |
| SR-05 | Only trusted backend talks to Docker; collector via read-only socket proxy; sandbox containers have no socket, no network, resource caps, non-root. | P1-S02, P2-S01 |
| SR-06 | Credentials only via `Settings`/`.env`; never in tracked files or logs. | P0-S02 onward |
| SR-07 | Review bound to patch hash; nothing deployed from a review. | P2-S05 |

## Integration requirements
| ID | Requirement | Delivered by |
|---|---|---|
| IR-01 | Tracks exchange data only through the five contracts in `backend/traceforge/contracts/`. | P0-S05 |
| IR-02 | One OpenAI-compatible gateway for Mistral, Ollama, Groq. | P1-S05 |
| IR-03 | Real GitHub REST integration (rubric C4). | P2-S06 |
| IR-04 | Frontend talks only to the FastAPI REST API. | P0-S03, P3-S03 |

## Evaluation requirements (Assignment 3 rubric, stage D)
| ID | Requirement | Delivered by |
|---|---|---|
| ER-01 | ≥50 labelled held-out examples per AI component (retrieval, diagnosis, repair), separate from dev examples. | P3-S01 |
| ER-02 | Metrics suited to each component, computed by script from saved runs. | P3-S02 |
| ER-03 | Baseline comparison per component (L vs G retrieval; rules vs LLM diagnosis; L0 vs G0 repair). | P3-S02, P4-S01 |
| ER-04 | ≥10 failure examples grouped by cause with planned fixes. | P4-S02 |
| ER-05 | Latency and cost per request measured on the running system. | P1-S05, P4-S01 |
| ER-06 | First R&D experiment against a baseline. | P4-S01 |

## Constraints
- Python 3.12 + uv; FastAPI; SQLAlchemy 2 + Alembic; PostgreSQL 16; Vite + React + TS with pnpm; Taskfile; Docker Compose; Ollama.
- Two members; work split into two lanes with separate folders.
- Mistral free tier (reported ~1 request/second; exact limits to be read from the admin panel in P1-S05).
- `main` blocks force push and deletion; either member may merge their own work (review optional).

## Acceptance criteria (whole project)
- **A3:** a config case and a code case go from UI input to a verified patch and stored review; a runtime_dependency decoy is diagnosed without a patch; an insufficient-evidence case abstains; a GitHub issue creates an incident; results page shows E1 and L0 vs G0 from saved runs on the frozen set; ≥10 failure analyses; both members demo and explain.
- **A4:** full 2×2 × 3 replicates with paired CIs; model comparison; security suite; CI green; public app link; paper and pitch.
