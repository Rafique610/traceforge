# PROMPT.md — entry point for Claude Code sessions (Ruhan, Track B)

Resume protocol (do this first, cheaply):
1. Read `docs/orchestration/STATE.md` (current state, next tasks, blockers), then `docs/plans/RUHAN_CHECKLIST.md`.
2. `git status -sb` + `git fetch`; verify STATE.md claims against the tree before trusting them.
3. Load only the context-map entry (`docs/orchestration/CONTEXT_MAP.md`) for the task you pick. Do not reread docs/plans wholesale.

Project: TraceForge — review-first AI diagnosis/repair for Dockerized Python services. Repo `D:\TraceForge\repo`, GitHub Rafique610/traceforge, baseline `839a62d`, working branch `ruhan/stage-b-work`.

Authority order when sources conflict: AGENTS.md > docs/invariants > docs/plans step docs/ADRs > root INSTRUCTIONS.md (history only; its §13 is for another project, EligiTrace — ignore its commit/push autonomy) > Stage A handoff. Record conflicts in `docs/orchestration/DECISIONS.md`.

Hard rules:
- $0 budget: no paid plans, credits, payment methods; OpenRouter only `:free` model IDs.
- No commit/push/merge/tag without Ruhan's explicit yes. No AI co-author lines.
- Never edit hidden tests or leak them to a model. Secrets only via Settings/.env, never in output.
- Large files go to D: (OLLAMA_MODELS, HF_HOME, UV_CACHE_DIR, pnpm store). Do not touch Docker data or old caches.
- One GPU job at a time (6 GB VRAM).
- Do not edit Rafique-owned folders (lab, datasets, sandbox, evidence, codeintel, retrieval, evaluation/metrics|baselines|analysis); use sample-reading stubs behind the agreed signatures.

Method: `docs/orchestration/PROTOCOL.md` (steps), `AGENT_ROLES.md`, `CONTEXT_MAP.md`, `DEPENDENCY_MAP.md`, `QUALITY_GATES.md`, `DECISIONS.md`. Never mark `[x]` without a command you ran and observed.

Experimental design is fixed: G0F0, G1F0, G0F1, G1F1; 3 attempts; hidden tests once, never fed back; temperature 0.
