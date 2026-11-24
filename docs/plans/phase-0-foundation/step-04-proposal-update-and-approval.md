# P0-S04 — Proposal update and supervisor approval

## A. Task identification
| Field | Value |
|---|---|
| Phase | 0 Foundation |
| Step | 4 |
| Task ID | P0-S04 |
| Synverk card | TRAC-3 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | Muhammad Rafique (technical sections) |
| Reviewer | Muhammad Rafique |
| Priority | High |
| Effort | 1 day |
| Status | PARTIALLY COMPLETE |

**Status sync 2026-11-25.** Evidence: revised PDF dated 23 Nov at `D:\TraceForge\proposal\TraceForge_Assignment3_Proposal.pdf` and a GCR_Upload pack exist on disk. The 18 Nov supervisor email authorises proceeding conditionally (see "Supervisor email (evidence)" below). The label stays PARTIALLY COMPLETE because a human step remains: the supervisor's written confirmation of the revised proposal is not on disk, and the title registration and Rafique review are not evidenced. Five-fact detail: `docs/plans/RUHAN_TASK_TRACKER.md`.

### Supervisor email (evidence)
- Email from Akhtar Jamil (supervisor) to Ruhan, Wednesday 18 Nov 2026, 10:41 AM, sent after he reviewed the first proposal. It calls TraceForge "an interesting work", the scope "a bit ambitious", asks to narrow the core contribution, and lists 13 recommended changes (obligations list in `docs/plans/PROJECT_REQUIREMENTS.md`).
- Key sentence: "You may proceed with the project after incorporating the recommended changes."
- Meaning: conditional written permission to proceed. It is NOT written approval of the revised version, NOT a signature or sign-off, NOT final acceptance, NOT a grade. The revised PDF (dated 23 Nov) incorporates the changes per the proposal's own changelog.
- The evidence file notes the supervisor also verbally approved continuing with the revised proposal; that is not a signed or written document.
- Paths (outside the repo): `D:\TraceForge\Assignment_3_TraceForge\Evidence\Supervisor_Email_Response.txt`, `D:\TraceForge\Assignment_3_TraceForge\Evidence\Supervisor_Email_Screenshot.png`, copies `D:\TraceForge\GCR_Upload\2_Supervisor_Approval_Email_Screenshot.png` and `2_Supervisor_Approval_Evidence.txt`.

## B. Objective
Make the submitted proposal match what is actually being built, and get written supervisor approval of the revised scope and R&D track. Rubric eligibility checks A1 (approval evidence) and A2 (track declared) depend on it, and the proposal itself is worth 40 marks (stage B).

## C. Prerequisites
- Current proposal PDF (`TraceForge_Assignment3_Proposal_Final.pdf`, outside the repo) and the supervisor's review.
- Facts: [PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md), [ARCHITECTURE.md](../ARCHITECTURE.md), [DECISIONS_AND_OPEN_QUESTIONS.md](../DECISIONS_AND_OPEN_QUESTIONS.md).
- Open question Q2 (Devstral list price) is optional: if not found, use the official Mistral Large rate and say so.

## D. Technical background
The proposal predates four decisions: the two-member team, free models, a narrowed evaluation (three AI components), and four design fixes found in review. The supervisor asked for narrowing; each change below answers that request or fixes a flaw an examiner could find.

## E. Implementation instructions
1. **Team (sections 1, 12):** two members with roll numbers; responsibilities = Track A / Track B from [TEAM_WORK_DISTRIBUTION.md](../TEAM_WORK_DISTRIBUTION.md); each does AI and engineering work.
2. **Models (sections 5, 9, 10):** primary Mistral free tier with a pinned Devstral model; comparator Qwen2.5-Coder-7B via Ollama; Groq spare. Remove GPT-4.1-mini as primary. Business cost: Mistral Large $0.50 / $1.50 per 1M tokens (official page) → about $7/month in tokens at 300 incidents × 35K tokens; keep the server cost range.
3. **Hardware:** RTX 3050 6 GB.
4. **Design fixes (sections 6, 8, 13):**
   - hidden tests run once at the end and never feed back;
   - both feedback arms get up to 3 attempts;
   - traceback anchoring in both retrieval arms; the graph arm adds only graph distance, expansion and config binding;
   - outcome class `runtime_dependency` (diagnose, no patch) beside abstention.
5. **Evaluation (section 8):** AI components = retrieval, diagnosis, repair; the report is a deterministic template. Dataset: 60 config + 60 code + 12 runtime_dependency + 12 insufficient_evidence held-out, ≥30 dev.
6. **Five safeguards (section 13):** distance labels with ≥50% distance ≥1; pipeline-first agent; rule-based diagnosis baseline; LLM response cache; freeze before tuning.
7. **Fix:** "R&D;" → "R&D" (two places).
8. **AI-tool declaration:** ChatGPT (drafting) and Claude (review, planning, documentation), with purposes.
9. Rafique reviews the technical sections against the docs.
10. (Remaining human step) Optionally email the supervisor with both members in CC: attach the revised PDF, list the changes in 5–6 bullets, ask for written confirmation of the revised scope and R&D track. The 18 Nov email already gave conditional permission to proceed.
11. Register/confirm the title in the Project Titles sheet.
12. Save the reply (PDF or screenshot) outside the public repo; note on TRAC-3 that it exists.

## F. Checklist
- [ ] Team section updated (2 members, roles)
- [ ] Model section updated; cost recalculated with cited official price
- [ ] Hardware corrected
- [ ] Four design fixes written into method/evaluation sections
- [ ] Three AI components and dataset numbers
- [ ] Five safeguards
- [ ] Typo fixed
- [ ] AI-tool declaration updated
- [ ] Rafique reviewed technical accuracy
- [ ] Every reference link still resolves
- [x] Supervisor's 18 Nov email (conditional permission) saved on disk (evidence paths above)
- [ ] Revised version sent to supervisor for written confirmation (both in CC)
- [ ] Title registered
- [ ] Reply saved; TRAC-3 updated

## G. Expected deliverables
Revised proposal PDF (kept outside the public repo because it lists roll numbers); sent email; saved approval.

## H. Testing and validation
- Cross-check every number in the PDF against [PROJECT_REQUIREMENTS.md](../PROJECT_REQUIREMENTS.md) and the domain doc.
- Re-check all reference URLs (the earlier check passed for all 13).
- Acceptance: the supervisor's reply explicitly approves, or lists changes that become new tasks.

## I. Dependencies and integration
- **Depends on:** nothing technical.
- **Feeds:** P4-S03 (the submission pack needs the PDF and approval). Any change the supervisor requests is logged in [DECISIONS_AND_OPEN_QUESTIONS.md](../DECISIONS_AND_OPEN_QUESTIONS.md).

## J. Definition of done
Revised PDF reviewed by Rafique and sent; approval saved, or requested changes logged as tasks.
