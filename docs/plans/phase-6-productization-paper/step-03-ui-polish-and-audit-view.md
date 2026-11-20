# P6-S03 — UI polish, audit view and experiment comparison

## A. Task identification
| Field | Value |
|---|---|
| Phase | 6 Productization and paper |
| Step | 3 |
| Task ID | P6-S03 |
| Synverk card | TRAC-31 (screenshot required) |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | Low (A4) |
| Effort | 2.5 days |
| Status | NOT STARTED |
| Branch | `ruhan/P6-S03-ui-polish` |

## B. Objective
Make the final demo and the public showcase clear: an audit timeline proving every action is recorded, a visual of why each code hit was retrieved (the research idea made visible), and the 2×2 comparison with confidence intervals.

## C. Prerequisites
- P3-S03 UI; P5-S02 `stats.json` for the comparison view; `GET /incidents/{id}/events`.

## D. Technical background
- **Audit timeline:** state transitions, tool calls (name, args hash, invalid flag), test runs, review — ordered, from audit events.
- **Graph path view:** for each G-mode hit, show the path from the evidence anchor (e.g. `trace frame → queue.consume —READS_CONFIG→ cfg:worker:ORDER_QUEUE`) using the hit's `reasons`; a small SVG or nested list is enough (no heavy graph library unless needed).
- **Comparison view:** 2×2 table of verified repair rate with 95% CIs, main effects and interaction, by distance bucket, n shown.

## E. Implementation instructions
1. `frontend/src/incidents/AuditTimeline.tsx`.
2. `frontend/src/incidents/HitPath.tsx` (renders reasons as a path).
3. `frontend/src/evaluation/FactorialView.tsx` reading an endpoint that serves `stats.json`.
4. Accessibility and layout pass with the **impeccable** skill (focus states, contrast, keyboard navigation for the review panel).
5. Vitest for each new component; screenshots attached.

**Gap fixes (21 Nov 2026; see D26–D31)**
- Add a rating page for the small usefulness study: a reviewer sees one report and answers 4 questions on a 1–5 scale (cause clear? evidence convincing? patch understandable? would approve?) plus a free-text note. Ratings saved as JSON with the report hash (D29).

## F. Checklist
- [ ] Audit timeline
- [ ] Hit path view
- [ ] Factorial comparison view with CIs and n
- [ ] impeccable UX/accessibility pass
- [ ] Tests
- [ ] Screenshots on TRAC-31
- [ ] Rating page saves ratings bound to the report hash

## G. Expected deliverables
New components above; small endpoint for `stats.json` if not already served.

## H. Testing and validation
- Values match `stats.json` and audit events exactly.
- Acceptance: keyboard-only reviewer flow works.

## I. Dependencies and integration
- **Depends on:** P3-S03, P5-S02.
- **Feeds:** final demo, P6-S04 figures.

## J. Definition of done
Merged after Rafique's review; screenshots attached; TRAC-31 approved.
