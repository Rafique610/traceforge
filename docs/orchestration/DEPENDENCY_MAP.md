# Dependency map (Track B, with cross-track inputs)

**Independent now (parallel):** P0-S03, P1-S05, P1-S04, P0-S06-B (needs a usable model), provider research.

**Sequential:**
- P1-S04 + P1-S05 → P1-S06 → P1-S07 (also needs Rafique's P1-S03).
- P1-S06 → P2-S04 (needs Rafique's P1-S02; use a fake runner returning sample `TestRunResult`) → P2-S05.
- P2-S06 needs only P1-S04.
- P3-S03 can start on samples (needs P0-S03; P2-S05 later). P3-S04 needs P2-S04, P2-S07 (Rafique-led), P3-S02, P3-S01.
- P4-S01 needs frozen dataset + metrics + runner. P4-S03 needs P0-S04, P2-S06, P3-S03, P4-S02. P5/P6 follow P4.

**Shared-file contention:** Taskfile.yml, config.py, main.py, pyproject.toml, README.md → orchestrator serialises.

**Interfaces to freeze before parallel work:** contracts (exist), gateway `chat(...) -> ModelResponse`, incident service `transition()`.

**External blockers:** Q3 supervisor reply (P0-S04); Rafique's lab/sandbox/evidence/retrieval/dataset (P1-S07, P2-S07, real runs in P3-S04, P4+); provider sign-in (human); Mistral access (Q1).
