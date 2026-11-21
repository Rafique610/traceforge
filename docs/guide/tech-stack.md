# Tech stack and security

Back to [TraceForge Explained](TraceForge-Explained.md). Versions below are the *minimum* versions declared in `backend/pyproject.toml` and `frontend/package.json` (exact resolved versions are in `uv.lock` and `pnpm-lock.yaml`; they were not re-read for this guide).

## 1. Backend libraries (implemented, in `backend/pyproject.toml`)

| Library | Declared | Why we use it |
|---|---|---|
| Python | `>=3.12,<3.13` (`backend/.python-version` = 3.12) | Project standard; matches the lab target |
| **FastAPI** | `>=0.165.0` | Web framework with automatic `/docs` test page and request validation |
| **uvicorn[standard]** | `>=0.54.0` | Server that runs FastAPI (`uv run uvicorn traceforge.main:app --reload`) |
| **Pydantic v2** (via FastAPI) and **pydantic-settings** | `>=2.16.3` | Data validation for contracts and API bodies; `Settings` reads env vars |
| **SQLAlchemy 2** | `>=2` | ORM (talk to the DB with Python objects, no raw SQL strings) |
| **Alembic** | `>=1.20.1` | Database migrations |
| **psycopg[binary]** | `>=3.3.9` | PostgreSQL driver (URL scheme `postgresql+psycopg`) |
| **openai** (client only) | `>=3.57.0` | One client that speaks the "OpenAI-compatible" chat protocol, used for Ollama, OpenRouter, Mistral and Groq by changing the base URL |
| httpx, pytest, ruff (dev group) | unpinned | Test client, test runner, linter/formatter (line length 100, rules E, F, I, B, UP) |

Why one OpenAI-compatible gateway: switching provider is a settings change, not a code change (decision B4 in `docs/orchestration/DECISIONS.md`).

Other infrastructure: **PostgreSQL 16** in Docker (`compose.yaml`), **uv** (Python packages), **Task** (`Taskfile.yml` task runner), **Docker Compose**, **Ollama** for local models (installed on the developer machine; the local model is `qwen2.5-coder:7b`, default in `Settings.llm_model`).

## 2. Frontend (in `frontend/package.json`)

| Library | Declared | Why |
|---|---|---|
| React / react-dom | `^19.3.1` | UI components |
| Vite | `^8.3.6` | Dev server and build; proxies `/api` to the backend |
| TypeScript | `~7.0.2` | Type safety (`tsc -b` runs in `pnpm build`) |
| Vitest, jsdom, Testing Library | `^5.1.1`, `^31.0.1`, `^16.3.3` | Component tests |
| oxlint | `^1.90.0` | Linter (`pnpm lint`) |
| pnpm | package manager | Project standard |

## 3. Planned stack (not in the code yet)

From `docs/domain/traceforge/index.md`: Python `ast` and Compose YAML parsing, BM25 (`rank-bm25` or Postgres full-text search, "decided in its step"), `networkx` for the graph, GitHub REST for issue intake. Primary hosted model "Mistral free tier, pinned Devstral" is **not usable** as assumed; see [problem log](problem-log.md). The final primary model is **pending** (Q1/D21; P0-S06 Part B not run).

## 4. Security safeguards

Rules come from `docs/invariants/security.md`. Status is what the code does today.

| Safeguard | Status | Where / evidence |
|---|---|---|
| Env vars only through `Settings` | **Implemented** | `config.py` docstring "The only place that reads environment variables"; secrets typed as `SecretStr` |
| No hardcoded credentials; `.env` git-ignored; `.env.example` names only | **Implemented** | `.gitignore` (`.env`, `.env.*`, `!.env.example`); `compose.yaml` uses `${VAR:?...}` |
| Free-only guard: paid or non-allowlisted provider refused; OpenRouter id must end `:free` | **Implemented** | `gateway.check_allowed`; test `test_free_only_guard_refuses` |
| Prompt size limit before sending | **Implemented** | `llm_max_prompt_chars`; test `test_prompt_too_long_raises_before_sending` |
| Rate limit and bounded retries | **Implemented** | `llm_max_rps` (default 1.0), `MAX_RETRIES = 5`, backoff `2**attempt` on 429/5xx |
| Call log has no message text or secrets | **Implemented** | `call_log.py`; test `test_no_secret_or_content_in_logs` |
| LLM gets typed tools only, no shell | **Implemented** | `tools.TOOLS` fixed dict of 4; unknown tool is a `ToolError` |
| Tool arguments validated (schema, regex, size caps) | **Implemented** | Pydantic models in `tools.py`; `MAX_RESULT_CHARS = 4000` |
| Path allowlist for model file reads | **Implemented** | `ToolContext.allowed_path` (`lab/<service>/`, no `..`) |
| Logs, code, tool results treated as untrusted data (prompt injection defence) | **Implemented** (prompt wording + wrapped tool results) | `prompts/diagnose_v1.md`; test `test_prompt_injection_does_not_change_tools_or_outcome` |
| Hidden tests never in the model's context | **Implemented** in agent and repair | `prompting.render_context` skips paths containing "hidden"; repair feedback uses visible output only; tests `test_hidden_tests_never_in_prompts`, `test_no_hidden_leak_and_hidden_once` |
| Patch policy: path allowlist, no test files, size cap, syntax, no test-literal special-casing | **Implemented** | `repair/policy.py` |
| Patches applied only in disposable worktrees; git called without a shell | **Implemented** | `repair/worktree.py` |
| Failed or timed-out sandbox never counts as success | **Implemented** in the loop | `repair/loop.py` (`_clean`, `_green`) |
| Audit trail is insert-only, payload hashed | **Implemented** | `AuditEvent`, repository has no update/delete; `payload_sha256` |
| Illegal state moves refused (409), guards on `DIAGNOSED`, `VERIFIED` | **Implemented** | `incidents/service.py` |
| Secret redaction before prompts and indexes | **Planned** (evidence collector, Rafique) | The sample evidence shows `DB_PASSWORD=[REDACTED]`, but no redaction code exists in this tree |
| Sandbox: no network, CPU/memory/pids/time caps, non-root, no Docker socket | **Planned** (Rafique) | No sandbox folder |
| Read-only Docker socket proxy for evidence collection | **Planned** (Rafique) | no code |
| Review bound to frozen patch hash; changed patch invalidates review; tamper gives 409 | **Planned** | `reviews/` does not exist; only a `review_id` guard exists |
| Nothing is ever deployed from a review | **By design**: there is no deploy code at all | n/a |
| GitHub issue text stored as untrusted evidence | **Planned** | `github/` does not exist |
| Authentication | **Not planned for the first assessment**: single-user local app; whether the public deployment needs login is "TO BE DECIDED" | `docs/plans/ARCHITECTURE.md` |

Honest limits worth knowing:
- The prompt-injection test uses a fake model, so it shows our tool layer and prompts do not change tools or the outcome in that scenario. It does not prove a real model cannot be fooled.
- The repair policy's `test_literal` check is a heuristic (new literal in the patch that also appears in visible tests).
- The incident tests run on SQLite; Postgres row locking is tested by a test that is skipped unless Postgres is running.
