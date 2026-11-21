# Devstral Small 2 on Ollama — definitive investigation (2026-11-21)

Method: public pages, Ollama's public registry, and **metadata-only** API calls (`/api/tags`, `/api/show`, `/api/balance`, `/api/usage`). **No inference request was sent to any Devstral model; no billable call; no credits; no plan change; no key printed.** Ruhan's intended-model setting for Devstral is unchanged (`evaluation/conditions/*.json`, ADR 0001); Qwen stays the local fallback.

## Conclusions
| # | Question | Answer | Evidence (verified unless marked) |
|---|---|---|---|
| 1 | Does the exact model exist in the public Ollama library? | **Yes, as a stale/historical listing.** | https://ollama.com/library/devstral-small-2:24b-cloud returns HTTP 200 and shows `ollama run devstral-small-2:24b-cloud`, "2.9M downloads", "Updated 11 months ago", 256K ctx, tools+vision; `/tags` lists the `24b-cloud` tag (digest `ec4a591da58a`); registry manifest `registry.ollama.ai/v2/library/devstral-small-2/manifests/24b-cloud` → HTTP 200 (405-byte stub, no layers). The page carries no retirement banner. |
| 2 | Is the exact cloud tag currently operational? | **No — retired.** | The cloud service answers for this exact tag with **HTTP 410 Gone**: `"devstral-small-2:24b was retired on July 15, 2026. Try glm-5.3-flash:cloud."` (`POST https://ollama.com/api/show {"model":"devstral-small-2:24b-cloud"}` with Ruhan's key; metadata call). The local stub gives the same 410 (`POST localhost:11434/api/show`). The same endpoint returns 200 for live models (e.g. `gpt-oss:20b`), so the check is discriminating. |
| 3 | Is it available to Ruhan's authenticated account? | **No.** | `GET /api/tags` (24 models, rechecked today) contains no Devstral; `/api/show` → 410 for `devstral-small-2:24b`, `devstral-small-2:24b-cloud`, and `devstral-2:123b`. |
| 4 | Can the account use it for free? | **Moot — it cannot be used at all.** Separately: no free allowance is confirmed. | `/api/balance`: included $0, purchased $0; pricing page lists no Free plan (see `free-model-providers.md`). The Reddit post (r/ollama 1u2ahuj) could not be read (login wall); the claim is **assumed to predate the 2026-07-15 retirement** (not verifiable). |
| 5 | Technically compatible with TraceForge? | **Yes in principle, moot today.** | Public metadata: tools + 256K context; our gateway can call `-cloud` models through the local server, but the free-only guard refuses them unless `TRACEFORGE_LLM_ALLOW_OLLAMA_CLOUD=true`. Nothing was tested (cannot be: retired). |
| 6 | Exact reason for each "no" | **Ollama retired the model on 2026-07-15 and the service returns 410 Gone.** The library page was not updated (it still says "Updated 11 months ago" and still offers the run command), and the registry still holds the tag stub. | lifecycle page https://docs.ollama.com/cloud/model-lifecycle: "Past retirements … July 15, 2026 … `devstral-2:123b`, `devstral-small-2:24b`"; "Upcoming retirements: none scheduled"; "Cloud model retirement does not affect local models." |

## Answers to the specific sub-questions
- *Does the retirement apply to the exact `:24b-cloud` tag?* Yes. The lifecycle table lists cloud names without the `-cloud` suffix (like the account catalog: `gemma4:31b`, `gpt-oss:120b`), and the service's 410 message for `devstral-small-2:24b-cloud` names `devstral-small-2:24b`. The earlier worry that base and cloud identifiers might differ is refuted by the 410 response.
- *Removed from inference entirely?* Yes for cloud inference (410). **Local weights are not affected**: the registry still serves `devstral-small-2:24b` with layers (15 GB, q4_K_M, 384K ctx; manifest HTTP 200).
- *Replacement?* Ollama's message suggests `glm-5.3-flash:cloud` (price 0.15/0.50 per 1M tokens; Vals SWE-bench Verified 92.0%, Terminal-Bench 37.0%) — **not free**. The lifecycle table gives no replacement for `devstral-small-2:24b` and `mistral-large-3:675b` for `devstral-2:123b`.
- *Clarification/newer variant?* None found; no newer Devstral Small tags in the library.
- *Why do public listing and account differ?* The website library is a catalogue of published tags; the service's live catalogue (`/api/tags`) only contains models still being served. Retired cloud models stay on the website with their stub tags.

## What would make Devstral usable at $0 (none verified)
1. **Local weights** `devstral-small-2:24b` (15 GB): downloadable per the registry; on this 6 GB GPU / 16 GB RAM desktop it would run mostly on CPU (estimate: very slow; not tested, **not downloaded** — needs approval and ~1 h at the observed ~4.5 MB/s). Not a candidate for the full experiment.
2. **Mistral's own API** (`devstral-small-latest`): free access unconfirmed; requires Ruhan to check his Mistral console (see `UNBLOCK_MESSAGES.md`).
3. OpenRouter has only the paid `mistralai/devstral-2512` (not free).

## Decision record
B14 is corrected and strengthened by B15 (DECISIONS.md): Devstral stays the intended model in configuration; there is currently no working route to it at any price via Ollama Cloud.
