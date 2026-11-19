# Core rules (always loaded)

## Folder structure: feature-based
- Each feature gets its own folder holding everything it needs (models, schemas, repository, service, helpers). Example: `backend/traceforge/incidents/`, `backend/traceforge/retrieval/`.
- Never split by technical layer across the app (no top-level `models/`, `services/`, `storage/` folders shared by every feature).
- A new feature means a new folder. Don't mix responsibilities across features.

## File size and design
- A file over ~300 lines has too much responsibility: split it.
- Use a design pattern only when it removes real complexity. When you use one, tell the user which and why.

## Real data only
- Never show invented numbers in UI, API responses, dashboards, reports or slides. Every figure comes from a real query, file, run artifact or service.
- If a metric can't be measured honestly, omit it. Experiment results come only from saved, rerunnable runs.

## Ponytail ladder (all code writing)
1. Does this need to exist at all?
2. Already in this codebase? Reuse it.
3. Standard library does it?
4. Native platform feature covers it?
5. An installed dependency solves it? No new packages without clear need.
6. Can it be one line?
7. Only then write the minimum code that works.

- No speculative abstractions (no factory for one product, no interface with one implementation).
- Bug fixes address the root cause: one shared guard beats patching every caller.
- Every non-trivial piece of code gets one minimal runnable check.
