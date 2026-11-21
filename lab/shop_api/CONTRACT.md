# shop_api contract

Base URL (lab): `http://127.0.0.1:8100`. Money is a JSON string with 2 decimals. Total = sum(unit_price x quantity) rounded half-up to 2 dp.

| Endpoint | Input | Success | Edge cases |
|---|---|---|---|
| `GET /products` | none | 200 `[{id,name,price}]` ordered by id | empty catalogue -> `200 []` (never 500) |
| `GET /products/{id}` | int id | 200 `{id,name,price}` | unknown id -> 404 |
| `POST /orders` | `{customer_email, items:[{product_id>0, quantity 1..100}]}` (1..50 items) | 201 `{id,status:"pending",total}`; saves price snapshots; pushes one job to `ORDER_QUEUE` | quantity <= 0, empty `items`, bad email -> 422; unknown product -> 404; broker unreachable -> 503 (order stays `pending`) |
| `GET /orders/{id}` | int id | 200 `{id,status,total}`; status becomes `confirmed` once the worker handled the job | unknown id -> 404 |
| `GET /orders/{id}/total` | int id | 200 `{order_id,total,item_count,average_unit_price,headline}`; `headline` = name of first line | unknown id -> 404; order with no lines -> `total "0.00"`, `item_count 0`, `average_unit_price "0.00"`, `headline null` |
| `GET /health` | none | 200 `{status:"ok",db:"ok",redis:"ok",worker:"ok"}` | any component not ok -> 503 `{status:"degraded", db/redis: "down: <ErrorType>", worker: "missing"}` |
| `GET /health/live` | none | 200 `{status:"ok"}` always (container liveness) | |

## Job produced (see worker/CONTRACT.md)
`POST /orders` LPUSHes JSON `{job_id, type:"order_confirmation", order_id, total, attempt:0, enqueued_at}` to the list named by `ORDER_QUEUE` (default `orders:confirm`).

## Configuration (env -> `app/settings.py`)
`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` (required), `DB_PASSWORD` (required), `DB_POOL_SIZE` (5), `REDIS_HOST`, `REDIS_PORT`, `ORDER_QUEUE`.

## Seed
`python -m app.seed` creates tables and inserts 4 products when the catalogue is empty (idempotent).
