# ADR 0002: Deployment

Status: DRAFT (host decision open, Q7)
Step: P6-S02

## Context
A4 needs containers, CI and a public deployment at zero cost. Only the reviewer app (API + UI +
Postgres) is deployed, in read-only showcase mode (`TRACEFORGE_SHOWCASE_MODE=true`: non-GET
requests return 403). Lab, sandbox and live LLM calls stay local.

## Options
Only facts with a source are stated as facts. Everything else is UNVERIFIED.

| Host | Verified facts (source) | Unverified |
|---|---|---|
| Neon (Postgres only) | Free plan: 1 GB storage per project; 100 CU-hours/project/month; scale-to-zero after 5 min inactivity, not disableable; writes fail at the storage cap. Source: https://neon.com/docs/introduction/plans (fetched 2026-11-21) | Cold-start latency; suitability as the API database for TraceForge |
| Fly.io | New organizations have no free tier or monthly free allowance; trial is $1 credit for 7 days or until used. Source: https://docs.fly.io/about/pricing (fetched 2026-11-21) | Anything else. Not zero-cost, so likely excluded. |
| Render | None (page fetch failed) | Free web service limits, free Postgres expiry, spin-down behaviour |
| Railway, Koyeb, Oracle Cloud free VM, GitHub Pages (static only) | None | All limits and pricing |
| Local compose (`compose.prod.yaml`) | Defined in this repo; built and run locally 2026-11-25 (see Verified locally) | Public host: NOT CHOSEN |

## Decision (draft)
Local compose for A3. The public host decision stays open (Q7) until the unverified rows are
checked against the providers' current docs. Neon is a candidate for the database only; the API
and web containers still need a host that offers a free container runtime.

## Consequences
- `compose.prod.yaml` is host-neutral: only `${VAR}` values, healthchecks, memory and CPU limits.
- Showcase mode needs the Settings field `showcase_mode` and `add_showcase(app, settings)` wired in `main.py`.
- Image sizes (local `docker build`, 2026-11-25): api 456 MB, web 74.1 MB. No single-stage baseline measured.

## Redeploy (local)
Set `TRACEFORGE_DB_USER`, `TRACEFORGE_DB_PASSWORD`, `TRACEFORGE_DB_NAME` in `.env`, then
`docker compose -f compose.prod.yaml --env-file .env up -d --build`. The web service listens on
`TRACEFORGE_WEB_PORT` (default 8080). The api container runs `alembic upgrade head` before serving (idempotent), so no manual migration.

## Verified locally (2026-11-25, Docker 29.5.3, no public host involved)
- `docker compose -f compose.prod.yaml config -q` passes; both images build; api runs as uid 10001.
- `compose up --wait` with throwaway credentials: db, api, web all healthy; migrations 0001 and 0002 applied
  on a clean volume; `GET /` 200, `GET /api/health` 200 (`db: up`), `POST /api/incidents` 403 (showcase).
- CI (`.github/workflows/ci.yml`) is pnpm-based, consistent with `frontend/pnpm-lock.yaml`; it has not run on GitHub.

## Needs a human
Host choice (Q7), host account and secrets, DNS/URL, branch protection marking CI jobs required on `main`
(owner: Rafique), first green CI run on GitHub, public link in README.

## Status check 2026-11-25
Still DRAFT; the host (Q7) is not decided and there is no public URL. Verified locally: both images build (api 456 MB, web 74.1 MB), compose up is healthy, migrations 0001/0002 apply, GET / and /api/health return 200 and POST returns 403 (showcase mode). `.github/workflows/ci.yml` passes actionlint but NO GitHub Actions run has happened. CI jobs are backend, frontend, contracts and docker (no security job); the frontend uses pnpm. Branch protection is Rafique's.
