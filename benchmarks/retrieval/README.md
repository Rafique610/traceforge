# Retrieval benchmark data (P5-S06)

Labels, queries and repo pins for the offline retrieval benchmark run by `backend/traceforge/retrieval_bench/`.
Zero LLM or provider calls. Gold is used only by the scorer.

## Contents

| File | What |
|---|---|
| `repos.json` | Three pinned repositories: URL, ref, exact commit SHA, license, size, content hash, local path |
| `queries/<repo>.json` | 15 queries per repo, each with gold units and a one-line justification per unit |
| `second_review.csv` | One row per (query, gold unit) for the independent second reviewer (agree / disagree columns blank) |

## Repositories

| Tier | Repo | Pin | License | Size | Python files |
|---|---|---|---|---|---|
| small | pallets/itsdangerous `2.2.0` | `096c8d42545d3b68ea21a4f890fb2b2d8979c0bd` | BSD-3-Clause | 139 KB | 8 source modules (15 `.py` with tests) |
| medium | psf/requests `v2.32.3` | `0e322af87745eff34caffe4df68456ebc20d9068` | Apache-2.0 | 5.2 MB | 18 source modules (36 `.py`) |
| complex | this repository's `lab/` (shop_api + worker + `compose.yaml` + `.env.example` + settings + tests) | repo `HEAD` `9f2eb794db0e8a14845a8e26815e4a88c38150e2`, `lab/` tree `3b9ea6112986a19e8fccaf64724f4ab990fc01d9` | project-internal | 63 KB | 30 non-test (42 `.py`) |

`backend/traceforge` is deliberately not a benchmark repo. The complex tier uses the lab (own code, has config, compose and tests); the dev-split faults are injected into this same lab, so the dev loader and tier (c) share code but not queries or labels. Total clone size is below 10 MB.

Re-create the clones (all under `runs/bench_repos/`, git-ignored):

```
git clone --depth 1 --branch 2.2.0  https://github.com/pallets/itsdangerous.git runs/bench_repos/itsdangerous
git clone --depth 1 --branch v2.32.3 https://github.com/psf/requests.git        runs/bench_repos/requests
mkdir runs/bench_repos/traceforge_lab && git archive 9f2eb794db0e8a14845a8e26815e4a88c38150e2 lab | tar -x -C runs/bench_repos/traceforge_lab
```

The harness refuses to run if a clone's `HEAD` (or, for the lab, the tree content hash) differs from the pin.

## Query design

Each repo has 15 queries covering six types (`exact_identifier`, `paraphrased_bug`, `symptom_no_identifier`, `indirect_dependency`, `configuration`, `multi_file`; 2 to 4 per type). For the two library repos "configuration" means constructor parameters and class-level defaults that configure behaviour (they have no env/compose files); for the lab it means env/compose/settings keys, with gold given as `cfg:KEY` chunks plus the `Settings.*` fields.

A query is plain text, as a user or issue would write it. Queries with identifiers or error messages are copied from the code at the pinned commit; symptom and paraphrase queries avoid source identifiers on purpose.

## Gold format

`gold` is a list of `{"id", "why"}`. `id` is a chunk id of the existing corpus (`traceforge.retrieval.corpus`): `sym:<path>::<qualname>` (function, method, class header, class-level field), `test:<path>::<qualname>`, `cfg:<KEY>`. `why` states in one line why the unit is relevant, based on the code. Gold means "a unit someone fixing this problem needs to read or change", not "the only line of the fix". The harness checks that every gold id exists in the corpus of the pinned tree (existence check only).

Known corpus limitation, applies to all methods equally: an overloaded method (for example `TimestampSigner.unsign` in itsdangerous) is one chunk holding the first `@overload` stub, so its real body is not indexed; the id is still valid gold.

## Who labelled, and what is still open

**Labels were authored and checked by Claude on behalf of Muhammad Ruhan Kamran by reading the actual source at the pinned commits (not from any retrieval tool's output). They have not been verified by a second person and need an independent spot check before any result is used beyond engineering validation.** Rafique reviews the task; the second-person label check is a separate step.

### Labelling protocol (used, and to follow when reviewing)

1. Write the query first, from a symptom, a paraphrase or a real error string in the code, without looking at any retrieval ranking.
2. Open the pinned source and read the code paths the query implies (callers and callees as far as needed).
3. List as gold every unit that someone fixing the problem would need to read or change: where the error is raised or the behaviour is decided, plus the direct parameters/settings and the minimum cross-file links the query asks for. Do not add units "because a retriever might find them".
4. Write one sentence of justification per unit that is checkable in the code.
5. Never edit labels after seeing a retrieval result. If a label is wrong, record the correction in `second_review.csv` and in a dated note, keep the original, and re-run all methods.

### Second-reviewer procedure (`second_review.csv`)

Check out the pinned commits, open each row's `gold_unit` and read the code. In `reviewer_agree_yes_no` write `yes` if the unit is relevant to the query and the justification is true, otherwise `no` (and say why in `reviewer_comment`). Also add a row with `MISSING` in `gold_unit` for any unit you would have included but is absent. Aim for all 15 queries of at least one repo, or a random 30% of rows. Report agreement as `yes / rows`; if it is below 90% on any repo, the labels of that repo must be revised before results are quoted. The reviewer should not look at `results/retrieval/` first.

## Running

```
cd backend
.venv/Scripts/python.exe -m traceforge.retrieval_bench --suite both --methods RET-L RET-G
```

Output: `results/retrieval/<run_id>/` (`per_query.csv`, `summary.csv`, `comparisons.csv`, `builds.csv`, `rankings.json`, `summary.json`, `report.md`). Never writes under `results/final`. Adding methods: see `backend/traceforge/retrieval_bench/registry.py` and `docs/research/retrieval-benchmark-baselines.md`.
