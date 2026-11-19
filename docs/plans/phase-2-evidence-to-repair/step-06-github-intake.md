# P2-S06 — GitHub intake

## A. Task identification
| Field | Value |
|---|---|
| Phase | 2 Evidence-to-repair |
| Step | 6 |
| Task ID | P2-S06 |
| Synverk card | TRAC-17 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | Normal |
| Effort | 1.5 days |
| Status | NOT STARTED |
| Branch | `ruhan/P2-S06-github-intake` |

## B. Objective
The real external integration the rubric requires (C4): an engineer pastes a GitHub issue URL and gets an incident whose issue text is stored as untrusted evidence.

## C. Prerequisites
- P1-S04 (incidents). Optional fine-grained GitHub token (read-only, public repos) in `.env`; unauthenticated works for public repos at a low rate.
- Decide where issues live (assumption AS9): a separate public repo `traceforge-lab-issues` or labelled issues on the main repo.

## D. Technical background
- GitHub REST `GET /repos/{owner}/{repo}/issues/{number}` returns title, body, labels, state. Use `httpx` with `Accept: application/vnd.github+json` and `X-GitHub-Api-Version`.
- Issue bodies are attacker-controllable text: store as evidence `kind="issue"` (content capped and marked untrusted), never as instructions.
- If GitHub is unreachable, fail clearly; never fall back silently to a local fixture (that would misrepresent a live integration).

## E. Implementation instructions
1. Create 2–3 issues describing seed-case symptoms in plain user language (e.g. "Order confirmations stopped arriving").
2. **Settings:** `github_token` (SecretStr, optional), `github_allowed_owners` (list) to restrict which repos can be fetched.
3. **`github/client.py`:** `parse_issue_url(url) -> (owner, repo, number)` (strict regex for `https://github.com/<owner>/<repo>/issues/<n>`); `fetch_issue(...)` with timeout 10 s; map 404/403/rate-limit to clear errors.
4. **`github/service.py`:** create incident with `source="github"`, `symptom` = issue title, service inferred from a label (`service:worker`) or required in the request; store body as an evidence item.
5. **`github/router.py`:** `POST /incidents/from-github` with `GitHubIntake` schema (`issue_url`, optional `service`).
6. **Tests:** URL validation (good, wrong host, PR URL, trailing junk); mocked API responses (200, 404, 403 rate limit); disallowed owner → 422; injected instruction in body stored verbatim as data and flagged untrusted.
7. README: how to try it with a real issue URL.

## F. Checklist
- [ ] Issues created for 2–3 seed symptoms
- [ ] Settings with optional token and owner allowlist
- [ ] Strict URL parser
- [ ] Client with timeouts and error mapping
- [ ] Incident + untrusted evidence creation
- [ ] Endpoint with schema
- [ ] Tests (URL, mocked API, allowlist, injection-as-data)
- [ ] Real issue → incident demonstrated; output on TRAC-17

## G. Expected deliverables
New: `backend/traceforge/github/{client,service,schemas,router}.py`, tests; GitHub issues. Modified: `config.py`, `.env.example`, `main.py`, `README.md`.

## H. Testing and validation
- Tests green; live: real issue URL creates an incident visible at `GET /incidents/{id}` with the issue as evidence.
- Acceptance: network off → clear 502-style error, no incident created.

## I. Dependencies and integration
- **Depends on:** P1-S04.
- **Unblocks:** P3-S03 (UI "create from GitHub"), P4-S03 (demo).

## J. Definition of done
Merged after Rafique's review; live intake demonstrated; TRAC-17 approved.
