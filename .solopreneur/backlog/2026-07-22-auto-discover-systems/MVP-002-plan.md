# Plan: Candidate generation — canonical identity, compatibility grammar, deterministic enumeration

## Context
MVP-002 builds the pure candidate-generation layer for auto-discovering profitable
betting systems. It defines: (1) a canonical identity for `SystemFilter`/`FeatureFilter`
so candidates dedup deterministically, (2) a one-dimension-at-a-time expansion grammar
that rejects incompatible/duplicate/no-op combinations, and (3) in-sample-only value
derivation (quantiles for numeric features, capped sorted levels for bool/categorical).
No evaluation or beam search here — that's MVP-003, which depends on this ticket's
`expand_candidates`-style function and `candidate_identity` function as its building
blocks.

**Branch**: `ticket/MVP-002`

## Key design decisions (from source review + advisor)
- **Dimension taxonomy** (`dimension_of`): `favorite_underdog` (favorite/underdog booleans,
  mutually exclusive), `home_away` (home/away booleans + matching `side`, mutually
  exclusive), `spread_range` (min_spread/max_spread together = one dimension),
  `total_range` (min_total/max_total together = one dimension), and one dimension per
  non-lookahead registry feature key (`feature:<key>`). `total_side` (over/under) is
  treated like `side` for spread bets: a required scope field fixed by the seed
  candidate, not an independently expandable dimension — this keeps it symmetric with
  `side`, which is likewise only ever changed as part of the `home_away` dimension.
  This is deliberately a different, dimension-counting scheme from
  `backtest.count_overfit_filters` (which counts values) — not reused, not touched.
- **Scope-only fields excluded from generation**: `seasons`, `weeks`, `teams`,
  `conferences`, `providers` are high-cardinality search *scope*, not candidate
  dimensions (MVP-003 treats season range as external scope config). They pass through
  from the seed `SystemFilter` untouched by `expand_candidates`, but are still sorted
  explicitly in `candidate_identity` per the ticket's explicit requirement.
- **home/away coupling**: verified empirically that `matches_system` only honors
  `home=True`/`away=True` when `side` matches (`side="away", home=True` → 0 matches).
  So expanding the `home_away` dimension sets both the bool flag and `side` together as
  one candidate, never the bool alone.
