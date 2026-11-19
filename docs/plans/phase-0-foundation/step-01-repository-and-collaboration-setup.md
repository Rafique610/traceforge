# P0-S01 — Repository and collaboration setup

## A. Task identification
| Field | Value |
|---|---|
| Phase | 0 Foundation |
| Step | 1 |
| Task ID | P0-S01 |
| Synverk card | none (pre-card setup) |
| Primary owner | Muhammad Rafique (repo owner) |
| Supporting | Muhammad Ruhan Kamran (accepts invites) |
| Reviewer | Ruhan |
| Priority | High (blocks every merge) |
| Effort | 0.5 day |
| Status | IN PROGRESS (repo, ignore rules, protection done; collaborator, Synverk sharing, PR #1 pending) |

## B. Objective
Both members can push branches, review each other's PRs and see the same board. Without this, `main` protection (1 approving review, admins included) means **nothing can merge**.

## C. Prerequisites
- Ruhan's GitHub username and the email he uses for Synverk (open question Q4).
- `gh` logged in as `Rafique610` (verified).

## D. Technical background
- Branch protection with `enforce_admins: true` applies to the owner too, so every change, including Rafique's, needs Ruhan's approval. This keeps contributions equal and visible (rubric C6).
- Synverk cards name the owner in their titles; assignment in Synverk needs the person to be a project member.
- `.gitattributes` with LF for source files avoids Windows CRLF noise inside Linux containers (risk T7).

## E. Implementation instructions
1. **Verify current state** (already done once):
   `gh api repos/Rafique610/traceforge/branches/main/protection --jq '{admins:.enforce_admins.enabled,reviews:.required_pull_request_reviews.required_approving_review_count}'` → `{"admins":true,"reviews":1}`.
2. **Add Ruhan as collaborator** with write access:
   `gh api -X PUT repos/Rafique610/traceforge/collaborators/<ruhan-username> -f permission=push`. Ruhan accepts the email invite.
3. **Share the Synverk project** with Ruhan (Synverk UI → project → share, or `share` MCP tool) with edit access.
4. **Assign cards** in Synverk by the owner in each title (Ruhan assigns his own after joining; Rafique assigns his).
5. **Add `.gitattributes`** at the root: `* text=auto eol=lf`, `*.ps1 text eol=crlf`, `*.pdf binary`.
6. **Merge PR #1** (research safeguards) once Ruhan approves.
7. **Merge this docs branch** (`rafique/execution-docs`) after Ruhan's review.
8. Both members clone and confirm `git pull` works.

## F. Checklist
- [x] Public repo `Rafique610/traceforge` created
- [x] `.gitignore` excludes course PDFs, `INSTRUCTIONS.md`, `.memory/`, `.env`
- [x] `main` protected (1 approval, admins included, no force push/deletion)
- [ ] Ruhan's GitHub username obtained
- [ ] Ruhan added with push access and invite accepted
- [ ] Synverk project shared with Ruhan
- [ ] Cards assigned to their owners in Synverk
- [ ] `.gitattributes` added (via PR)
- [ ] PR #1 reviewed and merged
- [ ] Execution docs PR reviewed and merged
- [ ] Both members cloned and pulled `main`

## G. Expected deliverables
- Collaborator entry for Ruhan; Synverk membership.
- `.gitattributes` (new).
- Merged PR #1 and docs PR.

## H. Testing and validation
- `gh api repos/Rafique610/traceforge/collaborators --jq '.[].login'` lists both logins.
- Ruhan opens a trivial PR from a branch: push succeeds; merge button is blocked until Rafique approves.
- Rafique's own PR cannot be merged without Ruhan's approval (proves admin enforcement).

## I. Dependencies and integration
- **Depends on:** nothing.
- **Unblocks:** every PR in the project; Synverk assignment.

## J. Definition of done
Both members can push, each PR needs the other's approval, both see and can move cards in Synverk, PR #1 and the docs PR are merged, and `.gitattributes` is on `main`.
