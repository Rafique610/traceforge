# Code graph performance (P2-S02)

Measured with `python -m traceforge.codeintel <repo> --no-cache --bench` (from `backend/`, venv Python 3.12, Windows 11, shared 16 GB machine with other agents running, so timings are noisy: the three repeats below show the spread). Numbers are wall-clock seconds from `time.perf_counter`.

What each column means:
- **cold**: no cache; scan + parse every file + assemble + build networkx graph (with reverse edges).
- **warm**: cache hit for every file (0 files re-parsed); still re-scans and hashes every file, loads the JSON, reassembles.
- **incremental**: one file edited in a temp copy of the repo; 1 file re-parsed, the rest from cache. The graph is reassembled from facts every time (cross-file resolution is not incremental), and the whole facts JSON is rewritten.
- **peak RSS**: Windows `PeakWorkingSetSize` of the whole benchmark process (interpreter, networkx, three builds, repo copy). **tracemalloc peak**: Python allocations of one cold build.

## Real package: `backend/traceforge` (100 Python files)
Graph: 578 nodes (86 class, 29 config_key, 100 file, 259 function, 56 method, 28 settings_field, 20 unknown), 1,410 forward edges + 1,410 reverse edges (650 calls, 243 imports, 429 defined_in, 60 reads_config, 28 declares_config), 34 UNKNOWN call edges.

| Run | cold | warm | incremental (1 file) | tracemalloc peak | peak RSS |
|---|---|---|---|---|---|
| 1 | 1.30 s | 0.39 s | 0.26 s | 5.1 MB | 54.0 MB |
| 2 | 0.91 s | 0.35 s | 0.26 s | 5.1 MB | 54.8 MB |
| 3 | 0.66 s | 0.41 s | 0.31 s | 5.1 MB | 54.3 MB |

Parse is about 90% of a cold build (0.73 s parse vs 0.08 s assemble in a single run).

Code map of this package: 26,375 characters, about 6,600 tokens (chars/4 estimate, not a tokenizer). That is too big to hand to a 4,000-token-budget prompt (limits report, D20) whole; use `code_map` per directory/file subset or the retrieved neighbourhood.

## Whole `backend/` (production code + tests, 157 files at the time of the run)
cold 1.46 s / 1.00 s; warm 0.35 s / 0.47 s; incremental 0.38 s / 0.42 s; tracemalloc peak 9.3 MB; peak RSS 67.5 MB (two runs). The file count of `backend/` changed between runs because other agents were adding files (249 files in a later cold-only run: 1,199 nodes, 3,038 forward edges, 48 unknown, 1.2 s).

## `lab/` (37 Python files + `compose.yaml`, measured 21 Nov 2026)
239 nodes, 504 forward edges (+504 reverse): 85 calls, 60 imports, 182 defined_in, 85 reads_config, 21 declares_config, 21 service_env, 5 depends_on, 2 service_runs, 43 tests_covers; 15 UNKNOWN call edges; 20 config keys; 4 services.

| Run | cold | warm | incremental | tracemalloc peak | peak RSS |
|---|---|---|---|---|---|
| 1 | 0.26 s | 0.15 s | 0.24 s | 1.6 MB | 44.1 MB |
| 2 | 0.21 s | 0.16 s | 0.20 s | 1.6 MB | 44.6 MB |
| 3 | 0.23 s | 0.25 s | 0.19 s | 1.6 MB | 44.4 MB |

Code map of lab: 6,479 characters, about 1,620 tokens (chars/4).

## Reading the numbers honestly
- At these sizes everything is sub-second and memory is tiny, so performance is not a constraint for this project. 
- The disk cache saves roughly 2x on cold-to-warm for the larger repos but **incremental is not much faster than warm**: filesystem scan, hashing, JSON load/save and full reassembly dominate once parsing is skipped. On the 37-file lab, cache gives almost nothing. Making assembly incremental would be the next step only if repos grow by 10x.
- Peak RSS is the whole benchmark process, mostly interpreter and library import, not graph size.
- Timing noise: runs overlapped with other agents' work on the same machine. Treat the spread as the uncertainty.
- Correctness of resolution is checked by `backend/tests/codeintel` (26 tests on a purpose-built fixture repo), not by these runs. No precision/recall of call resolution against ground truth was measured on the real package; the UNKNOWN counts above are only counts.

## Reproduce
```
cd backend
.venv\Scripts\python.exe -m traceforge.codeintel traceforge --no-cache --bench
.venv\Scripts\python.exe -m traceforge.codeintel ..\lab --no-cache --bench --map
```
