# PRD: Automated System Discovery

Source: `.solopreneur/discoveries/2026-07-22-auto-discover-systems.md`

## Overview

Add a search layer to cfb_system_maker that automatically explores the `SystemFilter` space (core filters + registry features) and surfaces candidate profitable systems, replacing manual one-combo-at-a-time filter building. Unlike a naive "AI auto-finder," this feature's core value is statistical honesty at scale: every surfaced candidate is holdout-validated and multiple-comparisons-corrected before it's shown, with clear UI disclosure that it's a search result, not a hand-built system. Search itself is deterministic (greedy/beam), not LLM-driven; an LLM may narrate top results in a later phase, but does not score candidates.

## User Stories

1. As an analyst, I want to run an automated search over the filter space, so that I find profitable systems I wouldn't have thought to build manually.
2. As an analyst, I want every auto-found system graded on out-of-sample (holdout) data only, so that I don't trust a system that was curve-fit to the seasons it was found in.
3. As an analyst, I want the search's significance threshold corrected for how many combinations were tried, so that a "significant" result isn't just noise from testing thousands of combos.
4. As an analyst, I want auto-found systems visually distinguished from manually-built ones (with "N candidates tested" shown), so that I don't mistake a dredged result for a reasoned one.
5. As an analyst, I want to save/compare an auto-found system exactly like a manual one, so that my existing save/load/compare workflow still works.
6. As an analyst, I want to configure search scope (e.g. max filters, seasons to search over, bet type), so that I can bound runtime and avoid trivially overfit results (too many active filters).
7. (P2) As an analyst, I want a plain-English narrative summary of the top-K found systems, so that I can scan results faster without reading raw stats.

## Acceptance Criteria

**Story 1 — Run search**
- Given a data-built `games.csv`/features sidecar exists, when I run `search` (CLI), then the system explores filter combinations via greedy/beam search and returns a ranked list of candidates.
- Given no built data exists, when I run `search`, then it writes `error=missing_data` plus actionable rebuild guidance to stderr and exits non-zero without a traceback. This aligns search with web API error naming; existing CLI `backtest` does not yet provide this structured error path.
- `--holdout-season` is required and must leave at least one in-sample season after scope filtering. Search refuses a missing, unknown, or all-data holdout rather than silently grading all seasons.
- Search-loop expansion/pruning uses `run_backtest_summary` (match+grade, no permutation-test overhead) — the full `run_backtest` (with 1000-iteration permutation test) runs only once per surviving candidate, on the final top-K, not on every candidate evaluated during search. (Engineer flag: calling full `run_backtest` per candidate across a beam search is plausibly hour-plus; this two-tier approach is required, not optional.)

