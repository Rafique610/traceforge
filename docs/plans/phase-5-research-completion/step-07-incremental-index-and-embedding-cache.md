# P5-S07 — Incremental chunk manifest, embedding cache and index verifier

Follow-up study **Retrieval modernization** (added 2026-11-24). Design: [retrieval-architecture-review.md](../../research/retrieval-architecture-review.md) section 3 (identity model, store layout, diff algorithm, workflow, scenarios). Decision D36. Conditional on frozen RC1 staying untouched; zero AxForge tokens.

## A. Task identification
| Field | Value |
|---|---|
| Phase | 5 Research completion |
| Step | 7 |
| Task ID | P5-S07 |
| Synverk card | — (not used, D16) |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | ESSENTIAL for embeddings; benefits caching generally |
| Effort | 2 days (design doc: 1.5 to 2.5) |
| Status | NOT STARTED |
| Branch | none (commit on `main`, D33) |

## B. Objective
Make embedding work incremental, resumable and auditable: a content-addressed vector cache plus a per-commit chunk manifest, so a code change re-embeds only changed chunks, a model upgrade builds a new namespace, and a verifier proves the index matches the source tree. Graph edge refresh stays separate from re-embedding.

## C. Prerequisites
- The data model can start in parallel with P5-S06; end-to-end use needs the P5-S06 chunk inventory.
- Review decisions: numpy flat store (no pgvector, FAISS or vector DB); the Postgres image is not changed.

## D. Technical background (full design in review section 3)
- Chunk identity: `chunk_key` = sha256(kind + qualname) (path stored as metadata); `content_hash` = sha256 of normalized text; `embed_key` = hash of (content_hash, model_id, revision, dims, preprocessing_version).
- Manifest diff classifies chunks as new / modified / deleted / moved; the embedding decision is authoritative via `ns.has(embed_key)`, the diff explains and audits.
- Three update classes kept apart: re-embed, re-link (edges), metadata-only.
- Layout: `models/<model_ns>/{vectors.npy,index.sqlite,model.json}`, `manifests/<repo_ns>/<commit>.json`, atomic `ACTIVE` pointer, write-ahead log.
- The existing per-function sha1 (12 hex) in graph facts is not reused for identity; sha256 is computed in the new module. `codeintel/*` and frozen files are not edited.

## E. Implementation instructions
1. New files outside the frozen list (e.g. `retrieval/embed_store.py`, `retrieval/manifest.py`, `retrieval/index_verify.py`), none imported by a frozen file, each <= ~300 lines.
2. Chunker wrapper over the existing corpus builder that adds `content_hash` / `chunk_key` without changing chunk boundaries or ids.
3. Namespaced store with idempotent batched puts (fixed batch size and order), resume after a crash, tombstones and explicit `gc`.
4. Manifest writer with `tree_hash`, `edges_hash`, `chunker_version`; atomic temp-file + `os.replace` for manifest and `ACTIVE`.
5. `plan(prev, cur, ns)` diff and a CLI that prints the plan (counts of new / modified / deleted / moved, need_embed, relink).
6. Verifier: recompute tree hash and every content hash, check each embed_key exists, dims match `model.json`, no NaN, report orphans.
7. Exclusion filter shared with the benchmark: never embed hidden tests, mutation patches, gold manifests or faultgen artifacts.
8. Tests use a deterministic fake embedder (no model needed).

## F. Checklist
- [ ] Identity functions and normalization with tests
- [ ] Manifest write/read, atomic switch
- [ ] Diff: new / modified / deleted / moved cases
- [ ] Store: idempotent put, resume, namespaces, gc
- [ ] Verifier and CLI
- [ ] Scenario tests for the six scenarios in review section 3.7
- [ ] Fingerprint unchanged; README updated

## G. Expected deliverables
New modules and tests; commands for plan / build / verify / gc; short operator notes in the README.

## H. Testing and validation
- Scenarios: body change -> 1 re-embed; added function -> 1; deleted -> 0 (tombstone); rename with the name in the embedded text -> 1 re-embed, metadata-only move -> 0; import change -> 0 embeddings and edge re-link only; new model -> new namespace, old untouched.
- Crash test: kill mid-batch, rerun resumes without duplicates; `ACTIVE` never points at a partial manifest.
- Verifier detects: edited source, missing vector, wrong dims, orphan vector.
- Acceptance: all tests pass with the fake embedder; two builds of the same commit give identical manifests and vectors; fingerprint `ee3d8d87...` unchanged; no network, 0 tokens.

## I. Dependencies and integration
- **Informed by:** retrieval-architecture-review.md sections 3 and 6.2.
- **Depends on:** P5-S06 (the data-model work runs in parallel with it).
- **Unblocks:** P5-S08 (dense index build and fusion arms).

## J. Definition of done
Tests green, verifier demonstrated on the dev corpus with the fake embedder, reviewed by Ruhan; NEEDS REVIEW, then owner approval.
