# TraceForge — project facts

**What it is.** A review-first system that takes a reproducible failure in a Dockerized Python service, collects read-only evidence, links it to the exact code symbols and config keys, diagnoses the root cause (or abstains), proposes a minimal code/config patch, and verifies it against hidden tests in a sandbox. An engineer approves or rejects the frozen patch. Nothing is deployed.

**Course.** AI-4009 Generative AI, FAST-NUCES. R&D Product track. Supervisor: Sir Akhtar Jamil.
**Team.** Muhammad Rafique (23i-0747), Muhammad Ruhan Kamran (23i-0062). Taha Ahmed is no longer on the team.
**Repo.** https://github.com/Rafique610/traceforge (public, owned by Rafique; Ruhan is a collaborator). `main` is protected; every change lands by PR reviewed by the other member.
**Work split.** Two parallel tracks with separate folders, joined only through `backend/traceforge/contracts/`. Track A (Rafique): lab, datasets, evidence, codeintel, retrieval, sandbox, evaluation. Track B (Ruhan): incidents, agent, repair, reviews, reports, github, frontend. Details in `docs/plans/end-to-end.md`.
**Hardware.** Both members: Windows, Docker Desktop, 6 GB VRAM GPU (Rafique: RTX 3050 6GB Laptop).
**Budget.** USD 0. Free API tiers and local models only.

## Scope (after supervisor review)
- In: configuration faults and Python application-code faults in a Docker Compose lab (API, queue worker, Postgres, Redis).
- Read-only only: infrastructure state (container health, logs, reachability). A dependency outage is a valid *diagnosis* (`runtime_dependency`) with no patch.
- Out: production deployment, automated recovery, multi-agent, MoE/SSD offload, fine-tuning, non-Python languages.

## Research question
Does evidence-bound graph retrieval improve root-cause localization and independently verified repair over lexical retrieval, and what does iterative test feedback add? 2×2 design: graph on/off × feedback on/off.

Design rules that make the comparison fair:
- Both retrieval arms get traceback anchoring (forced inclusion of the trace span). The graph arm adds only graph distance, ≤2-hop expansion and config-key binding.
- Both feedback arms get 3 attempts. F0: each attempt starts fresh. F1: each attempt sees visible test output. Hidden tests run once on the final patch and never feed back.

## Outcome classes
`configuration`, `application_code`, `runtime_dependency` (diagnose, no patch), `insufficient_evidence` (abstain).

## AI components (each needs ≥50 held-out labelled examples)
1. Retrieval (deterministic ranking; evaluated with Recall@5, MRR, nDCG@10).
2. Diagnosis (LLM; cause class + exact target, abstention precision).
3. Repair (LLM; independently verified repair rate).
The report is a deterministic template filled from the evidence ledger, not an AI component. Tool-use quality is measured through task success and invalid-call rate.

## Stack
| Part | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, PostgreSQL 16 |
| Frontend | Vite + React + TypeScript |
| Code intel | Python `ast`, Compose YAML parse, BM25 (`rank-bm25` or Postgres FTS, decided in its step), networkx |
| LLM | One OpenAI-compatible gateway. Primary: Mistral free tier, pinned Devstral model. Comparator/offline: Qwen2.5-Coder-7B via Ollama. Spare: Groq free tier. |
| Integration | GitHub REST (read issues from a fixtures repo) |
| Lab | Docker Compose: `shop-api` (FastAPI), `worker` (Redis queue consumer), Postgres, Redis |

## Folder layout
```
backend/traceforge/<feature>/   contracts, incidents, evidence, codeintel, retrieval, sandbox, agent, repair, reviews, reports, github, evaluation
frontend/src/<feature>/
lab/                            fixture services + compose + their public tests
datasets/                       generator, manifests (dev/test), hidden_tests/
docs/                           this tree
Taskfile.yml
```

## Phase status
Planning complete; no code yet. Execution manual: `docs/plans/README.md` (7 phases, 35 steps, task IDs `P<n>-S<nn>` mapped to Synverk cards TRAC-1…32).
