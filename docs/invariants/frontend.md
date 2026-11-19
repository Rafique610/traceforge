# Frontend (Vite + React + TypeScript)

- Single-page app in `frontend/`, built with Vite, package manager pnpm.
- Feature folders under `frontend/src/<feature>/` (e.g. `incidents/`, `review/`, `evaluation/`); shared bits in `frontend/src/shared/`.
- Talks only to the FastAPI backend over REST. No business rules in the UI; it renders what the API returns.
- Real data only (see core.md): no placeholder stats or fake progress.
- Design from the user's seat: a backend engineer triaging an incident wants the symptom, the evidence chain, the diff and the test result, in that order.
- UX review/polish → impeccable skill. Visual redesign → ui-ux-pro-max skill.