- **Team-scoped features**: candidate generation defaults to `perspective="bet_side"`
  only (documented scope cut, matches backlog.md cross-cutting risk #5). Values are
  derived by reading through `features.resolve_feature_value` (same resolver
  `matches_system`/`feature_ok` uses) so derived thresholds are guaranteed to match what
  the matcher actually reads — never read `feature_map[gid][key]` directly for
  team-scoped features.
- **Canonical identity**: a tuple-of-sorted-tuples key over every `SystemFilter` field
  (sets sorted, `feature_filters` sorted by their own canonical key, `FeatureFilter.value`
  sorted if it's a container). Used for dedup (a `set`/`dict` of seen identities during
  expansion) and as the final deterministic tie-break sort key.

## Step 1: Write `cfb_system_maker/search.py` — identity + dimension taxonomy
**Files**: `cfb_system_maker/search.py` (create)
**Do**:
- `candidate_identity(system: SystemFilter) -> tuple`: canonical, fully sorted
  representation of every field (explicit sort on all set-typed fields; sort
  `feature_filters` by their own canonical tuple; normalize `FeatureFilter.value`
  containers via `sorted()` when it's a list/tuple/set, else leave scalar as-is).
- `Dimension` enum/Literal + `dimension_of(...)` style helpers used internally by
  expansion (favorite_underdog, home_away, spread_range, total_range, total_side,
  `feature:<key>`).
- `active_dimensions(system: SystemFilter) -> set[str]`: which dimensions are already
  set on a candidate (used to block duplicates and count toward the cap).
- `count_dimensions(system: SystemFilter) -> int`: len(active_dimensions(system)) —
  explicitly separate from and does not call `backtest.count_overfit_filters`.
**Acceptance**: importable module; `candidate_identity` on two `SystemFilter`s built
with differently-ordered set literals / feature_filter tuples returns identical tuples.

## Step 2: In-sample value derivation (quantiles + categorical/bool levels)
**Files**: `cfb_system_maker/search.py` (same file, continue)
**Do**:
- `numeric_quantile_values(games, feature_map, feature_key, perspective, side, *, quantiles=(0.25, 0.5, 0.75)) -> list[float]`
  — pulls one value per game via `resolve_feature_value`/`resolve_storage_key`,
  drops `None`, sorts, computes fixed quartile cut points, dedups. Signature takes
  `games`/`feature_map` as explicit plain arguments (mirrors `backtest.run_backtest`),
  making it structurally impossible to smuggle in holdout rows — caller must pass an
  explicit in-sample list.
- `categorical_or_bool_values(games, feature_map, feature_key, perspective, side, *, limit=8) -> list`
  — same value extraction, `None` dropped, then sorted by `(-count, value)` and capped
  at `limit` (default 8, documented in docstring as the deterministic top-N cap).
- Both functions only ever read `feature_map`/`games` passed as parameters — no import
  of `storage`/`enrich` in `search.py`.
**Acceptance**: unit-testable in isolation; a holdout-only game passed as a *separate*
list never influences output (tested by never passing it in).

## Step 3: Candidate grammar — `expand_candidates`
**Files**: `cfb_system_maker/search.py` (same file, continue)
**Do**:
- `expand_candidates(parent: SystemFilter, games, feature_map, *, max_dimensions=4, hard_cap=6) -> list[SystemFilter]`:
  - Clamp/validate `max_dimensions <= hard_cap` (raise if caller passes over hard cap).
  - If `count_dimensions(parent) >= max_dimensions`, return `[]`.
  - For each candidate dimension not already active on `parent`, generate every legal
    one-step child (favorite=True / underdog=True as two children of
    `favorite_underdog`; home+side="home" / away+side="away" as two children of
    `home_away`; spread_range children from a small fixed threshold set derived the
    same quantile way from in-sample spreads, spread-bet candidates only; total_range
    similarly; one child per derived numeric quantile cut / categorical level per
    non-lookahead registry feature, `bet_side` perspective only).
  - Never emit a child identical to `parent` (no-op guard) and never emit the
    empty/default `SystemFilter` (only relevant for the root/seed call).
  - Dedup children by `candidate_identity` within one expansion call.
  - Sort final children by `candidate_identity` for deterministic order.
- Registry iteration uses `FEATURE_REGISTRY` tuple order (not dict/set order) and
  filters `feature.group != "result_lookahead"` at generation time.
**Acceptance**: same parent + same games/feature_map → identical output list/order
across repeated calls; a `home=True` child always carries `side="home"`; no
`result_lookahead` feature key ever appears; incompatible pairs never appear in a
single child.

## Step 4: Tests
**Files**: `tests/test_search.py` (create)
**Do**: cover, using small hand-built `GameRecord`/feature_map fixtures (no data-dir
access, matches `test_backtest.py` style):
- Deterministic enumeration: call `expand_candidates` twice with identical inputs,
  assert identical list (values and order).
- Incompatible-predicate exclusion: no child has both `favorite`/`underdog` True, both
  `home`/`away` True, or contradictory total/spread bounds.
- Duplicate-dimension exclusion: expanding a parent that already has `favorite=True`
  set never produces another `favorite_underdog` child.
- Lookahead exclusion: assert `havoc_offense_rate`, `havoc_defense_rate`, `attendance`
  never appear as a `FeatureFilter.key` in any generated candidate.
- In-sample-only derivation: build an in-sample list and a separate "holdout" list
  with an extreme/distinct value; call the value-derivation function with only the
  in-sample list; assert output is identical whether or not the holdout list variable
  even exists in scope (i.e., never pass it) — proves the signature can't leak it.
- Canonical dedup: build two `SystemFilter`s with same semantic content but sets/tuple
  built in different literal order (e.g. `{2023, 2024}` vs `{2024, 2023}`,
  `feature_filters=(a, b)` vs `(b, a)`); assert `candidate_identity` equal.
- Dimension cap: parent at `max_dimensions` returns `[]`; hard cap validation raises
  for `max_dimensions > 6`.
**Acceptance**: `python -m pytest tests/test_search.py -v` all green.

## Step 5: Full suite regression check
**Files**: none (verification only)
**Do**: run `python -m pytest` from repo root.
**Acceptance**: no failures/regressions in existing modules (search.py is new/additive,
should not touch any existing file).
