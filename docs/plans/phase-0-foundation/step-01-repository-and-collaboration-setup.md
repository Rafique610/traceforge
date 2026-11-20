# P0-S01 — Repository and collaboration setup

## A. Task identification
| Field | Value |
|---|---|
| Phase | 0 Foundation |
| Step | 1 |
| Task ID | P0-S01 |
| Synverk card | none (Synverk not used, D16) |
| Primary owner | Muhammad Rafique (repo owner) |
| Supporting | Muhammad Ruhan Kamran (accepts invite) |
| Reviewer | optional |
| Priority | High (blocks Ruhan's pushes) |
| Effort | 0.5 day |
| Status | IN PROGRESS (only Ruhan cloning `main` left) |

## B. Objective
Both members can push and merge their own work to `main`. No approving review is required (D6); `main` only blocks force pushes and deletion.

## C. Prerequisites
- Ruhan's GitHub username (open question Q4).
- `gh` logged in as `Rafique610` (verified).

## D. Technical background
- Branch protection keeps `enforce_admins: true` with no required review, so the owner is also blocked from force-pushing or deleting `main`, but anyone with push access can merge.
- `.gitattributes` with LF for source files avoids Windows CRLF noise inside Linux containers (risk T7).
- Before any work: `git fetch` and pull if behind (D17).

## E. Implementation instructions
1. **Verify current state:**
   `gh api repos/Rafique610/traceforge/branches/main/protection --jq '{admins:.enforce_admins.enabled,reviews:.required_pull_request_reviews,force:.allow_force_pushes.enabled}'` → `{"admins":true,"reviews":null,"force":false}`.
2. **Add Ruhan as collaborator** with write access:
   `gh api -X PUT repos/Rafique610/traceforge/collaborators/<ruhan-username> -f permission=push`. Ruhan accepts the email invite.
3. **Add `.gitattributes`** at the root: `* text=auto eol=lf`, `*.ps1 text eol=crlf`, `*.pdf binary`.
4. Both members clone and confirm `git pull` works.

## F. Checklist
- [x] Public repo `Rafique610/traceforge` created
- [x] `.gitignore` excludes course PDFs, `INSTRUCTIONS.md`, `.memory/`, `.env`
- [x] `main` protected (no force push/deletion; no required review)
- [x] PR #1 merged
- [x] Execution docs PR merged
- [x] Ruhan's GitHub username obtained (`ruhank-dev`)
- [x] Ruhan added with push access
- [x] `.gitattributes` added
- [ ] Both members cloned and pulled `main`

## G. Expected deliverables
- Collaborator entry for Ruhan.
- `.gitattributes` (new).

## H. Testing and validation
- `gh api repos/Rafique610/traceforge/collaborators --jq '.[].login'` lists both logins.
- Ruhan pushes a branch and merges a trivial change: succeeds without anyone's approval.
- `git push --force origin main` is rejected (proves protection).

## I. Dependencies and integration
- **Depends on:** nothing.
- **Unblocks:** Ruhan's work on `main`.

## J. Definition of done
Both members can push and merge their own work, force push/deletion of `main` is blocked, and `.gitattributes` is on `main`.