**Story 2 — Holdout-only grading, no leakage**
- Given a search run, when a candidate's grade is computed and reported, then it is computed only on `split_holdout`'s holdout seasons.
- Search selection/ranking/pruning during the search itself uses only in-sample seasons — holdout data is touched exactly once, to grade the final set of already-selected candidates. (Engineer flag: if holdout data influences which candidates advance during search, that's leakage even if the final displayed number is holdout-only.)
- Given a candidate matches zero games in the holdout set, when graded, then it is excluded from results (not shown with a misleading grade on near-zero sample).

**Story 3 — Multiple-comparisons correction**
- Given K finalists are graded on holdout, when p-values are reported, then their holdout **analytic** p-values are BH (Benjamini-Hochberg) corrected over those K independent final tests: p-values sorted ascending, each compared against its rank-scaled threshold (`i/K × alpha`), not a flat Bonferroni-style `alpha/K` division.
- `search_candidates_tested` means N candidates evaluated during in-sample discovery. It is provenance, not BH denominator. Using N with only K observed holdout p-values would not be a valid BH batch and would conflict with holdout-only final evaluation.
- BH correction is a batch operation: all K finalist holdout analytic p-values are collected, corrected together, then attached to each result as separate `raw_p`, `corrected_p`, and `bh_significant` fields. It does not feed back into `compute_grade` in this phase. Full `run_backtest` still supplies existing permutation p-value and letter grade as descriptive secondary statistics only.

**Story 4 — UI disclosure** *(P1)*
- Given a system was produced by search, when saved, then `SavedSystem.source = "search"` (vs `"manual"` default for existing flow) and `search_candidates_tested: int` are stored.
- Given a saved system with `source="search"`, when viewed in My Systems table or `/compare` picker, then it shows a small neutral-colored "Search" badge inline with the name (not red/green — those colors are reserved for profit/loss elsewhere in the UI) and a "N candidates tested" line in the same slot the existing `theory_line` subtext uses.
- The `/compare` picker (currently checkbox + name only, no metadata slot) gets the same badge treatment as the main table — without it, a user could select a search-found system into a comparison without ever seeing the disclosure.
- "Candidates tested" is provenance metadata, not a graded stat — it renders near but visually separate from the `stat-chips` row, not as a chip itself.

**Story 5 — Save/load/compare parity** *(P1)*
- Given an auto-found system, when saved, then it round-trips through existing `save_system`/`load_system` with the same backward-compatible default handling used for `theory`/`fade` (missing `source` on old saves defaults to `"manual"`).
- Given an auto-found system, when added to `/compare`, then it runs through the same `run_backtest` column as any saved system.

**Story 6 — Search scope config**
- Given search parameters (max active filters, season range, bet type spread/total), when I start a search, then results respect those bounds.
- Default max active filters = **4**, hard cap = **6**, tied to `_overfit_score`'s existing bands (`≤3 → 1.0`, `≤7 → 0.75`, `≤14 → 0.5`) so default search output stays in the 0.75+ overfit-score band rather than self-penalizing on grade.
- This cap governs filter **dimensions** (e.g. "spread threshold" counts as 1), not filter **values** (`count_overfit_filters` counts values — an `in` filter with 5 values counts as 5 there). Search-scope config and grade-time overfit penalty are two different counters measuring different things; both apply independently.
- Numeric feature filters (Elo, spreads, win probabilities, etc.) require a binning/quantile strategy to generate candidate threshold values before they can enter greedy/beam search — this is real design work, not assumed solved by "search the registry." MVP ships with a fixed quantile scheme (e.g. quartiles) for numeric features; smarter binning is a future improvement, not blocking MVP.
- Candidate enumeration order must be deterministic: `SystemFilter`'s `set`-typed fields are sorted explicitly before iteration (not relying on Python's randomized set-iteration order) — required for the reproducibility NFR below, independent of RNG seeding.
- Candidate grammar is explicit: search adds one compatible predicate per dimension; it never combines mutually exclusive choices (`favorite` + `underdog`, `home` + `away`, incompatible spread/total predicates), duplicates a dimension, or emits an unchanged/default-only candidate. Candidate identity uses canonical sorted serialization of all `SystemFilter` and `FeatureFilter` fields for deduplication and tie-breaking.

**Story 7 (P2) — Narrative summary**
- Given top-K search results, when I explicitly trigger "Narrate results" (opt-in action, not automatic on page load), then one LLM call summarizes them in plain English using only already-computed stats — no LLM in the scoring path, and cost stays visible/bounded to one call per explicit request.
- Rendered as a `theory-panel`-style collapsible text block appended to the existing results display — no new screen.

## Release Phases

**MVP**
- Story 1 (search CLI command, two-tier `run_backtest_summary`-then-`run_backtest` evaluation)
- Story 2 (mandatory holdout routing, no leakage during selection)
- Story 3 (BH correction, reported as separate field)
- Story 6 (scope config: default 4 / cap 6 filter dimensions, fixed quantile binning for numeric features, deterministic enumeration)

**P1**
- Story 4 (UI disclosure/badge in web — My Systems table + compare picker)
- Story 5 (save/load parity, `source` field + backward-compat default)

**P2**
- Story 7 (LLM narration layer, opt-in)

*Rationale: MVP is CLI-first and stats-safety-first per discovery brief's build order — a search that isn't holdout/FDR-gated and leakage-free is worse than no feature. Web UI polish and save/compare integration follow once the underlying numbers can be trusted. LLM narration is explicitly last and separable, consistent with "AI agent" being the wrong frame for the search itself.*

