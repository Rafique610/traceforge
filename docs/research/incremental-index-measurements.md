# Incremental index measurements (P5-S07)

Facts only. Hardware: Windows 11 Pro, AMD Ryzen 5 2600 (6 cores, 12 threads), 16 GB RAM (Ollama backend CPU/GPU not inspected), local Ollama at localhost:11434, model `all-minilm:22m` (384-d, revision tag = first 12 hex of the Ollama digest, `1b226e2802db`). Corpus: `lab/` (280 chunks from `build_graph` + `build_corpus`, 0.17 s to build). Batch size 32, one `/api/embed` request per batch. Command: `python -m traceforge.index sync --repo lab --namespace-root <dir>`.

| Run | New | Unchanged | embed calls | texts embedded | reused | seconds |
|---|---|---|---|---|---|---|
| Cold sync (empty namespace) | 280 | 0 | 9 | 276 | 0 | 34.3 |
| Warm resync (same commit) | 0 | 280 | 0 | 0 | 280 | 0.033 |

- 276 texts for 280 chunks: four chunks have byte-identical embedding text and share one content-addressed vector.
- Storage after cold sync: 634,881 bytes total (shards + manifest + model.json + ACTIVE.json) for 276 vectors x 384 float32 (about 424 KB of raw vectors).
- `verify` after the sync: no problems.
- Peak RSS was not measured. Single run each; no repetition, so timings carry no variance estimate (the cold time includes Ollama loading the model).
- Scenario (changed/added/deleted/renamed/moved/import/model-upgrade) embed counts are asserted in `backend/tests/index/test_index.py` with a fake embedder, not timed here.
