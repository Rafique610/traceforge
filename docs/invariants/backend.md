# Backend (FastAPI)

## Layout per feature
Each feature folder under `backend/traceforge/<feature>/` holds, as needed:
- `router.py`: thin endpoints that only call the repository/service. No business logic.
- `schemas.py`: Pydantic request/response models.
- `models.py`: SQLAlchemy ORM models.
- `repository.py`: all DB access for the feature.
- `service.py`: logic that isn't DB access.

App-wide: `main.py` (create app, middleware, include routers; nothing else), `config.py` (`Settings`), `database.py` (engine/session).

## Schemas are mandatory
- Every endpoint with a body or meaningful query params declares a Pydantic model in `schemas.py`. No unnamed dict bodies.
- Constrain values in the schema (enums, ranges, lengths) so bad input gets a 422 before it touches the DB.
- Typed responses where sensible, so `/docs` is a usable test console. Tell the user how to test each new endpoint in `/docs`.

## Database
- PostgreSQL through SQLAlchemy 2.x ORM; migrations with Alembic. No raw SQL strings.
- Append-only tables (audit events, frozen patches, reviews) are never updated in place.

## Long work
- Agent investigations run outside the request (FastAPI background task in A3). Endpoints return immediately with an ID; clients poll state.
