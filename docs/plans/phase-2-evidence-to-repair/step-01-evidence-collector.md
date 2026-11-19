# P2-S01 — Evidence collector

## A. Task identification
| Field | Value |
|---|---|
| Phase | 2 Evidence-to-repair |
| Step | 1 |
| Task ID | P2-S01 |
| Synverk card | TRAC-12 |
| Primary owner | Muhammad Rafique |
| Supporting | — |
| Reviewer | Muhammad Ruhan Kamran |
| Priority | Normal (critical path) |
| Effort | 2.5 days |
| Status | NOT STARTED |
| Branch | `rafique/P2-S01-evidence-collector` |

## B. Objective
Turn a failing lab into a real `EvidenceBundle` without ever writing to the lab or leaking secrets. Evidence is what diagnosis must cite, and what retrieval uses as anchors, so it must be faithful (exact log lines, exact trace frames) and pinned to a SHA.

## C. Prerequisites
- P1-S01 (lab), P0-S05 (`EvidenceBundle`).
- P1-S03 seed cases to test against.
- Read `docs/invariants/security.md` (Docker, redaction).

## D. Technical background
- **Read-only Docker access:** a socket proxy (assumption AS8: `tecnativa/docker-socket-proxy`) in the lab Compose with `CONTAINERS=1`, `POST=0`; the collector talks to `tcp://localhost:2375` (bound to localhost only). The raw socket is never given to app code that faces the LLM.
- **Redaction:** keys matching `PASSWORD|SECRET|TOKEN|KEY|DSN|URL` (case-insensitive) have values replaced by `«redacted:<type>»`; DSN-like values (`scheme://user:pass@host`) have credentials stripped even under other names. Allowlist of non-secret keys whose values are kept (host, port, queue names, DB name) because config diagnosis needs them.
- **Traceback parsing:** Python tracebacks follow `File "<path>", line <n>, in <func>`; map container paths (`/app/...`) to repo-relative paths (`lab/shop_api/app/...`) through a per-service prefix map.
- **Pinning:** `base_sha` = `git rev-parse HEAD` of the lab checkout under test; `compose_sha256` = hash of the normalized `docker compose config` output.

## E. Implementation instructions
1. Add the socket proxy service to `lab/compose.yaml` (port bound to `127.0.0.1`).
2. **`evidence/docker_read.py`:** via `docker.DockerClient(base_url=proxy)`: per service container `status`, `health`, `exit_code`, `restart_count`, `started_at`.
3. **`evidence/logs.py`:** last N lines / last T seconds per service (caps: 400 lines, 32 KB); one evidence item per log *block* (split on blank lines or traceback boundaries) so IDs stay meaningful.
4. **`evidence/config.py`:** effective env per container (from inspect `Config.Env`) + declared settings fields (import the service's settings class names statically from source, not by executing it); redact; produce items `kind="config"` with `key` and redacted value in `content`.
5. **`evidence/redaction.py`:** the rules above; pure functions; used by every other evidence module before building items.
6. **`evidence/traces.py`:** parse tracebacks from log items into `kind="trace_frame"` items with `path`, `line`, `function`; mark frames inside site-packages as `external`.
7. **`evidence/compose.py`:** parse `lab/compose.yaml` (`yaml.safe_load`): services, `depends_on`, env key names (values redacted) → `kind="compose"` items.
8. **`evidence/collector.py`:** `collect(incident_id, service, case: CaseManifest | None) -> EvidenceBundle`; for runtime cases apply `runtime.yaml` beforehand via the dataset tooling; IDs `EV-0001…` in stable order; each item `sha256` of its content.
9. **CLI** `task evidence:collect CASE=<id>`: applies the case to a fresh lab (`lab:reset` + patch + restart affected service), waits for the symptom, collects, prints the bundle summary, restores.
10. **Tests:** redaction table (passwords, tokens, DSNs, URLs with creds; allowlisted hosts kept); trace parser on 3 real lab tracebacks; compose parser; collector with a mocked Docker client.

Edge cases: container missing → health item says `absent` (evidence for runtime_dependency); logs empty → no log items (evidence for insufficient_evidence); log line containing a secret → redacted by pattern.

## F. Checklist
- [ ] Socket proxy in lab Compose (localhost only, read-only)
- [ ] Container state reader
- [ ] Log windowing and block splitting with caps
- [ ] Effective config with redaction and allowlist
- [ ] Redaction module with tests
- [ ] Traceback parser with path mapping and external-frame marking
- [ ] Compose parser
- [ ] `collect()` returning a valid bundle with stable IDs
- [ ] CLI applying a case and restoring the lab
- [ ] Tests incl. 3 real tracebacks
- [ ] Bundles for all 4 seed cases pasted (summarized) on TRAC-12

## G. Expected deliverables
New: `backend/traceforge/evidence/{docker_read,logs,config,redaction,traces,compose,collector}.py`, tests. Modified: `lab/compose.yaml`, `Taskfile.yml`, `README.md`. Interface: `collect(...) -> EvidenceBundle`.

## H. Testing and validation
- Redaction: no value from `.env` appears in any bundle (test loads `.env.example` names and asserts).
- Each seed case's bundle contains the symptom (traceback frame for the code case; connection/queue log lines for config and runtime cases; nothing decisive for the insufficient case).
- Acceptance: bundles validate against the contract; IDs stable across two collections of the same state.

## I. Dependencies and integration
- **Depends on:** P1-S01, P0-S05.
- **Unblocks:** P2-S03 (anchors), P2-S07 (real evidence for the agent).
- **Integration:** Ruhan's `EvidenceSource` gets a `LabEvidenceSource` calling `collect()` at Sync 2.

## J. Definition of done
Merged after Ruhan's review; seed bundles correct; redaction tests pass; works on both laptops; TRAC-12 approved.
