# Three-key development inference pool

`backend/traceforge/agent/pool.py` dispatches INDEPENDENT development requests (code reviews, test
generation, analyses) over three providers: `beatapi`, `axforge1`, `axforge2` (slot 2 only when
`axforge.slot2_enabled()`). It is never used for official work: `Task(official=True)` raises
`PoolRefused`, and every result row carries `tier="development"`.

- Sending goes through `gateway.chat` (the default `send`), so ledgers, model guards, pacing locks and
  `record_429` stay in the gateway. Models: AxForge `glm-5.3-flash`, BeatAPI `glm-5.3-flash-free`
  (the model the response reports is recorded in each row, with the provider).
- One in-flight request per provider, providers run concurrently. Scheduling intervals come from
  `axforge.MIN_START_INTERVAL_S` (30 s start to start) and `beatapi.MIN_INTERVAL_S`, plus jitter.
- Routing: BeatAPI takes any task; AxForge only tasks with `allow_axforge=True`, and only when BeatAPI
  is busy, cooling down or halted.
- Idempotency: key = sha256(task_id). Successful rows are appended and fsynced at once; on rerun they
  are skipped (a torn last line is ignored). Failure rows (`ok=false`) are kept but not skipped.
- Failure: the first failure halts that provider for the run, the failed task is not retried, and
  pending tasks stay available to other allowed providers. A pre-send refusal for a pending
  Retry-After (`Deferred`) is not a failure: exponential backoff with jitter, then the task is retried.
- `Pool.stats()`: per provider requests, tokens, latency list, p50/p95, failures, rpm; plus combined.
- The caller must have run `axforge.authorize()` for AxForge use; otherwise the gateway refuses and the
  provider halts. Tests use fakes and a fake clock only.
