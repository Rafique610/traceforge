# Tooling

| Area | Choice |
|---|---|
| Python | 3.12, managed with `uv` (`pyproject.toml` + `uv.lock`). Run everything via `uv run`, never bare `python`. |
| Node | pnpm with `package.json` + `pnpm-lock.yaml`. |
| Tests | pytest (backend), Vitest (frontend). |
| Lint/format | ruff (Python). |
| Task runner | `Taskfile.yml` at repo root. Every routine command gets a task. |
| Containers | Docker Desktop + Docker Compose. |
| Local LLM | Ollama. |

## Docker
- Dockerfiles are two-stage (build, then slim runtime).
- Docker DNS/network errors during build or pull: retry at least 3 times before giving up.

## Paths and shell
- Development is on Windows. Use forward slashes in code and configs; use `pathlib` in Python.
- Commands given to the user are PowerShell; Taskfile tasks must work from PowerShell.
