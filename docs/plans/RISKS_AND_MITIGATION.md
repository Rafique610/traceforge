# Risks and mitigation

Likelihood and impact: Low / Medium / High.

## Technical risks
| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| T1 | Mistral free-tier limits or terms change, or Devstral is withdrawn | Medium | High | Gateway supports Ollama and Groq behind one interface; response cache means finished runs never need re-calling; any switch recorded as an ADR | Ruhan |
| T2 | Mistral's OpenAI-compatible endpoint handles `tools` differently | Medium | Medium | Verify in P1-S05 smoke test; add the smallest adapter if needed | Ruhan |
| T3 | Local 7B model too weak for tool calling | High | Low | It is the comparator, not the main model; pipeline-first agent limits tool use; report results honestly | Ruhan |
| T4 | Graph retrieval shows no gain (ceiling: trace anchor finds everything) | Medium | High (research) | ≥50% cases with distance ≥1; results per distance; feedback factor still gives a measurable effect | Rafique |
| T5 | Python dynamic features break static graph edges | Medium | Medium | Mark `UNKNOWN`; uncertainty penalty; A4 adds runtime trace edges (P5-S01) | Rafique |
| T6 | Sandbox runs too slow for ~1,600 A4 runs | Medium | Medium | Prebuilt images, long-lived container per service, parallel cases; measure in P1-S02 | Rafique |
| T7 | Docker Desktop on Windows: path, line-ending, volume-mount issues | Medium | Medium | `pathlib`, POSIX paths in contracts, `.gitattributes` for LF in lab code, test on both laptops at each sync | Both |
| T8 | 6 GB VRAM limits context for local model | High | Low | Keep context ≤ 8K for local runs; local is comparator only | Ruhan |
| T9 | Embeddings give only a small or no retrieval gain (symptoms already contain identifiers and traces; benchmark near saturation) | Medium | Medium | Preregistered thresholds on dev; equal-token and budget-matched baselines; a no-go in ADR 0003 is an acceptable result; no frozen path depends on it | Rafique |

## Architectural and research-validity risks
| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| A1 | Hidden-test signal leaks into prompts | Low | High | Hidden tests outside worktree; leak test mandatory (P2-S04) | Ruhan |
| A2 | Feedback effect confounded with extra attempts | Low | High | Both arms get 3 attempts (fixed in design) | Ruhan |
| A3 | Test set tuned on by accident | Medium | High | Freeze + hash before tuning; runner refuses unfrozen test manifest | Rafique (freeze), Ruhan (runner) |
| A4 | Synthetic faults too easy or too uniform | Medium | Medium | ≥10 families, confusable pairs, decoys, wording variation, per-family results | Rafique |
| A5 | Labels wrong | Low | High | Labels from generator; validator red/green; peer check of 10 cases | Rafique |
| A6 | Unverifiable numbers in demo (rubric deduction up to 10) | Low | High | All numbers recomputed from saved runs by script | Both |
| A7 | Index staleness or leakage: stale vectors after a code or model change, or hidden tests / gold / fault patches embedded | Medium | High | Content-addressed keys, manifest + consistency verifier (P5-S07); exclusion filter and leakage test; two identical runs; RC1 fingerprint checked before and after | Rafique |

## Integration risks
| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| I1 | Contract drift between tracks | Medium | High | Contract-PR rule; sample tests both sides | Both |
| I2 | Agent tuned to sample quirks fails on real evidence | Medium | Medium | Realistic samples; Sync 1 and Sync 2 early | Ruhan |
| I3 | Two people editing Alembic history | Low | Medium | Only Track B writes migrations | Ruhan |

## Scheduling and dependency risks
| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| S1 | Track A Phase 2 (critical path) slips | Medium | High | Ruhan uses slack to pull UI forward; P3-S02 can be done early on samples | Rafique |
| S2 | Dataset volume (P3-S01) takes longer than planned | High | High | Parameterized templates from P1-S03; start variants during Phase 2 | Rafique |
| S3 | Supervisor approval delayed | Medium | Medium | Send P0-S04 in the first days; keep building the agreed scope | Ruhan |
| S4 | Free-tier rate slows A3 experiments | Medium | Medium | Start runs immediately after freeze; cache; run overnight | Ruhan |
| S5 | Scope creep: the retrieval study (about 6.5 d Rafique) competes with the existing Track A backlog (reviews, evidence/graph gaps, P5-S01/S02, P6) | Medium | Medium | P5-S09 and P5-S05 are droppable; P5-S11 only after go; P5-S10 needs approval; capacity question Q16(e); no existing task changed | Rafique, project owner |
| S6 | Scope creep and capacity for the root-cause/impact study (P5-S12 to P5-S17, about 13 d more for Rafique, about 19.5 d with the retrieval study; ASSUMPTION) | Medium | High | MVP only first (S12, S15, S16-reduced, about 12.5 d with S06 to S08); Tier 2 (S13, S14) only after measurable gain; P5-S17 conditional; capacity is an owner/Rafique decision (Q18); no existing task changed | Rafique, project owner |
| S7 | Static-analysis limits: dynamic dispatch, monkeypatching, reflection and framework magic are invisible; recall bounded by test coverage (26 of 99 functions in `lab/`) and unknown call targets | High | Medium | Report as `unknown`, never guess; "not analysable" section and fixed limitation statement in every impact report; scenario H tests abstention; no claim of complete coverage | Rafique |
| S8 | Graph noise: expansion adds irrelevant context and tokens (existing precision 4 to 6 % for G) | Medium | Medium | Budgeted per-hop top N, hub stop, equal-token comparison, preregistered thresholds; keep complexity only if thresholds pass | Rafique |
| S9 | Secret leakage via value extraction from compose and settings | Low | High | `.env` stays name-only; secret-named keys never stored; reports redact; secret-leak test in P5-S13 | Rafique |
| S10 | Overfitting the design to a small hand-built fixture set | Medium | Medium | Priors fixed before evaluation, second-person label verification, held-out cases, wide CIs stated (Q17) | Rafique, Ruhan |

## Team coordination risks
| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| C1 | Ruhan not yet a GitHub collaborator, so no PR can merge | High (now) | High | Add him first (P0-S01) | Rafique |
| C2 | Reviews pile up | Medium | Medium | One-working-day review rule; small PRs per step | Both |
| C3 | One member can't explain the other's part in the viva | Medium | High (individual marks) | Cross-reviews; each sync includes a walkthrough of the other's code | Both |
| C4 | Unequal contribution visible in Git history | Low | Medium | Balanced plan; PRs authored by the owner | Both |
