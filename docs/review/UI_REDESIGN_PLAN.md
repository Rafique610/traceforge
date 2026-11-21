# TraceForge UI redesign plan

## Problems found in the current UI (see docs/screenshots/ui-*.png, badge-*.png)
- No app shell: a plain header with two text links, no product identity, no page titles/breadcrumbs, no active-nav state.
- `/` is just the incident list; nothing summarises the system (counts, awaiting review, evaluation runs, API health).
- Tables are unstyled: full-width cells, no identity/source/cause columns, no relative time, no search, state is the only status.
- Incident detail is one long stack of identical boxed sections; the pipeline (evidence -> retrieval -> diagnosis -> patch -> sandbox -> review) is not visible, although `/incidents/{id}/events` has timestamps and counts for it.
- Diff viewer: monochrome rows, no line numbers, no file grouping, no syntax colouring, no split view; patch hash has no copy.
- Review form: approve/reject fire immediately (no confirmation), no "nothing is deployed" notice, no summary of what the model believes vs. what is uncertain.
- Evidence is a flat list; kinds are not grouped; "Evaluation" pages are bare tables.
- Colours are ad hoc (blue links, green/yellow/red pills), no dark mode, not usable on a 390px phone (header/table overflow), no skeletons, no 404/error boundary.

## Direction
- Shell: dark-navy sidebar (mark + wordmark, grouped nav Overview / Incidents / Evaluation / System) collapsing to a drawer on mobile; top bar with breadcrumbs, API health badge (real /health) and light/dark toggle (localStorage, try/catch).
- Tokens in CSS variables (light/dark via prefers-color-scheme + manual override), one teal accent, 4/8px spacing, system font stacks, no web fonts, no gradients.
- Pages: Dashboard (KPIs from real API counts, state bar chart in inline SVG, recent incidents, latest evaluation runs and model info, honest empty states), Incident list (dense table, search on loaded page, state filter, pagination), Incident detail (status header, stepper built from audit events + report, Summary / Evidence / Retrieved context / Diagnosis / Patch / Sandbox / Review), Review (split+unified diff with a hand-written Python/YAML tokenizer, file list with +/- counts, SHA copy, confirmation step, no-auto-deploy notice), New incident page, Evaluation list/detail, 404, error boundary.
- Real data only: no severity (API has none); stages that did not run say "not run"; model info only from run meta / report model_usage.
- No new dependencies (no chart or highlight library). No backend change needed: per-state counts come from `GET /incidents?state=X&limit=1` totals.
