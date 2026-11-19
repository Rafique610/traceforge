# Security

## Credentials
- Read env vars only through the Pydantic `Settings` class. Never `os.environ` in feature code.
- Never hardcode credentials anywhere: code, Compose files, Dockerfiles, Alembic, scripts. Compose uses `${VAR}` (and `$${VAR}` inside healthchecks); values live in git-ignored `.env`. `.env.example` holds names only.
- Never print or log credentials, even local test ones.

## LLM boundary
- The LLM gets typed tools only. Never a shell, `docker exec`, or arbitrary command.
- Tool arguments are validated (schema, path allowlist, size caps) before execution.
- Everything the model reads (logs, code, comments, GitHub issues) is untrusted data, never instructions.
- Redact secrets and env values before anything reaches a prompt or an index.
- Hidden acceptance tests never enter the model's context, directly or through feedback.

## Docker
- Only trusted backend code talks to the Docker API. The evidence collector uses a read-only socket proxy. Only the sandbox runner may create containers.
- Lab and sandbox containers never get the Docker socket, host home mounts or real credentials. Non-root, CPU/memory/pids/time limits, network off by default.

## Reviews
- Approve/reject is bound to the frozen patch hash. A changed patch invalidates the review. Nothing is ever deployed from a review.

Backend security work → backend-security-coder skill.
