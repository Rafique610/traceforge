# worker contract

Consumes order jobs from Redis, confirms the order in Postgres, "sends" the confirmation email (log line; the lab has no SMTP).

## Job format
JSON string on the Redis list `ORDER_QUEUE` (default `orders:confirm`), LPUSH by the API, BRPOP (5 s timeout) by the worker:
`{"job_id": str, "type": "order_confirmation", "order_id": int, "total": "14.50", "attempt": 0, "enqueued_at": float}`

## Behaviour
- Confirm: set `orders.status = "confirmed"`, `confirmed_at = now (UTC)`, then log the email. A job for an already confirmed order is a no-op (idempotent).
- Retries: a failing handler is retried up to 3 times (4 calls total) with backoff 1 s, 2 s, 4 s (`BACKOFF_BASE_S` x 2^n). After the last failure the job (plus `error`) is pushed to `<ORDER_QUEUE>:dead`.
- Unknown order id -> counts as a failure (retried, then dead-lettered). Malformed payload -> dead-lettered immediately, no retry.
- Broker unreachable at start: ping with backoff up to `CONNECT_ATTEMPTS` (10), logging every failure (`redis host:port not reachable`), then exit non-zero (no silent loop).
- Heartbeat: before every BRPOP the worker does `SET worker:heartbeat <epoch> EX 15`. Key absent = worker not running or blocked.
- Healthcheck: `python -m worker.heartbeat` exits 0 iff the key exists.

## Configuration (env -> `worker/settings.py`)
`REDIS_HOST`, `REDIS_PORT`, `ORDER_QUEUE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` (required), `DB_PASSWORD` (required), `DB_POOL_SIZE` (2), `MAX_RETRIES` (3), `BACKOFF_BASE_S` (1.0), `CONNECT_ATTEMPTS` (10). The API and worker must agree on `ORDER_QUEUE`.
