# P4-S03 — Demo script and submission pack

## A. Task identification
| Field | Value |
|---|---|
| Phase | 4 Assignment 3 delivery |
| Step | 3 |
| Task ID | P4-S03 |
| Synverk card | TRAC-23 (part 3 of 3) |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | Muhammad Rafique |
| Reviewer | Muhammad Rafique |
| Priority | High |
| Effort | 1.5 days |
| Status | NOT STARTED |
| Branch | `ruhan/P4-S03-demo-pack` |

## B. Objective
A demo that works live with realistic inputs (E1), a presentation where both members present (E2), and a complete submission package (eligibility A1–A5). The clean-clone dry run is the final gate for Assignment 3.

## C. Prerequisites
- P0-S04 (proposal + approval), P2-S06 (GitHub intake), P3-S03 (UI), P4-S02 (slides).

## D. Technical background
- Demo cases are chosen from **dev** cases (or held-out cases already reported), never by re-running test cases until they look good.
- Rubric C5 accepts "reproducible from the repository" instead of a public link: the README must make a fresh clone runnable.
- Have a fallback: cached LLM responses for the demo cases, so a provider outage doesn't kill the live demo (state this openly if used).

## E. Implementation instructions
1. **Demo script** (`docs/demo/a3-demo.md`, ~8 minutes):
   1. Healthy lab; show architecture slide (Rafique).
   2. Code case: create from lab case → investigate → evidence → ranked hits → diagnosis → diff → red/green + hidden pass → approve (Ruhan).
   3. Config case with distance ≥1: show graph path in the hit reasons (Rafique).
   4. runtime_dependency decoy (Redis stopped): diagnosis, no patch (Ruhan).
   5. GitHub issue intake → incident (Ruhan).
   6. Tampered-hash review rejected (Ruhan).
   7. Results page: E1, rules vs LLM, L0 vs G0, latency/cost, failures (Rafique).
2. **README** final pass: prerequisites, `.env` setup, `task lab:build`, `task dev`, `task web`, how to run the demo cases, how to reproduce the reported results.
3. **Dry run:** Rafique clones fresh on his laptop and follows only the README (Ruhan watches, notes every gap); fix gaps; repeat until clean.
4. **Submission pack:** proposal PDF, approval evidence, track declaration (R&D), repo link (instructor access confirmed — repo is public), AI-tool declaration (ChatGPT, Claude, and any coding tools actually used, with purposes), slides.
5. Fill the rubric self-evaluation form honestly.
6. Tag after approval: `a3-submission` (tagging needs an explicit yes per AGENTS.md).

## F. Checklist
- [ ] Demo script with presenter per segment
- [ ] Demo cases chosen from dev/reported cases
- [ ] Cached-response fallback prepared and disclosed
- [ ] README complete for a fresh clone
- [ ] Clean-clone dry run passes on Rafique's laptop
- [ ] Two full rehearsals with timing
- [ ] Submission pack assembled
- [ ] Self-evaluation form filled
- [ ] Tag created after explicit approval

## G. Expected deliverables
`docs/demo/a3-demo.md`, updated `README.md`, submission package, git tag `a3-submission`.

## H. Testing and validation
- Dry run from a fresh clone; every demo segment works twice in a row.
- Acceptance: both members can run any segment and answer "show me the code behind this".

## I. Dependencies and integration
- **Depends on:** P0-S04, P2-S06, P3-S03, P4-S02.
- **Unblocks:** Phase 5 and 6 (Assignment 4).

## J. Definition of done
Dry run clean; rehearsals done; package submitted; TRAC-23 moved to review with the dry-run notes; approved by the project owner.
