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

## Architectural and research-validity risks
| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| A1 | Hidden-test signal leaks into prompts | Low | High | Hidden tests outside worktree; leak test mandatory (P2-S04) | Ruhan |
| A2 | Feedback effect confounded with extra attempts | Low | High | Both arms get 3 attempts (fixed in design) | Ruhan |
| A3 | Test set tuned on by accident | Medium | High | Freeze + hash before tuning; runner refuses unfrozen test manifest | Rafique (freeze), Ruhan (runner) |
| A4 | Synthetic faults too easy or too uniform | Medium | Medium | ≥10 families, confusable pairs, decoys, wording variation, per-family results | Rafique |
| A5 | Labels wrong | Low | High | Labels from generator; validator red/green; peer check of 10 cases | Rafique |
| A6 | Unverifiable numbers in demo (rubric deduction up to 10) | Low | High | All numbers recomputed from saved runs by script | Both |

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

## Team coordination risks
| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| C1 | Ruhan not yet a GitHub collaborator, so no PR can merge | High (now) | High | Add him first (P0-S01) | Rafique |
| C2 | Reviews pile up | Medium | Medium | One-working-day review rule; small PRs per step | Both |
| C3 | One member can't explain the other's part in the viva | Medium | High (individual marks) | Cross-reviews; each sync includes a walkthrough of the other's code | Both |
| C4 | Unequal contribution visible in Git history | Low | Medium | Balanced plan; PRs authored by the owner | Both |
