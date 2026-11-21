# Common brief for every implementation agent (read first)

Repo `D:\TraceForge\repo`, Windows, branch `ruhan/stage-b-work`. The owner authorised implementing BOTH tracks (Ruhan's and Rafique's) to deliver the complete system. Read `PROMPT.md` and the step document(s) named in your task.

## Rules
- **Real implementations only.** No stand-in sandbox, placeholder retrieval, hardcoded metrics, sample evidence passed off as real, or fake dataset presented as the frozen dataset. Mocks/fakes only inside isolated unit tests and labelled as such. If a genuine resource is missing, say exactly what and do not substitute silently.
- Preserve existing work; inspect before editing; never overwrite another component. Existing folders you may need to read: `backend/traceforge/{contracts,agent,repair,incidents,reports,reviews,github,evaluation}`, `spikes/retrieval` (Rafique's spike, read-only reference).
- Follow `docs/invariants/*` (feature folders, files <300 lines, Settings-only env access, ORM only, no hardcoded credentials, security rules: hidden tests never in model context; Docker socket never in lab/sandbox containers; non-root; limits; network off by default).
- Contracts in `backend/traceforge/contracts/` are shared: do not change them; if you need a change, report it (do not edit).
- Do NOT edit `README.md`, `Taskfile.yml`, `main.py`, `config.py`, `pyproject.toml`, `docs/plans/**`, `docs/orchestration/**` (the orchestrator does). Report the exact lines/settings/tasks you need.
- Do NOT run `uv run`, `uv sync` or `uv add` (concurrent uv hangs; dependencies docker, networkx, rank-bm25, openai are being installed by the orchestrator — check `import docker, networkx, rank_bm25` works before running tests that need them). Use `D:\TraceForge\repo\backend\.venv\Scripts\python.exe -m pytest <paths> -q -p no:cacheprovider --basetemp=D:\AI\tmp\<yourname>` and `-m ruff check/format`.
- RAM is tight (16 GB, ~1-5 GB free): never leave containers running; run at most one Docker stack at a time; remove containers/networks you create (`docker rm -f`, `docker network rm`); never prune volumes/images; never touch existing Docker volumes. Large downloads go to D:. Prefer small base images already present (e.g. `python:3.12-slim`, `postgres:16`).
- $0 budget. Never print or log secrets. No git commit/push/merge/tag.
- Postgres for the app: container `traceforge-db-1` (port 5433, creds in git-ignored `.env`, loaded by the tests via `set -a; . <(sed 's/^\xEF\xBB\xBF//' .env)`); start with `docker compose up -d --wait db` in the repo root if stopped.
- Be honest in your final report: files created/changed, REAL command output (counts), what is unverified, what you could not do and why, interface summary, and the Taskfile/config lines you need. Keep it concise.
