# ADR 0001 — Primary model and provider strategy

Status: **PROPOSED — not final.** Q1 (exact Devstral ID and free access) is still open, so the primary model cannot be pinned yet. Date: 2026-11-21. Author: Ruhan's working session (Claude Code assisted). Reversible: yes.

## Context
The plan (D5/D21) names Mistral's Devstral as the primary cloud model and local Qwen2.5-Coder-7B as the comparator, at a USD 0 budget. Findings on 2026-11-21 (sources in `docs/research/free-model-providers.md`, decisions B4, B7, B11, B12):
- Devstral 2 needs paid Mistral API access; whether the free Experiment plan serves `devstral-small-latest` is unverified (needs Ruhan's console).
- OpenRouter lists only `mistralai/devstral-2512` at a paid price; no `:free` Devstral.
- Ollama Cloud's official `devstral-small-2:24b-cloud` exists, but cloud models are billed per token and no free allowance is documented; the third-party `zerocopia/...` copy is unreviewed.
- Local `qwen2.5-coder:7b` (via a 16k-context Ollama variant) works on the 6 GB GPU but is slow and weak at multi-line edits.
- Live results so far: local Qwen and OpenRouter `nvidia/nemotron-3-ultra-550b-a55b:free` (experimental only) in `docs/research/limits-report.md`; **no Devstral run exists**.

Update 2026-11-21 (B14, re-investigated): Ollama's lifecycle page lists `devstral-small-2:24b` and `devstral-2:123b` as retired on 2026-07-15 and the account's live cloud catalog has no Devstral, so the official cloud Devstral is unavailable at any price (account allowance also $0). Nothing was requested. Devstral remains the intended model but has no working $0 route today.

Update 2026-11-21 (B15): the cloud service itself returns HTTP 410 for `devstral-small-2:24b-cloud` ("retired on July 15, 2026"); see `docs/research/DEVSTRAL_OLLAMA_INVESTIGATION.md`. Devstral stays the intended model in configuration; there is no route to it via Ollama Cloud.

Update 2026-11-22 (B17, owner decision): the agent model is now **AxForge `glm-5.3-flash`** (`https://api.axforge.ai/v1`), free allowance of 3M tokens per 30 days, no card. Evidence so far is thin: one 31-token connection check and one live `agent:run` on the sample `code` case (diagnosis produced, 3 tool calls, 0 invalid; not sandbox-verified). No head-to-head against Qwen/Nemotron was run, by instruction. Open risks: reasoning tokens count toward `max_tokens`, latency 20-140 s per call at effort high, the free/paid split is not observable through the API (safety rests on a zero prepaid balance), and a BeatAPI-served GLM was stopped before any coding score. This ADR stays PROPOSED until a probe on identical cases exists.

## Decision (provisional)
0. **Owner-selected working model (2026-11-22): AxForge `glm-5.3-flash`**, guarded by `agent/axforge.py` (exact id, fixed host, one attempt, no fallback).
1. **Previously intended primary cloud model: Devstral** (`devstral-small-latest`, provider `mistral`), unchanged in `evaluation/conditions/*.json`. It is not pinned to a dated ID and not usable at $0 yet.
2. **Local `qwen2.5-coder:7b` is the reproducible baseline** and the only model that can currently run all four conditions at $0.
3. **Nemotron `:free` (OpenRouter) is experimental only**, never the primary; its numbers are not Devstral's.
4. **The gateway is provider-agnostic with a free-only guard:** non-`:free` OpenRouter IDs, non-allowlisted providers, and Ollama `-cloud` models are refused unless explicitly enabled. Experiments run at temperature 0 with the cache key including provider, model, prompt, tools, max_tokens, seed and replicate index.
5. A provider/model change for the experiment needs a new ADR (ml.md). One experiment never mixes models.

## Consequences
- The 2×2 experiment can run on local Qwen now; a Devstral run waits for confirmed free access.
- Model comparison (Devstral vs Qwen, same cases and conditions) is **NOT RUN**.
- ADR must be finalised when Q1 closes: exact model ID, date, observed limits, data terms.

## Conditions for reconsideration
Free Devstral access confirmed (Mistral Experiment plan or otherwise) → pin it and re-run the probe on identical cases; Ollama Cloud shows a non-zero included balance with no payment path → consider the official `devstral-small-2:24b-cloud`; the supervisor decides to allow a paid model (explicit approval needed).

## Evidence in the repository (2026-11-25)
Status stays **PROPOSED**; the owner decides. Only verified facts are listed here.
- AxForge `glm-5.3-flash` is the model used in every RC1 run in `results/final` (all conditions, temperature 0, live requests).
- Devstral and Mistral were NOT run (no free route; see the updates above).
- A local smoke on 25 Nov with `qwen3.5:4b-q4_K_M` (shop_api-001, G1, `--pipeline v5`, label EXPERIMENTAL-LOCAL-P5S04, run `runs/e2e/p5s04-local-smoke-qwen35-4b`) FAILED: `provider_error` BadRequestError (HTTP 400 from `/v1/chat/completions` after 54 s). The cause is unconfirmed (possibly the 4096 default context or the tool/thinking format). `qwen2.5-coder:7b`, which this ADR names as the local baseline, is not installed on the machine at present.
- No head-to-head probe numbers exist between any two models; none are claimed here. Model comparison remains NOT RUN.
- Key-1 allowance left on 25 Nov: 152,664 tokens; combined 742,728 left under the 4.8M internal ceiling.
- Local comparison on 25 Nov (P5-S04, `docs/research/model-sensitivity.md`; 12 stage-1 sites, G1, replicate 0, one at a time): local `qwen3.5-4b-ctx12k` (qwen3.5:4b-q4_K_M, num_ctx 12288) vs recorded `glm-5.3-flash` (RC1): verified repairs 4 vs 10; diagnosis class correct 9 vs 12; invalid tool calls 26 vs 0; median/P95 latency 275.6/406.5 s vs 24.0/28.6 s per case. The earlier HTTP 400 was Ollama's default 4096 context rejecting the prompt, not the tool format. n=12, one replicate, not mixed into `results/final`; no code model compared (`qwen2.5-coder:7b` not installed). This does not change the status.
- On 25 Nov the real end-to-end path with local Ollama reached DIAGNOSED correctly on shop_api-001 but the 4B model produced `malformed_edit` (no patch); BeatAPI free returned HTTP 503 twice. Nothing was spent on AxForge on 25 Nov.
