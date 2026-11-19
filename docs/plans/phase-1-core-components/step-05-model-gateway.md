# P1-S05 — Model gateway, response cache and ADR 0001

## A. Task identification
| Field | Value |
|---|---|
| Phase | 1 Core components |
| Step | 5 |
| Task ID | P1-S05 |
| Synverk card | TRAC-9 |
| Primary owner | Muhammad Ruhan Kamran |
| Supporting | — |
| Reviewer | Muhammad Rafique |
| Priority | Normal |
| Effort | 2 days |
| Status | NOT STARTED |
| Branch | `ruhan/P1-S05-model-gateway` |

## B. Objective
One way to call Mistral, Ollama or Groq with tools, where every call is logged (tokens, latency, cost) and cached. The cache makes experiments free to re-score and exactly reproducible (safeguard 4), and protects against the free tier's rate limits. This step also pins the primary model (open question Q1).

## C. Prerequisites
- P0-S02 (`Settings`).
- A Mistral account with a free API key (Ruhan) — key goes in `.env` only.
- Ollama installed with `ollama pull qwen2.5-coder:7b`.
- Optional Groq key.

## D. Technical background
- All three providers expose OpenAI-style chat completions: Mistral `https://api.mistral.ai/v1`, Ollama `http://localhost:11434/v1`, Groq `https://api.groq.com/openai/v1`. Using the `openai` SDK with a `base_url` keeps one code path (assumption AS6; verify `tools` support for Mistral in the smoke test).
- **Cache key:** SHA-256 of a canonical JSON of `(provider, model, messages, tools, temperature, max_tokens, seed)`. Same request → same response, no API call. A `--no-cache` flag forces live calls for smoke tests.
- **Cost:** free tier actual cost is 0, but each call also records a **list-price equivalent** from a price table in config, for the business section and per-case cost reporting (rubric D5).
- Temperature 0 for every experiment.

## E. Implementation instructions
1. `uv add openai`.
2. **Settings:** `llm_provider` (`mistral`/`ollama`/`groq`), `llm_model`, `mistral_api_key` (SecretStr), `groq_api_key` (SecretStr), `ollama_base_url`, `llm_cache_dir` (default `.cache/llm`), `llm_max_rps`, price table (`dict[str, tuple[float, float]]` per 1M in/out).
3. **`agent/gateway.py`:**
   - `ModelResponse` (Pydantic): `content`, `tool_calls` (name, arguments JSON), `tokens_in`, `tokens_out`, `latency_ms`, `cache_hit`, `provider`, `model`, `list_price_usd`.
   - `chat(messages, tools=None, *, profile=None, cache=True, max_tokens=...) -> ModelResponse`.
   - client per provider (`OpenAI(base_url=..., api_key=...)`; Ollama key can be any string).
   - simple rate limiter (min interval = 1/`llm_max_rps`).
   - retries on 429/5xx with exponential backoff (max 5); final failure raises `GatewayError` (callers record `INCONCLUSIVE`/`UNVERIFIED`, never invent output).
4. **`agent/cache.py`:** `get(key)`, `put(key, request, response)`; one JSON file per key under `llm_cache_dir/<provider>/<model>/<key[:2]>/<key>.json`. Add `.cache/` to `.gitignore`.
5. **`agent/call_log.py`:** append each call (without message content, only hashes and counts) to `runs/llm_calls.jsonl` for cost/latency analysis.
6. **Smoke test** `agent/smoke.py` + `task llm:smoke PROVIDER=mistral|ollama|groq`: one tool `get_service_status(service: str)`; ask the model to check `worker`; assert a valid tool call with JSON arguments; run twice and show the second is a cache hit.
7. If Mistral's tool-call format differs from OpenAI's, add the smallest adapter in `gateway.py` and document it.
8. **ADR** `docs/adrs/0001-primary-model.md`: chosen Devstral model ID (exact string), date, free-tier limits read from the Mistral admin panel (RPS, monthly tokens, data-training terms), Ollama comparator tag, and why.
9. Unit tests with a mocked client: cache hit/miss, retry on 429, cost calculation, request canonicalization (key order doesn't change the hash).

Edge cases: very long prompts beyond context → raise before sending; Ollama not running → clear error; secrets never logged (assert in a test that the key isn't in any log line).

## F. Checklist
- [ ] Settings for providers, keys (SecretStr), cache, rate, prices
- [ ] `ModelResponse` and `chat()`
- [ ] Rate limiter and retries
- [ ] Disk cache keyed by canonical SHA-256
- [ ] Call log without message content
- [ ] Smoke test for Mistral, Ollama (Groq optional)
- [ ] Mistral tool-call compatibility verified
- [ ] ADR 0001 with exact model ID and limits
- [ ] Unit tests (cache, retry, cost, canonical key, no secret in logs)
- [ ] `.cache/` and `runs/` git-ignored
- [ ] README: how to set keys and run the smoke test

## G. Expected deliverables
New: `backend/traceforge/agent/{gateway,cache,call_log,smoke}.py`, tests, `docs/adrs/0001-primary-model.md`. Modified: `config.py`, `.env.example`, `.gitignore`, `Taskfile.yml`, `README.md`. Interface: `chat(...) -> ModelResponse`.

## H. Testing and validation
- `task llm:smoke PROVIDER=mistral` and `PROVIDER=ollama` both pass; second run logs `cache_hit=true` and no network call.
- Unit tests green.
- Acceptance: ADR merged; answering open question Q1 in [DECISIONS_AND_OPEN_QUESTIONS.md](../DECISIONS_AND_OPEN_QUESTIONS.md) (update that row in this PR).

## I. Dependencies and integration
- **Depends on:** P0-S02.
- **Unblocks:** P1-S06 (agent), P3-S04 (runner uses cache), P5-S04 (model comparison).

## J. Definition of done
Merged after Rafique's review; smoke tests pass on both laptops (Ollama) and on Mistral; ADR merged; Q1 closed; TRAC-9 approved.
