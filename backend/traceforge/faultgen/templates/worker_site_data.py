# ruff: noqa: E501
"""Fault-site data for the worker service (job retries, dead letters, settings)."""

W = "lab/worker/"
WORKER_CODE_SITES = {
    "retry_count": dict(path=W + "retry.py", qual="with_backoff", family="off_by_one", distance=2, kind="job",
        old="    for attempt in range(retries + 1):\n",
        variants=["    for attempt in range(retries):\n", "    for attempt in range(retries + 2):\n",
                  "    for attempt in range(1, retries + 1):\n", "    for attempt in range(retries * 2):\n"]),
    "retry_last": dict(path=W + "retry.py", qual="with_backoff", family="boundary", distance=2, kind="job",
        old="            if attempt == retries:\n",
        variants=["            if attempt == retries - 1:\n", "            if attempt >= retries - 1:\n",
                  "            if attempt > retries:\n", "            if attempt == 0:\n"]),
    "backoff_formula": dict(path=W + "retry.py", qual="with_backoff", family="wrong_formula", distance=2, kind="job",
        old="            delay = base * 2**attempt\n",
        variants=["            delay = base * 2 * attempt\n", "            delay = base ** attempt\n",
                  "            delay = base * 2 ** (attempt + 1)\n", "            delay = base + 2**attempt\n"]),
    "dead_letter_queue": dict(path=W + "queue.py", qual="dead_letter", family="wrong_queue", distance=2, kind="job",
        old='    client.lpush(settings.dead_queue, json.dumps({**job, "error": error}))\n',
        variants=['    client.lpush(settings.order_queue, json.dumps({**job, "error": error}))\n',
                  '    client.lpush(settings.order_queue + ":dead:", json.dumps({**job, "error": error}))\n',
                  "    return None\n"]),
    "retry_budget": dict(path=W + "queue.py", qual="consume_once", family="wrong_argument", distance=1, kind="job",
        old="            retries=settings.max_retries,\n",
        variants=["            retries=settings.max_retries - 1,\n", "            retries=0,\n",
                  "            retries=settings.connect_attempts,\n", "            retries=settings.max_retries + 1,\n"]),
    "job_validation": dict(path=W + "queue.py", qual="parse_job", family="missing_validation", distance=2, kind="job",
        old='        job["order_id"] = int(job["order_id"])\n',
        variants=['        job["order_id"] = int(job.get("order_id", 0))\n', '        job["order_id"] = int(job.get("order_id") or 1)\n']),
    "malformed_route": dict(path=W + "queue.py", qual="pop_job", family="wrong_queue", distance=2, kind="job",
        old="        client.lpush(settings.dead_queue, raw)\n",
        variants=["        client.lpush(settings.order_queue, raw)\n", "        pass\n",
                  '        client.lpush(settings.dead_queue + ":x", raw)\n']),
}  # fmt: skip

WORKER_CONFIG_SITES = {
    "max_retries": dict(kind="job", family="wrong_value", line="    max_retries: int = @@\n", good="3",
                        bad=["0", "1", "30", "-1", "10", "2", "4", "100"]),
    "backoff_base_s": dict(kind="job", family="wrong_unit", line="    backoff_base_s: float = @@\n", good="1.0",
                           bad=["0.0", "10.0", "0.1", "1000.0", "-1.0"]),
    "order_queue": dict(kind="job", family="queue_name_mismatch", line='    order_queue: str = "@@"\n', good="orders:confirm",
                        bad=["orders:confirmed", "order:confirm", "orders-confirm", "orders:confirm:v2", "confirm", "orders:Confirm", "orders:confirm ", "jobs:confirm"]),
}  # fmt: skip
