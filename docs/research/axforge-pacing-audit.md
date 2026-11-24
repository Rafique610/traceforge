# AxForge request pacing: audit and enforcement (24 Nov 2026)

No AxForge request was made for this work (no probing, no tokens). Everything below comes from code, tests and the saved ledgers (`runs/axforge_usage.jsonl`, `backend/runs/llm_calls.jsonl`).

## 1. Every code path that sends to AxForge
- **One network path:** `gateway._call_axforge` -> `client.chat.completions.create`. Nothing else in the repo constructs an AxForge client or calls its URL (`make_client` is the only factory; the OpenAI client is created with `max_retries=0`, so the SDK itself never retries).
- **Callers of that path:** `gateway.chat`, used by the diagnose loop (every model/tool-loop request, v4 and v5), the patch stage (`ask_patch`) and the F1 repair attempts. Diagnosis tool calls (`read_symbol`, `search_code`...) are local; only model requests reach the network. BeatAPI and other providers have separate functions (`_call_beatapi`, `_call`).
- **No retries in the gateway for AxForge:** one attempt; the first failure sets a per-process halt, and later calls in that process are refused locally before any network use.

## 2. What was enforced before (CONFIRMED from the code)
| Question | Answer |
|---|---|
| Was 2 RPM enforced? | **No.** The limit was `MIN_GAP_S = 10.0` s. |
| What was measured? | The gap from the **completion** of the previous request to the start of the next, not start to start. |
| Shared across workers? | Threads of one process were serialised by an in-memory lock. |
| Shared across processes / resumes? | **No.** State (`_last_done`) lived in process memory. The first request of every new process (every runner invocation, every resume) waited **zero** seconds. Parallel processes were not coordinated. |
| Did `llm_max_rps` apply? | No, that throttle is for other providers. |
| Could a retry bypass it? | The gateway never retried AxForge. The diagnose loop could call `chat` again after a failure (see section 4), but those calls were refused locally by the halt, so they did not reach the network. |

## 3. What the history shows (reconstructed; the ledger records completion times only)
- 203 network events over 59 authorised processes: 178 successful requests and 25 failures (16 HTTP 429, 6 connection errors, 2 x 504, 1 x 502).
- Estimating each request's start as `completion - logged latency` (joined from `llm_calls.jsonl`), **60 of 202** consecutive start-to-start intervals were under 30 s, all inside a single process (none across processes: separate runs were minutes apart). 9 were under 10 s; those are either overlapping requests from the early parallel-worker experiments (the runner notes "axforge answered 429 to concurrent requests") or noise from the reconstruction (some joined latencies give negative completion-to-start gaps, so start times are approximate). Under a 30 s rule about 30% of intervals would have been too short.
- **The 16 HTTP 429s:** 5 arrived 0.0 to 11.4 s after a previous event in the same process, three of them 10.5, 10.7 and 11.4 s after a success, i.e. right at the old 10 s gap. 11 were the **first request of a fresh process**, including every failure since 13:30 today. Those cannot be explained by our pacing: they point to a provider-side block or quota that is independent of our spacing.
- **Conclusion (LIKELY, not proven):** a limit stricter than 10 s per request (consistent with 2 RPM) caused part of the 429s. The persistent 429s of the last hours are not explained by pacing alone; enforcing 2 RPM may not make the provider answer.

## 4. The "three requests within seconds" in the last evaluation invocation
**Correction of my previous report:** I wrote that the invocation sent three requests within seconds, all 429. That was wrong. The ledger shows exactly **one** network event per invocation: a single 429 at 13:29:38, 13:35:08 and 13:52:43 (each after one authorisation row). The three `GatewayError` rows in `requests.jsonl` of the `provider_error` artifacts were three calls of the diagnose loop's `chat_fn`: the first reached the network and got 429; the second and third were refused **locally** by the per-process halt, with no network use. The cause was the diagnose loop's tolerance for provider failures (`MAX_PROVIDER_FAILURES = 2`), which re-calls `chat` after a `GatewayError`; it was not a bypass of pacing and not a second code path. (The v5 change to stop at the first failure removes the local re-calls and the misleading rows; it did not change what reached the network.) Formal v4 behaviour is unchanged. The one 429 at 13:29:38 came 10.7 s after the previous completion, i.e. at the old 10 s gap.

## 5. What was changed (axforge.py, gateway.py only; BeatAPI untouched)
1. **Shared 2 RPM start-to-start pacing:** `MIN_START_INTERVAL_S = 30.0`. `pace()` takes a machine-wide OS byte lock (the same lock primitive BeatAPI uses; no BeatAPI rule is applied), reads `runs/axforge_pacing.json`, waits until 30 s after the previous request's **start**, stamps the new start **before** sending (so a failed request keeps the spacing), and holds the slot until `done_turn()`. At most one AxForge request is in flight machine-wide. Applies to every request (diagnosis and tool-loop requests included), across threads, processes and resumes. Unreadable state fails closed (a full interval); a backwards clock jump can never stall longer than one interval.
2. **429 handling:** the first 429 halts the run (existing halt, now also logged); `record_429` stores the status, timestamp, **redacted** response headers and `Retry-After` (seconds or HTTP date) in the ledger row and in the shared pacing state. No retry, no probing.
3. **Retry-After is respected:** a later request refuses immediately (`AxForgeRateLimited` -> `GatewayError`, no network, reservation released) until the Retry-After has elapsed; it never sleeps through it. Without a Retry-After header nothing blocks beyond the 30 s spacing (the absence is recorded).
4. No automatic retries were added. The v5 diagnose loop stops at the first provider failure (earlier change); v4 keeps its tolerance, which only causes local refusals.

## 6. Tests (`tests/agent/test_axforge_pacing.py`, 14 tests; the old completion-based tests were replaced)
Interval counted from the previous start (and not from its completion, shown by an exact 9 s wait after a 20 s request); no extra wait after a slow request; a new process honours the shared state; unreadable state and clock jumps; **4 parallel threads** and **3 real separate processes** keep the interval; 429 stops at once and later calls send nothing (one network request in total, also through `gateway.chat`); status, time, headers and Retry-After are recorded with secrets redacted; Retry-After forms; a later attempt is refused before Retry-After elapses (no network, no sleep) and allowed after; BeatAPI is untouched (`MIN_INTERVAL_S` still 90 s, its path never calls the AxForge pacing).

## 7. Limits
- Whether the provider's real limit is 2 RPM is not documented; 30 s is the owner's intended limit and a precaution.
- Older 429s did not store headers, so whether the provider ever sent a Retry-After is unknown; future 429s will show it.
- The shared state file is created on the first request after this change; nothing is seeded from history.

## 8. Update after the Level-1 evaluation ran under the new pacing
The evaluation (23 requests, no 429) ran with the new shared pacing, but **its start-to-start intervals cannot be proven from the saved data**: the ledger records completion times, and the logged latency includes the wait for the pacing slot, so reconstructing starts from it is wrong (a first attempt gave false "violations"; the 2.6 s completion gap it showed is a 31-token reply that began right after a 53.6 s request, which is compliant). The only direct evidence is the final state (`last_start` 8.6 s before the last completion) and the tests. To make this auditable, `pace()` now appends every request start to `runs/axforge_pacing.log.jsonl` (sent_at, previous start, wait, pid; tested). Runs from now on can be checked directly; this evaluation cannot.
