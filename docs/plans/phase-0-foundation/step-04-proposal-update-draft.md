# P0-S04 — proposal update: change list and email draft (DRAFT, not sent)

Status: **drafted 2026-11-21; NOT done.** Needs the proposal PDF (not in the repo), Ruhan's edits to it, Rafique's technical review, and, if wanted, the supervisor's written confirmation of the revised version (open question Q3 is ANSWERED-CONDITIONAL by the 18 Nov email, which arrived after this draft). Nothing here has been sent. No roll numbers in this file; they stay in the PDF kept outside the repo.

## Changes to make in the PDF (from step-04 section E, checked against the docs on 2026-11-21)
| # | Section | Change | Source |
|---|---|---|---|
| 1 | Team (1, 12) | Two members; responsibilities = Track A (Rafique) / Track B (Ruhan) | TEAM_WORK_DISTRIBUTION §1 |
| 2 | Models (5, 9, 10) | Replace GPT-4.1-mini as primary. Current plan: provider-agnostic gateway with a free-only guard; local Qwen2.5-Coder-7B via Ollama and OpenRouter `:free` models. **Decision needed:** the step doc still says Mistral free tier + pinned Devstral; research on 2026-11-21 found Devstral 2 needs paid API access (see docs/research/free-model-providers.md) | DECISIONS D5/D21, B4 |
| 3 | Hardware | Correct to the real machines (desktop GTX 1660 SUPER 6 GB; teammate RTX 3050 6 GB per docs) | domain doc, Q9 |
| 4 | Method/evaluation (6, 8, 13) | Hidden tests run once at the end and never feed back; both feedback arms get up to 3 attempts; traceback anchoring in both retrieval arms (graph adds distance, ≤2-hop expansion, config binding); outcome class `runtime_dependency` beside abstention | D10 |
| 5 | Evaluation (8) | AI components = retrieval, diagnosis, repair; report is a deterministic template; dataset 60 config + 60 code + 12 runtime_dependency + 12 insufficient_evidence held-out, ≥30 dev | D12, D15 |
| 6 | Safeguards (13) | Five safeguards: distance labels (≥50% distance ≥1), pipeline-first agent, rule baseline, LLM response cache, freeze before tuning | D11 |
| 7 | Cost (business) | Recompute with a cited official price. Mistral Large $0.50/$1.50 per 1M tokens (official page, per step doc); Devstral list price still unknown (Q2) | Q2 |
| 8 | Typo | "R&D;" → "R&D" (two places) | step-04 |
| 9 | AI-tool declaration | ChatGPT (drafting), Claude (review, planning, documentation, and implementation assistance — state the actual use accurately); Ruhan to confirm wording against course rules | step-04 |
| 10 | Added since the step was written | Feasibility prototype (P0-S06): retrieval spike + model probe feed edit format, context budget and model choice | D18–D25 |

## Email draft (to the supervisor, both members in CC)
Subject: TraceForge — revised proposal for your approval (scope and R&D track)

Dear Sir Akhtar Jamil,

Following your review, we have revised the TraceForge proposal and attach the updated PDF. In short:
- the team is now two members, with the work split into an evidence side and an agent side;
- scope is narrowed to configuration and Python code faults in a Dockerized lab; infrastructure is read-only evidence;
- the design is a 2×2 experiment (graph retrieval on/off × test feedback on/off), with hidden tests run once and never fed back to the model;
- evaluation covers three AI components (retrieval, diagnosis, repair) on a frozen held-out set, with a rule-based baseline;
- models are free or local only (budget USD 0).

Could you please confirm in writing that you approve the revised scope and the R&D Product track?

Regards,
Muhammad Ruhan Kamran and Muhammad Rafique

## Remaining checklist (from the step)
- [ ] Edit the PDF per the table  - [ ] Rafique reviews technical sections  - [ ] Re-check all reference URLs  - [ ] Send email  - [ ] Register title in the Project Titles sheet  - [ ] Save the reply outside the public repo