**CEO confirmed phasing as drafted** (see resolved open questions below — CLI-only MVP with no save/compare is acceptable; save/compare parity stays P1).

## Search Protocol (MVP contract)

1. CLI requires one or more `--holdout-season` values. It applies optional `--season` scope first, then calls `split_holdout`; all candidate generation, quantiles, matching, pruning, and ranking use only in-sample games and their feature rows.
2. Search uses deterministic beam search with explicit defaults: `--beam-width 100`, `--top-k 20`, `--min-decided-bets 100`, `--alpha 0.05`. CLI reports these effective values. Search rank is in-sample lower Wilson bound, then ROI, then decided-bet count, then canonical candidate identity. Candidates below minimum decided bets or with non-positive in-sample ROI do not advance.
3. Numeric thresholds are fixed in-sample quartiles. Boolean values and categorical levels are derived from in-sample feature rows only, sorted, and capped per dimension at documented deterministic limits. Missing feature values never become a candidate value.
4. After search completes, only final top-K systems touch holdout. Each receives one full holdout `run_backtest`; zero-holdout-bet finalists are omitted. BH operates over remaining finalist holdout analytic `stats.p_value` values. Output reports both `candidates_tested=N` and `finalists_graded=K`.
5. `result_lookahead` features are excluded before candidate generation. Search requires `processed/features.json` for registry-feature search; if absent, it returns a clear non-zero `missing_features` error naming `enrich` command. Core-filter-only mode is not implicit.

## Technical Requirements

- **New module**: `search.py` — canonical candidate generation and identity, compatibility rules, in-sample greedy/beam evaluation, in-sample-only value/quantile derivation, final holdout grading, and deterministic output ordering.
- **New CLI command**: `python -m cfb_system_maker search --data-dir data --holdout-season 2025 [--season 2019 ...] [--max-filters N] [--bet-type spread|total] [--beam-width 100] [--top-k 20] [--min-decided-bets 100] [--alpha 0.05]`.
- **Reuses as-is**: `SystemFilter`, `run_backtest`, `run_backtest_summary`, `compute_grade`, `split_holdout`, `_permutation_p_value`, `_overfit_score`/`count_overfit_filters`, `FEATURE_REGISTRY`.
- **New stats functions**: an exported analytic one-sided p-value helper usable from summary counts, plus BH correction `(p_values: list[float]) -> list[float]`, added to `backtest.py` beside existing statistics. BH operates over final holdout finalist analytic p-values only. `corrected_p` is reported separately and never merged into `compute_grade`.
- **Schema change**: `SavedSystem` gains `source: str = "manual"` and `search_candidates_tested: int | None = None`, following the `theory`/`fade` default-graceful precedent (`payload.get("field", default)` in `storage.py`) — no migration script needed.
- **Persistence API change (P1)**: extend `save_system` with keyword-only provenance arguments, serialize them in `_system_to_dict`, and read defaults in both `load_saved_system` and `load_example_system`. Existing callers and JSON files remain manual systems with no candidate count.
- **No new data pipeline** — operates entirely on already-built `games.csv` + `features.json` sidecar.
- **Web integration (P1)**: badge + metadata line added to `dashboard.html`'s existing `system-cell` pattern and `compare.html`'s picker list; one new `.badge-search` CSS rule. No new templates or screens.

## Verification Plan

- `tests/test_search.py`: deterministic enumeration/ordering; incompatible and lookahead predicates excluded; in-sample-only feature values and quantiles; canonical deduplication; minimum sample gate; required/valid holdout scope; holdout data cannot alter finalist identities; zero-holdout finalists omitted; full backtest call count is at most finalist count.
- `tests/test_backtest.py`: BH known-value and tie cases; adjusted p-values are monotonic after rank restoration; analytic raw p agrees with existing `SystemStats.p_value` for same decided bets.
- `tests/test_cli.py`: missing `games.csv` exits non-zero with `error=missing_data`; missing `features.json` exits non-zero with `missing_features`; output includes `candidates_tested`, `finalists_graded`, raw/adjusted p-values, and effective scope; same fixture produces byte-identical ranked output twice.
- P1 storage/web tests: old JSON defaults to manual provenance; search provenance round-trips; dashboard and compare picker expose neutral Search badge and candidate-count disclosure; manual systems show neither.
- Final gate: `.venv\\Scripts\\python.exe -m pytest -q`; representative-data benchmark records target-minute runtime and proves no full backtest occurs in beam expansion.

