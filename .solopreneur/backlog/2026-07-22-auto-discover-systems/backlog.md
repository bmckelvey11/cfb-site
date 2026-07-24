# Backlog: Automated System Discovery

## Source
Spec: `.solopreneur/specs/2026-07-22-auto-discover-systems.md`

## MVP
| ID | Title | Status | Depends On | Type | Size |
|----|-------|--------|------------|------|------|
| MVP-001 | Stats primitives — analytic p-value helper + BH correction | done | — | eng | S |
| MVP-002 | Candidate generation — canonical identity, compat grammar, deterministic enumeration | done | — | eng | L |
| MVP-003 | In-sample beam search — evaluation, pruning, ranking | done | MVP-002 | eng | L |
| MVP-004 | Holdout finalist grading + BH correction + result assembly | done | MVP-001, MVP-003 | eng | M |
| MVP-005 | `search` CLI command + structured error paths | pending | MVP-004 | eng | M |
| MVP-006 | Performance benchmark + reproducibility gate | pending | MVP-005 | eng | S |

## P1
| ID | Title | Status | Depends On | Type | Size |
|----|-------|--------|------------|------|------|
| P1-001 | `SavedSystem` provenance schema + CLI `--save` | pending | MVP-004 | eng | S |
| P1-002 | Web disclosure — Search badge + candidate-count (dashboard + compare) | pending | P1-001 | eng+design | M |

## P2
| ID | Title | Status | Depends On | Type | Size |
|----|-------|--------|------------|------|------|
| P2-001 | LLM narration of top-K results (opt-in) | pending | P1-002 | eng+design | M |

## Dependency Graph

```
MVP-002 ──► MVP-003 ──► MVP-004 ──► MVP-005 ──► MVP-006
MVP-001 ─────────────────────►┘
                                  MVP-004 ──► P1-001 ──► P1-002 ──► P2-001
```

## Parallel Groups

- MVP-001 and MVP-002 — no shared deps, buildable simultaneously.
- Remainder of MVP is a sequential chain (each stage's output is required input for the next — the search evaluation tiers are inherently sequential: candidate generation → in-sample beam eval → holdout grading → CLI wiring → benchmark).
- P1 and P2 are strictly sequential after MVP-004 (schema must exist before badge; badge/search-results surface must exist before narration).

## Cross-Cutting Risks (apply during review of any ticket below)

1. **Performance**: two-tier `run_backtest_summary` (beam, cheap, many calls) → `run_backtest` (holdout, expensive, ≤K calls) is a hard requirement, not an optimization nice-to-have. MVP-006 is the empirical proof; a benchmark failure means MVP-003's beam mechanics need rework, not a patch.
2. **Holdout leakage**: highest-risk correctness property in this feature. Must be enforced structurally (function signatures that make it impossible to pass holdout data into in-sample-only code paths), not just by testing — a subtle bug (e.g. passing the full unsplit dataset into a helper) silently reproduces "leakage even if the final displayed number is holdout-only."
3. **Deterministic enumeration**: every `set` iteration inside `search.py` must be sorted first. Easy to regress in a later edit — worth a review checklist item, not just a one-time test.
4. **BH correction scope**: `candidates_tested` (N, provenance only) vs `finalists_graded` (K, the actual BH batch) is an easy off-by-concept error. Analytic p-value (BH input) vs permutation p-value (descriptive secondary stat, from full `run_backtest`) is a second easy-to-conflate distinction. MVP-001 and MVP-004 warrant extra review scrutiny specifically here.
5. **MVP-002 scope decision (resolved)**: candidate generation for team-scoped registry features defaults to `bet_side` perspective only for MVP — not explicitly specified in the PRD, confirmed as acceptable scope-narrowing during backlog review. Document this choice in code (docstring/comment) so it isn't mistaken for an oversight later.