## Non-Functional Requirements

- **Performance**: search must complete in reasonable CLI wall-time (target: minutes, not hours) on ~13k games. Greedy/beam uses `run_backtest_summary`; only final survivors run full `run_backtest`. Using full `run_backtest` during expansion is disallowed. Initial benchmark test records candidate count, finalist count, elapsed time, and peak beam size against representative data.
- **Reproducibility**: search is deterministic given the same data + scope config — required for trust (a "profitable system" that can't be reproduced is worse than useless). This means: sorted/deterministic candidate enumeration (not relying on Python set-iteration order) AND seeded RNG for any randomized component (e.g. future genetic search, permutation tests) — both are independent requirements, not substitutes for each other.
- **No lookahead**: search must only use pre-game features already tagged as such in the registry (existing `running_stats.py` convention) — must not surface `result_lookahead`-tagged features as valid filters.
- **No selection leakage**: holdout games or feature rows must never influence candidate values, quantiles, expansion, pruning, ranking, or tie-breaks. They are accessed only once after finalist identities are fixed.
- **CSV/schema stability**: `SavedSystem` changes must default gracefully per project constraint; `GameRecord` CSV schema is untouched by this feature.

## Out of Scope

- LLM-driven candidate proposal/scoring (the search engine itself stays deterministic — explicitly rejected per discovery brief's technical feasibility findings).
- New data sources or pipeline stages — search operates only on already-built data.
- Real-time/continuous search (e.g. auto-re-running search as new season data arrives) — on-demand, user-triggered only.
- Genetic-algorithm search — greedy/beam is the MVP approach; genetic search is a possible future upgrade if beam search proves insufficient, not part of this spec.
- Portfolio-level optimization (combining multiple found systems into a meta-strategy) — single-system search only.
- Reconciling BH-corrected p-values into `compute_grade`'s existing composite score — corrected p ships as a separate displayed field in MVP/P1; folding it into the single letter-grade is a future design question.
- Smarter numeric-feature binning (beyond fixed quantiles) — future improvement, not MVP-blocking.

## Resolved Decisions

1. ~~Should Story 5 move into MVP?~~ **No — CLI-only ranked-list output is acceptable for MVP; save/compare parity stays P1.**
2. ~~Default/max search scope cap?~~ **Default 4 filter dimensions, hard cap 6** — tied to `_overfit_score`'s existing grading bands (see Story 6).
3. ~~FDR method — BH vs Bonferroni vs PBO/Deflated Sharpe?~~ **Benjamini-Hochberg over final holdout finalists**, implemented correctly as rank-based correction. N discovery candidates remain disclosed provenance; K independently graded holdout finalists form complete BH batch. PBO/Deflated Sharpe remains future work.
4. ~~Where does "candidates tested" surface for CLI-only MVP?~~ **Stdout summary line**, using the exact same field name (`search_candidates_tested`) that P1's UI will later read — avoids a silent rename/parsing mismatch between phases.

## Open Questions

None blocking — all four original open questions resolved above. Remaining refinements (BH-vs-`compute_grade` reconciliation, smarter numeric binning) are explicitly deferred to Out of Scope, not open blockers.

---
*Validated by @engineer (technical feasibility — flagged and resolved: permutation-test performance risk, holdout-selection leakage risk, BH-vs-Bonferroni wording error, filter-dimension-vs-filter-value cap ambiguity) and @designer (UX flow — badge/copy treatment for My Systems + compare picker, CLI-first MVP sequencing confirmed reasonable, narration placement as `theory-panel`-style opt-in block).*
